from datetime import datetime
from tortoise.expressions import Q
from tortoise.exceptions import IntegrityError

from app.core.crud import CRUDBase
from app.models.ticket import Ticket
from app.schemas.tickets import TicketCreate, TicketUpdate


def get_ticket_type_prefix(ticket_type: int) -> str:
    """获取工单类型前缀"""
    type_map = {
        0: "INC",  # 故障工单
        1: "REQ",  # 服务请求工单
        2: "MTN",  # 维护工单
        3: "MTN",  # 历史维护工单兼容
    }
    return type_map.get(ticket_type, "INC")


async def generate_ticket_no(ticket_type: int, min_sequence: int = 1) -> str:
    """生成工单编号，格式: {类型前缀}-{日期}-{序号}"""
    prefix = get_ticket_type_prefix(ticket_type)
    today = datetime.now().strftime("%Y%m%d")

    ticket_nos = await Ticket.filter(ticket_no__startswith=f"{prefix}-{today}-").values_list("ticket_no", flat=True)
    latest_num = 0
    for ticket_no in ticket_nos:
        try:
            latest_num = max(latest_num, int(str(ticket_no).rsplit("-", 1)[-1]))
        except (TypeError, ValueError):
            continue
    new_num = max(latest_num + 1, min_sequence)

    return f"{prefix}-{today}-{new_num:04d}"


class TicketController(CRUDBase[Ticket, TicketCreate, TicketUpdate]):
    def __init__(self):
        super().__init__(model=Ticket)

    async def list_tickets(self, page: int, page_size: int, search: Q = Q(), order: list = [], user_id: int = None):
        """查询工单列表（支持按用户过滤）"""
        if user_id is not None:
            search &= Q(user_id=user_id)
        return await self.list(page=page, page_size=page_size, search=search, order=order)

    async def create_ticket(self, obj_in: TicketCreate) -> Ticket:
        """创建工单"""
        data = obj_in.model_dump()

        # 新建工单强制设置为未开始状态
        # 状态说明：0-已完成, 1-进行中, 2-未开始, 3-已关闭
        # 已完成和已关闭状态只能通过管理员手动修改
        data["status"] = 2

        ticket_type = data.get("type", 0)
        next_sequence = 1
        for _ in range(5):
            data["ticket_no"] = await generate_ticket_no(ticket_type, min_sequence=next_sequence)
            try:
                next_sequence = int(data["ticket_no"].rsplit("-", 1)[-1]) + 1
            except (TypeError, ValueError):
                next_sequence += 1
            try:
                return await self.create(data)
            except IntegrityError as exc:
                if "ticket_no" not in str(exc):
                    raise
        raise IntegrityError("生成工单编号失败，请重试")

    async def update_ticket(self, id: int, obj_in: TicketUpdate) -> Ticket:
        """更新工单"""
        data = obj_in.model_dump(exclude_unset=True, exclude={"id", "ticket_no"})
        return await self.update(id=id, obj_in=data)
    
    async def get_ticket_by_no(self, ticket_no: str) -> Ticket:
        """根据工单编号获取工单"""
        return await Ticket.get_or_none(ticket_no=ticket_no)


ticket_controller = TicketController()
