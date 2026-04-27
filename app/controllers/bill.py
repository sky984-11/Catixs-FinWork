from app.core.crud import CRUDBase
from app.models.company import Bill, BillItem
from app.schemas.bills import BillCreate, BillUpdate


class BillController(CRUDBase[Bill, BillCreate, BillUpdate]):
    def __init__(self):
        super().__init__(model=Bill)


class BillItemController(CRUDBase[BillItem, dict, dict]):
    def __init__(self):
        super().__init__(model=BillItem)


bill_controller = BillController()
bill_item_controller = BillItemController()

