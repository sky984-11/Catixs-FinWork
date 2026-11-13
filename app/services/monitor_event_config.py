from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from tortoise.transactions import in_transaction

from app.models.monitor_event_config import MonitorEventConfig

DEFAULT_CATEGORIES = [
    {"key": "server", "label": "物理服务器"},
    {"key": "network", "label": "网络设备"},
    {"key": "circuit", "label": "国际线路"},
    {"key": "pve", "label": "PVE 虚拟化"},
    {"key": "other", "label": "其他"},
]


class Category(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    key: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    label: str = Field(min_length=1, max_length=40)


class SelectedHost(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hostid: str = Field(pattern=r"^[1-9][0-9]{0,19}$")
    category: str | None = Field(default=None, min_length=1, max_length=64)


class SettingsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=0)
    category_tag: str = Field(default="business_category", min_length=1, max_length=255)
    categories: list[Category] = Field(default_factory=list, max_length=50)
    hosts: list[SelectedHost] = Field(max_length=1000)

    @model_validator(mode="after")
    def validate_links(self):
        keys = [c.key for c in self.categories]
        names = [c.label for c in self.categories]
        ids = [h.hostid for h in self.hosts]
        if len(set(keys)) != len(keys) or len(set(names)) != len(names) or len(set(ids)) != len(ids):
            raise ValueError("分类标识、分类名称和主机不能重复")
        if any(h.category is not None and h.category not in keys for h in self.hosts):
            raise ValueError("请先为主机重新分配分类，再删除原分类")
        return self


async def load_settings():
    row = await MonitorEventConfig.get_or_none(id=1)
    return (
        {"revision": row.revision, "category_tag": row.category_tag, "categories": row.categories, "hosts": row.hosts}
        if row
        else {
            "revision": 0,
            "category_tag": "business_category",
            "categories": DEFAULT_CATEGORIES,
            "hosts": [],
        }
    )


async def save_settings(payload, verified_hosts, user_id):
    lookup = {h["hostid"]: h for h in verified_hosts if str(h.get("status")) == "0"}
    if any(h.hostid not in lookup for h in payload.hosts):
        raise HTTPException(422, "选择中包含已删除、停用或无权限的 Zabbix 主机，请移除后重新保存")
    hosts = [
        {
            "hostid": h.hostid,
            "name": lookup[h.hostid].get("name") or lookup[h.hostid].get("host", ""),
            "tags": lookup[h.hostid].get("tags", []),
        }
        for h in payload.hosts
    ]
    async with in_transaction():
        await MonitorEventConfig.get_or_create(id=1, defaults={"revision": 0, "updated_by_id": user_id})
        row = await MonitorEventConfig.filter(id=1).select_for_update().get()
        if row.revision != payload.revision:
            raise HTTPException(409, "配置已被其他用户修改，请重新加载后保存")
        row.categories = [c.model_dump() for c in payload.categories]
        row.category_tag = payload.category_tag.strip()
        if not row.category_tag:
            raise HTTPException(422, "请选择分类使用的 Zabbix 标签名称")
        row.hosts = hosts
        row.revision += 1
        row.updated_by_id = user_id
        await row.save()
    return {"revision": row.revision, "category_tag": row.category_tag, "categories": row.categories, "hosts": hosts}
