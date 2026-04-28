from tortoise.expressions import Q

from app.core.crud import CRUDBase
from app.models.company import Company
from app.schemas.vendors import VendorCreate, VendorUpdate


# 地区编码映射
REGION_CODE_MAP = {
    "UK": "U",  # 英国
    "GB": "U",  # 英国
    "United Kingdom": "U",
    "HK": "H",  # 香港
    "Hong Kong": "H",
    "CN": "C",  # 中国
    "China": "C",
    "中国": "C",
    "香港": "H",
    "英国": "U",
}


def get_region_code(country: str) -> str:
    """根据国家获取地区编码"""
    if not country:
        return "U"  # 默认英国
    country_normalized = country.strip().upper()
    # 直接匹配
    if country_normalized in REGION_CODE_MAP:
        return REGION_CODE_MAP[country_normalized]
    # 模糊匹配
    for key, value in REGION_CODE_MAP.items():
        if key.upper() in country_normalized or country_normalized in key.upper():
            return value
    return "U"  # 默认英国


async def generate_vendor_code(country: str) -> str:
    """生成供应商编号，格式: V + 地区码 + 0000(自增)"""
    region_code = get_region_code(country)
    prefix = f"V{region_code}"
    
    # 查找当前最大的编号
    max_code = await Company.filter(
        code__startswith=prefix
    ).order_by("-code").first()
    
    if max_code and max_code.code:
        try:
            # 提取数字部分并加1
            num = int(max_code.code[len(prefix):]) + 1
        except ValueError:
            num = 1
    else:
        num = 1
    
    # 生成新编号，保持5位数字部分（不够前面补0）
    return f"{prefix}{num:05d}"


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
            data["code"] = await generate_vendor_code(data.get("country", ""))
        
        return await self.create(data)

    async def update_vendor(self, id: int, obj_in: VendorUpdate) -> Company:
        data = obj_in.model_dump(exclude_unset=True, exclude={"id"})
        data["role"] = 2
        return await self.update(id=id, obj_in=data)


vendor_controller = VendorController()
