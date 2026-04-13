import logging

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.messages import AIMessage

from agents.extraction import extract_structured_data
from agents.graph_state import FinancialAssistantState
from agents.nodes import FILES_DIRECTORY
from db.cruds import save_statement, statement_exists


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
            if not statement_exists(structured_data.summary.card_number_masked, structured_data.summary.cut_off_date):
                statement_id = save_statement(structured_data)
                logging.info(f"saving statement  {filename.upper()} to Database")
                messages.append(f"Statement {statement_id} saved.")
            else:
                messages.append(f"Statement {filename.upper()} already exists.")
            processed += 1
        except Exception:
            logging.exception(f"Error processing {filename.upper()}.")

    return {"messages": [AIMessage(content="\n".join(messages))], "processed_count": processed}
