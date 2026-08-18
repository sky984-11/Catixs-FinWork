import json
import re
from typing import Any, Literal

import httpx
from fastapi import APIRouter
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from tortoise import Tortoise

from app.core.dependency import DependAuth
from app.log import logger
from app.models import User
from app.schemas import Fail, Success
from app.settings import settings

router = APIRouter()

FORBIDDEN_SQL_PATTERN = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|create|grant|revoke|copy|call|execute|do|vacuum|analyze|refresh|lock|set|reset)\b",
    re.IGNORECASE,
)
LIMIT_PATTERN = re.compile(r"\blimit\s+\d+\b", re.IGNORECASE)
TABLE_REF_PATTERN = re.compile(r"\b(?:from|join)\s+([a-zA-Z_][\w.]*)", re.IGNORECASE)


class FwAssistantMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)


class FwAssistantChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    model: str | None = None
    messages: list[FwAssistantMessage] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)


def _clean_text(value: str, limit: int = 8000) -> str:
    return str(value or "").strip()[:limit]


async def _current_user_context(current_user: User) -> dict[str, Any]:
    roles = await current_user.roles
    return jsonable_encoder(
        {
            "id": current_user.id,
            "username": current_user.username,
            "alias": current_user.alias,
            "email": current_user.email,
            "phone": current_user.phone,
            "is_superuser": current_user.is_superuser,
            "dept_id": current_user.dept_id,
            "roles": [{"id": role.id, "name": role.name, "desc": role.desc} for role in roles],
            "feishu_open_id": current_user.feishu_open_id,
            "feishu_union_id": current_user.feishu_union_id,
            "feishu_user_id": current_user.feishu_user_id,
        }
    )


def _request_context(chat_in: FwAssistantChatIn, current_user_context: dict[str, Any]) -> dict[str, Any]:
    return jsonable_encoder({**(chat_in.context or {}), "current_user": current_user_context})


def _schema_text() -> tuple[str, set[str]]:
    lines: list[str] = []
    allowed_tables: set[str] = set()
    models = Tortoise.apps.get("models", {})
    for model_name in sorted(models):
        model = models[model_name]
        table = model._meta.db_table
        if not table:
            continue
        allowed_tables.add(table)
        columns: list[str] = []
        for field_name, field in model._meta.fields_map.items():
            if field_name in model._meta.backward_fk_fields or field_name in model._meta.backward_o2o_fields:
                continue
            source_field = getattr(field, "source_field", None) or field_name
            description = getattr(field, "description", None) or ""
            field_type = type(field).__name__.replace("Field", "")
            columns.append(f"{source_field}({field_type}{f': {description}' if description else ''})")
        lines.append(f"- {table}: {', '.join(columns)}")
    return "\n".join(lines), allowed_tables


async def _call_ai(
    api_base: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
) -> dict:
    timeout = settings.FW_ASSISTANT_TIMEOUT or settings.DEEPSEEK_TIMEOUT
    async with httpx.AsyncClient(timeout=timeout, trust_env=True) as client:
        response = await client.post(
            f"{api_base}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "stream": False,
            },
        )
    data = response.json()
    if not isinstance(data, dict):
        data = {}
    if response.status_code >= 400:
        error = data.get("error") or {}
        error_message = error.get("message") if isinstance(error, dict) else str(error)
        raise RuntimeError(error_message or data.get("message") or "AI 调用失败")
    return data


def _first_choice_content(data: dict) -> str:
    choices = data.get("choices") or []
    if not choices:
        return ""
    return _clean_text(((choices[0] or {}).get("message") or {}).get("content") or "", 12000)


def _extract_json_object(content: str) -> dict:
    text = _clean_text(content, 12000)
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"\s*```$", "", text).strip()
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return {}
        try:
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}


def _normalize_sql(sql: str, allowed_tables: set[str]) -> str:
    cleaned = _clean_text(sql, 12000).rstrip(";").strip()
    lowered = cleaned.lower()
    if not (lowered.startswith("select ") or lowered.startswith("with ")):
        raise ValueError("只允许执行 SELECT/WITH 只读查询")
    if ";" in cleaned or "--" in cleaned or "/*" in cleaned or "*/" in cleaned:
        raise ValueError("SQL 中不允许包含多语句或注释")
    if FORBIDDEN_SQL_PATTERN.search(cleaned):
        raise ValueError("SQL 中包含非只读关键字")
    referenced_tables = {item.split(".")[-1].strip('"') for item in TABLE_REF_PATTERN.findall(cleaned)}
    unknown_tables = referenced_tables - allowed_tables
    if unknown_tables:
        raise ValueError(f"SQL 引用了未开放的表：{', '.join(sorted(unknown_tables))}")
    if not LIMIT_PATTERN.search(cleaned):
        limit = max(1, min(settings.FW_ASSISTANT_DB_QUERY_LIMIT, 100))
        cleaned = f"{cleaned} LIMIT {limit}"
    return cleaned


async def _plan_db_query(
    api_base: str,
    api_key: str,
    model: str,
    chat_in: FwAssistantChatIn,
    current_user_context: dict[str, Any],
) -> tuple[str, str] | None:
    schema, _ = _schema_text()
    if not schema:
        return None
    limit = max(1, min(settings.FW_ASSISTANT_DB_QUERY_LIMIT, 100))
    planner_prompt = (
        "你是 FinWork 只读 SQL 规划器。"
        "根据用户问题和数据库表结构生成一条 PostgreSQL SELECT 查询。"
        "只能查询给定表和字段，不能写入、修改、删除、创建、授权、调用函数或访问系统表。"
        f"查询结果最多 {limit} 行。"
        "如果问题不需要数据库或条件不足，返回 sql 为 null。"
        "只返回 JSON：{\"sql\":\"...\" 或 null,\"reason\":\"...\"}。"
        "\n\nFinWork 表结构：\n"
        + schema[:18000]
    )
    planner_prompt += (
        "\n\nCurrent user rule: every query must consider current_user context. "
        "When the user asks about my work, my projects, my tickets, assigned to me, "
        "or user-related data, filter with current_user.id, username, alias, email, or roles where the schema supports it."
    )
    history = "\n".join(f"{item.role}: {item.content}" for item in chat_in.messages[-6:])
    user_prompt = (
        f"当前页面上下文：{json.dumps(chat_in.context, ensure_ascii=False, default=str)}\n"
        f"历史对话：\n{history}\n\n"
        f"用户问题：{chat_in.message}"
    )
    data = await _call_ai(
        api_base,
        api_key,
        model,
        [{"role": "system", "content": planner_prompt}, {"role": "user", "content": user_prompt}],
        0,
    )
    parsed = _extract_json_object(_first_choice_content(data))
    sql = parsed.get("sql")
    if not sql:
        return None
    return str(sql), _clean_text(str(parsed.get("reason") or ""), 500)


async def _query_finwork_db(
    api_base: str,
    api_key: str,
    model: str,
    chat_in: FwAssistantChatIn,
    current_user_context: dict[str, Any],
) -> dict[str, Any]:
    if not settings.FW_ASSISTANT_DB_QUERY_ENABLED:
        return {"enabled": False, "reason": "数据库查询未启用", "rows": []}
    schema, allowed_tables = _schema_text()
    if not schema or not allowed_tables:
        return {"enabled": True, "reason": "未读取到 FinWork 表结构", "rows": []}
    plan = await _plan_db_query(api_base, api_key, model, chat_in, current_user_context)
    if not plan:
        return {"enabled": True, "reason": "本轮问题未生成数据库查询", "rows": []}
    planned_sql, reason = plan
    sql = _normalize_sql(planned_sql, allowed_tables)
    conn = Tortoise.get_connection(settings.DB_TYPE)
    rows = jsonable_encoder(await conn.execute_query_dict(sql))
    return {
        "enabled": True,
        "reason": reason,
        "sql": sql,
        "row_count": len(rows),
        "rows": rows[: max(1, min(settings.FW_ASSISTANT_DB_QUERY_LIMIT, 100))],
    }


def _build_answer_messages(
    chat_in: FwAssistantChatIn,
    db_context: dict[str, Any],
    current_user_context: dict[str, Any],
) -> list[dict[str, str]]:
    system_prompt = (
        "你是 FinWork 的网页小助手，使用中文回答。"
        "回答必须优先基于后端刚刚从 FinWork 数据库查询到的实时数据。"
        "不要编造数据库中没有出现的客户、项目、工单、账单、资产或报价。"
        "如果查询结果不足以回答，就明确说明缺少哪些条件或数据。"
        "回答要简洁、可执行；涉及列表、统计、风险和待办时，用清晰的条目呈现。"
    )
    page_title = _clean_text(str(chat_in.context.get("title") or ""), 120)
    page_path = _clean_text(str(chat_in.context.get("path") or ""), 160)
    system_prompt += "\nCurrent login user:\n" + json.dumps(
        current_user_context,
        ensure_ascii=False,
        default=str,
    )[:4000]
    if page_title or page_path:
        system_prompt += f"\n当前页面：{page_title or '未知'} {page_path}".strip()
    system_prompt += "\nFinWork 数据库查询上下文：\n" + json.dumps(
        db_context,
        ensure_ascii=False,
        default=str,
    )[:16000]

    cleaned: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    for item in chat_in.messages[-12:]:
        content = _clean_text(item.content)
        if content:
            cleaned.append({"role": item.role, "content": content})
    current_message = _clean_text(chat_in.message)
    if current_message and (not cleaned or cleaned[-1].get("content") != current_message):
        cleaned.append({"role": "user", "content": current_message})
    return cleaned


@router.post("/chat", summary="FW assistant chat")
async def chat(chat_in: FwAssistantChatIn, current_user: User = DependAuth):
    api_key = str(settings.FW_ASSISTANT_API_KEY or settings.DEEPSEEK_API_KEY or "").strip()
    if not api_key:
        return Fail(code=503, msg="小助手 AI key 未配置，请先在后端 .env 中配置 FW_ASSISTANT_API_KEY")

    api_base = str(
        settings.FW_ASSISTANT_API_BASE or settings.DEEPSEEK_API_BASE or "https://api.siliconflow.cn/v1"
    ).strip().rstrip("/")
    model = str(chat_in.model or settings.FW_ASSISTANT_MODEL or settings.DEEPSEEK_MODEL or "deepseek-ai/DeepSeek-V3").strip()

    try:
        current_user_context = await _current_user_context(current_user)
        chat_in.context = _request_context(chat_in, current_user_context)
        db_context = await _query_finwork_db(api_base, api_key, model, chat_in, current_user_context)
        data = await _call_ai(
            api_base,
            api_key,
            model,
            _build_answer_messages(chat_in, db_context, current_user_context),
            0.3,
        )
    except httpx.RequestError as exc:
        logger.warning("fw assistant ai request failed: %s", exc)
        return Fail(code=502, msg="AI 接口连接失败，请稍后重试")
    except RuntimeError as exc:
        logger.warning("fw assistant ai rejected: %s", exc)
        return Fail(code=502, msg=str(exc))
    except ValueError as exc:
        logger.warning("fw assistant query rejected: %s", exc)
        return Fail(code=400, msg=str(exc))
    except Exception as exc:
        logger.exception("fw assistant chat failed")
        return Fail(code=500, msg=str(exc))

    content = _first_choice_content(data)
    if not content:
        return Fail(code=502, msg="AI 未返回有效内容")

    return Success(data=jsonable_encoder({"content": content, "model": model, "db": db_context}))
