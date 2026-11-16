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

### 分类接收人

配置新增 `category_recipients` 字典，例如 `{"network":[12,18],"server":[25],"unclassified":[]}`。每个分类独立选择用户：键不存在时沿用 `recipient_ids` 默认名单；键存在时完全覆盖默认名单；空数组表示该分类不通知。`category_keys` 仍是总的通知范围筛选，不在范围内的分类不会参与分配。多分类事件合并名单并去重，告警、恢复、发送队列校验与手动重试遵循相同规则。

GET/PUT 返回该字段，旧数据返回 `{}`；旧客户端 PUT 省略或传 null 时保留已有规则，显式 `{}` 清空所有分类覆盖。最多 51 个分类（含未分类），每分类最多 50 名不重复的有效用户，分类必须存在、用户必须启用且具备飞书身份或邮箱。启用时，通知范围内至少一个分类须有接收人；默认名单可为空。错误沿用 422（无效分类/用户/空有效名单）、409（版本冲突/重试接收人不再匹配）。修改规则可能使新接收人收到本次启用以来仍在读取范围内的匹配事件，已发记录按事件/阶段/用户去重。

迁移 `192_20261116130646_notification_category_recipients.py` 新增可空 JSONB 列，旧行 null 按 `{}` 处理，保留原默认接收人及启用状态，不额外改变通知范围。

卡片排版：短状态标题 → 告警名称 → 各主机简称、地址和分类属性双列布局 → 小字路径 → 状态与时间信息 → 未恢复事件的排查建议 → 事件入口。主机名按 `PATH` 分离展示，不重复打印完整名称。持续时间省略零值单位；建议正文按纯文本输出并清除 Markdown 加粗、标题和代码标记，避免原始符号影响阅读。页面预览按服务端卡片区块渲染。

恢复通知不调用 AI、不生成或展示 AI/规则排查建议；卡片仅保留恢复事实、最终持续时间、主机属性及事件链接。恢复预览返回 `advice: ""`、`advice_source: "none"`，告警通知仍按原配置生成建议。已发送的消息不回写修改。

前缀 `/api/v1/monitor-events/notifications`。全部接口使用现有登录 token 和 `DependPermission` 按 HTTP 方法/路由校验，返回标准 `{code, msg, data}`。

| 方法/路径 | 参数 | 响应 data |
| --- | --- | --- |
| GET 空路径 | 无 | 配置、`users:[{id,name,reachable}]`、`categories:[{key,label}]`、`feishu_configured`、`ai_configured` |
| PUT 空路径 | 下方 JSON | 保存后的配置及新 revision |
| POST `/preview` | `{ "event_id": "123" }`，省略或 null 使用示例 | `{card,advice,advice_source:"ai或rule或none",sample:boolean}` |
| GET `/deliveries` | page≥1，page_size=1..100 默认20，status 可选 pending/sending/sent/failed/skipped | `{total,rows:[{id,event_id,event_name,phase,user_id,user_name,status,attempts,message,advice,advice_source,sent_at,created_at}]}` |
| POST `/deliveries/{delivery_id}/retry` | 正整数 ID，无请求体 | 成功消息“已加入发送队列” |

PUT 示例（用户 ID、分类 key 使用 GET 返回值）：

```json
{
  "revision": 0,
  "enabled": true,
  "recipient_ids": [12],
  "category_recipients": {},
  "category_keys": [],
  "minimum_severity": 2,
  "notify_recovery": true,
  "skip_suppressed": true,
  "ai_enabled": true
}
```

默认接收人最多 50 位、通知分类筛选最多 50 个，均不得重复；最低级别为 Zabbix 0..5，启用时通知范围内至少一个分类须有有效接收人（默认或单独配置），且飞书配置完整。`revision` 防止覆盖并发修改。GET/PUT 配置还包含 `enabled_since`、`last_poll_at`（Unix 秒）、`last_error`；不要在 PUT 中回传这些只读字段。新增接收人时可收到本次启用以来仍在读取范围内的匹配事件。

发送记录示例：

```json
{"code":200,"msg":"success","data":{"total":1,"rows":[{"id":1,"event_id":"123","event_name":"ICMP loss","phase":"problem","user_id":12,"user_name":"运维","status":"sent","attempts":1,"message":"发送成功","advice":"检查链路丢包","advice_source":"rule","sent_at":1794614400,"created_at":1794614390}]}}
```

错误：401 未登录/账户停用；403 无接口权限；404 通知不存在、事件不可见或不在纳管范围；409 配置版本冲突、通知未启用、接收人已变更、记录不可重试或达到次数上限；422 无效参数、接收用户无效、分类不存在或飞书未配置。Zabbix 上游错误沿用事件接口异常响应；AI 错误回退规则建议。后台轮询错误记录脱敏提示，不记录提示词、凭据或上游原始响应。

## 数据库与验证

Aerich 新迁移 `191_20261114110636_monitor_notifications.py` 新建 `monitor_notification_config` 与 `monitor_notification_delivery`，不改历史迁移。配置默认关闭。

回归测试：`.venv\Scripts\python.exe -m unittest tests.test_monitor_notifications tests.test_monitor_events`。所有通知发送及 AI 调用使用 mock，不给真实用户发送测试消息。
