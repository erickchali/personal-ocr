from agents.llm import get_llm
from agents.models import CreditCardStatement

llm = get_llm("google")


def extract_structured_data(pdf_content: str) -> CreditCardStatement:
    """
    Extract structured data from PDF content using the LLM.

    Args:
        pdf_content: Raw text content from the PDF

    Returns:
        CreditCardStatement: Validated Pydantic model with all extracted data
    """
    extraction_model = llm.with_structured_output(CreditCardStatement)

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

    result = extraction_model.invoke(extraction_prompt.format(content=pdf_content))

    return result
