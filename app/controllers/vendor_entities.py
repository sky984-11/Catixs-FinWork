from fastapi import HTTPException

from app.models.company import Company
from app.models.customer_center import CrmSigningEntity


def normalized(value):
    return "".join(str(value or "").lower().split())


def match_entity(source, candidates):
    """Only reconcile unique identities; IDs belong to different tables."""
    for field in ("registration_no", "tax_no"):
        value = normalized(getattr(source, field, None))
        matches = [item for item in candidates if value and normalized(getattr(item, field, None)) == value]
        if matches:
            return matches[0] if len(matches) == 1 else None
    names = {normalized(source.name), normalized(source.legal_name)} - {""}
    matches = [item for item in candidates if names & ({normalized(item.name), normalized(item.legal_name)} - {""})]
    if matches:
        return matches[0] if len(matches) == 1 else None
    # These are the three existing seed identities, not arbitrary name-prefix guesses.
    aliases = {"u": "catixs-ltd", "h": "77-telecom-ltd", "c": "catixs-cn"}
    code = normalized(source.code)
    code = aliases.get(code, code)
    matches = [
        item for item in candidates if code and aliases.get(normalized(item.code), normalized(item.code)) == code
    ]
    return matches[0] if len(matches) == 1 else None


async def entity_context():
    return await CrmSigningEntity.all(), await Company.filter(role=0)


def entity_fields(vendor, entities, companies):
    legacy = next((item for item in companies if item.id == vendor.contract_company_id), None)
    entity = next((item for item in entities if item.id == vendor.signing_entity_id), None)
    if entity is None and vendor.signing_entity_id is None and legacy:
        entity = match_entity(legacy, entities)
    return {
        "signing_entity_id": entity.id if entity else None,
        "signing_entity_name": entity.name if entity else (legacy.name if legacy else None),
        "legacy_signing_entity_unmatched": bool(legacy and entity is None),
    }


async def resolve_entity(data, current=None):
    if "signing_entity_id" not in data:
        # Old callers keep using internal-company IDs. Drop a stale CRM link if they change that ID.
        if current and "contract_company_id" in data and data["contract_company_id"] != current.contract_company_id:
            data["signing_entity_id"] = None
        return
    entity_id = data["signing_entity_id"]
    if entity_id is None:
        data["contract_company_id"] = None
        return
    entity = await CrmSigningEntity.get_or_none(id=entity_id)
    if entity is None:
        raise HTTPException(400, "签约主体不存在，请从客户管理签约主体中选择")
    if not entity.status and (current is None or current.signing_entity_id != entity.id):
        raise HTTPException(400, "签约主体已停用")
    companies = await Company.filter(role=0)
    legacy = match_entity(entity, companies)
    # Preserve an existing valid legacy link even when the internal table contains duplicates.
    if current and current.contract_company_id:
        existing = next((item for item in companies if item.id == current.contract_company_id), None)
        if existing and match_entity(existing, [entity]):
            legacy = existing
    data["contract_company_id"] = legacy.id if legacy else None
