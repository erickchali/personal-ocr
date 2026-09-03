import logging

from langsmith import traceable

from agents.llm import get_llm
from domain.models import CreditCardStatement

logger = logging.getLogger(__name__)

llm = get_llm("extraction")

MAX_ATTEMPTS = 2


class ExtractionError(RuntimeError):
    """The model never returned a statement we could parse."""


@traceable
def extract_structured_data(pdf_content: str) -> CreditCardStatement:
    """
    Extract structured data from PDF content using the LLM.

    Args:
        pdf_content: Raw text content from the PDF

    Returns:
        CreditCardStatement: Validated Pydantic model with all extracted data
    """
    # include_raw returns {"raw", "parsed", "parsing_error"} instead of raising, which is
    # what makes the retry below possible: a provider that ignores response_format returns
    # empty content on a *successful* call, so there is no exception to retry on.
    # json_schema support varies by model; drop the kwarg to fall back to function_calling.
    extraction_model = llm.with_structured_output(CreditCardStatement, method="json_schema", include_raw=True)

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

    prompt = extraction_prompt.format(content=pdf_content)

    for attempt in range(1, MAX_ATTEMPTS + 1):
        result = extraction_model.invoke(prompt)
        if result["parsed"] is not None:
            return result["parsed"]

        content = getattr(result["raw"], "content", "") or ""
        logger.warning(
            "Extraction attempt %s/%s produced no statement (%s chars returned, error: %s)",
            attempt,
            MAX_ATTEMPTS,
            len(content),
            result["parsing_error"],
        )

    raise ExtractionError(f"Model returned no parseable statement after {MAX_ATTEMPTS} attempts")
