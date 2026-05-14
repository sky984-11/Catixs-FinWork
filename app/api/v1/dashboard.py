from datetime import datetime, timedelta

from fastapi import APIRouter
from tortoise.expressions import Q

from app.api.v1.tickets.tickets import can_view_all_tickets, get_current_ticket_user
from app.core.dependency import DependAuth
from app.models.ticket import Ticket
from app.schemas.base import Success

router = APIRouter()


@router.get("/dashboard", summary="工单仪表盘", dependencies=[DependAuth])
async def ticket_dashboard():
    current_user = await get_current_ticket_user()
    scope_q = Q()
    if not await can_view_all_tickets(current_user):
        scope_q &= Q(user_id=current_user.id)

    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    risk_deadline = now - timedelta(hours=24)

    status_values = [0, 1, 2, 3]
    type_values = [0, 1, 2]
    active_status_q = Q(status__in=[1, 2])

    total = await Ticket.filter(scope_q).count()
    status_counts = {
        str(status): await Ticket.filter(scope_q & Q(status=status)).count()
        for status in status_values
    }
    type_counts = {
        str(ticket_type): await Ticket.filter(scope_q & Q(type=ticket_type)).count()
        for ticket_type in type_values
    }
    active_type_counts = {
        str(ticket_type): await Ticket.filter(scope_q & active_status_q & Q(type=ticket_type)).count()
        for ticket_type in type_values
    }
    today_created = await Ticket.filter(scope_q & Q(created_at__gte=today_start)).count()
    risk_count = await Ticket.filter(
        scope_q & active_status_q & Q(created_at__lte=risk_deadline)
    ).count()
    recent_objs = await Ticket.filter(scope_q).order_by("-created_at").limit(8)
    waiting_objs = await Ticket.filter(scope_q & active_status_q).order_by("created_at").limit(6)

    return Success(
        data={
            "total": total,
            "status_counts": status_counts,
            "type_counts": type_counts,
            "active_type_counts": active_type_counts,
            "today_created": today_created,
            "risk_count": risk_count,
            "recent_tickets": [await obj.to_dict() for obj in recent_objs],
            "waiting_tickets": [await obj.to_dict() for obj in waiting_objs],
        }
    )
