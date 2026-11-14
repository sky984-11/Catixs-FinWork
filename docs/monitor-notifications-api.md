# 事件通知管理

入口：事件管理 → 通知管理（`/events/notifications`）。平台管理员默认获得菜单和接口权限，其他角色按接口和菜单分别授权。通知配置为平台共享配置，修改权限应仅授予运维管理员。

## 行为与配置

- 默认关闭。选择 FinWork 的启用用户、通知分类、最低级别后保存并启用，后台约每分钟检查一次。仅使用平台纳管的主机及监控项范围。
- 用户身份按飞书 `open_id`、`user_id`、邮箱依次选用；用户须处于应用可见范围。接口不返回身份标识或邮箱。
- 分类为空表示所有平台分类；支持恢复通知、跳过抑制事件、AI 建议开关。
- 仅发现本次启用之后发生的事件，不补发此前旧告警；此前成功通知的未恢复事件继续跟踪恢复。首次发现时已恢复的短事件直接生成恢复通知。
- 每轮最多创建约 100 条待发记录、处理 10 条待发记录；大量告警会排队。沿用事件接口近 7 天、最多 2000 条的读取范围，达到上限显示警告；每轮额外跟踪 10 条此前发送成功的未恢复事件，轮转检查。
- 同一事件、通知阶段、接收人由数据库唯一约束去重。多进程用数据库租约互斥；发送前重新验证配置版本、纳管范围和接收用户状态。
- 失败/发送结果不确定时不自动重试，界面可人工确认后重试，最多 5 次。复用稳定飞书消息 UUID；飞书去重有时间窗口，因此超时后手动重试仍可能重复，不能保证外部发送绝对恰好一次。
- 飞书卡片区分告警与恢复颜色，包含级别、主机、地址、分类、发生/恢复时间、事件编号、Zabbix 事件链接和排查建议。持续时间仅在恢复通知中展示最终值，告警通知不展示此字段；卡片预览遵循同一规则。动态内容使用纯文本，避免告警名称中的标记被执行。
- AI 复用 `FW_ASSISTANT_API_BASE`、`FW_ASSISTANT_API_KEY`、`FW_ASSISTANT_MODEL`，发送告警摘要、相关主机/IP、当前指标值（不是故障发生时快照）；不携带用户身份、令牌，不开放工具或自动执行操作。20 秒超时或服务不可用时回退规则建议，并明确标记来源。建议需人工核实。
- 复用 `FEISHU_APP_ID`、`FEISHU_APP_SECRET` 配置，凭据仅在服务端使用。预览不发送飞书消息，但启用 AI 时会请求已配置的 AI 服务。

## API

前缀 `/api/v1/monitor-events/notifications`。全部接口使用现有登录 token 和 `DependPermission` 按 HTTP 方法/路由校验，返回标准 `{code, msg, data}`。

| 方法/路径 | 参数 | 响应 data |
| --- | --- | --- |
| GET 空路径 | 无 | 配置、`users:[{id,name,reachable}]`、`categories:[{key,label}]`、`feishu_configured`、`ai_configured` |
| PUT 空路径 | 下方 JSON | 保存后的配置及新 revision |
| POST `/preview` | `{ "event_id": "123" }`，省略或 null 使用示例 | `{card,advice,advice_source:"ai或rule",sample:boolean}` |
| GET `/deliveries` | page≥1，page_size=1..100 默认20，status 可选 pending/sending/sent/failed/skipped | `{total,rows:[{id,event_id,event_name,phase,user_id,user_name,status,attempts,message,advice,advice_source,sent_at,created_at}]}` |
| POST `/deliveries/{delivery_id}/retry` | 正整数 ID，无请求体 | 成功消息“已加入发送队列” |

PUT 示例（用户 ID、分类 key 使用 GET 返回值）：

```json
{
  "revision": 0,
  "enabled": true,
  "recipient_ids": [12],
  "category_keys": [],
  "minimum_severity": 2,
  "notify_recovery": true,
  "skip_suppressed": true,
  "ai_enabled": true
}
```

接收人最多 50 位、分类最多 50 个，均不得重复；最低级别为 Zabbix 0..5，启用时必须选择接收人且飞书配置完整。`revision` 防止覆盖并发修改。GET/PUT 配置还包含 `enabled_since`、`last_poll_at`（Unix 秒）、`last_error`；不要在 PUT 中回传这些只读字段。新增接收人时可收到本次启用以来仍在读取范围内的匹配事件。

发送记录示例：

```json
{"code":200,"msg":"success","data":{"total":1,"rows":[{"id":1,"event_id":"123","event_name":"ICMP loss","phase":"problem","user_id":12,"user_name":"运维","status":"sent","attempts":1,"message":"发送成功","advice":"检查链路丢包","advice_source":"rule","sent_at":1794614400,"created_at":1794614390}]}}
```

错误：401 未登录/账户停用；403 无接口权限；404 通知不存在、事件不可见或不在纳管范围；409 配置版本冲突、通知未启用、接收人已变更、记录不可重试或达到次数上限；422 无效参数、接收用户无效、分类不存在或飞书未配置。Zabbix 上游错误沿用事件接口异常响应；AI 错误回退规则建议。后台轮询错误记录脱敏提示，不记录提示词、凭据或上游原始响应。

## 数据库与验证

Aerich 新迁移 `191_20261114110636_monitor_notifications.py` 新建 `monitor_notification_config` 与 `monitor_notification_delivery`，不改历史迁移。配置默认关闭。

回归测试：`.venv\Scripts\python.exe -m unittest tests.test_monitor_notifications tests.test_monitor_events`。所有通知发送及 AI 调用使用 mock，不给真实用户发送测试消息。
