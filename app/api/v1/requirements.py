import logging
import re
from collections import Counter
from datetime import datetime
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
from fastapi import APIRouter, Query
from tortoise.exceptions import IntegrityError
from tortoise.expressions import Q

from app.models.company import Company
from app.models.project import CustomerProject, CustomerRequirement
from app.schemas.base import Success, SuccessExtra
from app.schemas.requirements import (
    CustomerRequirementCreate,
    CustomerRequirementStatusUpdate,
    CustomerRequirementUpdate,
    FeishuRequirementSyncPayload,
)
from app.utils.feishu_app import FEISHU_API_BASE, get_tenant_access_token

logger = logging.getLogger(__name__)
router = APIRouter()

FEISHU_REQUIREMENT_FIELD_ALIASES = {
    "title": ["需求主题", "需求标题", "需求名称", "需求", "标题", "名称", "title", "name"],
    "code": ["需求编号", "编号", "ID", "id", "code", "编号/ID"],
    "customer_name": ["客户", "客户名称", "公司", "客户/公司", "customer", "company"],
    "project_name": ["项目", "关联项目", "项目名称", "所属项目", "project"],
    "source": ["来源", "需求来源", "渠道", "source"],
    "source_detail": ["请求人; 媒介; 原始发起信息", "来源说明", "来源详情", "链接", "反馈来源", "source detail"],
    "requirement_type": ["类型", "需求类型", "分类", "type"],
    "status": ["状态", "需求状态", "进度", "阶段", "status"],
    "priority": ["优先级", "紧急程度", "优先级别", "priority"],
    "owner": ["负责人", "产品负责人", "跟进人", "owner", "pm"],
    "requester": ["请求人; 媒介; 原始发起信息", "提出人", "提交人", "需求方", "客户联系人", "requester"],
    "service_type": ["Service", "服务", "服务类型", "产品类型", "IDC服务", "业务类型", "service type"],
    "a_end": ["A-end", "A端", "A End", "A-end POP"],
    "z_end": ["Z-end", "Z端", "Z End", "B-end", "B端"],
    "region": ["区域", "地区", "国家/地区", "城市", "region", "location"],
    "datacenter": ["机房", "数据中心", "IDC", "POP", "datacenter"],
    "bandwidth": ["带宽", "端口", "流量", "bandwidth", "port"],
    "ip_count": ["IP数量", "IP数", "IPv4", "IPv6", "ip count"],
    "cabinet_count": ["机柜", "机柜数", "柜位", "cabinet"],
    "server_count": ["服务器", "服务器数量", "裸金属", "server"],
    "contract_term": ["合同周期", "周期", "租期", "term"],
    "budget_amount": ["预算", "客户预算", "预算金额", "budget"],
    "budget_currency": ["Currency", "币种", "预算币种", "currency"],
    "nrc_amount": ["NRC", "一次性费用", "初装费", "setup fee"],
    "expected_mrr": ["MRC", "预计MRR", "MRR", "月收入", "monthly revenue"],
    "target_price": ["Target", "目标价", "客户目标价", "target price"],
    "probability": ["成交概率", "赢单率", "概率", "probability"],
    "competitor": ["竞争对手", "竞品", "competitor"],
    "next_action": ["下一步", "下一步动作", "跟进动作", "next action"],
    "expected_at": ["截止日期", "期望日期", "期望时间", "期望上线", "期望完成时间", "expected date"],
    "planned_at": ["计划日期", "计划时间", "计划上线", "planned date"],
    "released_at": ["发布日期", "上线日期", "发布时间", "released date"],
    "value_score": ["价值", "价值分", "业务价值", "value"],
    "effort_score": ["成本", "工作量", "复杂度", "effort"],
    "confidence_score": ["信心", "确定性", "confidence"],
    "reach_score": ["触达", "影响范围", "覆盖用户", "reach"],
    "vote_count": ["投票", "投票数", "客户数", "votes"],
    "tags": ["标签", "tag", "tags"],
    "related_links": ["相关链接", "PRD", "文档", "链接", "links"],
    "description": ["需求细节，负责人及解决方案", "需求描述", "描述", "背景", "问题", "详情", "description"],
    "acceptance_criteria": ["验收标准", "验收条件", "AC", "acceptance criteria"],
    "solution": ["方案", "解决方案", "备注", "solution"],
}

STATUS_MAP = {
    "线索": "lead",
    "新线索": "lead",
    "待确认": "lead",
    "已确认": "qualified",
    "有效需求": "qualified",
    "方案中": "solution",
    "方案设计": "solution",
    "报价中": "quotation",
    "已报价": "quotation",
    "谈判中": "negotiation",
    "商务谈判": "negotiation",
    "已成交": "won",
    "赢单": "won",
    "丢单": "lost",
    "已丢单": "lost",
    "搁置": "shelved",
    "暂停": "shelved",
    "需求池": "pool",
    "待评审": "reviewing",
    "评审中": "reviewing",
    "已规划": "planned",
    "规划中": "planned",
    "设计中": "designing",
    "研发中": "developing",
    "开发中": "developing",
    "测试中": "testing",
    "已发布": "released",
    "已上线": "released",
    "已拒绝": "rejected",
    "拒绝": "rejected",
}

PRIORITY_MAP = {
    "低": "low",
    "中": "medium",
    "中等": "medium",
    "高": "high",
    "紧急": "urgent",
    "最高": "urgent",
    "p0": "urgent",
    "p1": "high",
    "p2": "medium",
    "p3": "low",
}

SOURCE_MAP = {
    "客户": "customer",
    "客户反馈": "customer",
    "销售": "sales",
    "销售录入": "sales",
    "支持": "support",
    "工单": "support",
    "内部": "internal",
    "内部规划": "internal",
    "运维": "ops",
    "市场": "market",
    "其他": "other",
}

TYPE_MAP = {
    "机柜托管": "colocation",
    "托管": "colocation",
    "机柜": "colocation",
    "服务器": "server",
    "裸金属": "server",
    "独立服务器": "server",
    "带宽": "bandwidth",
    "IP": "ip",
    "云": "cloud",
    "云服务器": "cloud",
    "托管服务": "managed",
    "安全": "security",
    "高防": "security",
    "新功能": "feature",
    "功能": "feature",
    "优化": "improvement",
    "体验优化": "improvement",
    "bug": "bug",
    "缺陷": "bug",
    "调研": "research",
    "运维": "ops",
    "其他": "other",
}


async def serialize_requirement(item: CustomerRequirement) -> dict:
    data = await item.to_dict()
    data["tags"] = normalize_string_list(data.get("tags"))
    data["related_links"] = normalize_string_list(data.get("related_links"))
    data["customer_name"] = ""
    data["customer_legal_name"] = ""
    data["project_name"] = ""
    data["project_code"] = ""
    data["priority_score"] = calculate_priority_score(data)

    if data.get("customer_id"):
        customer = await Company.get_or_none(id=data["customer_id"])
        if customer:
            data["customer_name"] = customer.name or ""
            data["customer_legal_name"] = customer.legal_name or ""
    if data.get("project_id"):
        project = await CustomerProject.get_or_none(id=data["project_id"])
        if project:
            data["project_name"] = project.name or ""
            data["project_code"] = project.code or ""
    return data


def normalize_string_list(value) -> list[str]:
    if not value:
        return []
    values = value.split(",") if isinstance(value, str) else value
    result = []
    seen = set()
    for item in values:
        text = str(item or "").strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def normalize_requirement_payload(payload: dict) -> dict:
    if not str(payload.get("code") or "").strip():
        payload["code"] = None
    for key in [
        "source_detail",
        "owner",
        "requester",
        "service_type",
        "a_end",
        "z_end",
        "region",
        "datacenter",
        "bandwidth",
        "contract_term",
        "budget_currency",
        "target_price",
        "competitor",
        "next_action",
        "description",
        "acceptance_criteria",
        "solution",
    ]:
        if payload.get(key) is None:
            payload[key] = ""
        elif isinstance(payload[key], str):
            payload[key] = payload[key].strip()
    payload["tags"] = normalize_string_list(payload.get("tags"))
    payload["related_links"] = normalize_string_list(payload.get("related_links"))
    return payload


def clean(value: Any) -> str:
    return str(value or "").strip()


def normalize_requirement_code_part(value: str) -> str:
    text = re.sub(r"\s+", "", clean(value))
    text = re.sub(r"[^\w\u4e00-\u9fff-]+", "", text)
    return text or "REQ"


async def generate_requirement_code(customer_id: int | None) -> str:
    customer_name = "REQ"
    if customer_id:
        customer = await Company.get_or_none(id=customer_id)
        if customer:
            customer_name = customer.legal_name or customer.name or customer.code or "REQ"

    date_part = datetime.now().strftime("%Y%m%d")
    customer_part = normalize_requirement_code_part(customer_name)
    base = f"{customer_part}-{date_part}"
    max_base_length = 47
    if len(base) > max_base_length:
        base = f"{customer_part[: max_base_length - len(date_part) - 1]}-{date_part}"

    existing_codes = await CustomerRequirement.filter(code__startswith=base).values_list("code", flat=True)
    max_sequence = 0
    for code in existing_codes:
        match = re.fullmatch(rf"{re.escape(base)}(\d+)", clean(code))
        if match:
            max_sequence = max(max_sequence, int(match.group(1)))
    return f"{base}{max_sequence + 1:02d}"


def unique_feishu_requirement_code(code: str | None, record_id: str, code_counts: Counter[str]) -> str | None:
    base = clean(code)
    if not base:
        return None
    if code_counts.get(base, 0) <= 1:
        return base[:50]
    suffix = clean(record_id)[-6:]
    return f"{base}-{suffix}"[:50] if suffix else base[:50]


def parse_feishu_bitable_url(url: str) -> dict[str, str]:
    parsed = urlparse(clean(url))
    params = parse_qs(parsed.query)
    parts = [part for part in parsed.path.split("/") if part]
    app_token = ""
    if "base" in parts:
        index = parts.index("base")
        if len(parts) > index + 1:
            app_token = parts[index + 1]
    return {
        "app_token": app_token,
        "table_id": (params.get("table") or [""])[0],
        "view_id": (params.get("view") or [""])[0],
    }


def feishu_plain_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, list):
        parts = [feishu_plain_value(item) for item in value]
        parts = [str(item) for item in parts if item not in (None, "")]
        return ", ".join(parts)
    if isinstance(value, dict):
        for key in ("text", "name", "en_name", "email", "link", "url"):
            if value.get(key):
                return value.get(key)
        if "value" in value:
            return feishu_plain_value(value.get("value"))
        return ", ".join(str(item) for item in value.values() if item not in (None, ""))
    return value


def feishu_url_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        for item in value:
            link = feishu_url_value(item)
            if link:
                return link
        return clean(feishu_plain_value(value))
    if isinstance(value, dict):
        for key in ("tmp_url", "url", "link"):
            if value.get(key):
                return clean(value.get(key))
        return clean(feishu_plain_value(value))
    return clean(value)


def pick_feishu_field(fields: dict[str, Any], key: str) -> Any:
    normalized = {name.strip().lower(): value for name, value in fields.items()}
    for alias in FEISHU_REQUIREMENT_FIELD_ALIASES.get(key, []):
        if alias.strip().lower() in normalized:
            return feishu_plain_value(normalized[alias.strip().lower()])
    return None


def pick_feishu_url_field(fields: dict[str, Any], key: str) -> str:
    normalized = {name.strip().lower(): value for name, value in fields.items()}
    for alias in FEISHU_REQUIREMENT_FIELD_ALIASES.get(key, []):
        if alias.strip().lower() in normalized:
            return feishu_url_value(normalized[alias.strip().lower()])
    return ""


def parse_feishu_date(value: Any):
    value = feishu_plain_value(value)
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp = timestamp / 1000
        return datetime.fromtimestamp(timestamp).date()
    text = clean(value)
    compact = re.sub(r"\D", "", text)
    if len(compact) >= 8:
        try:
            return datetime.strptime(compact[:8], "%Y%m%d").date()
        except ValueError:
            pass
    for pattern in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y-%m", "%Y/%m", "%Y.%m"):
        try:
            parsed = datetime.strptime(text, pattern)
            return parsed.date()
        except ValueError:
            continue
    return None


def parse_feishu_int(value: Any, default: int = 0) -> int:
    value = feishu_plain_value(value)
    if value in (None, ""):
        return default
    if isinstance(value, (int, float)):
        return max(0, int(value))
    match = re.search(r"-?\d+", clean(value).replace(",", ""))
    return max(0, int(match.group(0))) if match else default


def parse_feishu_float(value: Any, default: float | None = None) -> float | None:
    value = feishu_plain_value(value)
    if value in (None, ""):
        return default
    if isinstance(value, (int, float)):
        return max(0.0, float(value))
    match = re.search(r"-?\d+(?:\.\d+)?", clean(value).replace(",", ""))
    return max(0.0, float(match.group(0))) if match else default


def map_value(value: Any, mapping: dict[str, str], default: str) -> str:
    text = clean(feishu_plain_value(value))
    if not text:
        return default
    lower = text.lower()
    if lower in mapping:
        return mapping[lower]
    if text in mapping:
        return mapping[text]
    return lower if lower in set(mapping.values()) else default


async def fetch_feishu_bitable_records(app_token: str, table_id: str, view_id: str = "") -> list[dict[str, Any]]:
    token = await get_tenant_access_token()
    if not token:
        raise Exception("飞书应用凭证未配置或获取 tenant_access_token 失败")
    records = []
    page_token = ""
    async with httpx.AsyncClient(timeout=20.0) as client:
        while True:
            params = {"page_size": 500}
            if view_id:
                params["view_id"] = view_id
            if page_token:
                params["page_token"] = page_token
            response = await client.get(
                f"{FEISHU_API_BASE}/bitable/v1/apps/{app_token}/tables/{table_id}/records",
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )
            try:
                data = response.json()
            except ValueError:
                raise Exception(f"飞书多维表返回非 JSON：{response.text[:200]}")
            if response.status_code != 200 or data.get("code") != 0:
                raise Exception(f"读取飞书多维表失败：{data.get('msg') or data}")
            payload = data.get("data") or {}
            records.extend(payload.get("items") or [])
            if not payload.get("has_more"):
                break
            page_token = payload.get("page_token") or ""
            if not page_token:
                break
    return records


async def find_customer_by_name(name: str, create_missing: bool = False) -> Company | None:
    name = clean(name)
    if not name:
        return None
    customer = await Company.filter(Q(name=name) | Q(legal_name=name) | Q(code=name)).first()
    if customer or not create_missing:
        return customer
    return await Company.create(role=1, name=name, legal_name=name, status=True)


async def find_project_by_name(name: str) -> CustomerProject | None:
    name = clean(name)
    if not name:
        return None
    return await CustomerProject.filter(Q(name=name) | Q(code=name) | Q(name__contains=name)).first()


async def feishu_record_to_requirement_payload(
    record: dict[str, Any],
    create_missing_customers: bool = False,
) -> dict[str, Any]:
    fields = record.get("fields") or {}
    title = clean(pick_feishu_field(fields, "title"))
    customer_name = clean(pick_feishu_field(fields, "customer_name"))
    project_name = clean(pick_feishu_field(fields, "project_name"))
    customer = await find_customer_by_name(customer_name, create_missing_customers)
    project = await find_project_by_name(project_name)
    related_link = pick_feishu_url_field(fields, "related_links")
    payload = {
        "title": title,
        "code": clean(pick_feishu_field(fields, "code")) or None,
        "customer_id": customer.id if customer else None,
        "project_id": project.id if project else None,
        "source": "feishu",
        "source_record_id": record.get("record_id"),
        "source_detail": clean(pick_feishu_field(fields, "source_detail")),
        "requirement_type": map_value(pick_feishu_field(fields, "requirement_type"), TYPE_MAP, "bandwidth"),
        "status": map_value(pick_feishu_field(fields, "status"), STATUS_MAP, "lead"),
        "priority": map_value(pick_feishu_field(fields, "priority"), PRIORITY_MAP, "medium"),
        "owner": clean(pick_feishu_field(fields, "owner")),
        "requester": clean(pick_feishu_field(fields, "requester")),
        "service_type": clean(pick_feishu_field(fields, "service_type")),
        "a_end": clean(pick_feishu_field(fields, "a_end")),
        "z_end": clean(pick_feishu_field(fields, "z_end")),
        "region": clean(pick_feishu_field(fields, "region")),
        "datacenter": clean(pick_feishu_field(fields, "datacenter")),
        "bandwidth": clean(pick_feishu_field(fields, "bandwidth")),
        "ip_count": parse_feishu_int(pick_feishu_field(fields, "ip_count")),
        "cabinet_count": parse_feishu_float(pick_feishu_field(fields, "cabinet_count"), 0) or 0,
        "server_count": parse_feishu_int(pick_feishu_field(fields, "server_count")),
        "contract_term": clean(pick_feishu_field(fields, "contract_term")),
        "budget_amount": parse_feishu_float(pick_feishu_field(fields, "budget_amount")),
        "budget_currency": clean(pick_feishu_field(fields, "budget_currency")) or "USD",
        "nrc_amount": parse_feishu_float(pick_feishu_field(fields, "nrc_amount")),
        "expected_mrr": parse_feishu_float(pick_feishu_field(fields, "expected_mrr")),
        "target_price": clean(pick_feishu_field(fields, "target_price")),
        "probability": min(parse_feishu_int(pick_feishu_field(fields, "probability"), 30), 100),
        "competitor": clean(pick_feishu_field(fields, "competitor")),
        "next_action": clean(pick_feishu_field(fields, "next_action")),
        "expected_at": parse_feishu_date(pick_feishu_field(fields, "expected_at")),
        "planned_at": parse_feishu_date(pick_feishu_field(fields, "planned_at")),
        "released_at": parse_feishu_date(pick_feishu_field(fields, "released_at")),
        "value_score": min(parse_feishu_int(pick_feishu_field(fields, "value_score")), 100),
        "effort_score": min(parse_feishu_int(pick_feishu_field(fields, "effort_score")), 100),
        "confidence_score": min(parse_feishu_int(pick_feishu_field(fields, "confidence_score")), 100),
        "reach_score": min(parse_feishu_int(pick_feishu_field(fields, "reach_score")), 100),
        "vote_count": parse_feishu_int(pick_feishu_field(fields, "vote_count")),
        "tags": normalize_string_list(pick_feishu_field(fields, "tags")),
        "related_links": normalize_string_list([related_link] if related_link else pick_feishu_field(fields, "related_links")),
        "description": clean(pick_feishu_field(fields, "description")),
        "acceptance_criteria": clean(pick_feishu_field(fields, "acceptance_criteria")),
        "solution": clean(pick_feishu_field(fields, "solution")),
        "sort_order": 0,
    }
    if not payload["source_detail"]:
        payload["source_detail"] = customer_name or project_name or "飞书多维表"
    return normalize_requirement_payload(payload)


def calculate_priority_score(data: dict) -> int:
    return (
        int(data.get("value_score") or 0) * 2
        + int(data.get("reach_score") or 0)
        + int(data.get("confidence_score") or 0)
        + min(int(data.get("vote_count") or 0), 100)
        + int(data.get("probability") or 0)
        + min(int(float(data.get("expected_mrr") or 0) / 100), 100)
        - int(data.get("effort_score") or 0)
    )


def build_requirement_summary(rows: list[dict]) -> dict:
    status_counts = {}
    priority_counts = {}
    source_counts = {}
    for row in rows:
        status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1
        priority_counts[row["priority"]] = priority_counts.get(row["priority"], 0) + 1
        source_counts[row["source"]] = source_counts.get(row["source"], 0) + 1
    return {
        "count": len(rows),
        "status_counts": status_counts,
        "priority_counts": priority_counts,
        "source_counts": source_counts,
    }


def requirement_integrity_error_response(exc: IntegrityError) -> Success:
    message = str(exc)
    if "code" in message.lower():
        return Success(msg="需求编号已存在，请换一个编号", code=400)
    return Success(msg=f"需求保存失败：{message}", code=400)


@router.get("/list", summary="查看需求列表")
async def list_requirements(
    page: int = Query(1, description="页码"),
    page_size: int = Query(100, description="每页数量"),
    keyword: str = Query("", description="标题、编号、客户、项目、负责人"),
    customer_id: int | None = Query(None, description="客户ID"),
    project_id: int | None = Query(None, description="项目ID"),
    status: str = Query("", description="需求状态"),
    priority: str = Query("", description="优先级"),
    source: str = Query("", description="来源"),
    owner: str = Query("", description="负责人"),
    service_type: str = Query("", description="IDC服务类型"),
    region: str = Query("", description="区域"),
):
    q = Q()
    if keyword:
        q &= (
            Q(title__contains=keyword)
            | Q(code__contains=keyword)
            | Q(owner__contains=keyword)
            | Q(requester__contains=keyword)
            | Q(source_detail__contains=keyword)
            | Q(service_type__contains=keyword)
            | Q(a_end__contains=keyword)
            | Q(z_end__contains=keyword)
            | Q(region__contains=keyword)
            | Q(datacenter__contains=keyword)
            | Q(bandwidth__contains=keyword)
            | Q(competitor__contains=keyword)
            | Q(next_action__contains=keyword)
            | Q(description__contains=keyword)
        )
    if customer_id:
        q &= Q(customer_id=customer_id)
    if project_id:
        q &= Q(project_id=project_id)
    if status:
        q &= Q(status=status)
    if priority:
        q &= Q(priority=priority)
    if source:
        q &= Q(source=source)
    if owner:
        q &= Q(owner__contains=owner)
    if service_type:
        q &= Q(service_type__contains=service_type)
    if region:
        q &= Q(region__contains=region)

    total = await CustomerRequirement.filter(q).count()
    rows = (
        await CustomerRequirement.filter(q)
        .order_by("sort_order", "-priority", "-updated_at")
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    data = [await serialize_requirement(row) for row in rows]
    summary = build_requirement_summary(data)
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size, summary=summary)


@router.get("/get", summary="查看需求详情")
async def get_requirement(requirement_id: int = Query(..., description="需求ID")):
    requirement = await CustomerRequirement.get(id=requirement_id)
    return Success(data=await serialize_requirement(requirement))


@router.post("/create", summary="创建需求")
async def create_requirement(requirement_in: CustomerRequirementCreate):
    payload = normalize_requirement_payload(requirement_in.model_dump())
    payload["code"] = await generate_requirement_code(payload.get("customer_id"))
    try:
        requirement = await CustomerRequirement.create(**payload)
    except IntegrityError as exc:
        return requirement_integrity_error_response(exc)
    except Exception as exc:
        logger.exception("requirement create failed")
        return Success(msg=f"需求创建失败：{exc}", code=500)
    return Success(msg="Created Successfully", data=await serialize_requirement(requirement))


@router.post("/update", summary="更新需求")
async def update_requirement(requirement_in: CustomerRequirementUpdate):
    payload = normalize_requirement_payload(requirement_in.model_dump(exclude_unset=True, exclude={"id"}))
    payload.pop("code", None)
    payload["updated_at"] = datetime.now()
    try:
        await CustomerRequirement.filter(id=requirement_in.id).update(**payload)
        requirement = await CustomerRequirement.get(id=requirement_in.id)
    except IntegrityError as exc:
        return requirement_integrity_error_response(exc)
    except Exception as exc:
        logger.exception("requirement update failed: requirement_id=%s", requirement_in.id)
        return Success(msg=f"需求更新失败：{exc}", code=500)
    return Success(msg="Updated Successfully", data=await serialize_requirement(requirement))


@router.post("/status", summary="更新需求状态")
async def update_requirement_status(requirement_in: CustomerRequirementStatusUpdate):
    await CustomerRequirement.filter(id=requirement_in.id).update(
        status=requirement_in.status,
        sort_order=requirement_in.sort_order,
        updated_at=datetime.now(),
    )
    requirement = await CustomerRequirement.get(id=requirement_in.id)
    return Success(msg="Updated Successfully", data=await serialize_requirement(requirement))


@router.delete("/delete", summary="删除需求")
async def delete_requirement(requirement_id: int = Query(..., description="需求ID")):
    requirement = await CustomerRequirement.get(id=requirement_id)
    await requirement.delete()
    return Success(msg="Deleted Successfully")


@router.post("/feishu/sync", summary="同步飞书多维表需求记录")
async def sync_feishu_requirements(payload: FeishuRequirementSyncPayload):
    parsed = parse_feishu_bitable_url(payload.url)
    app_token = clean(payload.app_token) or parsed["app_token"]
    table_id = clean(payload.table_id) or parsed["table_id"]
    view_id = clean(payload.view_id) or parsed["view_id"]
    if not app_token or not table_id:
        return Success(msg="请填写飞书多维表链接，或提供 app_token/table_id", code=400)

    try:
        records = await fetch_feishu_bitable_records(app_token, table_id, view_id)
    except Exception as exc:
        logger.exception("requirement feishu fetch failed")
        return Success(msg=str(exc), code=502)

    prepared_rows = []
    skipped = []
    for record in records:
        record_id = clean(record.get("record_id"))
        try:
            requirement_data = await feishu_record_to_requirement_payload(
                record,
                create_missing_customers=payload.create_missing_customers,
            )
        except Exception as exc:
            logger.exception("requirement feishu record parse failed: record_id=%s", record_id)
            skipped.append({"record_id": record_id, "reason": f"parse_failed:{exc}"})
            continue

        if not requirement_data.get("title"):
            skipped.append({"record_id": record_id, "reason": "title_empty"})
            continue

        prepared_rows.append(
            {
                "record_id": record_id,
                "data": requirement_data,
            }
        )

    code_counts = Counter(clean(row["data"].get("code")) for row in prepared_rows if clean(row["data"].get("code")))
    previews = []
    created = []
    updated = []
    for row in prepared_rows:
        record_id = row["record_id"]
        requirement_data = row["data"]
        requirement_data["code"] = unique_feishu_requirement_code(
            requirement_data.get("code"),
            record_id,
            code_counts,
        )
        preview = {
            "record_id": record_id,
            "title": requirement_data.get("title"),
            "code": requirement_data.get("code"),
            "status": requirement_data.get("status"),
            "priority": requirement_data.get("priority"),
            "owner": requirement_data.get("owner"),
        }
        if payload.dry_run:
            previews.append(preview)
            continue

        try:
            existing = None
            if payload.update_existing and record_id:
                existing = await CustomerRequirement.filter(source_record_id=record_id).first()
            if not existing and payload.update_existing and requirement_data.get("code"):
                existing_by_code = await CustomerRequirement.filter(code=requirement_data["code"]).all()
                if len(existing_by_code) == 1 and not clean(existing_by_code[0].source_record_id):
                    existing = existing_by_code[0]

            if existing:
                requirement_data["updated_at"] = datetime.now()
                await CustomerRequirement.filter(id=existing.id).update(**requirement_data)
                updated.append({**preview, "id": existing.id})
            else:
                try:
                    requirement = await CustomerRequirement.create(**requirement_data)
                except IntegrityError:
                    fallback_code = f"FS-{record_id[-10:]}" if record_id else None
                    if not fallback_code or requirement_data.get("code") == fallback_code:
                        raise
                    requirement_data["code"] = fallback_code
                    preview["code"] = fallback_code
                    requirement = await CustomerRequirement.create(**requirement_data)
                created.append({**preview, "id": requirement.id})
        except IntegrityError as exc:
            skipped.append({"record_id": record_id, "reason": f"integrity_error:{exc}"})
        except Exception as exc:
            logger.exception("requirement feishu save failed: record_id=%s", record_id)
            skipped.append({"record_id": record_id, "reason": f"save_failed:{exc}"})

    return Success(
        data={
            "total": len(records),
            "previews": previews,
            "created": created,
            "updated": updated,
            "skipped": skipped,
        }
    )
