from tortoise.expressions import Q

from app.core.crud import CRUDBase
from app.models.company import Company
from app.schemas.companies import CompanyCreate, CompanyUpdate


class CompanyController(CRUDBase[Company, CompanyCreate, CompanyUpdate]):
    def __init__(self):
        super().__init__(model=Company)

    async def list_companies(self, page: int, page_size: int, search: Q = Q(), order: list = []):
        return await self.list(page=page, page_size=page_size, search=search, order=order)


company_controller = CompanyController()