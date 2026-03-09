import logging
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field

from agents.extraction import extract_structured_data
from agents.graph_state import FinancialAssistantState
from agents.llm import get_llm
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


def process_files_node(state: FinancialAssistantState) -> dict:
    pending_file_names = state["pending_files"]
    processed = 0
    messages = []

    for filename in pending_file_names:
        file_path = FILES_DIRECTORY / filename
        logging.info(f"Processing {filename.upper()}.txt")
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
            if not statement_exists(
                structured_data.summary.card_number_masked, structured_data.summary.cut_off_date
            ):
                statement_id = save_statement(structured_data)
                logging.info(f"saving statement  {filename.upper()} to Database")
                messages.append(f"Statement {statement_id} saved.")
            else:
                messages.append(f"Statement {filename.upper()} already exists.")
            processed += 1
        except Exception:
            logging.exception(f"Error processing {filename.upper()}.")

    return {"messages": [AIMessage(content="\n".join(messages))], "processed_count": processed}


def query_stub_node(state: FinancialAssistantState) -> dict:
    """Stub node for query processing (coming in Phase 3)."""
    return {"messages": [AIMessage(content="Query feature coming soon.")]}


def respond_node(state: FinancialAssistantState) -> dict:
    """Generate a conversational response using the full message history."""
    response = llm.invoke(state["messages"])
    return {"messages": [response]}
