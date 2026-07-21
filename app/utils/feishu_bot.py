"""
飞书机器人通知工具模块
用于发送工单相关通知到飞书群组
"""

import json
import logging
from datetime import datetime
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# 飞书机器人Webhook地址
FEISHU_WEBHOOK_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/5e4f6911-411c-4802-b2be-60597e46eb46"

# 工单类型映射
TICKET_TYPE_MAP = {
    0: "故障工单(INC)",
    1: "服务请求工单(REQ)",
    2: "维护工单(MTN)",
    3: "维护工单(MTN)",
}

# 工单状态映射
TICKET_STATUS_MAP = {
    0: "已完成",
    1: "进行中",
    2: "未开始",
    3: "已关闭",
}


async def send_feishu_message(content: dict, webhook_url: str | None = None) -> bool:
    """
    发送飞书机器人消息
    
    Args:
        content: 消息内容字典
        webhook_url: 飞书机器人 Webhook，不传则使用默认工单机器人
        
    Returns:
        bool: 是否发送成功
    """
    try:
        target_webhook_url = webhook_url or FEISHU_WEBHOOK_URL
        if not target_webhook_url:
            logger.warning("飞书消息未发送：Webhook 地址为空")
            return False

        async with httpx.AsyncClient() as client:
            response = await client.post(
                target_webhook_url,
                json=content,
                timeout=10.0
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("code") == 0:
                    logger.info("飞书消息发送成功")
                    return True
                else:
                    logger.error(f"飞书消息发送失败: {result}")
                    return False
            else:
                logger.error(f"飞书消息发送失败，状态码: {response.status_code}")
                return False
                
    except Exception as e:
        logger.error(f"飞书消息发送异常: {e}")
        return False


async def send_project_task_due_notification(
    *,
    webhook_url: str,
    stage: str,
    project_name: str,
    task_title: str,
    due_date: str,
    assignee: str | None = None,
    customer_name: str | None = None,
    project_code: str | None = None,
    remark: str | None = None,
) -> bool:
    stage_label = "即将到期" if stage == "due_soon" else "已到期"
    template = "orange" if stage == "due_soon" else "red"
    fields = [
        ("项目", project_name),
        ("子任务", task_title),
        ("ETA", due_date),
        ("负责人", assignee or "未设置"),
    ]
    if customer_name:
        fields.append(("客户", customer_name))
    if project_code:
        fields.append(("项目编号", project_code))
    if remark:
        fields.append(("备注", remark))

    card_content = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"项目子任务{stage_label}提醒",
                },
                "template": template,
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": "\n".join(f"**{label}：** {value}" for label, value in fields),
                    },
                },
            ],
        },
    }
    return await send_feishu_message(card_content, webhook_url=webhook_url)


async def send_project_daily_summary_notification(
    *,
    webhook_url: str,
    summary_date: str,
    sections: list[dict],
    mention_text: str = "",
) -> bool:
    elements = []
    if mention_text:
        elements.append(
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**负责人：** {mention_text}",
                },
            }
        )

    total_projects = sum(int(section.get("count") or 0) for section in sections)
    total_tasks = sum(int(section.get("open_task_count") or 0) for section in sections)
    elements.append(
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**项目数：** {total_projects}    **未完成子任务：** {total_tasks}",
            },
        }
    )

    for section in sections:
        elements.append({"tag": "hr"})
        elements.append(
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": (
                        f"**{section.get('label')}** "
                        f"({section.get('count', 0)} 个项目 / {section.get('open_task_count', 0)} 个未完成子任务)"
                    ),
                },
            }
        )
        projects = section.get("projects") or []
        if not projects:
            elements.append(
                {
                    "tag": "note",
                    "elements": [{"tag": "plain_text", "content": "暂无项目"}],
                }
            )
            continue

        content_lines = []
        for project in projects[:8]:
            owners = project.get("owners") or "未设置负责人"
            due_date = project.get("due_date") or "无截止日期"
            progress = project.get("progress", 0)
            task_titles = project.get("task_titles") or []
            task_text = "；".join(task_titles[:3]) if task_titles else "暂无未完成子任务"
            if len(task_titles) > 3:
                task_text += f"；另有 {len(task_titles) - 3} 项"
            content_lines.append(
                f"- **{project.get('name')}** ｜{progress}%｜{owners}｜ETA {due_date}\n  子任务：{task_text}"
            )
        if len(projects) > 8:
            content_lines.append(f"- 还有 {len(projects) - 8} 个项目未展示")

        elements.append(
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "\n".join(content_lines),
                },
            }
        )

    card_content = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"项目看板每日总结 - {summary_date}",
                },
                "template": "blue",
            },
            "elements": elements,
        },
    }
    return await send_feishu_message(card_content, webhook_url=webhook_url)


async def send_project_daily_summary_card(
    *,
    webhook_url: str,
    summary_date: str,
    sections: list[dict],
    mention_text: str = "",
) -> bool:
    elements = []
    if mention_text:
        elements.append(
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"**负责人：** {mention_text}"},
            }
        )

    total_projects = sum(int(section.get("count") or 0) for section in sections)
    total_tasks = sum(int(section.get("open_task_count") or 0) for section in sections)
    elements.append(
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**项目数：** {total_projects}    **未完成子任务：** {total_tasks}",
            },
        }
    )

    for section in sections:
        elements.append({"tag": "hr"})
        elements.append(
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": (
                        f"**{section.get('label')}** "
                        f"({section.get('count', 0)} 个项目 / {section.get('open_task_count', 0)} 个未完成子任务)"
                    ),
                },
            }
        )
        projects = section.get("projects") or []
        if not projects:
            elements.append({"tag": "note", "elements": [{"tag": "plain_text", "content": "暂无项目"}]})
            continue

        content_lines = []
        for project in projects[:8]:
            project_name = markdown_link(project.get("name"), project.get("url"))
            owners = project.get("owners") or "未设置负责人"
            due_date = project.get("due_date") or "无截止日期"
            progress = project.get("progress", 0)
            tasks = project.get("tasks") or []
            task_parts = []
            for task in tasks[:3]:
                task_title = markdown_link(task.get("title"), task.get("url"))
                task_due = task.get("due_date") or "未设置"
                task_parts.append(f"{task_title}（ETA {task_due}）")
            task_text = "；".join(task_parts) if task_parts else "暂无未完成子任务"
            if len(tasks) > 3:
                task_text += f"；另有 {len(tasks) - 3} 项"
            content_lines.append(f"- **{project_name}** ｜{progress}%｜{owners}｜ETA {due_date}\n  子任务：{task_text}")
        if len(projects) > 8:
            content_lines.append(f"- 还有 {len(projects) - 8} 个项目未展示")

        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "\n".join(content_lines)}})

    card_content = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": f"项目看板每日总结 - {summary_date}"},
                "template": "blue",
            },
            "elements": elements,
        },
    }
    return await send_feishu_message(card_content, webhook_url=webhook_url)


def markdown_link(text: str | None, url: str | None) -> str:
    label = str(text or "-").replace("[", "［").replace("]", "］")
    link = str(url or "").strip()
    return f"[{label}]({link})" if link else label


async def send_ticket_created_notification(
    ticket_no: str,
    title: str,
    ticket_type: int,
    status: int,
    creator_name: str,
    description: str,
    created_at: datetime,
    location: Optional[str] = None,
    ticket_url: Optional[str] = None,
) -> bool:
    """
    发送工单创建通知
    
    Args:
        ticket_no: 工单编号
        title: 工单标题
        ticket_type: 工单类型
        status: 工单状态
        creator_name: 创建人姓名
        description: 工单描述
        created_at: 创建时间
        location: 发生地点（可选）
        ticket_url: 工单详情链接（可选）
        
    Returns:
        bool: 是否发送成功
    """
    type_name = TICKET_TYPE_MAP.get(ticket_type, "未知类型")
    status_name = TICKET_STATUS_MAP.get(status, "未知状态")
    
    # 构建卡片消息
    card_content = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"🎫 新工单提醒 - {ticket_no}"
                },
                "template": "blue"
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**工单标题：** {title}"
                    }
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**工单类型：** {type_name}"
                    }
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**当前状态：** {status_name}"
                    }
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**创建人：** {creator_name}"
                    }
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**创建时间：** {created_at.strftime('%Y-%m-%d %H:%M')}"
                    }
                }
            ]
        }
    }
    
    # 添加地点信息（如果有）
    if location:
        card_content["card"]["elements"].append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**发生地点：** {location}"
            }
        })
    
    # 添加描述信息
    # 截断过长的描述
    desc_display = description[:200] + "..." if len(description) > 200 else description
    card_content["card"]["elements"].append({
        "tag": "div",
        "text": {
            "tag": "lark_md",
            "content": f"**工单描述：**\n{desc_display}"
        }
    })

    if ticket_url:
        card_content["card"]["elements"].append({
            "tag": "action",
            "actions": [
                {
                    "tag": "button",
                    "text": {
                        "tag": "plain_text",
                        "content": "查看工单详情"
                    },
                    "type": "primary",
                    "url": ticket_url
                }
            ]
        })
    
    # 添加分隔线
    card_content["card"]["elements"].append({
        "tag": "hr"
    })
    
    # 添加提示信息
    card_content["card"]["elements"].append({
        "tag": "note",
        "elements": [
            {
                "tag": "plain_text",
                "content": "💡 请管理员及时处理该工单"
            }
        ]
    })
    
    return await send_feishu_message(card_content)


async def send_ticket_status_changed_notification(
    ticket_no: str,
    title: str,
    ticket_type: int,
    old_status: int,
    new_status: int,
    operator_name: str,
    completion_note: Optional[str] = None,
) -> bool:
    """
    发送工单状态变更通知
    
    Args:
        ticket_no: 工单编号
        title: 工单标题
        ticket_type: 工单类型
        old_status: 原状态
        new_status: 新状态
        operator_name: 操作人姓名
        
    Returns:
        bool: 是否发送成功
    """
    type_name = TICKET_TYPE_MAP.get(ticket_type, "未知类型")
    old_status_name = TICKET_STATUS_MAP.get(old_status, "未知状态")
    new_status_name = TICKET_STATUS_MAP.get(new_status, "未知状态")
    
    # 根据状态设置不同的模板颜色
    template_color = "blue"
    if new_status == 0:  # 已完成
        template_color = "green"
    elif new_status == 3:  # 已关闭
        template_color = "grey"
    elif new_status == 1:  # 进行中
        template_color = "orange"
    
    card_content = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"🔄 工单状态变更 - {ticket_no}"
                },
                "template": template_color
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**工单标题：** {title}"
                    }
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**工单类型：** {type_name}"
                    }
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**状态变更：** {old_status_name} → **{new_status_name}**"
                    }
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**操作人：** {operator_name}"
                    }
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**变更时间：** {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                    }
                }
            ]
        }
    }
    if completion_note:
        note_display = completion_note[:300] + "..." if len(completion_note) > 300 else completion_note
        card_content["card"]["elements"].append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**完成回复/备注：**\n{note_display}"
            }
        })

    return await send_feishu_message(card_content)


async def send_ticket_reply_notification(
    ticket_no: str,
    title: str,
    ticket_type: int,
    replier_name: str,
    content: str,
    reply_to_user_name: Optional[str] = None,
    parent_content: Optional[str] = None,
    ticket_url: Optional[str] = None,
) -> bool:
    type_name = TICKET_TYPE_MAP.get(ticket_type, "未知类型")
    content_display = content[:500] + "..." if len(content) > 500 else content
    card_content = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"工单回复 - {ticket_no}"
                },
                "template": "blue"
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**工单标题：** {title}"
                    }
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**工单类型：** {type_name}"
                    }
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**回复人：** {replier_name}"
                    }
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**回复内容：**\n{content_display}"
                    }
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**回复时间：** {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                    }
                },
            ]
        }
    }
    if reply_to_user_name:
        parent_display = (parent_content or "")[:200]
        card_content["card"]["elements"].insert(3, {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**回复对象：** {reply_to_user_name}\n**原内容：** {parent_display}"
            }
        })
    if ticket_url:
        card_content["card"]["elements"].append({
            "tag": "action",
            "actions": [
                {
                    "tag": "button",
                    "text": {
                        "tag": "plain_text",
                        "content": "查看工单详情"
                    },
                    "type": "primary",
                    "url": ticket_url
                }
            ]
        })
    return await send_feishu_message(card_content)
