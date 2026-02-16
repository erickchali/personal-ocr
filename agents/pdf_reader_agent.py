import logging
import uuid
from pathlib import Path

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.tools import ToolRuntime
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.types import Command

# Import our Pydantic models
from agents.models import CreditCardStatement, OCRCustomState
from db.cruds import save_statement, statement_exists

load_dotenv()

PDF_DIRECTORY = Path(__file__).parent.parent / "pdf-to-process"

SYSTEM_PROMPT = """You are a financial document processing assistant. Your job is to:

1. List available PDF files when asked
2. Read and parse each credit card statements
3. Extract structured data from statements into a specific format

When extracting transaction data:
- "Débitos" are purchases/debits (money spent)
- "Créditos" are payments/credits (money received/paid)
- "Q" means Quetzales (GTQ), "$" means US Dollars (USD)
- "Fecha de operación" = operation date (when bank processed)
- "Fecha de consumo" = consumption date (when purchase was made)

Always be thorough and extract ALL transactions from the document.
"""


@tool
def list_pdf_files(
    runtime: ToolRuntime,
) -> Command:
    """
    List all PDF files available in the processing directory.

    Use this tool first to see what files are available before reading them.
    Returns a numbered list of PDF filenames.
    """
    writer = runtime.stream_writer
    writer(f"Checking if directory {PDF_DIRECTORY} exists...")
    if not PDF_DIRECTORY.exists():
        return f"Error: Directory {PDF_DIRECTORY} does not exist"

    writer(f"Directory {PDF_DIRECTORY} exists...")

    pdf_files = list(PDF_DIRECTORY.glob("*.pdf"))

    if not pdf_files:
        return "No PDF files found in the processing directory."

    file_names = [f.name for f in pdf_files]
    # Format as numbered list for easy reference

    writer(f"Found {len(pdf_files)} PDF files in {PDF_DIRECTORY}...")
    return Command(
        update={
            "messages": [
                ToolMessage(
                    content=(
                        f"{len(file_names)} Files Found, "
                        "please proceed to read and process all files"
                    ),
                    tool_call_id=runtime.tool_call_id,
                )
            ],
            "files_to_process": file_names,
        }
    )


@tool
def read_pdf_content(
    runtime: ToolRuntime,
) -> Command:
    """
    Read and extract text content from all pdf files in the pre-defined directory.

    Returns:
        The extracted text content from all pages of the PDF.

    Use this after list_pdf_files() to read a specific document.
    """
    writer = runtime.stream_writer
    state = runtime.state
    files_to_process = state.get("files_to_process", [])
    message = ToolMessage(content="All files processed.", tool_call_id=runtime.tool_call_id)
    for filename in files_to_process:
        file_path = PDF_DIRECTORY / filename
        logging.info(f"Processing {filename.upper()}.txt")
        if not file_path.exists():
            return f"Error: File '{filename}' not found in {PDF_DIRECTORY}"

        if not filename.lower().endswith(".pdf"):
            return "Error: File must be a PDF"
        try:
            loader = PyPDFLoader(str(file_path))
            documents = loader.load()

            # Combine all pages with page markers
            content_parts = []
            for i, doc in enumerate(documents, 1):
                content_parts.append(f"--- Page {i} ---\n{doc.page_content}")

            pdf_content = "\n\n".join(content_parts)
            # with open(PDF_DIRECTORY / filename.lower().replace(".pdf", ".txt"), "w") as text_file:
            #     logging.info(f"Writing extracted text content to {filename.upper()}.txt")
            #     text_file.write(pdf_content)
            try:
                structured_data = extract_structured_data(pdf_content)
                # with open(
                #     PDF_DIRECTORY / filename.lower().replace(".pdf", ".json"), "w"
                # ) as json_file:
                #     json_file.write(structured_data.model_dump_json(indent=4))

                # Save to database (skip if already exists)
                if not statement_exists(
                    structured_data.summary.card_number_masked, structured_data.summary.cut_off_date
                ):
                    statement_id = save_statement(structured_data)
                    logging.info(f"saving statement  {filename.upper()} to Database")
                    writer(f"Saved statement {statement_id} to database")
                else:
                    writer("Statement already exists in database, skipping")

                writer(f"Successfully extracted structured data from {file_path}")
            except Exception:
                logging.exception("Extraction error:")
                message = ToolMessage(
                    content=f"Unable to get extructured data from file {filename}",
                    tool_call_id=runtime.tool_call_id,
                )
        except Exception as e:
            logging.exception(f"Error reading PDF: {str(e)}")
            message = ToolMessage(
                content=f"Unable to get extructured data from file {filename}",
                tool_call_id=runtime.tool_call_id,
            )

    return Command(update={"messages": [message]})


# model = ChatOpenAI(
#     model="gpt-5-mini",
#     temperature=0,
# )
model = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    max_retries=2,
)

agent = create_agent(
    model=model,
    tools=[list_pdf_files, read_pdf_content],
    system_prompt=SYSTEM_PROMPT,
    state_schema=OCRCustomState,
)


def extract_structured_data(pdf_content: str) -> CreditCardStatement:
    """
    Extract structured data from PDF content using the LLM.

    This uses .with_structured_output() which:
    - Tells the LLM exactly what format to return
    - Validates the output against the Pydantic model
    - Raises an error if the format is wrong

    Args:
        pdf_content: Raw text content from the PDF

    Returns:
        CreditCardStatement: Validated Pydantic model with all extracted data
    """
    # Create a model specifically for structured extraction
    # with_structured_output() constrains the LLM to return our exact schema
    extraction_model = model.with_structured_output(CreditCardStatement)

    extraction_prompt = """Extract all information from this credit card statement.

Be thorough and extract:
1. All summary/header information (account holder, balances, dates, etc.)
2. ALL transactions - both debits and credits, in both currencies
3. Installment payments (Cuotas)
4. Any credits or cashback

For transaction_type, use:
- "purchase" for regular purchases/debits
- "payment" for payments made (GRACIAS POR SU PAGO)
- "installment" for Cuotas
- "credit" for cashback/rewards (ByMastercard PedidosY)

IMPORTANT - For credit_card_reference field:
Transactions are grouped by card, and each group ends with a "SUB TOTAL XXXXXX XXXX" row.
- Look for "SUB TOTAL XXXXXX XXXX" rows (e.g., "SUB TOTAL XXXXXX 3251", "SUB TOTAL XXXXXX 3269")
- ALL transactions BEFORE a subtotal row should have that card reference (e.g., "XXXXXX 3251")
- This pattern repeats for each section: GTQ transactions, USD transactions, installments (Cuotas)
- For "OTROS CARGOS" (other charges), credit_card_reference can be null

Example: If you see transactions followed by "SUB TOTAL XXXXXX 3251", then another set
of transactions followed by "SUB TOTAL XXXXXX 3269", the first group gets "XXXXXX 3251"
and the second group gets "XXXXXX 3269".

Statement content:
{content}
"""

    # The LLM will return a CreditCardStatement object directly
    result = extraction_model.invoke(extraction_prompt.format(content=pdf_content))

    return result


# ============================================================================
# MAIN EXECUTION
# ============================================================================


def process_statement(user_request: str) -> dict:
    """
    Main function to process a user request about PDF statements.

    This orchestrates the full flow:
    1. Agent reads the PDF based on user request
    2. Extract structured data from the content
    3. Return both the agent's response and structured data

    Args:
        user_request: Natural language request from the user

    Returns:
        Dict with 'agent_response', 'structured_data', and 'raw_content'
    """
    # Step 1: Run the agent to get the PDF content
    result = agent.invoke(
        {"messages": [HumanMessage(content=user_request)]},
        {"configurable": {"thread_id": str(uuid.uuid4())}},
    )

    # Get the last message (agent's final response)
    agent_response = result["messages"][-1].content

    # Step 2: Find the PDF content from tool calls
    # Look through messages for the read_pdf_content tool result
    pdf_content = None
    for msg in result["messages"]:
        if hasattr(msg, "content") and "--- Page" in str(msg.content):
            pdf_content = msg.content
            break

    # Step 3: If we found PDF content, extract structured data
    structured_data = None
    if pdf_content:
        print("\n--- PDF Content ---")
        print(pdf_content)
        try:
            structured_data = extract_structured_data(pdf_content)
        except Exception as e:
            print(f"Extraction error: {e}")

    return {
        "agent_response": agent_response,
        "structured_data": structured_data,
        "raw_content": pdf_content,
    }


if __name__ == "__main__":
    # Example usage
    print("=" * 60)
    print("PDF Reader Agent - Credit Card Statement Parser")
    print("=" * 60)

    # Process a request
    # result = process_statement(
    #     "Please list the available PDFs and then read the credit card statement"
    # )
    user_request = "Please list the available PDFs and then read all credit card statements"
    result = agent.invoke(
        {"messages": [HumanMessage(content=user_request)]},
        {"configurable": {"thread_id": str(uuid.uuid4())}},
    )
    logging.warning(result["messages"][-1].content)

    # if result["structured_data"]:
    #     print("\n--- Extracted Structured Data (JSON) ---")
    #     statement = result["structured_data"]
    #
    #     # Convert Pydantic model to JSON string
    #     json_output = statement.model_dump_json(indent=2)
    #     print(json_output)
