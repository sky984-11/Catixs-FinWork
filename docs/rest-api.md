# Catixs FinWork REST API 文档

版本：`0.1.0`

本文档由后端 FastAPI OpenAPI schema 生成，面向外部项目调用。接口基础路径为 `/api/v1`，完整机器可读 OpenAPI 文件见 [openapi.json](./openapi.json)。

## 快速接入

### FW 小助手（阿里百炼）

`POST /api/v1/fw-assistant/chat`，沿用登录鉴权（`token` 或 `Authorization: Bearer`）；百炼密钥仅由后端使用。

后端环境配置：`FW_ASSISTANT_API_KEY` 为百炼密钥；`FW_ASSISTANT_API_BASE` 为业务空间 OpenAI 兼容地址，例如 `https://<WorkspaceId>.cn-beijing.maas.aliyuncs.com/compatible-mode/v1`（不含 `/chat/completions`）；`FW_ASSISTANT_MODEL` 默认 `deepseek-v4.1-flash`，须已获得业务空间调用授权；`FW_ASSISTANT_TIMEOUT` 默认 45 秒。未指定地址时使用北京地域公共兼容地址。修改配置后重启后端。

FW 小助手不再回退使用 `DEEPSEEK_*` 配置；其他模块不受影响。前端不再发送固定模型名或读取 `VITE_FW_ASSISTANT_MODEL`，模型统一由后端配置。保留请求中的可选 `model` 字段供既有调用方覆盖，调用方须传百炼支持的模型名。请求使用非流式、非思考模式（`stream: false`、`enable_thinking: false`）。

请求 JSON：`message` 必填、1–8000 字符；`model` 可选；`messages` 默认空数组，每项含 `role`（system/user/assistant）和 `content`（1–8000 字符；客户端 system 消息不作为系统指令）；`context` 默认空对象，可传页面 `path`、`title`。用户身份由后端认证结果确定，不能通过 context 或工具参数覆盖。

数据库访问已改为 MCP：助手发现工具后，通过百炼 Function Calling 请求查询，将 MCP 结果以 `role=tool` 回传模型生成回答。助手使用请求级进程内 JSON-RPC 传输，与下述 HTTP 端点共用工具实现及权限校验，不需要额外进程或向百炼提供数据库密码、登录 token。已移除模型生成并执行任意 SQL 的流程。

响应保留 `content`、`model`、`db`；`db.enabled/reason/rows/row_count` 描述本轮查询，兼容字段 `db.sql` 为空字符串（不再执行模型 SQL）；新增 `db.queries` 记录各次查询的 `tool/is_error/result`。顶层 `rows` 为最近一次成功查询的数据，精确统计值读取 `queries[].result.count`。`FW_ASSISTANT_DB_QUERY_ENABLED=false` 时不向模型提供工具且拒绝直接工具查询。最多4轮工具交互、8次工具执行，累计结果达到60KB后停止后续执行并要求模型总结；每次查询10秒超时，整个模型/工具循环60秒超时，保持前端70秒等待上限。

```json
{"message":"你好","messages":[],"context":{"path":"/","title":"首页"}}
```

成功响应示例（本轮无需查询数据库）：

```json
{"code":200,"msg":"OK","data":{"content":"你好，请问需要什么帮助？","model":"deepseek-v4.1-flash","db":{"enabled":true,"reason":"本轮尚未查询数据库","sql":"","rows":[],"queries":[]}}}
```

错误：401 未登录或认证无效；422 请求参数校验失败；503 未配置助手密钥；502 上游连接失败、拒绝请求或未返回内容；400 查询校验失败；500 内部处理错误。业务错误结构为 `{"code":502,"msg":"错误说明","data":null}`；认证及参数校验错误使用 FastAPI `detail` 格式。

官方协议参考：[阿里百炼 OpenAI 兼容 Chat API](https://help.aliyun.com/zh/model-studio/qwen-api-via-openai-chat-completions)。

### FW 数据库 MCP

端点：`POST /api/v1/fw-assistant/mcp`，采用 MCP `2025-06-18` 的无状态 Streamable HTTP JSON 响应方式。支持 `initialize`、`notifications/initialized`、`ping`、`tools/list`、`tools/call`；无服务器主动通知、SSE、会话 ID 或批量请求。`GET` 经过认证后返回405。客户端初始化须传 `protocolVersion`、`capabilities`、`clientInfo`，服务端协商到 `2025-06-18`；不支持此版本的客户端应断开。

每次请求均须携带 FinWork 登录 `token` 或 `Authorization: Bearer <API token>`（使用项目现有认证，不提供 MCP OAuth 发现）。请求头要求 `Content-Type: application/json`、`Accept: application/json, text/event-stream`；初始化后带 `MCP-Protocol-Version: 2025-06-18`。API token 绑定用户的数据范围与登录用户相同。若携带 Origin，必须匹配后端 `WEB_BASE_URL`、`WEB_DEV_BASE_URL`、`https://WEB_DOMAIN` 或明确列出的 `CORS_ORIGINS`，通配符不授权 MCP Origin。

工具：

| 名称 | 参数 | 行为 |
| --- | --- | --- |
| `finwork_schema` | `{}` | 返回当前用户有列表权限的数据集及字段含义 |
| `finwork_query` | 必填 `dataset`；可选 `columns`、`filters`、`order_by`、`limit`、`offset`、`mode` | 执行受限 ORM 只读查询或计数 |
| `finwork_ops_read` | 必填 `action`，其他参数按数据源提供，见下文 | 读取云资源快照、Syslog、Akvorado 流量分析 |

开放数据集包括 `projects`、`project_tasks`、`tickets`、`customers`、`contracts`、`bills`、`cabinets`，以及下表中的运维数据集。已注册数据集的全部本表数据库字段向 FW 助手开放，包括扩展配置、附件元数据及图片URL；实际文件内容不读取。字段从 ORM 元数据发现，不再使用逐字段业务白名单。数据集权限和行范围保持不变，用户表、系统表不因此开放；凭据键及常见凭据文本仍脱敏。不支持 SQL、任意 JOIN 或写入。

设备明细补充 `customer_name/cabinet_name/location_name/region_name`，与 `type/u_position/u_height` 一起可直接查询。`status=1` 表示使用中；`customer_id` 的 `isnull=false` 筛选不表示缺少明细权限。请求 `columns` 最多128项，省略时返回全部本表字段及可用名称别名。未知字段返回“字段不存在或不是本表字段”，并提示按schema修正，不能解释成权限不足；数量查询使用count，明细查询使用rows。单条结果过大时应减少columns，不取消数据权限。

- 项目及任务：要求 `/api/v1/project/list` 的 GET 权限，且仅能查询本人负责或共享给本人的项目及其任务，沿用项目列表范围（管理员也应用此范围）。
- 工单：沿用工单模块的管理员/NOC可见全部、普通用户只看本人创建工单的规则；已关闭工单也可显式查询或计数。
- 客户、合同、账单：分别要求 `/api/v1/customer-center/customers`、`/contracts`、`/bills` 的 GET 权限，管理员权限沿用现有规则。
- 机柜：要求 `/api/v1/asset/cabinet/list` 的 GET 权限，沿用机柜列表的数据范围（无额外用户行过滤）；只有设备列表权限不能查询机柜。无权限时 `finwork_schema` 不显示 `cabinets`，直接查询返回 `isError=true`。

`cabinets` 支持全部本表字段及所属机房、区域、客户名称，完整字段由 `finwork_schema` 返回。`location_name`、`region_name`、`customer_name` 是服务端固定关联提供的名称字段，可用于筛选、投影及排序；未分配客户时 `customer_name=null`。照片字段仅返回URL，设备明细使用devices查询；不将租用U位范围当作实际空闲U位。默认包括启用和停用机柜，仅查询启用机柜须加 `status=true`。

示例：查询指定机房的启用机柜及电力配置，使用同一 MCP 端点和认证头：

```json
{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"finwork_query","arguments":{"dataset":"cabinets","columns":["id","name","code","location_name","customer_name","capacity_u","rental_start_u","rental_end_u","power_allocation_kw"],"filters":[{"field":"location_name","operator":"contains","value":"目标机房"},{"field":"status","value":true}],"order_by":["code"],"limit":20}}}
```

数量统计使用相同筛选并指定 `mode=count`；空结果仍为 `isError=false`，参数、权限和数据库错误沿用下述 MCP 错误约定。

`filters` 最多12项，按 AND 组合，每项 `{field, operator, value}`；operator 默认 `eq`，另支持 `in`（最多100项列表）、`contains`（文本）、`gte`、`lte`、`isnull`（布尔值）。字段须为本表数据库字段或已提供的名称别名，筛选不能扩大服务端用户范围。`order_by` 默认 `["-id"]`，最多5项；`columns` 可省略。`limit` 为1–100，实际不超过 `FW_ASSISTANT_DB_QUERY_LIMIT`（默认50，上限100）；`offset` 为0–10000。`mode` 默认为 `rows`，`count` 返回当前权限及筛选下的准确总数，忽略分页。

查询请求示例（初始化之后）：

```json
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"finwork_query","arguments":{"dataset":"tickets","mode":"count","filters":[{"field":"status","operator":"eq","value":2}]}}}
```

响应示例：

```json
{"jsonrpc":"2.0","id":3,"result":{"content":[{"type":"text","text":"{\"dataset\":\"tickets\",\"count\":2,\"rows\":[]}"}],"isError":false}}
```

行查询结果包含 `rows/row_count/offset/has_more/next_offset/truncated`。单字段文本截断至1000字符；每次查询结果行约30KB上限，未返回完的记录用 `next_offset` 继续读取，不能把 `row_count` 当总数。

HTTP 错误：401认证失败、403 Origin被拒绝、406 Accept不兼容、415 Content-Type错误、413请求超过64KiB、400 JSON解析失败或版本不支持。JSON-RPC 错误：`-32700`解析失败、`-32600`非法消息、`-32601`未知方法、`-32602`未知工具或非法协议参数。已知工具的参数错误、权限不足、查询关闭、超时及数据库错误返回 `result.isError=true`，不会伪装成空查询成功。通知返回202空响应。审计保留路径/操作者/状态，不记录助手或MCP请求/响应正文。

协议依据：[MCP Streamable HTTP](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports)、[百炼 Function Calling](https://help.aliyun.com/zh/model-studio/qwen-function-calling)。

#### 运维中心覆盖范围

以 `app/core/init_app.py` 中当前启用的运维菜单为准，覆盖服务工单、网络节点、机柜资源、资产库存、日志中心、流量分析、云资源、DHCP池、运维日志。已移除的 IP 管理和旧设备维护计划菜单不启用。本次只读接入，不开放开关机、控制台、通知、创建、修改、删除或同步刷新操作。

| 菜单/业务 | `finwork_query.dataset` | 对应 GET 权限 |
| --- | --- | --- |
| 服务工单及回复 | `tickets`、`ticket_replies` | 沿用工单身份及可见范围；回复按父工单权限过滤，不按回复作者扩大范围 |
| 网络节点 | `regions`、`locations` | `/api/v1/asset/region/list`、`/api/v1/asset/location/list` |
| 机柜、设备 | `cabinets`、`devices` | `/api/v1/asset/cabinet/list`、`/api/v1/asset/device/list` |
| 设备品牌及型号 | `device_brands`、`device_models` | `/api/v1/asset/device-brand/list` |
| 资产库存、分类、流水 | `inventory`、`inventory_categories`、`inventory_flows` | 分别 `/api/v1/asset/inventory/list`、`/inventory-category/list`、`/inventory-flow/list` |
| 库存关联销售单及明细 | `inventory_sales`、`inventory_sale_items` | `/api/v1/asset/inventory-sale/list` |
| DHCP池及分配记录 | `dhcp_pools`、`dhcp_leases` | `/api/v1/pve/dhcp-pools` |
| 云资源关联和本地元数据 | `cloud_bindings`、`vm_metadata` | `/api/v1/pve/nodes`、`/api/v1/pve/vms` |
| 运维日志、计划、工程师 | `remote_logs`、`remote_plans`、`remote_engineers` | `/api/v1/remote-assistance/overview` |

所有数据集支持既有字段筛选、排序、分页及计数。`finwork_schema.datasets` 返回当前用户获准的数据集和字段；新增 `finwork_schema.operations` 返回可用的外部/快照读取 action。业务 ID（如 `cabinet_id`、`inventory_id`、`pool_id`、`ticket_id`）可用于关联查询；不允许模型自行传关联字段或 SQL。

运维计费字段 `billing_data`、工程师 `billing_rules`、计划 `customer_pricing` 返回存储值，不重新计算费用。JSON 字段（包括attributes和附件元数据）按深度8层、每层最多100项、字符串1000字符截断，删除常见凭据键并脱敏常见凭据文本，修改过的结果标记 `truncated=true`；不读取附件实体内容，不返回登录凭据。实际空闲U位需结合设备的 `u_position/u_height/status` 分析，不能仅由租用范围判断。

#### `finwork_ops_read` 参数与结果

| action | 数据源和权限 | 参数/说明 |
| --- | --- | --- |
| `cloud_nodes` | 本地云资源快照，`GET /api/v1/pve/nodes` | 可选 `remote/status/keyword`，返回节点容量、状态、位置等白名单字段 |
| `cloud_vms` | 本地云资源快照，`GET /api/v1/pve/vms` | 可选 `remote/status/vmid/customer_id/keyword`，返回虚拟机规格、状态、客户等白名单字段 |
| `syslog_devices` | Syslog SSH读取，`GET /api/v1/syslog/devices` | 列出日志设备目录 |
| `syslog_files` | Syslog SSH读取，`GET /api/v1/syslog/files` | 必填有效IP `device`，列日志文件 |
| `syslog_logs` | Syslog SSH读取，`GET /api/v1/syslog/logs` | 必填 `device/file`；可选 `keyword/level/vendor/tail`；file须为纯文件名，tail默认1000、范围100–5000 |
| `traffic_regions` | 配置的Akvorado区域，沿用代理的登录鉴权 | 返回区域代码，不返回服务地址 |
| `traffic_widget` | Akvorado只读统计，沿用代理的登录鉴权 | 必填 `region`；`widget` 默认 `flow-rate`，支持 `flow-last/exporters/top/src-as/top/dst-as/top/protocol/top/src-country/top/dst-country/top/src-port/top/dst-port/top/exporter` |
| `traffic_graph` | Akvorado只读流量图，沿用代理的登录鉴权 | 必填 `region/start/end`；时间必须带时区、跨度大于0且不超过24小时；可选 `dimensions/filter/units/limit` |

云资源、Syslog和区域列表采用 `limit`（默认20，1–100且不超过系统查询行数限制）、`offset`（0–10000）、`mode`（rows/count）。结果含 `source/rows/row_count/total/has_more/next_offset`；云资源另外带 `synced_at/stale`，日志带 `observed_at/scope`。云资源只读取现有快照，不刷新、不写库；无已同步快照时报错，超过5分钟、dirty或存在同步错误时标记stale。必须向用户说明快照时间，不能称为实时数据。日志统计仅针对文件末尾tail行的匹配结果，不代表全文件或全站日志总数。

流量统计不支持offset和count；图表limit按Top N最多20组，固定请求20个时间点，实际采样由上游决定。dimensions最多4个，可用 `ExporterName/SrcAS/DstAS/SrcCountry/DstCountry/Proto/SrcAddr/DstAddr/SrcPort/DstPort/InIfName/OutIfName`；units支持 `l3bps/l2bps/pps/fps`，默认l3bps；filter为Akvorado过滤表达式，最多1000字符。只允许预配置区域与固定统计API，不接受URL、凭据、命令或重定向。流量结果保留在 `data`，不拆分时序数组；过大结果报错，请缩小范围。响应附带region、查询时间和observed_at；widget单位由对应上游指标决定，顶层units为null。

外部读取同样受10秒工具超时、单次约30KB输出及整轮调用预算限制；上游网络/API版本错误返回 `isError=true`，不伪装成空结果，错误不带内部连接信息。仅提供查询入口并不代表生产数据源已连通；需部署环境能访问现有Syslog SSH与Akvorado服务。

云资源查询示例：

```json
{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"finwork_ops_read","arguments":{"action":"cloud_vms","status":"running","limit":20}}}
```

流量查询示例（时间使用带时区ISO格式）：

```json
{"jsonrpc":"2.0","id":6,"method":"tools/call","params":{"name":"finwork_ops_read","arguments":{"action":"traffic_graph","region":"SZ","start":"2026-10-24T10:00:00+08:00","end":"2026-10-24T11:00:00+08:00","dimensions":["ExporterName"],"units":"l3bps","limit":10}}}
```

Akvorado接口依据：[官方路由定义](https://github.com/akvorado/akvorado/blob/main/console/root.go)、[图表参数](https://github.com/akvorado/akvorado/blob/main/console/graph.go)。

### API tokens（永久令牌）

系统管理 → **API tokens**，仅超级管理员及 `admin` / `管理员` 角色可管理，管理接口不接受历史 `dev` 调试凭据。Token 绑定一个启用用户，继承该用户当前的角色、接口权限和业务数据范围；普通用户即使被分配 token 管理接口权限也不能管理令牌。创建后不能更换所属用户。

- 支持名称、用途说明、启用状态及到期时间；`expires_at: null` 表示永久有效，设置到期时间时须传含时区且晚于当前时间的 ISO 8601 字符串，例如 `2099-01-01T00:00:00+08:00`。
- 明文仅在创建/重新生成成功时返回一次，数据库只保存 SHA-256 摘要。列表和编辑响应不包含明文或摘要，管理响应禁止缓存，管理请求/响应体不写入审计日志（保留操作者、路由、结果）。
- 停用、到期、删除、重新生成后，旧 token 在后续认证时立即失效；用户停用/删除后同样不可使用。重新生成保留启用状态及到期时间。最近使用时间按认证成功计，约每分钟更新一次，不表示业务操作成功。
- 既有 `token: <登录JWT>` 仍可用；API token 使用 `token: <API token>` 或 `Authorization: Bearer <API token>`。两种请求头值冲突返回 `401`；缺少凭据现在统一返回 `401`（此前必填请求头校验为 `422`）。停用用户的登录 JWT 也不再通过认证。

```bash
curl 'http://localhost:9999/api/v1/finance/quote/list?page=1&page_size=20' \
  -H 'Authorization: Bearer <API token>'
```

管理接口基础路径：`/api/v1/api-tokens`，均要求管理员认证：

| 方法 | 路由 | 参数/行为 |
| --- | --- | --- |
| GET | `/api/v1/api-tokens` | `page` 默认1；`page_size` 默认20、最大100；可选 `name`、`user_id`、`status`（`enabled/disabled/expired/user_disabled`） |
| GET | `/api/v1/api-tokens/users` | 无参数，返回可绑定的启用用户 `id/username/alias` |
| POST | `/api/v1/api-tokens` | JSON：`name` 必填、1–100字符；`user_id` 必填；`description` 最多500字符；`is_enabled` 默认true；`expires_at` 默认null |
| PUT | `/api/v1/api-tokens/{token_id}` | 完整提交名称、说明、启用状态、到期时间；默认值同创建，不接受 `user_id` |
| POST | `/api/v1/api-tokens/{token_id}/status` | JSON：`{"is_enabled":false}`；启用传true |
| POST | `/api/v1/api-tokens/{token_id}/regenerate` | 无请求体，立即替换旧值，返回新明文一次 |
| DELETE | `/api/v1/api-tokens/{token_id}` | 无请求体，删除并撤销令牌 |

创建请求：`{"name":"监控集成","user_id":2,"description":"读取业务状态","is_enabled":true,"expires_at":null}`。

创建/重新生成响应示例（`token` 为占位符）：

```json
{"code":200,"msg":"OK","data":{"id":1,"name":"监控集成","description":"读取业务状态","user_id":2,"username":"integration","user_active":true,"created_by_id":1,"created_by_name":"admin","is_enabled":true,"expires_at":null,"last_used_at":null,"created_at":"2026-10-23T10:00:00+08:00","updated_at":"2026-10-23T10:00:00+08:00","status":"enabled","token":"<仅此一次返回的API token>"}}
```

列表响应为 `{"code":200,"msg":"OK","data":[...],"total":1,"page":1,"page_size":20}`，每项结构同上但没有 `token`；编辑/启停响应为单项且没有 `token`。删除响应为 `{"code":200,"msg":"已删除","data":null}`。

错误码：`400` 绑定用户无效；`401` 缺少/无效/停用/过期凭据或用户停用；`403` 非管理员或业务接口无权限；`404` 令牌不存在；`422` 字段、分页、时间格式或时间范围错误。业务调用继续遵循原接口权限。

新增 Aerich 迁移 `179_20261023120000_api_tokens.py`，仅创建 `api_token` 表及索引，包含 SQLite/PostgreSQL 分支。部署前后端后按现有流程执行 `aerich upgrade` 并重启后端；启动时自动补齐系统管理菜单。回滚该迁移会删除所有 API tokens。

设计参考：[Zabbix API tokens](https://www.zabbix.com/documentation/current/en/manual/web_interface/frontend_sections/users/api_tokens)。

### 仪表盘物理机概览

- `GET /api/v1/asset/device/list?overview=true`：读取数据库中的物理服务器（`type=0`），排除已下架（`status=4`）和未关联有效客户的设备；沿用 `token` 登录及原设备列表接口权限。
- `overview` 为可选布尔值，默认 `false`，原分页响应不变。概览模式返回全部符合筛选条件的设备，不使用分页；支持原地区、机房、机柜、关键字、类型及状态筛选。
- 响应示例：`{"code":200,"data":[{"id":1,"name":"服务器","asset_no":"SERVER-001","brand":"Dell","model":"R740","status":1,"customer_ids":[10],"customer_names":["示例客户"],"region_name":"香港","location_name":"HK-01","cabinet_name":"A01","configurations":[{"name":"整机","cpu_model":"Xeon","cpu_count":"2","cpu_cores":"32","memory":"128GB","disk":"2 × 960GB SSD"}]}]}`。
- 四合一服务器按机箱计台数，`configurations` 分别返回各节点配置；共享设备按每个关联客户展示，顶部设备总量去重。概览仅输出指定的硬件配置字段，不返回管理密码、令牌或其他扩展属性。
- 错误码：`401` 登录无效；`403` 无设备列表权限；`422` 参数类型错误。该接口不探测设备实时电源状态，不将资产的“空闲”状态误判为关机。

四合一节点客户映射：`POST /api/v1/asset/device/create`、`POST /api/v1/asset/device/update` 的 `attributes.nodes[]` 支持可选 `customer_id`，例如 `{"form_factor":"four_node","nodes":[{"name":"N1","customer_id":10},{"name":"N2","customer_id":20}]}`。节点客户必须属于设备顶层 `customer_ids`，否则返回400；允许同一客户关联多个节点，`null` 表示解除映射。编辑请求省略该字段时保留仍属于设备已选客户的原映射。权限沿用设备创建、更新接口，无需数据库迁移。

物理机概览新增 `form_factor`，四合一的 `configurations[]` 包含各节点 `customer_id`；仪表盘按节点归属筛选客户配置。历史未映射节点不推测归属，显示待映射提示。标准设备仍按整机关联客户展示，四合一按机箱统计台数。

### 云资源数据库快照

- `GET /api/v1/pve/nodes`、`GET /api/v1/pve/vms` 从 `cloud_resource_snapshot` 表读取节点、虚拟机配置及地区快照，不在请求中等待 PDM。虚拟机列表仍关联本地客户元数据。
- 两个接口新增可选布尔参数 `refresh`（默认 `false`）：`true` 触发后台同步并立即返回现有快照；`/vms` 保留 `node` 节点过滤参数。认证仍使用 `token`，沿用原有节点/虚拟机列表权限。
- 没有快照或快照超过5分钟时，访问自动触发后台同步；无访问时不定期运行。数据库租约合并多个请求/进程的同步任务，失败后访问重试间隔至少30秒。
- `/nodes` 保留 `data` 数组，增加顶层 `sync`；`/vms` 保留 `data.items`、`data.summary`，增加 `data.nodes` 和 `data.sync`，仪表盘仅需调用 `/vms`。
- 响应示例：`{"code":200,"data":{"items":[],"summary":{"total":0,"running":0,"stopped":0},"nodes":[],"sync":{"synced_at":null,"refreshing":true,"stale":true,"error":""}}}`。首次读取空数组表示尚无快照，前端需结合 `sync` 展示初始化状态；同步中页面每3秒只重新读取快照。
- 创建、配置修改、节点变更、开关机、删除和迁移操作会触发后台刷新；有任务ID时先等待任务结束（最多约4分钟），超时或进程重启后由后续访问补偿。失败保留旧快照，不将失败节点当作空节点。只有成功取得完整资源列表时才移除已消失资源。
- 错误码：`401` 无效登录、`403` 无接口权限、`422` 参数校验失败。云平台同步失败通过 `sync.error` 返回，不覆盖已有数据。
- 新增迁移 `40_20260914120000_cloud_snapshot.py`；首次访问触发初始化同步，表内保存最近快照，不修改现有客户归属表结构。
- 空列表校验：资源汇总仅返回宿主节点或空资源时，需成功查询 QEMU 和 LXC 列表才能确认节点没有虚拟机；查询失败或结构不完整时保留旧数据并返回同步异常，避免错误清空快照。
- `POST /api/v1/pve/vms/delete`：等待 PVE 删除任务明确成功后，才移除快照资源、释放 DHCP 租约并清理元数据。短期删除标记防止并发同步及云端缓存将旧资源写回，最长保留10分钟。任务报错、状态查询失败、缺少任务编号或等待超时均返回失败，不执行上述清理。

### 运维计划与记录附件

- 通用上传：`POST /api/v1/remote-assistance/attachments/upload`，原 `/plans/attachments/upload` 保持兼容。两者均仅要求 `token` 登录，不要求独立上传 API 权限；前后端需同步部署并重启后端。
- 运维日志前端参照项目看板，使用 `application/json` 上传：`{"filename":"说明.txt","content_type":"text/plain","data":"data:text/plain;base64,aGVsbG8="}`。`filename` 必填且不超过255字符，`content_type` 可选，`data` 必填，支持纯 Base64 或 Base64 Data URL；响应格式保持不变。原 multipart `file` 上传仍可用。
- JSON 上传错误码：`400` 编码无效、解码后为空或超过20MiB；`422` JSON/字段无效或编码内容超限；`401` 登录无效（缺少 token 为 `422`）；`500` 写入失败。审计日志不记录附件编码内容。Base64 请求体比原文件约大三分之一，部署代理需允许至少30MiB请求体；仓库 Nginx 配置已同步，业务文件上限仍为20MiB。Cloudflare 若按路径发起挑战，仍需按其事件记录调整规则，JSON 上传不能保证解除所有代理拦截。
- 运维记录创建 `POST /api/v1/remote-assistance/remote-hands`、编辑 `PUT /api/v1/remote-assistance/remote-hands/{item_id}` 支持同格式的 `attachments` 数组（最多50项）；省略字段保留原附件。概览的 `remote_hands[].attachments` 返回记录自身及关联计划附件，按 URL 去重；完成计划时将附件保留到生成的记录。
- 立即删除：`DELETE /api/v1/remote-assistance/attachments`，JSON 请求示例 `{"url":"/uploads/remote-plans/0123456789abcdef0123456789abcdef.bin"}`。成功响应 `{"code":200,"msg":"附件已删除","data":null}`。物理文件与所有关联计划、记录的附件引用一并删除；之后取消编辑不会恢复附件。重复删除不存在的文件也返回成功。
- 删除权限：必须登录；未关联的新上传附件可直接删除；已关联附件要求具有每个关联计划/记录的 `PUT` 编辑权限（或管理员权限），无需独立分配删除附件 API。错误码：`401` 无效登录；`403` 缺少关联对象编辑权限；`422` 缺少 token 或 URL 格式不合法；`500` 删除失败。
- 新增迁移 `41_20260916120000_record_attachments.py`，为 `remote_hands` 增加 JSONB 附件字段；PostgreSQL 启动前补列也已同步，旧计划附件通过关联查询兼容。无字段更名或旧接口删除。
- 权限匹配兼容实际路径及 FastAPI 路由模板，例如 `PUT /api/v1/remote-assistance/remote-hands/{item_id}`；仍要求角色具有对应方法和路径权限。

- `POST /api/v1/remote-assistance/plans/attachments/upload`：使用 `multipart/form-data`，必填字段 `file`。多附件逐个调用此接口；单文件非空且不超过20MB。
- 认证：请求头 `token`；附件上传与工单上传一致，仅校验登录，无需单独分配上传接口权限。计划创建、编辑和查询仍沿用运维记录模块的 API 权限校验。
- 成功响应：`{"code":200,"msg":"OK","data":{"name":"操作说明.pdf","url":"/uploads/remote-plans/0123456789abcdef0123456789abcdef.bin","size":1024}}`。
- `POST /api/v1/remote-assistance/plans`、兼容路径 `POST /api/v1/remote-assistance/plans/create` 和 `PUT /api/v1/remote-assistance/plans/{plan_id}` 的 JSON 请求新增可选字段 `attachments`，最多50项，每项使用上传响应的 `name`、`url`、`size`。创建、编辑响应及 `GET /api/v1/remote-assistance/overview` 中的计划均返回该数组。
- 请求示例（附件字段）：`{"attachments":[{"name":"操作说明.pdf","url":"/uploads/remote-plans/0123456789abcdef0123456789abcdef.bin","size":1024}]}`，其他计划必填字段保持原样。
- 编辑时省略 `attachments` 保留已有附件，传 `[]` 移除当前对象附件关联；仅待执行计划允许编辑。界面删除按钮调用上述立即删除接口；仅取消编辑不会删除新上传文件。附件按现有 `/uploads` 静态资源方式下载，前端使用原文件名保存。
- 错误码：`400` 空文件、超过20MB、引用文件不存在或计划不可编辑；`401` 登录无效；`403` 无接口权限；`422` 缺少文件或附件字段校验失败（含超过50项）；`500` 文件写入失败。
- 数据库升级：新增迁移 `39_20260910120000_plan_attachments.py`，为历史计划填充空附件数组。
- 启动兼容：PostgreSQL 的 `ensure_pre_schema_columns()` 会在生成模型 schema 前补齐附件字段，避免旧表缺列导致启动失败；重复启动及后续正式迁移均可安全重复执行。

- Base URL：`http(s)://<host>/api/v1`
- 数据格式：默认使用 `application/json`；上传/导入类接口使用 `multipart/form-data`。
- 认证方式：多数业务接口需要在请求头携带 `token: <access_token>`。
- 获取 Token：`POST /api/v1/base/access_token`。
- 公开文档接口：`GET /api/v1/api/docs`，OpenAPI JSON：`GET /api/v1/api/docs/openapi` 或项目静态文件 `docs/openapi.json`。

## 认证示例

```bash
curl -X POST 'http://localhost:9999/api/v1/base/access_token' \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"your-password"}'
```

后续请求：

```bash
curl 'http://localhost:9999/api/v1/finance/quote/list?page=1&page_size=20' \
  -H 'token: <access_token>'
```

## 通用响应

普通响应：

```json
{"code": 200, "msg": "OK", "data": {}}
```

分页响应：

```json
{"code": 200, "msg": null, "data": [], "total": 0, "page": 1, "page_size": 20}
```

## 分页与查询约定

- 常见列表接口使用 `page`、`page_size` 作为分页参数。
- `GET` 接口参数通常放在 Query String。
- `POST/PUT/PATCH` 接口通常提交 JSON body，少数上传接口提交表单文件。
- 删除接口多数使用 `DELETE` + Query 参数或路径参数。

## 接口总览（215 个分组条目，205 个唯一操作）

### API文档

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `GET` | `/api/v1/api/docs` | 公开API文档 | - | application/json: - |

### API模块

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `POST` | `/api/v1/api/create` | 创建Api | application/json: ApiCreate | application/json: - |
| `DELETE` | `/api/v1/api/delete` | 删除Api | - | application/json: - |
| `GET` | `/api/v1/api/get` | 查看Api | - | application/json: - |
| `GET` | `/api/v1/api/list` | 查看API列表 | - | application/json: - |
| `POST` | `/api/v1/api/refresh` | 刷新API列表 | - | application/json: - |
| `POST` | `/api/v1/api/update` | 更新Api | application/json: ApiUpdate | application/json: - |

### Akvorado

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `GET` | `/api/v1/akvorado/proxy/{region}/{path}` | Proxy Akvorado region UI | - | application/json: - |
| `POST` | `/api/v1/akvorado/proxy/{region}/{path}` | Proxy Akvorado region UI | - | application/json: - |
| `PUT` | `/api/v1/akvorado/proxy/{region}/{path}` | Proxy Akvorado region UI | - | application/json: - |
| `PATCH` | `/api/v1/akvorado/proxy/{region}/{path}` | Proxy Akvorado region UI | - | application/json: - |
| `DELETE` | `/api/v1/akvorado/proxy/{region}/{path}` | Proxy Akvorado region UI | - | application/json: - |
| `OPTIONS` | `/api/v1/akvorado/proxy/{region}/{path}` | Proxy Akvorado region UI | - | application/json: - |

### NetBox IPAM

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `GET` | `/api/v1/netbox/ipam/filter-options` | NetBox IPAM filter options | - | application/json: - |
| `GET` | `/api/v1/netbox/ipam/filter-options` | NetBox IPAM filter options | - | application/json: - |
| `POST` | `/api/v1/netbox/ipam/ip-addresses` | Create NetBox IP address | application/json: object | application/json: - |
| `POST` | `/api/v1/netbox/ipam/ip-addresses` | Create NetBox IP address | application/json: object | application/json: - |
| `PATCH` | `/api/v1/netbox/ipam/ip-addresses/{ip_id}` | Update NetBox IP address | application/json: object | application/json: - |
| `PATCH` | `/api/v1/netbox/ipam/ip-addresses/{ip_id}` | Update NetBox IP address | application/json: object | application/json: - |
| `DELETE` | `/api/v1/netbox/ipam/ip-addresses/{ip_id}` | Delete NetBox IP address | - | application/json: - |
| `DELETE` | `/api/v1/netbox/ipam/ip-addresses/{ip_id}` | Delete NetBox IP address | - | application/json: - |
| `GET` | `/api/v1/netbox/ipam/overview` | NetBox IPAM overview | - | application/json: - |
| `GET` | `/api/v1/netbox/ipam/overview` | NetBox IPAM overview | - | application/json: - |
| `GET` | `/api/v1/netbox/ipam/prefix-ips` | NetBox IPAM prefix IP list | - | application/json: - |
| `GET` | `/api/v1/netbox/ipam/prefix-ips` | NetBox IPAM prefix IP list | - | application/json: - |
| `GET` | `/api/v1/netbox/ipam/prefix-options` | NetBox prefix edit options | - | application/json: - |
| `GET` | `/api/v1/netbox/ipam/prefix-options` | NetBox prefix edit options | - | application/json: - |
| `POST` | `/api/v1/netbox/ipam/prefixes` | Create NetBox prefix | application/json: object | application/json: - |
| `POST` | `/api/v1/netbox/ipam/prefixes` | Create NetBox prefix | application/json: object | application/json: - |
| `PATCH` | `/api/v1/netbox/ipam/prefixes/{prefix_id}` | Update NetBox prefix | application/json: object | application/json: - |
| `PATCH` | `/api/v1/netbox/ipam/prefixes/{prefix_id}` | Update NetBox prefix | application/json: object | application/json: - |
| `DELETE` | `/api/v1/netbox/ipam/prefixes/{prefix_id}` | Delete NetBox prefix | - | application/json: - |
| `DELETE` | `/api/v1/netbox/ipam/prefixes/{prefix_id}` | Delete NetBox prefix | - | application/json: - |
| `POST` | `/api/v1/netbox/ipam/sync-pve-ips` | Schedule PVE guest-agent IP sync to NetBox | - | application/json: - |
| `POST` | `/api/v1/netbox/ipam/sync-pve-ips` | Schedule PVE guest-agent IP sync to NetBox | - | application/json: - |
| `POST` | `/api/v1/netbox/ipam/sync-pve-ips/run-now` | Run PVE IP sync immediately | - | application/json: - |
| `POST` | `/api/v1/netbox/ipam/sync-pve-ips/run-now` | Run PVE IP sync immediately | - | application/json: - |

### PVE Datacenter模块

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `GET` | `/api/v1/pve/nodes` | PDM remote list | - | application/json: - |
| `POST` | `/api/v1/pve/nodes/add` | Add PVE remote to PDM | application/json: PDMAddRemoteRequest | application/json: - |
| `POST` | `/api/v1/pve/nodes/probe` | Probe PVE remote TLS | application/json: PDMProbeRemoteRequest | application/json: - |
| `GET` | `/api/v1/pve/nodes/realms` | PVE remote realms | - | application/json: - |
| `PUT` | `/api/v1/pve/nodes/remote/{remote}` | Update PVE remote | application/json: PDMUpdateRemoteRequest | application/json: - |
| `DELETE` | `/api/v1/pve/nodes/remote/{remote}` | Delete PVE remote | - | application/json: - |
| `GET` | `/api/v1/pve/nodes/remote/{remote}/remark` | Read PVE node remark | - | application/json: - |
| `PUT` | `/api/v1/pve/nodes/remote/{remote}/remark` | Update PVE node remark | application/json: PDMRemoteRemarkRequest | application/json: - |
| `GET` | `/api/v1/pve/tasks/status` | PDM remote task status | - | application/json: - |
| `GET` | `/api/v1/pve/vms` | PDM virtual machine list | - | application/json: - |
| `GET` | `/api/v1/pve/vms/config` | Read PVE virtual machine core config | - | application/json: - |
| `POST` | `/api/v1/pve/vms/config` | Update PVE virtual machine core config | application/json: VMConfigUpdateRequest | application/json: - |
| `POST` | `/api/v1/pve/vms/create` | PVE virtual machine create | application/json: VMCreateRequest | application/json: - |
| `GET` | `/api/v1/pve/vms/create-options` | PVE virtual machine create options | - | application/json: - |
| `POST` | `/api/v1/pve/vms/delete` | Delete PDM virtual machine | application/json: VMDeleteRequest | application/json: - |
| `GET` | `/api/v1/pve/vms/ips` | PVE virtual machine guest-agent IP list | - | application/json: - |
| `POST` | `/api/v1/pve/vms/migrate` | PDM virtual machine remote migration | application/json: VMMigrateRequest | application/json: - |
| `GET` | `/api/v1/pve/vms/migration-options` | PDM virtual machine migration options | - | application/json: - |
| `POST` | `/api/v1/pve/vms/novnc` | PDM virtual machine noVNC console | application/json: NoVNCRequest | application/json: - |
| `POST` | `/api/v1/pve/vms/power` | Start or shutdown PDM virtual machine | application/json: VMPowerRequest | application/json: - |
| `POST` | `/api/v1/pve/vms/reboot` | Reboot PVE virtual machine | application/json: VMDeleteRequest | application/json: - |

### PVE Grafana

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `GET` | `/api/v1/pve/grafana/proxy/{path}` | Proxy Grafana with service account token | - | application/json: - |
| `POST` | `/api/v1/pve/grafana/proxy/{path}` | Proxy Grafana with service account token | - | application/json: - |
| `PUT` | `/api/v1/pve/grafana/proxy/{path}` | Proxy Grafana with service account token | - | application/json: - |
| `PATCH` | `/api/v1/pve/grafana/proxy/{path}` | Proxy Grafana with service account token | - | application/json: - |
| `DELETE` | `/api/v1/pve/grafana/proxy/{path}` | Proxy Grafana with service account token | - | application/json: - |
| `OPTIONS` | `/api/v1/pve/grafana/proxy/{path}` | Proxy Grafana with service account token | - | application/json: - |

### Syslog日志管理模块

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `GET` | `/api/v1/syslog/devices` | Syslog 设备目录 | - | application/json: - |
| `GET` | `/api/v1/syslog/files` | Syslog 日志文件列表 | - | application/json: - |
| `GET` | `/api/v1/syslog/logs` | Syslog 日志查询 | - | application/json: - |
| `GET` | `/api/v1/syslog/raw` | Syslog 原始日志 | - | application/json: - |

### 仪表盘模块

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `GET` | `/api/v1/ticket/dashboard` | 工单仪表盘 | - | application/json: - |

### 供应商模块

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `POST` | `/api/v1/vendor/create` | 创建供应商 | application/json: VendorCreate | application/json: - |
| `DELETE` | `/api/v1/vendor/delete` | 删除供应商 | - | application/json: - |
| `GET` | `/api/v1/vendor/export` | 导出供应商 | - | application/json: - |
| `GET` | `/api/v1/vendor/get` | 查看供应商 | - | application/json: - |
| `POST` | `/api/v1/vendor/import` | 导入供应商 | multipart/form-data: Body_import_vendor_api_v1_vendor_import_post | application/json: - |
| `GET` | `/api/v1/vendor/list` | 查看供应商列表 | - | application/json: - |
| `POST` | `/api/v1/vendor/update` | 更新供应商 | application/json: VendorUpdate | application/json: - |

### 公司模块

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `POST` | `/api/v1/company/create` | 创建公司 | application/json: CompanyCreate | application/json: - |
| `DELETE` | `/api/v1/company/delete` | 删除公司 | - | application/json: - |
| `GET` | `/api/v1/company/get` | 查看公司 | - | application/json: - |
| `GET` | `/api/v1/company/list` | 查看公司列表 | - | application/json: - |
| `POST` | `/api/v1/company/update` | 更新公司 | application/json: CompanyUpdate | application/json: - |

### 基础模块

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `POST` | `/api/v1/base/access_token` | 获取token | application/json: CredentialsSchema | application/json: - |
| `POST` | `/api/v1/base/avatar` | 上传当前用户头像 | application/json: UserAvatarUpload | application/json: - |
| `POST` | `/api/v1/base/profile` | 更新当前用户信息 | application/json: UserProfileUpdate | application/json: - |
| `POST` | `/api/v1/base/update_password` | 修改密码 | application/json: UpdatePassword | application/json: - |
| `GET` | `/api/v1/base/userapi` | 查看用户API | - | application/json: - |
| `GET` | `/api/v1/base/userinfo` | 查看用户信息 | - | application/json: - |
| `GET` | `/api/v1/base/usermenu` | 查看用户菜单 | - | application/json: - |

### 定时任务模块

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `POST` | `/api/v1/task/create` | 创建定时任务 | application/json: ScheduledTaskCreate | application/json: - |
| `DELETE` | `/api/v1/task/delete` | 删除定时任务 | - | application/json: - |
| `GET` | `/api/v1/task/get` | 查看定时任务 | - | application/json: - |
| `GET` | `/api/v1/task/list` | 查看定时任务列表 | - | application/json: - |
| `GET` | `/api/v1/task/logs` | 查看定时任务执行日志 | - | application/json: - |
| `DELETE` | `/api/v1/task/logs` | 清理定时任务执行日志 | - | application/json: - |
| `POST` | `/api/v1/task/run` | 手动执行定时任务 | - | application/json: - |
| `POST` | `/api/v1/task/toggle` | 启停定时任务 | application/json: ScheduledTaskToggle | application/json: - |
| `POST` | `/api/v1/task/update` | 更新定时任务 | application/json: ScheduledTaskUpdate | application/json: - |

### 审计日志模块

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `GET` | `/api/v1/auditlog/list` | 查看操作日志 | - | application/json: - |

### 客户项目看板

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `DELETE` | `/api/v1/project/attachment/delete` | 删除项目截图资料 | - | application/json: - |
| `POST` | `/api/v1/project/attachment/upload` | 上传项目截图资料 | application/json: ProjectAttachmentUpload | application/json: - |
| `POST` | `/api/v1/project/create` | 创建客户项目 | application/json: CustomerProjectCreate | application/json: - |
| `DELETE` | `/api/v1/project/delete` | 删除客户项目 | - | application/json: - |
| `POST` | `/api/v1/project/discussion/create` | 新增项目讨论 | application/json: ProjectDiscussionCreate | application/json: - |
| `DELETE` | `/api/v1/project/discussion/delete` | 删除项目讨论 | - | application/json: - |
| `GET` | `/api/v1/project/get` | 查看客户项目 | - | application/json: - |
| `GET` | `/api/v1/project/list` | 查看客户项目列表 | - | application/json: - |
| `POST` | `/api/v1/project/status` | 更新客户项目看板状态 | application/json: CustomerProjectStatusUpdate | application/json: - |
| `POST` | `/api/v1/project/task/create` | 创建项目任务 | application/json: ProjectTaskCreate | application/json: - |
| `DELETE` | `/api/v1/project/task/delete` | 删除项目任务 | - | application/json: - |
| `POST` | `/api/v1/project/task/update` | 更新项目任务 | application/json: ProjectTaskUpdate | application/json: - |
| `POST` | `/api/v1/project/update` | 更新客户项目 | application/json: CustomerProjectUpdate | application/json: - |

### 工单模块

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `POST` | `/api/v1/ticket/create` | 创建工单 | application/json: TicketCreate | application/json: - |
| `DELETE` | `/api/v1/ticket/delete` | 删除工单 | - | application/json: - |
| `GET` | `/api/v1/ticket/get` | 查看工单详情 | - | application/json: - |
| `GET` | `/api/v1/ticket/get_by_no` | 根据工单编号查询工单 | - | application/json: - |
| `GET` | `/api/v1/ticket/list` | 查看工单列表 | - | application/json: - |
| `POST` | `/api/v1/ticket/reply` | 回复工单 | application/json: TicketReplyCreate | application/json: - |
| `POST` | `/api/v1/ticket/reply/create` | 回复工单 | application/json: TicketReplyCreate | application/json: - |
| `GET` | `/api/v1/ticket/reply/list` | 查看工单回复 | - | application/json: - |
| `POST` | `/api/v1/ticket/reply_create` | 回复工单 | application/json: TicketReplyCreate | application/json: - |
| `POST` | `/api/v1/ticket/send_email` | 发送工单邮件通知 | application/json: TicketEmailSend | application/json: - |
| `POST` | `/api/v1/ticket/update` | 更新工单 | application/json: TicketUpdate | application/json: - |
| `POST` | `/api/v1/ticket/upload` | 上传工单附件图片 | application/json: TicketAttachmentUpload | application/json: - |
| `GET` | `/api/v1/ticket/users` | 查看工单用户选项 | - | application/json: - |

### 报价系统

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `POST` | `/api/v1/finance/quote/create` | 创建报价 | application/json: FinanceQuoteCreate | application/json: - |
| `DELETE` | `/api/v1/finance/quote/delete` | 删除报价 | - | application/json: - |
| `GET` | `/api/v1/finance/quote/field-options` | 报价字段选项 | - | application/json: - |
| `GET` | `/api/v1/finance/quote/get` | 查看报价 | - | application/json: - |
| `GET` | `/api/v1/finance/quote/list` | 查看报价列表 | - | application/json: - |
| `GET` | `/api/v1/finance/quote/site-options` | 站点选项 | - | application/json: - |
| `POST` | `/api/v1/finance/quote/update` | 更新报价 | application/json: FinanceQuoteUpdate | application/json: - |

### 用户模块

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `POST` | `/api/v1/user/create` | 创建用户 | application/json: UserCreate | application/json: - |
| `DELETE` | `/api/v1/user/delete` | 删除用户 | - | application/json: - |
| `GET` | `/api/v1/user/get` | 查看用户 | - | application/json: - |
| `GET` | `/api/v1/user/list` | 查看用户列表 | - | application/json: - |
| `POST` | `/api/v1/user/reset_password` | 重置密码 | application/json: Body_reset_password_api_v1_user_reset_password_post | application/json: - |
| `POST` | `/api/v1/user/update` | 更新用户 | application/json: UserUpdate | application/json: - |

### 菜单模块

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `POST` | `/api/v1/menu/create` | 创建菜单 | application/json: MenuCreate | application/json: - |
| `DELETE` | `/api/v1/menu/delete` | 删除菜单 | - | application/json: - |
| `GET` | `/api/v1/menu/get` | 查看菜单 | - | application/json: - |
| `GET` | `/api/v1/menu/list` | 查看菜单列表 | - | application/json: - |
| `POST` | `/api/v1/menu/update` | 更新菜单 | application/json: MenuUpdate | application/json: - |

### 角色模块

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `GET` | `/api/v1/role/authorized` | 查看角色权限 | - | application/json: - |
| `POST` | `/api/v1/role/authorized` | 更新角色权限 | application/json: RoleUpdateMenusApis | application/json: - |
| `POST` | `/api/v1/role/create` | 创建角色 | application/json: RoleCreate | application/json: - |
| `DELETE` | `/api/v1/role/delete` | 删除角色 | - | application/json: - |
| `GET` | `/api/v1/role/get` | 查看角色 | - | application/json: - |
| `GET` | `/api/v1/role/list` | 查看角色列表 | - | application/json: - |
| `POST` | `/api/v1/role/update` | 更新角色 | application/json: RoleUpdate | application/json: - |

### 账单模块

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `POST` | `/api/v1/bill/create` | 创建账单 | application/json: BillCreate | application/json: - |
| `DELETE` | `/api/v1/bill/delete` | 删除账单 | - | application/json: - |
| `GET` | `/api/v1/bill/get` | 查看账单 | - | application/json: - |
| `GET` | `/api/v1/bill/list` | 查看账单列表 | - | application/json: - |
| `POST` | `/api/v1/bill/update` | 更新账单 | application/json: BillUpdate | application/json: - |
| `POST` | `/api/v1/bill/upload_voucher` | 上传付款凭证 | multipart/form-data: Body_upload_payment_voucher_api_v1_bill_upload_voucher_post | application/json: - |

### 资产管理模块

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `POST` | `/api/v1/asset/cabinet/create` | 创建机柜 | application/json: AssetCabinetCreate | application/json: - |
| `DELETE` | `/api/v1/asset/cabinet/delete` | 删除机柜 | - | application/json: - |
| `GET` | `/api/v1/asset/cabinet/get` | 机柜详情 | - | application/json: - |
| `GET` | `/api/v1/asset/cabinet/list` | 机柜列表 | - | application/json: - |
| `POST` | `/api/v1/asset/cabinet/update` | 更新机柜 | application/json: AssetCabinetUpdate | application/json: - |
| `POST` | `/api/v1/asset/device-brand/create` | 创建设备品牌 | application/json: AssetDeviceBrandCreate | application/json: - |
| `DELETE` | `/api/v1/asset/device-brand/delete` | 删除设备品牌 | - | application/json: - |
| `GET` | `/api/v1/asset/device-brand/list` | 设备品牌型号列表 | - | application/json: - |
| `POST` | `/api/v1/asset/device-model/create` | 创建设备型号 | application/json: AssetDeviceModelCreate | application/json: - |
| `DELETE` | `/api/v1/asset/device-model/delete` | 删除设备型号 | - | application/json: - |
| `POST` | `/api/v1/asset/device/create` | 创建设备 | application/json: AssetDeviceCreate | application/json: - |
| `DELETE` | `/api/v1/asset/device/delete` | 删除设备 | - | application/json: - |
| `GET` | `/api/v1/asset/device/get` | 设备详情 | - | application/json: - |
| `GET` | `/api/v1/asset/device/list` | 设备列表 | - | application/json: - |
| `POST` | `/api/v1/asset/device/update` | 更新设备 | application/json: AssetDeviceUpdate | application/json: - |
| `POST` | `/api/v1/asset/inventory-category/create` | 创建库存分类 | application/json: AssetInventoryCategoryCreate | application/json: - |
| `DELETE` | `/api/v1/asset/inventory-category/delete` | 删除库存分类 | - | application/json: - |
| `GET` | `/api/v1/asset/inventory-category/list` | 库存分类列表 | - | application/json: - |
| `POST` | `/api/v1/asset/inventory-category/update` | 更新库存分类 | application/json: AssetInventoryCategoryUpdate | application/json: - |
| `GET` | `/api/v1/asset/inventory-flow/list` | 库存流水列表 | - | application/json: - |
| `POST` | `/api/v1/asset/inventory-sale/cancel` | 取消库存销售单 | application/json: AssetInventorySaleCancel | application/json: - |
| `POST` | `/api/v1/asset/inventory-sale/create` | 创建库存销售单 | application/json: AssetInventorySaleCreate | application/json: - |
| `GET` | `/api/v1/asset/inventory-sale/list` | 库存销售单列表 | - | application/json: - |
| `POST` | `/api/v1/asset/inventory/create` | 创建库存 | application/json: AssetInventoryCreate | application/json: - |
| `DELETE` | `/api/v1/asset/inventory/delete` | 删除库存 | - | application/json: - |
| `GET` | `/api/v1/asset/inventory/export` | 导出库存 | - | application/json: - |
| `GET` | `/api/v1/asset/inventory/get` | 库存详情 | - | application/json: - |
| `POST` | `/api/v1/asset/inventory/import` | 导入库存 | multipart/form-data: Body_import_inventory_api_v1_asset_inventory_import_post | application/json: - |
| `GET` | `/api/v1/asset/inventory/list` | 库存列表 | - | application/json: - |
| `POST` | `/api/v1/asset/inventory/update` | 更新库存 | application/json: AssetInventoryUpdate | application/json: - |
| `POST` | `/api/v1/asset/location/create` | 创建位置 | application/json: AssetLocationCreate | application/json: - |
| `DELETE` | `/api/v1/asset/location/delete` | 删除位置 | - | application/json: - |
| `GET` | `/api/v1/asset/location/list` | 位置列表 | - | application/json: - |
| `POST` | `/api/v1/asset/location/update` | 更新位置 | application/json: AssetLocationUpdate | application/json: - |
| `POST` | `/api/v1/asset/region/create` | 创建区域 | application/json: AssetRegionCreate | application/json: - |
| `DELETE` | `/api/v1/asset/region/delete` | 删除区域 | - | application/json: - |
| `GET` | `/api/v1/asset/region/get` | 区域详情 | - | application/json: - |
| `GET` | `/api/v1/asset/region/list` | 区域列表 | - | application/json: - |
| `POST` | `/api/v1/asset/region/update` | 更新区域 | application/json: AssetRegionUpdate | application/json: - |
| `GET` | `/api/v1/asset/tree` | 资产位置树 | - | application/json: - |

### 运维记录费用与通用计费规则

2026-09-24更新：[按次施工报价、通用附加费用及多币种结果](maintenance-billing.md)。客户管理已移除报价字段，记录界面提供工程师规则或自定义，自定义支持一口价（fixed）和本次工程师单价微调（hourly）；计划仍可选择一口价或工程师规则。默认使用工程师规则，不修改工程师档案。附加费用使用 `billing_rules.additional_fees`，实际时长和本次免收项使用 `billing_context.additional_fee_minutes` / `excluded_fee_ids`。多币种结果使用`totals`，不能仅通过`total:null`判断待确认。下述紧急维护、交通及商务条款字段仅用于历史兼容，新工程师界面不再提供。

- 工程师 `POST /api/v1/remote-assistance/engineers`、`PUT /api/v1/remote-assistance/engineers/{engineer_id}` 的 `billing_rules` 支持通用模式 `mode: general`。省略保持原规则，null清除；旧小时阶梯和旧固定档位请求仍兼容。新建规则默认不填单价，不设地区、附加费用及夜班时段；前端参考模板功能已移除。
- 通用示例：`{"name":"示例工程师","billing_rules":{"mode":"general","currency":"GBP","pricing":"hourly","hourly_rate":"30.00","transport_mode":"hourly","commute_minutes":60}}`。2小时人工60 GBP，加一次通勤30 GBP，总计90 GBP。创建响应 `{"code":200,"msg":"工程师已创建","data":null}`；编辑响应 `{"code":200,"msg":"工程师已更新","data":null}`。概览 `GET /api/v1/remote-assistance/overview` 的 `data.engineers[].billing_rules` 返回完整规则。
- `pricing`：hourly固定小时单价、package按时长所在档位收固定总价、tiered_hourly按区间小时单价累加。对应 `hourly_rate`、`tiers:[{up_to_minutes,total_fee}]`、`hourly_tiers:[{up_to_minutes,hourly_rate}]`。package档位上限严格递增且价格不降低；tiered_hourly最后一档上限为null。最多20档。`minimum_minutes`为最低计费分钟，`billing_increment_minutes`为向上取整步长（默认1）。0分钟不产生费用。金额非负、最多两位小数，不同币种不自动换汇。
- package超出最后一档：`overtime_enabled`、`overtime_hourly_rate`、`overtime_threshold_minutes`（1–60）和`overtime_rounding`配置加班；未配置时超出档位显示待确认。取整支持half_hour_round（每小时余量达到阈值进一小时）、ceil_after_threshold（达到阈值后按小时向上取整）、actual_after_threshold（达到阈值后按实际分钟折算）。
- **所有到场、离场、计划时间的无偏移字符串均按北京时间UTC+8解释和返回**。含Z或UTC偏移的输入先转换为北京时间。`timezone`为该次运维所在地IANA时区，如Asia/Shanghai、Asia/Singapore、Asia/Seoul、America/Los_Angeles、America/New_York、Europe/Berlin、Europe/London；不改变实际时长，只决定当地时间和夜班时段。前端“到场/离场”快捷操作也使用北京时间，不依赖浏览器或服务器所在时区。历史无偏移数据不自动批量转换，应按已确认的录入口径核对。
- 夜班：`night_enabled`、`night_start`/`night_end`（当地HH:mm，可跨午夜）、`night_multiplier`（1–10）、`night_basis`（proportional按该收费区间实际夜班分钟占比分摊附加费；any_overlap该收费区间涉及夜班就对区间全额加价）。按UTC时间轴逐分钟换算当地时间，支持夏令时跳时、重复小时；不会使用固定偏移替代IANA时区。启用但时段未确认时保留规则、标记费用待确认。单次自动计费最多31天，超出需拆分记录。
- 紧急维护：`emergency_fee`、`emergency_response_minutes`、`emergency_regions`、`emergency_confirmation_regions`，覆盖地区留空表示不限地区，待确认区优先；地区按记录的地区名称精确匹配。`night_applies_to_emergency`默认false，即夜班加价后再加紧急费。未勾选本次紧急维护时不收紧急费；勾选但费用或区域未确认时不生成最终合计。
- 交通：`transport_mode`支持none、fixed（每次transport_fee）、hourly（每次commute_minutes工时费）、reimburse（本次实报实销）。通勤单价`commute_hourly_rate`留空时仅hourly模式沿用人工小时单价，其他模式须填写。`transport_included_regions`指定免交通费地区，留空表示每次收取。交通/通勤仅加一次，不增加运维工时、不参与夜班倍率。
- 商务条款：`project_services`配置单独报价服务；`settlement_cycles`可填日结、周结、月结、按次及自定义文字；`payment_methods`可配置多个自定义名称，字段name、note、tax_mode（none不另加税、included已含税、extra按约定税率另加、confirm待确认）、tax_rate（百分数，0–100，可空）、tax_base（labor人工费或subtotal人工+交通）。未选择已配置的收款方式、税费未确认时，不生成最终合计。`note`存放规则说明。地区、结算及收款名称不绑定国家。
- 地区报价示例仅保留为自动化测试数据，不作为产品内可选模板。

#### 费用试算接口

- `POST /api/v1/remote-assistance/billing/preview`，登录token必需，仅计算请求中提供的规则，不读取其他工程师或记录，因此不要求独立API授权。
- JSON示例：`{"rules":{"mode":"general","currency":"USD","pricing":"hourly","hourly_rate":"30.00","transport_mode":"fixed","transport_fee":"100.00"},"arrived_at":"2026-09-22T10:00","left_at":"2026-09-22T12:00","timezone":"Asia/Singapore","region":"新加坡","context":{"emergency":false,"service_type":"standard"}}`。
- 成功响应示意：`{"code":200,"msg":"OK","data":{"status":"calculated","currency":"USD","total":"160.00","subtotal":"160.00","work_minutes":120,"billable_minutes":120,"night_minutes":0,"timezone":"Asia/Singapore","local_arrived_at":"2026-09-22T10:00:00+08:00","local_left_at":"2026-09-22T12:00:00+08:00","lines":[{"label":"人工费（计费120分钟）","amount":"60.00"},{"label":"每次固定交通费","amount":"100.00"}],"notices":[]}}`。未知费用返回status=pending、total=null、notices说明，subtotal仅为已确认部分，不表示最终应付。
- context支持emergency、service_type（standard/project）、payment_method（规则中收款方式名称）、reimbursed_transport（已确认交通报销金额）。项目单独报价不套用工时规则。价格、时区、地区、起止时间与收款方式均由调用方明确提供。
- 无token为422，无效token为401；规则结构、时区无效为422；时间无法解析、倒序、跨度超限及业务条件不完整返回200且status=pending/total=null。模型限制与字段见同步的OpenAPI文档。

#### 运维记录与规则快照

- 记录创建 `POST /api/v1/remote-assistance/remote-hands`、更新 `PUT /api/v1/remote-assistance/remote-hands/{item_id}` 新增可选 `billing_context`（结构同试算context）和 `refresh_billing_rules`（默认false）。context省略或null保留已有上下文，传对象替换。更新仍按既有完整表单提交客户、工程师、时间等字段。
- 保存记录、完成计划生成记录时，后端根据本次`customer_pricing`、工程师规则、北京时间、时区、地区及context计算，保存`remote_hands.billing_data`，包含context、rules、customer_pricing、result。报价和现场费用经后端校验，客户端传入的最终合计不会被信任。工程师规则刷新不覆盖本次施工报价。计算在工作线程执行。
- 同一工程师的既有记录默认沿用已保存规则，改时间或context后重新计算；修改工程师使用新工程师规则。前端“采用工程师最新规则”对应refresh_billing_rules=true，保存后使用当前规则重新计算。直接修改工程师单价不会静默重算历史记录。
- 概览及完成计划响应的运维记录新增 `billing_context`、`billing_rules_snapshot`、`billing_result`，其他字段兼容。历史无快照记录按当前规则试算并标记 `billing_result.basis: current_rules`，只读查询不写回数据库。费用显示、明细提示、CSV导出均区分试算与已保存费用。未确认费用CSV金额为空，并附计费说明。导出覆盖当前筛选的所有分页。
- 记录、工程师、计划接口继续沿用各方法/路由的角色权限；无权限403，模型校验422，既有业务失败响应code400。费用计算不会自动创建账单或改变结算状态。
- 部署前运行 `aerich upgrade`，应用 `176_20260922120000_remote_billing_snapshot.py`（新增可空JSONB字段，无历史金额回填）；原工程师规则字段迁移175仍需已应用。回滚176会删除保存的规则及费用快照。迁移测试使用独立内存库，未改动运行数据库。

### 运维记录模块

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `POST` | `/api/v1/remote-assistance/engineers` | 新增工程师 | application/json: EngineerPayload | application/json: - |
| `PUT` | `/api/v1/remote-assistance/engineers/{engineer_id}` | 更新工程师 | application/json: EngineerPayload | application/json: - |
| `DELETE` | `/api/v1/remote-assistance/engineers/{engineer_id}` | 删除工程师 | - | application/json: - |
| `GET` | `/api/v1/remote-assistance/overview` | 运维记录页面数据 | - | application/json: - |
| `POST` | `/api/v1/remote-assistance/remote-hands` | 新增运维记录 | application/json: RemoteHandsPayload | application/json: - |
| `PUT` | `/api/v1/remote-assistance/remote-hands/{item_id}` | 更新运维记录 | application/json: RemoteHandsPayload | application/json: - |
| `DELETE` | `/api/v1/remote-assistance/remote-hands/{item_id}` | 删除运维记录 | - | application/json: - |

### 部门模块

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `POST` | `/api/v1/dept/create` | 创建部门 | application/json: DeptCreate | application/json: - |
| `DELETE` | `/api/v1/dept/delete` | 删除部门 | - | application/json: - |
| `GET` | `/api/v1/dept/get` | 查看部门 | - | application/json: - |
| `GET` | `/api/v1/dept/list` | 查看部门列表 | - | application/json: - |
| `POST` | `/api/v1/dept/update` | 更新部门 | application/json: DeptUpdate | application/json: - |

### 银行模块

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `POST` | `/api/v1/bank/create` | 创建银行 | application/json: BankCreate | application/json: - |
| `DELETE` | `/api/v1/bank/delete` | 删除银行 | - | application/json: - |
| `GET` | `/api/v1/bank/list` | 查看银行列表 | - | application/json: - |
| `POST` | `/api/v1/bank/update` | 更新银行 | application/json: BankUpdate | application/json: - |

### 银行账户模块

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `POST` | `/api/v1/bank_account/create` | 创建银行账户 | application/json: BankAccountCreate | application/json: - |
| `DELETE` | `/api/v1/bank_account/delete` | 删除银行账户 | - | application/json: - |
| `GET` | `/api/v1/bank_account/list` | 查看银行账户列表 | - | application/json: - |
| `POST` | `/api/v1/bank_account/update` | 更新银行账户 | application/json: BankAccountUpdate | application/json: - |

## 接口明细

### API文档

#### `GET /api/v1/api/docs`

- 摘要：公开API文档
- Operation ID：`get_api_docs_api_v1_api_docs_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| path | query | 否 | string | API路径 |
| method | query | 否 | string | 请求方式 |
| tags | query | 否 | string | API模块 |
| include_public | query | 否 | boolean | 是否包含无需权限的公开接口 |

### API模块

#### `POST /api/v1/api/create`

- 摘要：创建Api
- Operation ID：`create_api_api_v1_api_create_post`
- Request Body：application/json: ApiCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/api/delete`

- 摘要：删除Api
- Operation ID：`delete_api_api_v1_api_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| api_id | query | 是 | integer | ApiID |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/api/get`

- 摘要：查看Api
- Operation ID：`get_api_api_v1_api_get_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| id | query | 是 | integer | Api |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/api/list`

- 摘要：查看API列表
- Operation ID：`list_api_api_v1_api_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| page | query | 否 | integer | 页码 |
| page_size | query | 否 | integer | 每页数量 |
| path | query | 否 | string | API路径 |
| summary | query | 否 | string | API简介 |
| tags | query | 否 | string | API模块 |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/api/refresh`

- 摘要：刷新API列表
- Operation ID：`refresh_api_api_v1_api_refresh_post`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/api/update`

- 摘要：更新Api
- Operation ID：`update_api_api_v1_api_update_post`
- Request Body：application/json: ApiUpdate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

### Akvorado

#### `GET /api/v1/akvorado/proxy/{region}/{path}`

- 摘要：Proxy Akvorado region UI
- Operation ID：`akvorado_proxy_api_v1_akvorado_proxy__region___path__get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| region | path | 是 | string |  |
| path | path | 是 | string |  |
| token | query | 否 | string |  |

#### `POST /api/v1/akvorado/proxy/{region}/{path}`

- 摘要：Proxy Akvorado region UI
- Operation ID：`akvorado_proxy_api_v1_akvorado_proxy__region___path__get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| region | path | 是 | string |  |
| path | path | 是 | string |  |
| token | query | 否 | string |  |

#### `PUT /api/v1/akvorado/proxy/{region}/{path}`

- 摘要：Proxy Akvorado region UI
- Operation ID：`akvorado_proxy_api_v1_akvorado_proxy__region___path__get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| region | path | 是 | string |  |
| path | path | 是 | string |  |
| token | query | 否 | string |  |

#### `PATCH /api/v1/akvorado/proxy/{region}/{path}`

- 摘要：Proxy Akvorado region UI
- Operation ID：`akvorado_proxy_api_v1_akvorado_proxy__region___path__get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| region | path | 是 | string |  |
| path | path | 是 | string |  |
| token | query | 否 | string |  |

#### `DELETE /api/v1/akvorado/proxy/{region}/{path}`

- 摘要：Proxy Akvorado region UI
- Operation ID：`akvorado_proxy_api_v1_akvorado_proxy__region___path__get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| region | path | 是 | string |  |
| path | path | 是 | string |  |
| token | query | 否 | string |  |

#### `OPTIONS /api/v1/akvorado/proxy/{region}/{path}`

- 摘要：Proxy Akvorado region UI
- Operation ID：`akvorado_proxy_api_v1_akvorado_proxy__region___path__get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| region | path | 是 | string |  |
| path | path | 是 | string |  |
| token | query | 否 | string |  |

### NetBox IPAM

#### `GET /api/v1/netbox/ipam/filter-options`

- 摘要：NetBox IPAM filter options
- Operation ID：`ipam_filter_options_api_v1_netbox_ipam_filter_options_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| search | query | 否 | string |  |
| family | query | 否 | integer | null |  |
| status | query | 否 | string |  |
| refresh | query | 否 | boolean |  |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/netbox/ipam/filter-options`

- 摘要：NetBox IPAM filter options
- Operation ID：`ipam_filter_options_api_v1_netbox_ipam_filter_options_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| search | query | 否 | string |  |
| family | query | 否 | integer | null |  |
| status | query | 否 | string |  |
| refresh | query | 否 | boolean |  |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/netbox/ipam/ip-addresses`

- 摘要：Create NetBox IP address
- Operation ID：`create_ip_address_api_v1_netbox_ipam_ip_addresses_post`
- Request Body：application/json: object
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/netbox/ipam/ip-addresses`

- 摘要：Create NetBox IP address
- Operation ID：`create_ip_address_api_v1_netbox_ipam_ip_addresses_post`
- Request Body：application/json: object
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `PATCH /api/v1/netbox/ipam/ip-addresses/{ip_id}`

- 摘要：Update NetBox IP address
- Operation ID：`update_ip_address_api_v1_netbox_ipam_ip_addresses__ip_id__patch`
- Request Body：application/json: object
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| ip_id | path | 是 | integer |  |
| token | header | 是 | string | token验证 |

#### `PATCH /api/v1/netbox/ipam/ip-addresses/{ip_id}`

- 摘要：Update NetBox IP address
- Operation ID：`update_ip_address_api_v1_netbox_ipam_ip_addresses__ip_id__patch`
- Request Body：application/json: object
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| ip_id | path | 是 | integer |  |
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/netbox/ipam/ip-addresses/{ip_id}`

- 摘要：Delete NetBox IP address
- Operation ID：`delete_ip_address_api_v1_netbox_ipam_ip_addresses__ip_id__delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| ip_id | path | 是 | integer |  |
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/netbox/ipam/ip-addresses/{ip_id}`

- 摘要：Delete NetBox IP address
- Operation ID：`delete_ip_address_api_v1_netbox_ipam_ip_addresses__ip_id__delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| ip_id | path | 是 | integer |  |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/netbox/ipam/overview`

- 摘要：NetBox IPAM overview
- Operation ID：`ipam_overview_api_v1_netbox_ipam_overview_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| search | query | 否 | string |  |
| family | query | 否 | integer | null |  |
| status | query | 否 | string |  |
| region | query | 否 | string |  |
| customer | query | 否 | string |  |
| supplier | query | 否 | string |  |
| page | query | 否 | integer |  |
| page_size | query | 否 | integer |  |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/netbox/ipam/overview`

- 摘要：NetBox IPAM overview
- Operation ID：`ipam_overview_api_v1_netbox_ipam_overview_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| search | query | 否 | string |  |
| family | query | 否 | integer | null |  |
| status | query | 否 | string |  |
| region | query | 否 | string |  |
| customer | query | 否 | string |  |
| supplier | query | 否 | string |  |
| page | query | 否 | integer |  |
| page_size | query | 否 | integer |  |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/netbox/ipam/prefix-ips`

- 摘要：NetBox IPAM prefix IP list
- Operation ID：`ipam_prefix_ips_api_v1_netbox_ipam_prefix_ips_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| prefix | query | 是 | string |  |
| prefix_id | query | 否 | string |  |
| page | query | 否 | integer |  |
| page_size | query | 否 | integer |  |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/netbox/ipam/prefix-ips`

- 摘要：NetBox IPAM prefix IP list
- Operation ID：`ipam_prefix_ips_api_v1_netbox_ipam_prefix_ips_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| prefix | query | 是 | string |  |
| prefix_id | query | 否 | string |  |
| page | query | 否 | integer |  |
| page_size | query | 否 | integer |  |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/netbox/ipam/prefix-options`

- 摘要：NetBox prefix edit options
- Operation ID：`prefix_options_api_v1_netbox_ipam_prefix_options_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `GET /api/v1/netbox/ipam/prefix-options`

- 摘要：NetBox prefix edit options
- Operation ID：`prefix_options_api_v1_netbox_ipam_prefix_options_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/netbox/ipam/prefixes`

- 摘要：Create NetBox prefix
- Operation ID：`create_prefix_api_v1_netbox_ipam_prefixes_post`
- Request Body：application/json: object
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/netbox/ipam/prefixes`

- 摘要：Create NetBox prefix
- Operation ID：`create_prefix_api_v1_netbox_ipam_prefixes_post`
- Request Body：application/json: object
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `PATCH /api/v1/netbox/ipam/prefixes/{prefix_id}`

- 摘要：Update NetBox prefix
- Operation ID：`update_prefix_api_v1_netbox_ipam_prefixes__prefix_id__patch`
- Request Body：application/json: object
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| prefix_id | path | 是 | integer |  |
| token | header | 是 | string | token验证 |

#### `PATCH /api/v1/netbox/ipam/prefixes/{prefix_id}`

- 摘要：Update NetBox prefix
- Operation ID：`update_prefix_api_v1_netbox_ipam_prefixes__prefix_id__patch`
- Request Body：application/json: object
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| prefix_id | path | 是 | integer |  |
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/netbox/ipam/prefixes/{prefix_id}`

- 摘要：Delete NetBox prefix
- Operation ID：`delete_prefix_api_v1_netbox_ipam_prefixes__prefix_id__delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| prefix_id | path | 是 | integer |  |
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/netbox/ipam/prefixes/{prefix_id}`

- 摘要：Delete NetBox prefix
- Operation ID：`delete_prefix_api_v1_netbox_ipam_prefixes__prefix_id__delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| prefix_id | path | 是 | integer |  |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/netbox/ipam/sync-pve-ips`

- 摘要：Schedule PVE guest-agent IP sync to NetBox
- Operation ID：`sync_pve_ips_to_netbox_api_v1_netbox_ipam_sync_pve_ips_post`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/netbox/ipam/sync-pve-ips`

- 摘要：Schedule PVE guest-agent IP sync to NetBox
- Operation ID：`sync_pve_ips_to_netbox_api_v1_netbox_ipam_sync_pve_ips_post`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/netbox/ipam/sync-pve-ips/run-now`

- 摘要：Run PVE IP sync immediately
- Operation ID：`run_pve_ip_sync_now_api_v1_netbox_ipam_sync_pve_ips_run_now_post`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| node | query | 否 | string |  |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/netbox/ipam/sync-pve-ips/run-now`

- 摘要：Run PVE IP sync immediately
- Operation ID：`run_pve_ip_sync_now_api_v1_netbox_ipam_sync_pve_ips_run_now_post`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| node | query | 否 | string |  |
| token | header | 是 | string | token验证 |

### PVE Datacenter模块

#### `GET /api/v1/pve/nodes`

- 摘要：PDM remote list
- Operation ID：`list_nodes_api_v1_pve_nodes_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/pve/nodes/add`

- 摘要：Add PVE remote to PDM
- Operation ID：`add_pve_remote_api_v1_pve_nodes_add_post`
- Request Body：application/json: PDMAddRemoteRequest
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/pve/nodes/probe`

- 摘要：Probe PVE remote TLS
- Operation ID：`probe_pve_remote_api_v1_pve_nodes_probe_post`
- Request Body：application/json: PDMProbeRemoteRequest
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `GET /api/v1/pve/nodes/realms`

- 摘要：PVE remote realms
- Operation ID：`pve_remote_realms_api_v1_pve_nodes_realms_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| hostname | query | 是 | string |  |
| fingerprint | query | 否 | string |  |
| token | header | 是 | string | token验证 |

#### `PUT /api/v1/pve/nodes/remote/{remote}`

- 摘要：Update PVE remote
- Operation ID：`update_pve_remote_api_v1_pve_nodes_remote__remote__put`
- Request Body：application/json: PDMUpdateRemoteRequest
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| remote | path | 是 | string |  |
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/pve/nodes/remote/{remote}`

- 摘要：Delete PVE remote
- Operation ID：`delete_pve_remote_api_v1_pve_nodes_remote__remote__delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| remote | path | 是 | string |  |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/pve/nodes/remote/{remote}/remark`

- 摘要：Read PVE node remark
- Operation ID：`get_pve_remote_remark_api_v1_pve_nodes_remote__remote__remark_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| remote | path | 是 | string |  |
| host | query | 否 | string |  |
| token | header | 是 | string | token验证 |

#### `PUT /api/v1/pve/nodes/remote/{remote}/remark`

- 摘要：Update PVE node remark
- Operation ID：`update_pve_remote_remark_api_v1_pve_nodes_remote__remote__remark_put`
- Request Body：application/json: PDMRemoteRemarkRequest
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| remote | path | 是 | string |  |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/pve/tasks/status`

- 摘要：PDM remote task status
- Operation ID：`task_status_api_v1_pve_tasks_status_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| upid | query | 是 | string |  |
| remote | query | 否 | string |  |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/pve/vms`

- 摘要：PDM virtual machine list
- Operation ID：`list_vms_api_v1_pve_vms_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| node | query | 否 | string |  |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/pve/vms/config`

- 摘要：Read PVE virtual machine core config
- Operation ID：`vm_config_api_v1_pve_vms_config_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| remote | query | 是 | string |  |
| vmid | query | 是 | integer |  |
| type | query | 否 | string |  |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/pve/vms/config`

- 摘要：Update PVE virtual machine core config
- Operation ID：`update_vm_config_api_v1_pve_vms_config_post`
- Request Body：application/json: VMConfigUpdateRequest
- Response：application/json: -

网卡更新：`networks` 为按 `key`（如 `net1`）更新的增量列表，未提交的网卡保持不变。
已有网卡仅更新明确传入的字段；省略字段保留原值，`vlan`、`mtu`、`rate` 传 `null` 清除对应设置，
`firewall: false` 关闭防火墙。保留 MAC 地址及页面未展示的 PVE 参数（如 `queues`、`link_down`、`trunks`）。
仅字段顺序、显式默认值等表示不同不会触发网卡更新。无 `key` 为新增，`{ "key": "net1", "delete": true }` 为删除。
客户端保存新增网卡后应重新读取配置，取得 PVE 分配的网卡编号及 MAC，避免再次保存时重复新增。

请求示例（只修改 `net1` 的网桥）：

```json
{"remote":"pve-a","vmid":100,"networks":[{"key":"net1","bridge":"vmbr20"}]}
```

成功响应示例：`{"code":200,"msg":"虚拟机配置已更新，部分配置需重启虚拟机后生效","data":null}`。
权限：有效 `token`，并具有该路由的 POST 权限（管理员按既有鉴权规则放行）。
错误码：400（非 QEMU、配置读取或保存失败）、401（认证失败）、403（无接口权限）、422（请求字段校验失败）。

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/pve/vms/create`

- 摘要：PVE virtual machine create
- Operation ID：`create_vm_api_v1_pve_vms_create_post`
- Request Body：application/json: VMCreateRequest
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `GET /api/v1/pve/vms/create-options`

- 摘要：PVE virtual machine create options
- Operation ID：`create_options_api_v1_pve_vms_create_options_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| node_ip | query | 是 | string | PVE node IP or PDM remote name |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/pve/vms/delete`

请求参数与权限保持不变：有效 `token`，具备该接口 POST 权限；请求包含 `remote`、`vmid`，可附带 `type`、`node`、`status`、`name`。
服务端最多等待 240 秒确认 PVE 任务完成，客户端请求超时为 300 秒。
仅 PVE 任务结果为 `OK` 时返回成功：

```json
{"code":200,"msg":"虚拟机删除完成","data":{"remote":"pve-a","vmid":100,"deleted":true}}
```

失败返回 HTTP 400，例如 `{"code":400,"msg":"删除虚拟机失败: VM is locked","data":null}`。
前端显示错误并保留列表记录；超时或查询失败不代表 PVE 任务已停止，应稍后刷新核实。
其他错误码：401（认证失败）、403（无接口权限）、422（请求校验失败）。

- 摘要：Delete PDM virtual machine
- Operation ID：`delete_vm_api_v1_pve_vms_delete_post`
- Request Body：application/json: VMDeleteRequest
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `GET /api/v1/pve/vms/ips`

- 摘要：PVE virtual machine guest-agent IP list
- Operation ID：`list_vm_ips_api_v1_pve_vms_ips_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| node | query | 否 | string |  |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/pve/vms/migrate`

- 摘要：PDM virtual machine remote migration
- Operation ID：`migrate_vm_api_v1_pve_vms_migrate_post`
- Request Body：application/json: VMMigrateRequest
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `GET /api/v1/pve/vms/migration-options`

- 摘要：PDM virtual machine migration options
- Operation ID：`migration_options_api_v1_pve_vms_migration_options_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| remote | query | 是 | string |  |
| vmid | query | 是 | integer |  |
| type | query | 否 | string |  |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/pve/vms/novnc`

- 摘要：PDM virtual machine noVNC console
- Operation ID：`novnc_console_api_v1_pve_vms_novnc_post`
- Request Body：application/json: NoVNCRequest
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/pve/vms/power`

- 摘要：Start or shutdown PDM virtual machine
- Operation ID：`power_vm_api_v1_pve_vms_power_post`
- Request Body：application/json: VMPowerRequest
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/pve/vms/reboot`

- 摘要：Reboot PVE virtual machine
- Operation ID：`reboot_vm_api_v1_pve_vms_reboot_post`
- Request Body：application/json: VMDeleteRequest
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

### PVE Grafana

#### `GET /api/v1/pve/grafana/proxy/{path}`

- 摘要：Proxy Grafana with service account token
- Operation ID：`grafana_proxy_api_v1_pve_grafana_proxy__path__get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| path | path | 是 | string |  |
| token | query | 否 | string |  |

#### `POST /api/v1/pve/grafana/proxy/{path}`

- 摘要：Proxy Grafana with service account token
- Operation ID：`grafana_proxy_api_v1_pve_grafana_proxy__path__get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| path | path | 是 | string |  |
| token | query | 否 | string |  |

#### `PUT /api/v1/pve/grafana/proxy/{path}`

- 摘要：Proxy Grafana with service account token
- Operation ID：`grafana_proxy_api_v1_pve_grafana_proxy__path__get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| path | path | 是 | string |  |
| token | query | 否 | string |  |

#### `PATCH /api/v1/pve/grafana/proxy/{path}`

- 摘要：Proxy Grafana with service account token
- Operation ID：`grafana_proxy_api_v1_pve_grafana_proxy__path__get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| path | path | 是 | string |  |
| token | query | 否 | string |  |

#### `DELETE /api/v1/pve/grafana/proxy/{path}`

- 摘要：Proxy Grafana with service account token
- Operation ID：`grafana_proxy_api_v1_pve_grafana_proxy__path__get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| path | path | 是 | string |  |
| token | query | 否 | string |  |

#### `OPTIONS /api/v1/pve/grafana/proxy/{path}`

- 摘要：Proxy Grafana with service account token
- Operation ID：`grafana_proxy_api_v1_pve_grafana_proxy__path__get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| path | path | 是 | string |  |
| token | query | 否 | string |  |

### Syslog日志管理模块

#### `GET /api/v1/syslog/devices`

- 摘要：Syslog 设备目录
- Operation ID：`list_syslog_devices_api_v1_syslog_devices_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `GET /api/v1/syslog/files`

- 摘要：Syslog 日志文件列表
- Operation ID：`list_syslog_files_api_v1_syslog_files_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| device | query | 是 | string |  |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/syslog/logs`

- 摘要：Syslog 日志查询
- Operation ID：`query_syslog_logs_api_v1_syslog_logs_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| page | query | 否 | integer |  |
| page_size | query | 否 | integer |  |
| device | query | 是 | string |  |
| file | query | 是 | string |  |
| keyword | query | 否 | string |  |
| level | query | 否 | string |  |
| vendor | query | 否 | string |  |
| tail | query | 否 | integer |  |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/syslog/raw`

- 摘要：Syslog 原始日志
- Operation ID：`get_syslog_raw_api_v1_syslog_raw_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| device | query | 是 | string |  |
| file | query | 是 | string |  |
| tail | query | 否 | integer |  |
| token | header | 是 | string | token验证 |

### 仪表盘模块

#### `GET /api/v1/ticket/dashboard`

- 摘要：工单仪表盘
- Operation ID：`ticket_dashboard_api_v1_ticket_dashboard_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

### 供应商模块

#### `POST /api/v1/vendor/create`

- 摘要：创建供应商
- Operation ID：`create_vendor_api_v1_vendor_create_post`
- Request Body：application/json: VendorCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/vendor/delete`

- 摘要：删除供应商
- Operation ID：`delete_vendor_api_v1_vendor_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| vendor_id | query | 是 | integer | 供应商ID |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/vendor/export`

- 摘要：导出供应商
- Operation ID：`export_vendor_api_v1_vendor_export_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `GET /api/v1/vendor/get`

- 摘要：查看供应商
- Operation ID：`get_vendor_api_v1_vendor_get_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| vendor_id | query | 是 | integer | 供应商ID |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/vendor/import`

- 摘要：导入供应商
- Operation ID：`import_vendor_api_v1_vendor_import_post`
- Request Body：multipart/form-data: Body_import_vendor_api_v1_vendor_import_post
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `GET /api/v1/vendor/list`

- 摘要：查看供应商列表
- Operation ID：`list_vendor_api_v1_vendor_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| page | query | 否 | integer | 页码 |
| page_size | query | 否 | integer | 每页数量 |
| name | query | 否 | string | 供应商名称，用于搜索 |
| code | query | 否 | string | 供应商编号 |
| status | query | 否 | boolean | null | 启用状态 |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/vendor/update`

- 摘要：更新供应商
- Operation ID：`update_vendor_api_v1_vendor_update_post`
- Request Body：application/json: VendorUpdate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

### 公司模块

#### `POST /api/v1/company/create`

- 摘要：创建公司
- Operation ID：`create_company_api_v1_company_create_post`
- Request Body：application/json: CompanyCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/company/delete`

- 摘要：删除公司
- Operation ID：`delete_company_api_v1_company_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| company_id | query | 是 | integer | 公司ID |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/company/get`

- 摘要：查看公司
- Operation ID：`get_company_api_v1_company_get_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| company_id | query | 是 | integer | 公司ID |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/company/list`

- 摘要：查看公司列表
- Operation ID：`list_company_api_v1_company_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| page | query | 否 | integer | 页码 |
| page_size | query | 否 | integer | 每页数量 |
| name | query | 否 | string | 公司简称/全称，用于搜索 |
| code | query | 否 | string | 公司编号 |
| role | query | 否 | integer | null | 角色：0=签约主体, 1=客户, 2=供应商, 3=客户+供应商 |
| status | query | 否 | boolean | null | 启用状态 |
| business_only | query | 否 | boolean | 仅查询客户和供应商 |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/company/update`

- 摘要：更新公司
- Operation ID：`update_company_api_v1_company_update_post`
- Request Body：application/json: CompanyUpdate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

### 基础模块

#### `POST /api/v1/base/access_token`

- 摘要：获取token
- Operation ID：`login_access_token_api_v1_base_access_token_post`
- Request Body：application/json: CredentialsSchema
- Response：application/json: -

参数：

无

#### `POST /api/v1/base/avatar`

- 摘要：上传当前用户头像
- Operation ID：`upload_user_avatar_api_v1_base_avatar_post`
- Request Body：application/json: UserAvatarUpload
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/base/profile`

- 摘要：更新当前用户信息
- Operation ID：`update_user_profile_api_v1_base_profile_post`
- Request Body：application/json: UserProfileUpdate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/base/update_password`

- 摘要：修改密码
- Operation ID：`update_user_password_api_v1_base_update_password_post`
- Request Body：application/json: UpdatePassword
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `GET /api/v1/base/userapi`

- 摘要：查看用户API
- Operation ID：`get_user_api_api_v1_base_userapi_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `GET /api/v1/base/userinfo`

- 摘要：查看用户信息
- Operation ID：`get_userinfo_api_v1_base_userinfo_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `GET /api/v1/base/usermenu`

- 摘要：查看用户菜单
- Operation ID：`get_user_menu_api_v1_base_usermenu_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

### 定时任务模块

#### `POST /api/v1/task/create`

- 摘要：创建定时任务
- Operation ID：`create_task_api_v1_task_create_post`
- Request Body：application/json: ScheduledTaskCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/task/delete`

- 摘要：删除定时任务
- Operation ID：`delete_task_api_v1_task_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| id | query | 是 | integer | 任务ID |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/task/get`

- 摘要：查看定时任务
- Operation ID：`get_task_api_v1_task_get_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| id | query | 是 | integer | 任务ID |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/task/list`

- 摘要：查看定时任务列表
- Operation ID：`list_task_api_v1_task_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| page | query | 否 | integer | 页码 |
| page_size | query | 否 | integer | 每页数量 |
| name | query | 否 | string | 任务名称 |
| task_type | query | 否 | string | 任务类型 |
| is_enabled | query | 否 | boolean | 是否启用 |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/task/logs`

- 摘要：查看定时任务执行日志
- Operation ID：`list_task_logs_api_v1_task_logs_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| page | query | 否 | integer | 页码 |
| page_size | query | 否 | integer | 每页数量 |
| task_id | query | 否 | integer | 任务ID |
| status | query | 否 | string | 执行状态 |
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/task/logs`

- 摘要：清理定时任务执行日志
- Operation ID：`clear_task_logs_api_v1_task_logs_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| task_id | query | 否 | integer | 任务ID |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/task/run`

- 摘要：手动执行定时任务
- Operation ID：`run_task_api_v1_task_run_post`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| id | query | 是 | integer | 任务ID |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/task/toggle`

- 摘要：启停定时任务
- Operation ID：`toggle_task_api_v1_task_toggle_post`
- Request Body：application/json: ScheduledTaskToggle
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/task/update`

- 摘要：更新定时任务
- Operation ID：`update_task_api_v1_task_update_post`
- Request Body：application/json: ScheduledTaskUpdate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

### 审计日志模块

#### `GET /api/v1/auditlog/list`

- 摘要：查看操作日志
- Operation ID：`get_audit_log_list_api_v1_auditlog_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| page | query | 否 | integer | 页码 |
| page_size | query | 否 | integer | 每页数量 |
| username | query | 否 | string | 操作人名称 |
| module | query | 否 | string | 功能模块 |
| method | query | 否 | string | 请求方法 |
| summary | query | 否 | string | 接口描述 |
| path | query | 否 | string | 请求路径 |
| status | query | 否 | integer | 状态码 |
| start_time | query | 否 | string | 开始时间 |
| end_time | query | 否 | string | 结束时间 |
| token | header | 是 | string | token验证 |

### 客户项目看板

#### `DELETE /api/v1/project/attachment/delete`

- 摘要：删除项目截图资料
- Operation ID：`delete_project_attachment_api_v1_project_attachment_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| attachment_id | query | 是 | integer | 附件ID |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/project/attachment/upload`

- 摘要：上传项目截图资料
- Operation ID：`upload_project_attachment_api_v1_project_attachment_upload_post`
- Request Body：application/json: ProjectAttachmentUpload
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/project/create`

- 摘要：创建客户项目
- Operation ID：`create_project_api_v1_project_create_post`
- Request Body：application/json: CustomerProjectCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/project/delete`

- 摘要：删除客户项目
- Operation ID：`delete_project_api_v1_project_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| project_id | query | 是 | integer | 项目ID |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/project/discussion/create`

- 摘要：新增项目讨论
- Operation ID：`create_project_discussion_api_v1_project_discussion_create_post`
- Request Body：application/json: ProjectDiscussionCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/project/discussion/delete`

- 摘要：删除项目讨论
- Operation ID：`delete_project_discussion_api_v1_project_discussion_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| discussion_id | query | 是 | integer | 讨论ID |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/project/get`

- 摘要：查看客户项目
- Operation ID：`get_project_api_v1_project_get_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| project_id | query | 是 | integer | 项目ID |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/project/list`

- 摘要：查看客户项目列表
- Operation ID：`list_project_api_v1_project_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| page | query | 否 | integer | 页码 |
| page_size | query | 否 | integer | 每页数量 |
| keyword | query | 否 | string | 项目名、编号、合同号或负责人 |
| customer_id | query | 否 | integer | null | 客户ID |
| status | query | 否 | string | 项目状态 |
| priority | query | 否 | string | 优先级 |
| health | query | 否 | string | 健康度 |
| owner | query | 否 | string | 负责人 |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/project/status`

- 摘要：更新客户项目看板状态
- Operation ID：`update_project_status_api_v1_project_status_post`
- Request Body：application/json: CustomerProjectStatusUpdate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/project/task/create`

- 摘要：创建项目任务
- Operation ID：`create_project_task_api_v1_project_task_create_post`
- Request Body：application/json: ProjectTaskCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/project/task/delete`

- 摘要：删除项目任务
- Operation ID：`delete_project_task_api_v1_project_task_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| task_id | query | 是 | integer | 任务ID |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/project/task/update`

- 摘要：更新项目任务
- Operation ID：`update_project_task_api_v1_project_task_update_post`
- Request Body：application/json: ProjectTaskUpdate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/project/update`

- 摘要：更新客户项目
- Operation ID：`update_project_api_v1_project_update_post`
- Request Body：application/json: CustomerProjectUpdate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

### 工单模块

#### `POST /api/v1/ticket/create`

- 摘要：创建工单
- Operation ID：`create_ticket_api_v1_ticket_create_post`
- Request Body：application/json: TicketCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/ticket/delete`

- 摘要：删除工单
- Operation ID：`delete_ticket_api_v1_ticket_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| ticket_id | query | 是 | integer | 工单ID |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/ticket/get`

- 摘要：查看工单详情
- Operation ID：`get_ticket_api_v1_ticket_get_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| ticket_id | query | 是 | integer | 工单ID |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/ticket/get_by_no`

- 摘要：根据工单编号查询工单
- Operation ID：`get_ticket_by_no_api_v1_ticket_get_by_no_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| ticket_no | query | 是 | string | 工单编号 |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/ticket/list`

- 摘要：查看工单列表
- Operation ID：`list_tickets_api_v1_ticket_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| page | query | 否 | integer | 页码 |
| page_size | query | 否 | integer | 每页数量 |
| title | query | 否 | string | 工单标题，用于搜索 |
| status | query | 否 | integer | null | 工单状态：0-已完成, 1-进行中, 2-未开始, 3-已关闭 |
| type | query | 否 | integer | null | 工单类型：0-故障工单, 1-服务请求, 2-维护工单 |
| user_id | query | 否 | integer | null | 用户ID |
| assignee_id | query | 否 | integer | null | 处理人ID |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/ticket/reply`

- 摘要：回复工单
- Operation ID：`create_ticket_reply_api_v1_ticket_reply_post`
- Request Body：application/json: TicketReplyCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/ticket/reply/create`

- 摘要：回复工单
- Operation ID：`create_ticket_reply_api_v1_ticket_reply_create_post`
- Request Body：application/json: TicketReplyCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `GET /api/v1/ticket/reply/list`

- 摘要：查看工单回复
- Operation ID：`list_ticket_replies_api_v1_ticket_reply_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| ticket_id | query | 是 | integer | 工单ID |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/ticket/reply_create`

- 摘要：回复工单
- Operation ID：`create_ticket_reply_api_v1_ticket_reply_create_post`
- Request Body：application/json: TicketReplyCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/ticket/send_email`

- 摘要：发送工单邮件通知
- Operation ID：`send_ticket_email_api_v1_ticket_send_email_post`
- Request Body：application/json: TicketEmailSend
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/ticket/update`

- 摘要：更新工单
- Operation ID：`update_ticket_api_v1_ticket_update_post`
- Request Body：application/json: TicketUpdate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/ticket/upload`

- 摘要：上传工单附件图片
- Operation ID：`upload_ticket_attachment_api_v1_ticket_upload_post`
- Request Body：application/json: TicketAttachmentUpload
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| ticket_id | query | 否 | integer | null | 工单ID |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/ticket/users`

- 摘要：查看工单用户选项
- Operation ID：`list_ticket_users_api_v1_ticket_users_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

### 报价系统

#### `POST /api/v1/finance/quote/create`

- 摘要：创建报价
- Operation ID：`create_quote_api_v1_finance_quote_create_post`
- Request Body：application/json: FinanceQuoteCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/finance/quote/delete`

- 摘要：删除报价
- Operation ID：`delete_quote_api_v1_finance_quote_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| quote_id | query | 是 | integer | 报价ID |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/finance/quote/field-options`

- 摘要：报价字段选项
- Operation ID：`list_field_options_api_v1_finance_quote_field_options_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| quote_type | query | 否 | string | 报价类型 |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/finance/quote/get`

- 摘要：查看报价
- Operation ID：`get_quote_api_v1_finance_quote_get_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| quote_id | query | 是 | integer | 报价ID |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/finance/quote/list`

- 摘要：查看报价列表
- Operation ID：`list_quote_api_v1_finance_quote_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| page | query | 否 | integer | 页码 |
| page_size | query | 否 | integer | 每页数量 |
| quote_type | query | 否 | string | 报价类型 |
| region | query | 否 | string | 地区 |
| status | query | 否 | integer | null | 状态 |
| keyword | query | 否 | string | 关键字 |
| sort_field | query | 否 | string | 排序字段 |
| sort_order | query | 否 | string | 排序方向 |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/finance/quote/site-options`

- 摘要：站点选项
- Operation ID：`list_site_options_api_v1_finance_quote_site_options_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| quote_type | query | 否 | string | 报价类型 |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/finance/quote/update`

- 摘要：更新报价
- Operation ID：`update_quote_api_v1_finance_quote_update_post`
- Request Body：application/json: FinanceQuoteUpdate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

### 用户模块

#### `POST /api/v1/user/create`

- 摘要：创建用户
- Operation ID：`create_user_api_v1_user_create_post`
- Request Body：application/json: UserCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/user/delete`

- 摘要：删除用户
- Operation ID：`delete_user_api_v1_user_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| user_id | query | 是 | integer | 用户ID |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/user/get`

- 摘要：查看用户
- Operation ID：`get_user_api_v1_user_get_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| user_id | query | 是 | integer | 用户ID |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/user/list`

- 摘要：查看用户列表
- Operation ID：`list_user_api_v1_user_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| page | query | 否 | integer | 页码 |
| page_size | query | 否 | integer | 每页数量 |
| username | query | 否 | string | 用户名称，用于搜索 |
| email | query | 否 | string | 邮箱地址 |
| dept_id | query | 否 | integer | 部门ID |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/user/reset_password`

- 摘要：重置密码
- Operation ID：`reset_password_api_v1_user_reset_password_post`
- Request Body：application/json: Body_reset_password_api_v1_user_reset_password_post
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/user/update`

- 摘要：更新用户
- Operation ID：`update_user_api_v1_user_update_post`
- Request Body：application/json: UserUpdate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

### 菜单模块

#### `POST /api/v1/menu/create`

- 摘要：创建菜单
- Operation ID：`create_menu_api_v1_menu_create_post`
- Request Body：application/json: MenuCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/menu/delete`

- 摘要：删除菜单
- Operation ID：`delete_menu_api_v1_menu_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| id | query | 是 | integer | 菜单id |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/menu/get`

- 摘要：查看菜单
- Operation ID：`get_menu_api_v1_menu_get_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| menu_id | query | 是 | integer | 菜单id |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/menu/list`

- 摘要：查看菜单列表
- Operation ID：`list_menu_api_v1_menu_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| page | query | 否 | integer | 页码 |
| page_size | query | 否 | integer | 每页数量 |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/menu/update`

- 摘要：更新菜单
- Operation ID：`update_menu_api_v1_menu_update_post`
- Request Body：application/json: MenuUpdate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

### 角色模块

#### `GET /api/v1/role/authorized`

- 摘要：查看角色权限
- Operation ID：`get_role_authorized_api_v1_role_authorized_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| id | query | 是 | integer | 角色ID |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/role/authorized`

- 摘要：更新角色权限
- Operation ID：`update_role_authorized_api_v1_role_authorized_post`
- Request Body：application/json: RoleUpdateMenusApis
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/role/create`

- 摘要：创建角色
- Operation ID：`create_role_api_v1_role_create_post`
- Request Body：application/json: RoleCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/role/delete`

- 摘要：删除角色
- Operation ID：`delete_role_api_v1_role_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| role_id | query | 是 | integer | 角色ID |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/role/get`

- 摘要：查看角色
- Operation ID：`get_role_api_v1_role_get_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| role_id | query | 是 | integer | 角色ID |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/role/list`

- 摘要：查看角色列表
- Operation ID：`list_role_api_v1_role_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| page | query | 否 | integer | 页码 |
| page_size | query | 否 | integer | 每页数量 |
| role_name | query | 否 | string | 角色名称，用于查询 |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/role/update`

- 摘要：更新角色
- Operation ID：`update_role_api_v1_role_update_post`
- Request Body：application/json: RoleUpdate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

### 账单模块

#### `POST /api/v1/bill/create`

- 摘要：创建账单
- Operation ID：`create_bill_api_v1_bill_create_post`
- Request Body：application/json: BillCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/bill/delete`

- 摘要：删除账单
- Operation ID：`delete_bill_api_v1_bill_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| bill_id | query | 是 | integer | 账单ID |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/bill/get`

- 摘要：查看账单
- Operation ID：`get_bill_api_v1_bill_get_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| bill_id | query | 是 | integer | 账单ID |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/bill/list`

- 摘要：查看账单列表
- Operation ID：`list_bill_api_v1_bill_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| page | query | 否 | integer | 页码 |
| page_size | query | 否 | integer | 每页数量 |
| company_id | query | 否 | integer | null | 公司ID |
| bill_type | query | 否 | integer | null | 账单类型(1客户/2供应商) |
| bill_month | query | 否 | string | null | 账单月份 |
| invoice_no | query | 否 | string | 账单编号 |
| customer_name | query | 否 | string | 客户/供应商名称 |
| is_settled | query | 否 | boolean | null | 是否结清 |
| sort_field | query | 否 | string | 排序字段 |
| sort_order | query | 否 | string | 排序方向 |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/bill/update`

- 摘要：更新账单
- Operation ID：`update_bill_api_v1_bill_update_post`
- Request Body：application/json: BillUpdate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/bill/upload_voucher`

- 摘要：上传付款凭证
- Operation ID：`upload_payment_voucher_api_v1_bill_upload_voucher_post`
- Request Body：multipart/form-data: Body_upload_payment_voucher_api_v1_bill_upload_voucher_post
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| bill_id | query | 是 | integer | 账单ID |
| token | header | 是 | string | token验证 |

### 资产管理模块

#### `POST /api/v1/asset/cabinet/create`

- 摘要：创建机柜
- Operation ID：`create_cabinet_api_v1_asset_cabinet_create_post`
- Request Body：application/json: AssetCabinetCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/asset/cabinet/delete`

- 摘要：删除机柜
- Operation ID：`delete_cabinet_api_v1_asset_cabinet_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| cabinet_id | query | 是 | integer |  |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/asset/cabinet/get`

- 摘要：机柜详情
- Operation ID：`get_cabinet_api_v1_asset_cabinet_get_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| cabinet_id | query | 是 | integer |  |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/asset/cabinet/list`

- 摘要：机柜列表
- Operation ID：`list_cabinet_api_v1_asset_cabinet_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| page | query | 否 | integer |  |
| page_size | query | 否 | integer |  |
| location_id | query | 否 | integer | null |  |
| name | query | 否 | string |  |
| code | query | 否 | string |  |
| status | query | 否 | boolean | null |  |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/asset/cabinet/update`

- 摘要：更新机柜
- Operation ID：`update_cabinet_api_v1_asset_cabinet_update_post`
- Request Body：application/json: AssetCabinetUpdate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/asset/device-brand/create`

- 摘要：创建设备品牌
- Operation ID：`create_device_brand_api_v1_asset_device_brand_create_post`
- Request Body：application/json: AssetDeviceBrandCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/asset/device-brand/delete`

- 摘要：删除设备品牌
- Operation ID：`delete_device_brand_api_v1_asset_device_brand_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| brand_id | query | 是 | integer |  |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/asset/device-brand/list`

- 摘要：设备品牌型号列表
- Operation ID：`list_device_brands_api_v1_asset_device_brand_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/asset/device-model/create`

- 摘要：创建设备型号
- Operation ID：`create_device_model_api_v1_asset_device_model_create_post`
- Request Body：application/json: AssetDeviceModelCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/asset/device-model/delete`

- 摘要：删除设备型号
- Operation ID：`delete_device_model_api_v1_asset_device_model_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| model_id | query | 是 | integer |  |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/asset/device/create`

- 摘要：创建设备
- Operation ID：`create_device_api_v1_asset_device_create_post`
- Request Body：application/json: AssetDeviceCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/asset/device/delete`

- 摘要：删除设备
- Operation ID：`delete_device_api_v1_asset_device_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| device_id | query | 是 | integer |  |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/asset/device/get`

- 摘要：设备详情
- Operation ID：`get_device_api_v1_asset_device_get_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| device_id | query | 是 | integer |  |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/asset/device/list`

- 摘要：设备列表
- Operation ID：`list_device_api_v1_asset_device_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| page | query | 否 | integer |  |
| page_size | query | 否 | integer |  |
| region_id | query | 否 | integer | null |  |
| location_id | query | 否 | integer | null |  |
| cabinet_id | query | 否 | integer | null |  |
| keyword | query | 否 | string |  |
| type | query | 否 | integer | null |  |
| status | query | 否 | integer | null |  |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/asset/device/update`

- 摘要：更新设备
- Operation ID：`update_device_api_v1_asset_device_update_post`
- Request Body：application/json: AssetDeviceUpdate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/asset/inventory-category/create`

- 摘要：创建库存分类
- Operation ID：`create_inventory_category_api_v1_asset_inventory_category_create_post`
- Request Body：application/json: AssetInventoryCategoryCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/asset/inventory-category/delete`

- 摘要：删除库存分类
- Operation ID：`delete_inventory_category_api_v1_asset_inventory_category_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| category_id | query | 是 | integer |  |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/asset/inventory-category/list`

- 摘要：库存分类列表
- Operation ID：`list_inventory_categories_api_v1_asset_inventory_category_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/asset/inventory-category/update`

- 摘要：更新库存分类
- Operation ID：`update_inventory_category_api_v1_asset_inventory_category_update_post`
- Request Body：application/json: AssetInventoryCategoryUpdate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `GET /api/v1/asset/inventory-flow/list`

- 摘要：库存流水列表
- Operation ID：`list_inventory_flows_api_v1_asset_inventory_flow_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| page | query | 否 | integer |  |
| page_size | query | 否 | integer |  |
| inventory_id | query | 否 | integer | null |  |
| flow_type | query | 否 | string |  |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/asset/inventory-sale/cancel`

- 摘要：取消库存销售单
- Operation ID：`cancel_inventory_sale_api_v1_asset_inventory_sale_cancel_post`
- Request Body：application/json: AssetInventorySaleCancel
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/asset/inventory-sale/create`

- 摘要：创建库存销售单
- Operation ID：`create_inventory_sale_api_v1_asset_inventory_sale_create_post`
- Request Body：application/json: AssetInventorySaleCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `GET /api/v1/asset/inventory-sale/list`

- 摘要：库存销售单列表
- Operation ID：`list_inventory_sales_api_v1_asset_inventory_sale_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| page | query | 否 | integer |  |
| page_size | query | 否 | integer |  |
| keyword | query | 否 | string |  |
| status | query | 否 | integer | null |  |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/asset/inventory/create`

- 摘要：创建库存
- Operation ID：`create_inventory_api_v1_asset_inventory_create_post`
- Request Body：application/json: AssetInventoryCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/asset/inventory/delete`

- 摘要：删除库存
- Operation ID：`delete_inventory_api_v1_asset_inventory_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| inventory_id | query | 是 | integer |  |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/asset/inventory/export`

- 摘要：导出库存
- Operation ID：`export_inventory_api_v1_asset_inventory_export_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `GET /api/v1/asset/inventory/get`

- 摘要：库存详情
- Operation ID：`get_inventory_api_v1_asset_inventory_get_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| inventory_id | query | 是 | integer |  |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/asset/inventory/import`

- 摘要：导入库存
- Operation ID：`import_inventory_api_v1_asset_inventory_import_post`
- Request Body：multipart/form-data: Body_import_inventory_api_v1_asset_inventory_import_post
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `GET /api/v1/asset/inventory/list`

- 摘要：库存列表
- Operation ID：`list_inventory_api_v1_asset_inventory_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| page | query | 否 | integer |  |
| page_size | query | 否 | integer |  |
| region_id | query | 否 | integer | null |  |
| location_id | query | 否 | integer | null |  |
| keyword | query | 否 | string |  |
| type | query | 否 | string |  |
| subtype | query | 否 | string |  |
| status | query | 否 | boolean | null |  |
| only_low_stock | query | 否 | boolean |  |
| only_available | query | 否 | boolean |  |
| sort_by | query | 否 | string |  |
| sort_order | query | 否 | string |  |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/asset/inventory/update`

- 摘要：更新库存
- Operation ID：`update_inventory_api_v1_asset_inventory_update_post`
- Request Body：application/json: AssetInventoryUpdate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/asset/location/create`

- 摘要：创建位置
- Operation ID：`create_location_api_v1_asset_location_create_post`
- Request Body：application/json: AssetLocationCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/asset/location/delete`

- 摘要：删除位置
- Operation ID：`delete_location_api_v1_asset_location_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| location_id | query | 是 | integer |  |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/asset/location/list`

- 摘要：位置列表
- Operation ID：`list_location_api_v1_asset_location_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| page | query | 否 | integer |  |
| page_size | query | 否 | integer |  |
| region_id | query | 否 | integer | null |  |
| type | query | 否 | integer | null |  |
| name | query | 否 | string |  |
| status | query | 否 | boolean | null |  |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/asset/location/update`

- 摘要：更新位置
- Operation ID：`update_location_api_v1_asset_location_update_post`
- Request Body：application/json: AssetLocationUpdate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/asset/region/create`

- 摘要：创建区域
- Operation ID：`create_region_api_v1_asset_region_create_post`
- Request Body：application/json: AssetRegionCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/asset/region/delete`

- 摘要：删除区域
- Operation ID：`delete_region_api_v1_asset_region_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| region_id | query | 是 | integer |  |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/asset/region/get`

- 摘要：区域详情
- Operation ID：`get_region_api_v1_asset_region_get_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| region_id | query | 是 | integer |  |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/asset/region/list`

- 摘要：区域列表
- Operation ID：`list_region_api_v1_asset_region_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| page | query | 否 | integer |  |
| page_size | query | 否 | integer |  |
| name | query | 否 | string |  |
| code | query | 否 | string |  |
| status | query | 否 | boolean | null |  |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/asset/region/update`

- 摘要：更新区域
- Operation ID：`update_region_api_v1_asset_region_update_post`
- Request Body：application/json: AssetRegionUpdate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `GET /api/v1/asset/tree`

- 摘要：资产位置树
- Operation ID：`asset_tree_api_v1_asset_tree_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

### 运维记录模块

#### `POST /api/v1/remote-assistance/engineers`

- 摘要：新增工程师
- Operation ID：`create_engineer_api_v1_remote_assistance_engineers_post`
- Request Body：application/json: EngineerPayload
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `PUT /api/v1/remote-assistance/engineers/{engineer_id}`

- 摘要：更新工程师
- Operation ID：`update_engineer_api_v1_remote_assistance_engineers__engineer_id__put`
- Request Body：application/json: EngineerPayload
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| engineer_id | path | 是 | integer |  |
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/remote-assistance/engineers/{engineer_id}`

- 摘要：删除工程师
- Operation ID：`delete_engineer_api_v1_remote_assistance_engineers__engineer_id__delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| engineer_id | path | 是 | integer |  |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/remote-assistance/overview`

- 摘要：运维记录页面数据
- Operation ID：`overview_api_v1_remote_assistance_overview_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/remote-assistance/remote-hands`

- 摘要：新增运维记录
- Operation ID：`create_remote_hands_api_v1_remote_assistance_remote_hands_post`
- Request Body：application/json: RemoteHandsPayload
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `PUT /api/v1/remote-assistance/remote-hands/{item_id}`

- 摘要：更新运维记录
- Operation ID：`update_remote_hands_api_v1_remote_assistance_remote_hands__item_id__put`
- Request Body：application/json: RemoteHandsPayload
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| item_id | path | 是 | integer |  |
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/remote-assistance/remote-hands/{item_id}`

- 摘要：删除运维记录
- Operation ID：`delete_remote_hands_api_v1_remote_assistance_remote_hands__item_id__delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| item_id | path | 是 | integer |  |
| token | header | 是 | string | token验证 |

### 部门模块

#### `POST /api/v1/dept/create`

- 摘要：创建部门
- Operation ID：`create_dept_api_v1_dept_create_post`
- Request Body：application/json: DeptCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/dept/delete`

- 摘要：删除部门
- Operation ID：`delete_dept_api_v1_dept_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| dept_id | query | 是 | integer | 部门ID |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/dept/get`

- 摘要：查看部门
- Operation ID：`get_dept_api_v1_dept_get_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| id | query | 是 | integer | 部门ID |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/dept/list`

- 摘要：查看部门列表
- Operation ID：`list_dept_api_v1_dept_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| name | query | 否 | string | 部门名称 |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/dept/update`

- 摘要：更新部门
- Operation ID：`update_dept_api_v1_dept_update_post`
- Request Body：application/json: DeptUpdate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

### 银行模块

#### `POST /api/v1/bank/create`

- 摘要：创建银行
- Operation ID：`create_bank_api_v1_bank_create_post`
- Request Body：application/json: BankCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/bank/delete`

- 摘要：删除银行
- Operation ID：`delete_bank_api_v1_bank_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| bank_id | query | 是 | integer | 银行ID |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/bank/list`

- 摘要：查看银行列表
- Operation ID：`list_bank_api_v1_bank_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| page | query | 否 | integer | 页码 |
| page_size | query | 否 | integer | 每页数量 |
| name | query | 否 | string | 银行名称，用于搜索 |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/bank/update`

- 摘要：更新银行
- Operation ID：`update_bank_api_v1_bank_update_post`
- Request Body：application/json: BankUpdate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

### 银行账户模块

#### `POST /api/v1/bank_account/create`

- 摘要：创建银行账户
- Operation ID：`create_bank_account_api_v1_bank_account_create_post`
- Request Body：application/json: BankAccountCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/bank_account/delete`

- 摘要：删除银行账户
- Operation ID：`delete_bank_account_api_v1_bank_account_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| bank_account_id | query | 是 | integer | 银行账户ID |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/bank_account/list`

- 摘要：查看银行账户列表
- Operation ID：`list_bank_account_api_v1_bank_account_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| page | query | 否 | integer | 页码 |
| page_size | query | 否 | integer | 每页数量 |
| company_id | query | 是 | integer | 公司ID |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/bank_account/update`

- 摘要：更新银行账户
- Operation ID：`update_bank_account_api_v1_bank_account_update_post`
- Request Body：application/json: BankAccountUpdate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

## 数据模型索引

| 模型 | 类型 | 必填字段 | 字段 |
|---|---|---|---|
| `ApiCreate` | object | path, method, tags | path:string, summary:string, method:MethodType, tags:string |
| `ApiUpdate` | object | path, method, tags, id | path:string, summary:string, method:MethodType, tags:string, id:integer |
| `AssetCabinetCreate` | object | location_id, name | location_id:integer, name:string, code:string, row:string, column:string, capacity_u:integer, remark:string, status:boolean |
| `AssetCabinetUpdate` | object | location_id, name, id | location_id:integer, name:string, code:string, row:string, column:string, capacity_u:integer, remark:string, status:boolean, id:integer |
| `AssetDeviceBrandCreate` | object | name | name:string, sort:integer, status:boolean |
| `AssetDeviceCreate` | object | cabinet_id, asset_no, name | cabinet_id:integer, asset_no:string, name:string, type:integer, brand:string, model:string, serial_no:string, u_position:integer \| null, u_height:integer, status:integer, mgmt_ip:string, business_ip:string, owner:string, purchase_date:string \| null, warranty_expire:string \| null, attributes:object, remark:string |
| `AssetDeviceModelCreate` | object | brand_id, name | brand_id:integer, name:string, sort:integer, status:boolean |
| `AssetDeviceUpdate` | object | cabinet_id, asset_no, name, id | cabinet_id:integer, asset_no:string, name:string, type:integer, brand:string, model:string, serial_no:string, u_position:integer \| null, u_height:integer, status:integer, mgmt_ip:string, business_ip:string, owner:string, purchase_date:string \| null, warranty_expire:string \| null, attributes:object, remark:string, id:integer |
| `AssetInventoryCategoryCreate` | object | name | name:string, parent_id:integer \| null, sort:integer, status:boolean |
| `AssetInventoryCategoryUpdate` | object | name, id | name:string, parent_id:integer \| null, sort:integer, status:boolean, id:integer |
| `AssetInventoryCreate` | object | location_id, type | location_id:integer, type:string, subtype:string, quantity:integer, threshold:integer, cost_price:number, cost_price_currency:string, sale_price:number, sale_price_currency:string, attributes:object, remark:string, status:boolean |
| `AssetInventorySaleCancel` | object | id | id:integer, reason:string |
| `AssetInventorySaleCreate` | object | items | customer_name:string, customer_contact:string, sale_date:string \| null, remark:string, items:array[AssetInventorySaleItemIn] |
| `AssetInventorySaleItemIn` | object | inventory_id, quantity | inventory_id:integer, quantity:integer, unit_price:number, remark:string |
| `AssetInventoryUpdate` | object | location_id, type, id | location_id:integer, type:string, subtype:string, quantity:integer, threshold:integer, cost_price:number, cost_price_currency:string, sale_price:number, sale_price_currency:string, attributes:object, remark:string, status:boolean, id:integer |
| `AssetLocationCreate` | object | region_id, name | region_id:integer, name:string, type:integer, address:string, remark:string, status:boolean |
| `AssetLocationUpdate` | object | region_id, name, id | region_id:integer, name:string, type:integer, address:string, remark:string, status:boolean, id:integer |
| `AssetRegionCreate` | object | name, code | name:string, code:string, remark:string, status:boolean |
| `AssetRegionUpdate` | object | name, code, id | name:string, code:string, remark:string, status:boolean, id:integer |
| `BankAccountCreate` | object | company_id | company_id:integer, bank_id:integer \| null, bank_code:string, branch_code:string, account_name:string, account_number:string, swift_code:string, iban:string, sort_code:string, currency:string |
| `BankAccountUpdate` | object | id, company_id | id:integer, company_id:integer, bank_id:integer \| null, bank_code:string, branch_code:string, account_name:string, account_number:string, swift_code:string, iban:string, sort_code:string, currency:string |
| `BankCreate` | object | name | name:string, country:string, swift_code:string, bank_address:string |
| `BankUpdate` | object | id, name | id:integer, name:string, country:string, swift_code:string, bank_address:string |
| `BillCreate` | object | company_id | company_id:integer, invoice_no:string, customer_name:string, bill_month:string \| null, invoice_date:string \| null, due_date:string \| null, billing_start_date:string \| null, billing_end_date:string \| null, currency:string, net_amount:number \| null, vat_amount:number \| null, total_amount:number \| null, paid_amount:number \| null, unpaid_amount:number \| null, is_settled:boolean, payment_voucher_url:string, owner:string, remark:string, bill_type:integer, items:array[BillItemIn] |
| `BillItemIn` | object | - | id:integer \| null, service_id:string \| null, service:string \| null, item:string \| null, location:string \| null, start_date:string \| null, end_date:string \| null, nrc_amount:number \| null, mrc_amount:number \| null, amount:number \| null |
| `BillUpdate` | object | company_id, id | company_id:integer, invoice_no:string, customer_name:string, bill_month:string \| null, invoice_date:string \| null, due_date:string \| null, billing_start_date:string \| null, billing_end_date:string \| null, currency:string, net_amount:number \| null, vat_amount:number \| null, total_amount:number \| null, paid_amount:number \| null, unpaid_amount:number \| null, is_settled:boolean, payment_voucher_url:string, owner:string, remark:string, bill_type:integer, items:array[BillItemIn], id:integer |
| `Body_import_inventory_api_v1_asset_inventory_import_post` | object | file | file:string |
| `Body_import_vendor_api_v1_vendor_import_post` | object | file | file:string |
| `Body_reset_password_api_v1_user_reset_password_post` | object | user_id | user_id:integer |
| `Body_upload_payment_voucher_api_v1_bill_upload_voucher_post` | object | file | file:string |
| `CompanyCreate` | object | name | role:integer \| null, name:string, legal_name:string \| null, logo_url:string \| null, code:string \| null, country:string \| null, address:string \| null, noc_email:string \| null, noc_phone:string \| null, remark:string \| null, tax_no:string \| null, company_email:string \| null, bill_email:string \| null, contact_person:string \| null, company_phone:string \| null, registration_no:string \| null, contract_company_id:integer \| null, status:boolean |
| `CompanyUpdate` | object | id, name | id:integer, role:integer \| null, name:string, legal_name:string \| null, logo_url:string \| null, code:string \| null, country:string \| null, address:string \| null, noc_email:string \| null, noc_phone:string \| null, remark:string \| null, tax_no:string \| null, company_email:string \| null, bill_email:string \| null, contact_person:string \| null, company_phone:string \| null, registration_no:string \| null, contract_company_id:integer \| null, status:boolean |
| `CredentialsSchema` | object | username, password | username:string, password:string |
| `CustomerProjectCreate` | object | name | name:string, code:string \| null, customer_id:integer \| null, status:string, priority:string, health:string, owner:string \| null, contract_no:string \| null, start_date:string \| null, due_date:string \| null, progress:integer, budget_amount:number \| null, budget_currency:string, description:string \| null, sort_order:integer |
| `CustomerProjectStatusUpdate` | object | id, status | id:integer, status:string, sort_order:integer |
| `CustomerProjectUpdate` | object | name, id | name:string, code:string \| null, customer_id:integer \| null, status:string, priority:string, health:string, owner:string \| null, contract_no:string \| null, start_date:string \| null, due_date:string \| null, progress:integer, budget_amount:number \| null, budget_currency:string, description:string \| null, sort_order:integer, id:integer |
| `DeptCreate` | object | name | name:string, desc:string, order:integer, parent_id:integer |
| `DeptUpdate` | object | name, id | name:string, desc:string, order:integer, parent_id:integer, id:integer |
| `EngineerPayload` | object | - | name:string, contact:string, wechat_id:string, wechat_group:string, region:string, is_active:integer, note:string, billing_rules:GeneralBillingRules \| EngineerBillingRules \| MaintenanceBillingRules \| null |
| `FinanceQuoteCreate` | object | - | quote_type:string, service_resource:string, region:string, service_name:string, cpu_model:string, cpu_cores:string, memory:string, disk:string, bandwidth:string, burst:string, traffic:string, site_a:string, protection:string, xc_cabling:string, contract_terms:string, delivery_time:string, ip_count:string, provider:string, currency:string, nrc:number, mrc:number, usd_per_mbps_nrc:string, usd_per_mbps_mrc:number, cost_price:number, target_price:number, sale_price:number, status:integer, sort:integer, note:string, remark:string |
| `FinanceQuoteUpdate` | object | id | quote_type:string, service_resource:string, region:string, service_name:string, cpu_model:string, cpu_cores:string, memory:string, disk:string, bandwidth:string, burst:string, traffic:string, site_a:string, protection:string, xc_cabling:string, contract_terms:string, delivery_time:string, ip_count:string, provider:string, currency:string, nrc:number, mrc:number, usd_per_mbps_nrc:string, usd_per_mbps_mrc:number, cost_price:number, target_price:number, sale_price:number, status:integer, sort:integer, note:string, remark:string, id:integer |
| `HTTPValidationError` | object | - | detail:array[ValidationError] |
| `MenuCreate` | object | name, path, order | menu_type:MenuType, name:string, icon:string \| null, path:string, order:integer \| null, parent_id:integer \| null, is_hidden:boolean \| null, component:string, keepalive:boolean \| null, redirect:string \| null |
| `MenuType` | string | - | - |
| `MenuUpdate` | object | id, menu_type, name, path, order, parent_id, component | id:integer, menu_type:MenuType \| null, name:string \| null, icon:string \| null, path:string \| null, order:integer \| null, parent_id:integer \| null, is_hidden:boolean \| null, component:string, keepalive:boolean \| null, redirect:string \| null |
| `MethodType` | string | - | - |
| `NoVNCRequest` | object | remote, vmid | remote:string, vmid:integer, type:string, node:string \| null |
| `PDMAddRemoteRequest` | object | hostname | hostname:string, authid:string \| null, token:string \| null, fingerprint:string \| null, remote_id:string \| null, create_token:string \| null, web_url:string \| null |
| `PDMProbeRemoteRequest` | object | hostname | hostname:string, fingerprint:string \| null |
| `PDMRemoteRemarkRequest` | object | - | remark:string, host:string \| null |
| `PDMUpdateRemoteRequest` | object | hostname | hostname:string, fingerprint:string \| null, original_hostname:string \| null |
| `ProjectAttachmentUpload` | object | project_id, filename, content_type, data | project_id:integer, task_id:integer \| null, filename:string, content_type:string, data:string, remark:string \| null |
| `ProjectDiscussionCreate` | object | project_id, content | project_id:integer, content:string, task_id:integer \| null, attachment_id:integer \| null |
| `ProjectTaskCreate` | object | project_id, title | project_id:integer, title:string, assignee:string \| null, due_date:string \| null, is_done:boolean, sort_order:integer, remark:string \| null |
| `ProjectTaskUpdate` | object | project_id, title, id | project_id:integer, title:string, assignee:string \| null, due_date:string \| null, is_done:boolean, sort_order:integer, remark:string \| null, id:integer |
| `RemoteHandsPayload` | object | - | customer:string, ticket:string, engineer_id:integer \| null, engineer_name:string, engineer_contact:string, engineer_wechat:string, engineer_group:string, region:string, site:string, rack:string, timezone:string, arrived_at:string, left_at:string, work_minutes:integer, status:string, note:string |
| `RoleCreate` | object | name | name:string, desc:string |
| `RoleUpdate` | object | id, name | id:integer, name:string, desc:string |
| `RoleUpdateMenusApis` | object | id | id:integer, menu_ids:array[integer], api_infos:array[object] |
| `ScheduledTaskCreate` | object | name | name:string, task_type:string, script_path:string \| null, command:string \| null, schedule_type:string, day_of_week:integer \| null, hour:integer, minute:integer, interval_minutes:integer \| null, is_enabled:boolean |
| `ScheduledTaskToggle` | object | id, is_enabled | id:integer, is_enabled:boolean |
| `ScheduledTaskUpdate` | object | name, id | name:string, task_type:string, script_path:string \| null, command:string \| null, schedule_type:string, day_of_week:integer \| null, hour:integer, minute:integer, interval_minutes:integer \| null, is_enabled:boolean, id:integer |
| `TicketAttachmentUpload` | object | filename, content_type, data | filename:string, content_type:string, data:string |
| `TicketCreate` | object | title | title:string, type:integer, user_id:integer \| null, desc:string, location:string, start_time:string \| null, end_time:string \| null, attachment_url:string, assignee_id:integer \| null, completion_note:string \| null |
| `TicketEmailSend` | object | ticket_id | ticket_id:integer, user_ids:array[integer] |
| `TicketReplyCreate` | object | ticket_id, content | ticket_id:integer, content:string, parent_id:integer \| null, reply_to_ticket:boolean \| null |
| `TicketUpdate` | object | - | id:integer \| null, ticket_no:string \| null, title:string \| null, status:integer \| null, type:integer \| null, user_id:integer \| null, desc:string \| null, location:string \| null, start_time:string \| null, end_time:string \| null, attachment_url:string \| null, assignee_id:integer \| null, completion_note:string \| null |
| `UpdatePassword` | object | old_password, new_password | old_password:string, new_password:string |
| `UserAvatarUpload` | object | filename, content_type, data | filename:string, content_type:string, data:string |
| `UserCreate` | object | email, username, password | email:string, username:string, avatar:string \| null, password:string, is_active:boolean \| null, is_superuser:boolean \| null, role_ids:array[integer] \| null, dept_id:integer \| null |
| `UserProfileUpdate` | object | username, email | username:string, email:string, avatar:string \| null |
| `UserUpdate` | object | id, email, username | id:integer, email:string, username:string, avatar:string \| null, is_active:boolean \| null, is_superuser:boolean \| null, role_ids:array[integer] \| null, dept_id:integer \| null |
| `VMConfigUpdateRequest` | object | remote, vmid | remote:string, vmid:integer, type:string, node:string \| null, cores:integer \| null, memory_gb:number \| null, disk_gb:number \| null, disk_key:string \| null, networks:array[VMNetworkDeviceRequest] |
| `VMCreateRequest` | object | region, storage, vm_name, os_type, os_version, cpu_cores, memory_gb, disk_gb, password, network | region:string, storage:string, vm_name:string, description:string \| null, os_type:string, os_version:string, cpu_cores:integer, memory_gb:integer, disk_gb:integer, password:string, network:VMNetworkConfig |
| `VMDeleteRequest` | object | remote, vmid | remote:string, vmid:integer, type:string, node:string \| null, status:string \| null |
| `VMMigrateRequest` | object | remote, vmid, target, target_storage, target_bridge | remote:string, vmid:integer, type:string, target:string, target_vmid:integer \| null, target_storage:string, target_bridge:string, delete_source:boolean, online:boolean, bwlimit:integer \| null, node:string \| null, target_endpoint:string \| null |
| `VMNetworkConfig` | object | - | mode:string, ip:string \| null, mask:string \| null, dns:string \| null, gw:string \| null, vlan:integer \| null, rate_limit:number \| null |
| `VMNetworkDeviceRequest` | object | - | key:string \| null, model:string, macaddr:string \| null, bridge:string, vlan:integer \| null, mtu:integer \| null, rate:number \| null, firewall:boolean, delete:boolean |
| `VMPowerRequest` | object | remote, vmid, action | remote:string, vmid:integer, type:string, node:string \| null, action:string |
| `ValidationError` | object | loc, msg, type | loc:array[string \| integer], msg:string, type:string |
| `VendorCreate` | object | name | name:string, code:string, country:string, address:string, noc_email:string, noc_phone:string, remark:string, tax_no:string, company_email:string, company_phone:string, registration_no:string, contract_company_id:integer \| null, status:boolean |
| `VendorUpdate` | object | id, name | id:integer, name:string, code:string, country:string, address:string, noc_email:string, noc_phone:string, remark:string, tax_no:string, company_email:string, company_phone:string, registration_no:string, contract_company_id:integer \| null, status:boolean |


### 资源状态更新（2026-09-21）

- `POST /api/v1/pve/vms/delete` 成功后只定点移除目标 `remote` + `vmid` 的快照、租约和元数据；不触发全量同步。前端立即移除对应行、更新数量与分页，失败保留原行。请求、响应、权限与错误码沿用上文。
- `POST /api/v1/asset/device/create`、`POST /api/v1/asset/device/update` 的 `status` 新增 `6`（预留），保留 0–4 及历史值含义。示例：`{"cabinet_id":1,"asset_no":"S01","name":"Server-01","u_position":1,"type":0,"customer_ids":[],"status":6}`；更新另传 `id`。返回原设备对象，含 `status`、`customer_ids`。服务器选择客户默认使用（1）；移除所有客户后为空闲（0），同时清除旧单客户引用和已解除的节点客户映射。未关联客户时可手动预留，已有客户且未改变关联时可保留维护等显式状态。
- 设备接口沿用登录及对应 POST 权限；无效客户/节点映射返回业务码400，认证失败401、权限不足403、字段校验422；请求和成功响应结构不变。预留设备不计入空闲资源，无数据库结构变更。
