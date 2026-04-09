import logging
from pathlib import Path
from typing import Literal

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.messages import AIMessage
from langgraph.types import Command, interrupt
from pydantic import BaseModel, Field

from agents.extraction import extract_structured_data
from agents.graph_state import FinancialAssistantState
from agents.llm import get_llm
from agents.tools import fetch_all_statements, fetch_statement_transactions
from db.cruds import save_statement, statement_exists

llm = get_llm()

FILES_DIRECTORY = Path(__file__).parent.parent / "pdf-to-process"


class IntentClassification(BaseModel):
    """Classify user intent into one of three categories."""

    intent: str = Field(
        description=(
            'The user intent. Must be one of: "upload" (user wants to process/upload '
            'PDF bank statements), "query" (user wants to ask questions about their '
            'financial data), or "chat" (general conversation, greetings, help).'
        )
    )


def router_node(state: FinancialAssistantState) -> dict:
    """Classify the user's intent from their last message."""
    last_message = state["messages"][-1]
    classifier = llm.with_structured_output(IntentClassification)
    result = classifier.invoke(
        f"Classify this user message into one of: upload, query, chat.\n\n"
        f"Message: {last_message.content}"
    )
    return {"intent": result.intent}


def list_files_node(state: FinancialAssistantState) -> dict:

    pdf_files = list(FILES_DIRECTORY.glob("*.pdf"))

    if not pdf_files:
        return {"messages": [AIMessage(content="No files to process")]}

    file_names = [_.name for _ in pdf_files]
    success_message = AIMessage(content=f"Found {len(pdf_files)} files.")
    return {"messages": [success_message], "pending_files": file_names}


def extract_files_node(state: FinancialAssistantState) -> dict:
    pending_file_names = state["pending_files"]
    messages = []

    statements = []
    for filename in pending_file_names:
        file_path = FILES_DIRECTORY / filename
        logging.info(f"Processing {filename.upper()}.pdf")
        if not filename.lower().endswith(".pdf"):
            messages.append(f"{file_path} Not a PDF.")
            continue
        try:
            loader = PyPDFLoader(str(file_path))
            documents = loader.load()

            content_parts = []
            for i, doc in enumerate(documents, 1):
                content_parts.append(f"--- Page {i} ---\n{doc.page_content}")
            pdf_content = "\n\n".join(content_parts)

            structured_data = extract_structured_data(pdf_content)
            statements.append(structured_data)

        except Exception:
            logging.exception(f"Error processing {filename.upper()}.")

    return {
        "pending_statements": statements,
        "messages": [
            AIMessage(content=f"Extracted {len(statements)} statements, awaiting approval")
        ],
    }


def query_node(state: FinancialAssistantState) -> dict:
    llm_with_tools = llm.bind_tools([fetch_statement_transactions, fetch_all_statements])
    response = llm_with_tools.invoke(state["messages"])
    return {"messages": [response]}


def respond_node(state: FinancialAssistantState) -> dict:
    """Generate a conversational response using the full message history."""
    response = llm.invoke(state["messages"])
    return {"messages": [response]}


def approval_node(state: FinancialAssistantState) -> Command[Literal["save_files", "cancel"]]:
    pending_statements = state["pending_statements"]
    summary_messages = ["Statements pending to be processed"]
    for statement in pending_statements:
        summary_messages.append(
            f"{statement.summary.card_number_masked} - {statement.summary.card_type}"
        )
    final_message = "\n".join(summary_messages)
    approve = interrupt({"question": "Insert in DB?", "details": final_message})

    if approve:
        return Command(goto="save_files")
    return Command(goto="cancel")


def cancel_node(state: FinancialAssistantState) -> dict:
    return {"messages": [AIMessage(content="Statements not saved to db.")]}


def save_files_node(state: FinancialAssistantState) -> dict:
    pending_statements = state["pending_statements"]
    messages = []
    processed = 0
    for statement in pending_statements:
        if not statement_exists(
            statement.summary.card_number_masked, statement.summary.cut_off_date
        ):
            statement_id = save_statement(statement)
            logging.info("saving statement to Database")
            messages.append(f"Statement {statement_id} saved.")
            processed += 1
        else:
            messages.append("Statement already exists.")
    return {"messages": [AIMessage(content="\n".join(messages))], "processed_count": processed}
