from app.core.crud import CRUDBase
from app.models.company import Bank
from app.schemas.banks import BankCreate, BankUpdate


class BankController(CRUDBase[Bank, BankCreate, BankUpdate]):
    def __init__(self):
        super().__init__(model=Bank)


bank_controller = BankController()

