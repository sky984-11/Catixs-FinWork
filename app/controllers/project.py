from tortoise.expressions import Q

from app.core.crud import CRUDBase
from app.models.project import CustomerProject
from app.schemas.projects import CustomerProjectCreate, CustomerProjectUpdate


class CustomerProjectController(
    CRUDBase[CustomerProject, CustomerProjectCreate, CustomerProjectUpdate]
):
    def __init__(self):
        super().__init__(model=CustomerProject)

    async def list_projects(self, page: int, page_size: int, search: Q = Q(), order: list = []):
        return await self.list(page=page, page_size=page_size, search=search, order=order)


customer_project_controller = CustomerProjectController()
