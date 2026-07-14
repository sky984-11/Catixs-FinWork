from app.core.crud import CRUDBase
from app.models.finance import FinanceQuote
from app.schemas.finance_quotes import FinanceQuoteCreate, FinanceQuoteUpdate


class FinanceQuoteController(CRUDBase[FinanceQuote, FinanceQuoteCreate, FinanceQuoteUpdate]):
    def __init__(self):
        super().__init__(model=FinanceQuote)


finance_quote_controller = FinanceQuoteController()
