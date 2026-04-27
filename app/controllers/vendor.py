from tortoise.expressions import Q

from app.core.crud import CRUDBase
from app.models.company import Company
from app.schemas.vendors import VendorCreate, VendorUpdate


class VendorController(CRUDBase[Company, VendorCreate, VendorUpdate]):
    def __init__(self):
        super().__init__(model=Company)

    async def list_vendors(self, page: int, page_size: int, search: Q = Q(), order: list = []):
        # 供应商角色固定为2
        search &= Q(role=2)
        return await self.list(page=page, page_size=page_size, search=search, order=order)

    async def create_vendor(self, obj_in: VendorCreate) -> Company:
        data = obj_in.model_dump()
        data["role"] = 2
        return await self.create(data)

    async def update_vendor(self, id: int, obj_in: VendorUpdate) -> Company:
        data = obj_in.model_dump(exclude_unset=True, exclude={"id"})
        data["role"] = 2
        return await self.update(id=id, obj_in=data)


vendor_controller = VendorController()
