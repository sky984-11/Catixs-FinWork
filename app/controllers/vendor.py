from tortoise.expressions import Q

from app.core.crud import CRUDBase
from app.models.company import Company
from app.schemas.vendors import VendorCreate, VendorUpdate


async def generate_vendor_code(contract_company_id: int) -> str:
    """生成供应商编号，格式: 签约主体公司code + 0000(自增)"""
    prefix = "V"
    
    # 获取签约主体公司的code作为前缀
    if contract_company_id:
        contract_company = await Company.get_or_none(id=contract_company_id)
        if contract_company and contract_company.code:
            prefix = "V" + contract_company.code
    
    # 统计该前缀下的供应商数量，+1 作为新的编号
    count = await Company.filter(
        code__startswith=prefix,
        role=2
    ).count()
    
    # 新编号 = 当前数量 + 1
    new_num = count + 1
    
    return f"{prefix}{new_num:04d}"


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
        
        # 如果没有提供编号，自动生成
        if not data.get("code"):
            contract_company_id = data.get("contract_company_id")
            if contract_company_id:
                data["code"] = await generate_vendor_code(contract_company_id)
            else:
                # 没有签约主体时使用默认生成方式
                data["code"] = await generate_vendor_code(0)
        
        return await self.create(data)

    async def update_vendor(self, id: int, obj_in: VendorUpdate) -> Company:
        data = obj_in.model_dump(exclude_unset=True, exclude={"id"})
        data["role"] = 2
        return await self.update(id=id, obj_in=data)


vendor_controller = VendorController()
