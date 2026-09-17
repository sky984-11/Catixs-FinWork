import asyncio
import base64
import binascii
import logging
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel, Field
from tortoise.transactions import in_transaction

from app.core.ctx import CTX_USER_ID
from app.models.company import Company, VendorAttachment

logger = logging.getLogger(__name__)
ATTACHMENT_DIR = Path(__file__).resolve().parents[2] / "private_uploads" / "vendors"
MAX_ATTACHMENT_SIZE = 20 * 1024 * 1024
MAX_ENCODED_SIZE = 4 * ((MAX_ATTACHMENT_SIZE + 2) // 3) + 1024


async def ensure_vendor_columns() -> None:
    """Support deployments that create missing schema at startup without shipping migration history."""
    connection = Company._meta.db
    fields = {
        "payment_terms": "VARCHAR(200)",
        "sales_contact": "TEXT",
        "billing_contact": "TEXT",
        "noc_contact": "TEXT",
        "signing_entity_id": 'BIGINT REFERENCES "crm_signing_entity" ("id") ON DELETE SET NULL',
    }
    if connection.schema_generator.DIALECT == "sqlite":
        existing = {item["name"] for item in await connection.execute_query_dict('PRAGMA table_info("company")')}
        if not existing:
            return
        for name, data_type in fields.items():
            if name not in existing:
                await connection.execute_script(f'ALTER TABLE "company" ADD COLUMN "{name}" {data_type};')
    else:
        for name, data_type in fields.items():
            await connection.execute_script(
                f'ALTER TABLE IF EXISTS "company" ADD COLUMN IF NOT EXISTS "{name}" {data_type};'
            )


class VendorAttachmentUpload(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field("application/octet-stream", min_length=1, max_length=200)
    data: str = Field(..., min_length=1, max_length=MAX_ENCODED_SIZE)
    vendor_id: int | None = Field(None, gt=0)


def attachment_data(item: VendorAttachment) -> dict:
    return {"id": item.id, "name": item.filename, "size": item.size, "content_type": item.content_type}


async def require_vendor(vendor_id: int) -> None:
    if not await Company.filter(id=vendor_id, role=2).exists():
        raise HTTPException(404, "供应商不存在")


async def bind_attachments(vendor_id: int, ids: list[int]) -> None:
    for attachment_id in set(ids):
        item = await VendorAttachment.filter(id=attachment_id).select_for_update().first()
        if item is None:
            raise HTTPException(400, "附件已删除，请重新上传")
        if item.vendor_id == vendor_id:
            continue
        if item.vendor_id is not None or item.owner_id != CTX_USER_ID.get():
            raise HTTPException(403, "不能关联其他供应商或其他用户的附件")
        item.vendor_id = vendor_id
        await item.save(update_fields=["vendor_id", "updated_at"])


async def upload_attachment(payload: VendorAttachmentUpload, owner_id: int) -> dict:
    if payload.vendor_id is not None:
        await require_vendor(payload.vendor_id)
    encoded = payload.data
    if len(encoded) > MAX_ENCODED_SIZE:
        raise HTTPException(413, "附件不能超过20MiB")
    if encoded.startswith("data:"):
        header, separator, encoded = encoded.partition(",")
        if not separator or not header.endswith(";base64"):
            raise HTTPException(400, "无效的Base64 Data URL")
    try:
        content = await asyncio.to_thread(base64.b64decode, encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise HTTPException(400, "无效的Base64编码") from exc
    if not content:
        raise HTTPException(400, "附件不能为空")
    if len(content) > MAX_ATTACHMENT_SIZE:
        raise HTTPException(413, "附件不能超过20MiB")
    filename = payload.filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not filename or any(ord(char) < 32 for char in filename):
        raise HTTPException(400, "无效的文件名")
    stored_name = uuid4().hex
    path = ATTACHMENT_DIR / stored_name
    await asyncio.to_thread(ATTACHMENT_DIR.mkdir, parents=True, exist_ok=True)
    try:
        await asyncio.to_thread(path.write_bytes, content)
        item = await VendorAttachment.create(
            owner_id=owner_id,
            vendor_id=payload.vendor_id,
            filename=filename,
            stored_name=stored_name,
            content_type=payload.content_type,
            size=len(content),
        )
    except Exception:
        await asyncio.to_thread(path.unlink, missing_ok=True)
        raise
    logger.info("vendor attachment uploaded id=%s user=%s size=%s", item.id, owner_id, item.size)
    return attachment_data(item)


async def check_access(item: VendorAttachment | None, user_id: int) -> VendorAttachment:
    if item is None:
        raise HTTPException(404, "附件不存在")
    if item.vendor_id is None:
        if item.owner_id != user_id:
            raise HTTPException(403, "不能访问其他用户的未保存附件")
    else:
        await require_vendor(item.vendor_id)
    return item


async def delete_attachment(attachment_id: int, user_id: int) -> None:
    staged = None
    path = None
    try:
        async with in_transaction():
            item = await VendorAttachment.filter(id=attachment_id).select_for_update().first()
            item = await check_access(item, user_id)
            path = ATTACHMENT_DIR / item.stored_name
            if await asyncio.to_thread(path.exists):
                staged = path.with_name(f"{item.stored_name}.deleting")
                await asyncio.to_thread(path.rename, staged)
            await item.delete()
    except Exception:
        if staged is not None and await asyncio.to_thread(staged.exists):
            await asyncio.to_thread(staged.rename, path)
        raise
    if staged is not None:
        try:
            await asyncio.to_thread(staged.unlink)
        except OSError:
            # Restore the row and file so that a failed physical deletion remains retryable.
            await asyncio.to_thread(staged.rename, path)
            await VendorAttachment.create(**{field: getattr(item, field) for field in item._meta.db_fields})
            raise HTTPException(500, "附件删除失败，请重试")
    logger.info("vendor attachment deleted id=%s user=%s", attachment_id, user_id)
