from datetime import datetime
from tortoise.expressions import Q

from app.core.crud import CRUDBase
from app.models.ticket import Ticket
from app.schemas.tickets import TicketCreate, TicketUpdate


def get_ticket_type_prefix(ticket_type: int) -> str:
    """获取工单类型前缀"""
    type_map = {
        0: "INC",  # 故障工单
        1: "REQ",  # 服务请求工单
        2: "CHG",  # 变更工单
        3: "MTN",  # 维护工单
    }
    return type_map.get(ticket_type, "INC")


async def generate_ticket_no(ticket_type: int) -> str:
    """生成工单编号，格式: {类型前缀}-{日期}-{序号}"""
    prefix = get_ticket_type_prefix(ticket_type)
    today = datetime.now().strftime("%Y%m%d")
    
    # 统计当天同类型工单数量
    count = await Ticket.filter(
        ticket_no__startswith=f"{prefix}-{today}"
    ).count()
    
    # 新编号 = 当前数量 + 1
    new_num = count + 1
    
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
        
        # 自动生成工单编号
        ticket_type = data.get("type", 0)
        data["ticket_no"] = await generate_ticket_no(ticket_type)
        
        # 新建工单强制设置为未开始状态
        # 状态说明：0-已完成, 1-进行中, 2-未开始, 3-已关闭
        # 已完成和已关闭状态只能通过管理员手动修改
        data["status"] = 2
        
        return await self.create(data)

    async def update_ticket(self, id: int, obj_in: TicketUpdate) -> Ticket:
        """更新工单"""
        data = obj_in.model_dump(exclude_unset=True, exclude={"id"})
        return await self.update(id=id, obj_in=data)
    
    async def get_ticket_by_no(self, ticket_no: str) -> Ticket:
        """根据工单编号获取工单"""
        return await Ticket.get_or_none(ticket_no=ticket_no)


ticket_controller = TicketController()
