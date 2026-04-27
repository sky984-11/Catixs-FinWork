from app.core.crud import CRUDBase
from app.models.company import BankAccount
from app.schemas.bank_accounts import BankAccountCreate, BankAccountUpdate


class BankAccountController(CRUDBase[BankAccount, BankAccountCreate, BankAccountUpdate]):
    def __init__(self):
        super().__init__(model=BankAccount)


bank_account_controller = BankAccountController()

