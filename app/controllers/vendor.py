from fastapi import HTTPException
from tortoise.exceptions import IntegrityError
from tortoise.expressions import Q
from tortoise.transactions import in_transaction

from app.controllers.vendor_attachments import bind_attachments
from app.controllers.vendor_entities import resolve_entity
from app.core.crud import CRUDBase
from app.models.company import Company, VendorAttachment
from app.models.customer_center import CrmSigningEntity
from app.schemas.vendors import VendorCreate, VendorUpdate


async def generate_vendor_code(contract_company_id: int, signing_entity_id: int | None = None) -> str:
    """生成供应商编号，格式: 签约主体公司code + 0000(自增)"""
    prefix = "V"

    # 获取签约主体公司的code作为前缀
    if contract_company_id:
        contract_company = await Company.get_or_none(id=contract_company_id)
        if contract_company and contract_company.code:
            prefix = "V" + contract_company.code
    if signing_entity_id:
        entity = await CrmSigningEntity.get(id=signing_entity_id)
        identity = f"{entity.name} {entity.legal_name or ''} {entity.code or ''}".lower()
        if "77" in identity:
            prefix = "VH"
        elif "科特思" in identity or "catixs-cn" in identity:
            prefix = "VC"
        elif "catixs" in identity:
            prefix = "VU"
        else:
            prefix = "V" + next(
                (char.upper() for char in entity.code or entity.name if char.isascii() and char.isalpha()), "C"
            )

    codes = await Company.filter(code__startswith=prefix).values_list("code", flat=True)
    numbers = [int(code[len(prefix) :]) for code in codes if code[len(prefix) :].isdigit()]
    new_num = max(numbers, default=0) + 1

    return f"{prefix}{new_num:04d}"


class VendorController(CRUDBase[Company, VendorCreate, VendorUpdate]):
    def __init__(self):
        super().__init__(model=Company)

    async def get(self, id: int) -> Company:
        vendor = await Company.get_or_none(id=id, role=2)
        if vendor is None:
            raise HTTPException(status_code=404, detail="供应商不存在")
        return vendor

    async def validate_entity(self, data: dict) -> None:
        entity_id = data.get("contract_company_id")
        if entity_id is not None and not await Company.filter(id=entity_id, role=0).exists():
            raise HTTPException(status_code=400, detail="签约主体必须为内部公司")

    async def list_vendors(self, page: int, page_size: int, search: Q = Q(), order: list = []):
        # 供应商角色固定为2
        search &= Q(role=2)
        return await self.list(page=page, page_size=page_size, search=search, order=order)

    async def create_vendor(self, obj_in: VendorCreate) -> Company:
        data = obj_in.model_dump()
        if "signing_entity_id" not in obj_in.model_fields_set:
            data.pop("signing_entity_id", None)
        attachment_ids = data.pop("attachment_ids", [])
        data["role"] = 2
        await self.validate_entity(data)
        await resolve_entity(data)

        # 如果没有提供编号，自动生成
        if not data.get("code"):
            contract_company_id = data.get("contract_company_id")
            if contract_company_id:
                data["code"] = await generate_vendor_code(contract_company_id, data.get("signing_entity_id"))
            else:
                # 没有签约主体时使用默认生成方式
                data["code"] = await generate_vendor_code(0, data.get("signing_entity_id"))

        try:
            async with in_transaction():
                vendor = await self.create(data)
                await bind_attachments(vendor.id, attachment_ids)
                return vendor
        except IntegrityError as exc:
            raise HTTPException(status_code=409, detail="供应商编号已存在，请修改编号或重试") from exc

    async def update_vendor(self, id: int, obj_in: VendorUpdate) -> Company:
        data = obj_in.model_dump(exclude_unset=True, exclude={"id"})
        attachment_ids = data.pop("attachment_ids", [])
        data["role"] = 2
        await self.validate_entity(data)
        await resolve_entity(data, await self.get(id))
        if not data.get("code"):
            data.pop("code", None)
        try:
            async with in_transaction():
                vendor = await self.update(id=id, obj_in=data)
                await bind_attachments(vendor.id, attachment_ids)
                return vendor
        except IntegrityError as exc:
            raise HTTPException(status_code=409, detail="供应商编号已存在") from exc

    async def remove(self, id: int) -> None:
        vendor = await self.get(id)
        if await VendorAttachment.filter(vendor_id=id).exists():
            raise HTTPException(409, "请先在编辑窗口删除供应商附件")
        try:
            await vendor.delete()
        except IntegrityError as exc:
            raise HTTPException(409, "供应商仍有关联记录，无法删除") from exc

    async def generate_code(self, contract_company_id: int = None) -> str:
        """生成供应商编号的公共方法"""
        if contract_company_id:
            return await generate_vendor_code(contract_company_id)
        return await generate_vendor_code(0)


vendor_controller = VendorController()
