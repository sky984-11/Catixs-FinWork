import hashlib

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


TRANSMISSION_FIELDS = [
    {"key": "circuit_id", "label": "线路编号"},
    {"key": "provider", "label": "供应商"},
    {"key": "site_a", "label": "A 端位置"},
    {"key": "site_b", "label": "B 端位置"},
    {"key": "bandwidth", "label": "带宽"},
]


def category_fields(category):
    fields = category.get("fields")
    return fields if fields is not None else TRANSMISSION_FIELDS if category.get("label") == "传输线路" else []


class CategoryField(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    key: str = Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_-]{0,39}$")
    label: str = Field(min_length=1, max_length=40)


class Category(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    key: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    label: str = Field(min_length=1, max_length=40)
    fields: list[CategoryField] | None = Field(default=None, max_length=20)

    @model_validator(mode="after")
    def unique_fields(self):
        keys = [f.key for f in self.fields or []]
        labels = [f.label for f in self.fields or []]
        if len(keys) != len(set(keys)) or len(labels) != len(set(labels)):
            raise ValueError("字段键和名称不能重复")
        return self


class SelectedHost(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hostid: str = Field(pattern=r"^[1-9][0-9]{0,19}$")
    category: str | None = Field(default=None, min_length=1, max_length=64)
    itemids: list[str] | None = Field(default=None, min_length=1, max_length=2000)
    attributes: dict[str, str] = Field(default_factory=dict, max_length=20)

    @model_validator(mode="after")
    def validate_items(self):
        if any(len(k) > 40 or len(v) > 300 for k, v in self.attributes.items()):
            raise ValueError("属性键最多 40 字符，值最多 300 字符")
        if self.itemids is not None and (
            len(set(self.itemids)) != len(self.itemids)
            or any(
                not value.isascii() or not value.isdigit() or int(value) <= 0 or len(value) > 20
                for value in self.itemids
            )
        ):
            raise ValueError("监控项 ID 必须为不重复的正整数")
        return self


class SettingsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=0)
    category_tag: str = Field(default="business_category", min_length=1, max_length=255)
    categories: list[Category] | None = Field(default=None, max_length=50)
    hosts: list[SelectedHost] = Field(max_length=1000)

    @model_validator(mode="after")
    def validate_links(self):
        keys = [c.key for c in self.categories or []]
        names = [c.label for c in self.categories or []]
        ids = [h.hostid for h in self.hosts]
        if "unclassified" in keys:
            raise ValueError("unclassified 为系统保留分类标识")
        if len(set(keys)) != len(keys) or len(set(names)) != len(names) or len(set(ids)) != len(ids):
            raise ValueError("分类标识、分类名称和主机不能重复")
        if self.categories is not None and any(h.category is not None and h.category not in keys for h in self.hosts):
            raise ValueError("请先为主机重新分配分类，再删除原分类")
        if sum(len(h.itemids or []) for h in self.hosts) > 20000:
            raise ValueError("指定监控项总数不能超过 20000")
        return self


async def load_settings():
    row = await MonitorEventConfig.get_or_none(id=1)
    if row and any("itemids" not in host or "category" not in host for host in row.hosts):
        # One-time JSON upgrade; future classification never reads Zabbix tags.
        async with in_transaction():
            row = await MonitorEventConfig.filter(id=1).select_for_update().get()
            if any("itemids" not in host or "category" not in host for host in row.hosts):
                categories = list(row.categories)
                for host in row.hosts:
                    if "category" not in host:
                        labels = sorted(
                            {
                                t["value"].strip()
                                for t in host.get("tags", [])
                                if t.get("tag") == row.category_tag and t.get("value", "").strip()
                            }
                        )
                        host["category"] = None
                        if labels:
                            label = labels[0][:40]
                            match = next((c for c in categories if c["label"] == label), None)
                            if match is None:
                                match = {
                                    "key": "local_" + hashlib.sha256(label.encode()).hexdigest()[:32],
                                    "label": label,
                                }
                                categories.append(match)
                            host["category"] = match["key"]
                    host.setdefault("itemids", None)
                row.categories = categories
                row.revision += 1
                await row.save(update_fields=["categories", "hosts", "revision", "updated_at"])
    return (
        {
            "revision": row.revision,
            "category_tag": row.category_tag,
            "category_source": "platform",
            "categories": [{**c, "fields": category_fields(c)} for c in row.categories],
            "hosts": row.hosts,
        }
        if row
        else {
            "revision": 0,
            "category_tag": "business_category",
            "category_source": "platform",
            "categories": DEFAULT_CATEGORIES,
            "hosts": [],
        }
    )


async def save_settings(payload, verified_hosts, user_id):
    lookup = {h["hostid"]: h for h in verified_hosts if str(h.get("status")) == "0"}
    if any(h.hostid not in lookup for h in payload.hosts):
        raise HTTPException(422, "选择中包含已删除、停用或无权限的 Zabbix 主机，请移除后重新保存")
    async with in_transaction():
        await MonitorEventConfig.get_or_create(id=1, defaults={"revision": 0, "updated_by_id": user_id})
        row = await MonitorEventConfig.filter(id=1).select_for_update().get()
        if row.revision != payload.revision:
            raise HTTPException(409, "配置已被其他用户修改，请重新加载后保存")
        categories = [c.model_dump() for c in payload.categories] if payload.categories is not None else row.categories
        previous_categories = {c["key"]: c for c in row.categories}
        for category in categories:
            if category.get("fields") is None:
                category["fields"] = category_fields(previous_categories.get(category["key"], category)) or []
        old_hosts = {h["hostid"]: h for h in row.hosts}
        hosts = []
        for host in payload.hosts:
            old = old_hosts.get(host.hostid, {})
            category = host.category if "category" in host.model_fields_set else old.get("category")
            itemids = host.itemids if "itemids" in host.model_fields_set else old.get("itemids")
            if category is not None and category not in {c["key"] for c in categories}:
                raise HTTPException(422, "分类仍有关联主机，请先调整主机分类")
            definition = next((c for c in categories if c["key"] == category), {})
            allowed = {f["key"] for f in category_fields(definition)}
            values = host.attributes if "attributes" in host.model_fields_set else old.get("attributes", {})
            attributes = {k: v.strip() for k, v in values.items() if k in allowed and v.strip()}
            hosts.append(
                {
                    "hostid": host.hostid,
                    "name": lookup[host.hostid].get("name") or lookup[host.hostid].get("host", ""),
                    "tags": lookup[host.hostid].get("tags", []),
                    "category": category,
                    "itemids": itemids,
                    "attributes": attributes,
                }
            )
        row.categories = categories
        row.category_tag = payload.category_tag.strip()
        if not row.category_tag:
            raise HTTPException(422, "请选择分类使用的 Zabbix 标签名称")
        row.hosts = hosts
        row.revision += 1
        row.updated_by_id = user_id
        await row.save()
    return {
        "revision": row.revision,
        "category_tag": row.category_tag,
        "category_source": "platform",
        "categories": row.categories,
        "hosts": hosts,
    }


def local_categories(hosts, config):
    categories = config.get("categories", [])
    keys = {c["key"] for c in categories}
    selected = {h["hostid"]: h.get("category") for h in config["hosts"]}
    definitions = {c["key"]: category_fields(c) for c in categories}
    selected_hosts = {h["hostid"]: h for h in config["hosts"]}
    for host in hosts:
        saved = selected_hosts.get(host["hostid"], {})
        values = saved.get("attributes", {})
        host["attributes"] = [
            {**field, "value": values[field["key"]]}
            for field in definitions.get(saved.get("category"), [])
            if values.get(field["key"])
        ]
    assigned = {
        h["hostid"]: [selected[h["hostid"]]] if selected.get(h["hostid"]) in keys else ["unclassified"] for h in hosts
    }
    options = list(categories)
    if any(value == ["unclassified"] for value in assigned.values()):
        options.append({"key": "unclassified", "label": "未分类"})
    return assigned, options
