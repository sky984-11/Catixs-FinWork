import asyncio
import csv
import io
import json
import logging
from datetime import datetime

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import ValidationError
from tortoise.expressions import Q

from app.controllers import vendor_attachments
from app.controllers import vendor_contacts
from app.controllers.vendor import generate_vendor_code, vendor_controller
from app.controllers.vendor_entities import entity_context, entity_fields, match_entity, resolve_entity
from app.core.dependency import DependAuth
from app.models.admin import User
from app.models.company import Company, VendorAttachment
from app.schemas.base import Success, SuccessExtra
from app.schemas.vendors import VendorCreate, VendorUpdate

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/contacts/list", summary="供应商联系人列表")
async def list_vendor_contacts():
    return Success(data=await vendor_contacts.list_contacts())


@router.post("/contacts/create", summary="新增供应商联系人")
async def create_vendor_contact(payload: vendor_contacts.ContactInput):
    return Success(data=await vendor_contacts.save_contact(payload))


@router.post("/contacts/update", summary="编辑供应商联系人")
async def update_vendor_contact(payload: vendor_contacts.ContactUpdate):
    return Success(data=await vendor_contacts.save_contact(payload, payload.id))


@router.delete("/contacts/delete", summary="删除供应商联系人")
async def delete_vendor_contact(contact_id: str = Query(..., min_length=1, max_length=80)):
    await vendor_contacts.delete_contact(contact_id)
    return Success(msg="联系人已删除")


@router.get("/next-code", summary="预览供应商编号")
async def next_vendor_code(signing_entity_id: int = Query(..., gt=0)):
    data = {"signing_entity_id": signing_entity_id}
    await resolve_entity(data)
    code = await generate_vendor_code(0, signing_entity_id)
    return Success(data={"code": code})


async def vendor_data(vendor: Company) -> dict:
    data = await vendor.to_dict()
    data.update(entity_fields(vendor, *(await entity_context())))
    data["attachments"] = [
        vendor_attachments.attachment_data(item)
        for item in await VendorAttachment.filter(vendor_id=vendor.id).order_by("id")
    ]
    data["contacts"] = await vendor_contacts.list_contacts(vendor.id)
    return data


@router.post(
    "/attachments/upload",
    summary="上传供应商附件",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": vendor_attachments.VendorAttachmentUpload.model_json_schema()}},
        }
    },
)
async def upload_vendor_attachment(request: Request, user: User = DependAuth):
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > vendor_attachments.MAX_ENCODED_SIZE + 8192:
            raise HTTPException(413, "附件请求过大")
    try:
        payload = vendor_attachments.VendorAttachmentUpload.model_validate(json.loads(body))
    except (ValueError, ValidationError):
        raise HTTPException(422, "附件字段无效，请检查文件名、类型和Base64数据")
    return Success(data=await vendor_attachments.upload_attachment(payload, user.id))


@router.get("/attachments/download", summary="下载供应商附件")
async def download_vendor_attachment(attachment_id: int = Query(..., gt=0), user: User = DependAuth):
    item = await vendor_attachments.check_access(await VendorAttachment.get_or_none(id=attachment_id), user.id)
    path = vendor_attachments.ATTACHMENT_DIR / item.stored_name
    if not await asyncio.to_thread(path.is_file):
        raise HTTPException(404, "附件文件不存在")
    return FileResponse(path, filename=item.filename, media_type="application/octet-stream")


@router.delete("/attachments/delete", summary="删除供应商附件")
async def delete_vendor_attachment(attachment_id: int = Query(..., gt=0), user: User = DependAuth):
    await vendor_attachments.delete_attachment(attachment_id, user.id)
    return Success(msg="附件已删除")


@router.get("/list", summary="查看供应商列表")
async def list_vendor(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, description="每页数量"),
    name: str = Query("", description="供应商名称，用于搜索"),
    code: str = Query("", description="供应商编号"),
    status: bool | None = Query(None, description="启用状态"),
    keyword: str = Query("", description="供应商编号或名称"),
    signing_entity_id: int | None = Query(None, gt=0, description="CRM签约主体ID"),
):
    q = Q()
    entities, companies = await entity_context()
    if keyword.strip():
        keyword = keyword.strip()
        q &= Q(name__icontains=keyword) | Q(code__icontains=keyword)
    if signing_entity_id is not None:
        legacy_ids = [
            company.id for company in companies
            if (entity := match_entity(company, entities)) and entity.id == signing_entity_id
        ]
        q &= Q(signing_entity_id=signing_entity_id) | Q(
            signing_entity_id=None, contract_company_id__in=legacy_ids
        )
    if name:
        q &= Q(name__contains=name)
    if code:
        q &= Q(code__contains=code)
    if status is not None:
        q &= Q(status=status)

    total, vendor_objs = await vendor_controller.list_vendors(page=page, page_size=page_size, search=q, order=["id"])
    data = [await obj.to_dict() for obj in vendor_objs]
    for vendor, item in zip(vendor_objs, data):
        item.update(entity_fields(vendor, entities, companies))
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size)


@router.get("/get", summary="查看供应商")
async def get_vendor(
    vendor_id: int = Query(..., description="供应商ID"),
):
    vendor_obj = await vendor_controller.get(id=vendor_id)
    return Success(data=await vendor_data(vendor_obj))


@router.post("/create", summary="创建供应商")
async def create_vendor(
    vendor_in: VendorCreate,
):
    vendor_obj = await vendor_controller.create_vendor(vendor_in)
    return Success(msg="Created Successfully", data=await vendor_data(vendor_obj))


@router.post("/update", summary="更新供应商")
async def update_vendor(
    vendor_in: VendorUpdate,
):
    vendor_obj = await vendor_controller.update_vendor(id=vendor_in.id, obj_in=vendor_in)
    return Success(msg="Updated Successfully", data=await vendor_data(vendor_obj))


@router.delete("/delete", summary="删除供应商")
async def delete_vendor(
    vendor_id: int = Query(..., description="供应商ID"),
):
    await vendor_controller.remove(id=vendor_id)
    return Success(msg="Deleted Successfully")


@router.get("/export", summary="导出供应商")
async def export_vendor():
    """导出所有供应商为CSV格式"""
    # 查询所有供应商
    vendors = await Company.filter(role=2).all()

    # 获取签约主体公司列表
    entities, companies = await entity_context()

    # 创建CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # 写入表头
    writer.writerow(
        [
            "编号",
            "名称",
            "国家/地区",
            "地址",
            "公司邮箱",
            "公司电话",
            "NOC邮箱",
            "NOC电话",
            "税号",
            "注册号",
            "签约主体",
            "备注",
            "状态",
            "付款条件",
            "销售联系人",
            "账单联系人",
            "NOC联系信息",
        ]
    )

    # 写入数据
    for v in vendors:
        writer.writerow(
            [
                v.code or "",
                v.name or "",
                v.country or "",
                v.address or "",
                v.company_email or "",
                v.company_phone or "",
                v.noc_email or "",
                v.noc_phone or "",
                v.tax_no or "",
                v.registration_no or "",
                entity_fields(v, entities, companies)["signing_entity_name"] or "",
                v.remark or "",
                "启用" if v.status else "禁用",
                v.payment_terms or "",
                v.sales_contact or "",
                v.billing_contact or "",
                v.noc_contact or "",
            ]
        )

    # 返回CSV文件
    output.seek(0)
    filename = f"vendors_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/import", summary="导入供应商")
async def import_vendor(
    file: UploadFile = File(..., description="CSV文件"),
):
    # 检查文件类型
    if not file.filename.lower().endswith(".csv"):
        return Success(msg="请上传 CSV 文件", code=400)

    # 读取文件内容
    content = await file.read()

    # 解析CSV
    try:
        decoded = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            decoded = content.decode("gbk")
        except UnicodeDecodeError:
            return Success(msg="文件编码不支持，请使用 UTF-8 或 GBK 编码", code=400)

    reader = csv.DictReader(io.StringIO(decoded))

    # 获取签约主体公司列表
    entities, companies = await entity_context()

    success_count = 0
    error_rows = []

    for row_num, row in enumerate(reader, start=2):
        try:
            # 查找签约主体公司ID
            contract_company_id = None
            contract_company_name = (row.get("签约主体") or row.get("Catixs Entity") or "").strip()
            matches = [item for item in entities if item.name == contract_company_name and item.status]
            legacy_matches = [item for item in companies if item.name == contract_company_name]
            if contract_company_name and len(matches) != 1:
                if matches or len(legacy_matches) != 1:
                    raise ValueError("签约主体不存在或名称不唯一，请核对客户管理签约主体")
                contract_company_id = legacy_matches[0].id

            # 解析状态
            status = True
            status_str = row.get("状态", "").strip()
            if status_str in ["禁用", "停用", "disabled", "inactive"]:
                status = False

            # 创建供应商
            vendor_data = {
                "name": (row.get("名称") or row.get("Vendor Name") or "").strip(),
                "code": (row.get("编号") or row.get("Vendor ID") or "").strip(),
                "payment_terms": (row.get("付款条件") or row.get("Payment Terms") or "").strip(),
                "sales_contact": (row.get("销售联系人") or row.get("Sales Contact") or "").strip(),
                "billing_contact": (row.get("账单联系人") or row.get("Billing Contact") or "").strip(),
                "noc_contact": (row.get("NOC联系信息") or row.get("NOC Contact") or "").strip(),
                "country": row.get("国家/地区", "").strip(),
                "address": row.get("地址", "").strip(),
                "company_email": row.get("公司邮箱", "").strip(),
                "company_phone": row.get("公司电话", "").strip(),
                "noc_email": row.get("NOC邮箱", "").strip(),
                "noc_phone": row.get("NOC电话", "").strip(),
                "tax_no": row.get("税号", "").strip(),
                "registration_no": row.get("注册号", "").strip(),
                "contract_company_id": contract_company_id,
                "remark": row.get("备注", "").strip(),
                "status": status,
                "role": 2,
            }

            if len(matches) == 1:
                vendor_data["signing_entity_id"] = matches[0].id

            await vendor_controller.create_vendor(VendorCreate(**vendor_data))
            success_count += 1

        except Exception as e:
            error_rows.append(f"第{row_num}行: {str(e)}")

    msg = f"导入成功 {success_count} 条"
    if error_rows:
        msg += f"，错误: {'; '.join(error_rows[:5])}"
        if len(error_rows) > 5:
            msg += f" ... 等{len(error_rows)}条错误"

    return Success(msg=msg)
