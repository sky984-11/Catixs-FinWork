# 事件管理

入口：一级目录“事件管理”（`/events`），包含四个独立页面：

| 菜单 | 路由 | 用途 |
| --- | --- | --- |
| 事件列表 | `/ops/events`（兼容原入口） | 当前问题，默认未确认，同主机/触发器仅显示最新一条 |
| 历史事件 | `/events/history` | 近 7 天逐次事件记录，默认已恢复，支持切换全部状态 |
| 监控主机 | `/events/hosts` | 点击“纳管主机”打开弹窗，按主机组选主机，指定平台分类及监控项；编辑/移除立即保存后生效 |
| 分类管理 | `/events/categories` | 平台内新增、重命名、删除分类；显示关联主机；分类被使用时禁止删除，须先重新分配主机 |

数据实时读取用户已选的 Zabbix 主机，不创建本地事件副本。菜单升级复用原事件列表 ID，并保留 `/ops/events` 访问。管理员获得目录和全部子菜单；原事件读者保留事件/历史入口，具有 settings GET 权限的原读者同时可查看配置页面，无 PUT 权限时为只读，不自动扩展 API 权限。

## 配置与权限

后端读取 `.env` 的 `ZABBIX_URL`、`ZABBIX_TOKEN`；不返回或记录 token。可选 `ZABBIX_VERIFY_TLS` 默认为 false，与原集成一致，有受信证书时可设为 true。迁移 189 保存已选主机与配置版本；新增迁移 `190_20261113190000_monitor_category_tag.py` 增加分类标签名 `category_tag`，默认 `business_category`。启动初始化一级菜单；管理员默认具备权限，其他角色须单独授予读取、处置或配置权限。

共享 Zabbix 账号决定候选主机可见范围；分类与主机选择为系统共享配置，获授事件读取权限的用户仅能查看已选主机事件，不提供客户级数据隔离。Zabbix 账号还需对应 API 和主机操作权限。已验证 Zabbix 7.4.11；7.2+ 使用 Bearer，旧版兼容 JSON-RPC auth，但旧版抑制能力未验证。

## 仪表盘与定位

- 事件列表只读取当前问题（`history=false`），默认筛选未确认告警，不加载已恢复历史；按同一主机集合和同一触发器归类，仅展示每类最新事件，再应用状态等筛选。历史事件页使用 `history=true`，逐次展示近 7 天记录，按发生时间倒序，默认已恢复。两个页面均可双击行打开同类历史（不继承列表的状态筛选）。达到 2,000 条读取上限时提示历史可能不完整。
- 列表和详情批量读取恢复事件时间，返回 `recovery_clock` 和 `duration_seconds`。已恢复告警持续时间为恢复时间减发生时间，未恢复时为查询时刻减发生时间；无法读取恢复事件时 `duration_seconds=null`，不将未知时长显示为零。记录来源为 Zabbix，FinWork 不另存历史副本，历史可用性取决于 Zabbix 保留策略。
- 顶部统计始终针对当前未恢复问题（包括抑制），不随历史列表切换而改变；异常主机按 ID 去重。
- 分类由 FinWork 的 categories 与 host.category 控制，与 Zabbix 标签脱钩。每台主机可指定一个平台分类或保持未分类；事件按关联主机的分类归属，跨主机触发器可以出现在多个分类，顶部主机数按 ID 去重。Zabbix 标签保留作为定位参考。
- 明细聚合目标 IP、主机名、Zabbix ID、主机组、库存位置、触发/恢复表达式、指标现值及采样时间、标签、同主机事件、抑制来源、处置历史；支持复制定位信息和跳转原事件。
- 指标值是最新采样而非告警发生时快照。规则建议按名称关键词覆盖连通性、存储、CPU、内存、网络线路及硬件环境；明确标注建议依据，不生成未经证实的根因。
- 页面可每 30 秒刷新，后台页和操作弹窗期间暂停自动刷新。错误时保留上次成功数据并标注错误及更新时间，不以空数据冒充健康。
- 最多选择 1,000 台主机，每次展示不超过 2,000 条事件；超过读取上限会明确提示。业务列可调宽，操作列固定右侧。

## API

统一前缀 `/api/v1/monitor-events`，携带现有 `token` 请求头或 API token Bearer。

| 方法 | 路径 | 参数 / 用途 |
| --- | --- | --- |
| GET | `/settings` | 读取本地 categories、hosts（含 category、itemids）、revision、category_source=platform；不连接 Zabbix |
| GET | `/host-groups` | 返回当前 Zabbix 账号可见、包含启用主机的主机组，不加载主机列表 |
| GET | `/host-options` | 必填正整数 `group_id`；可选 `keyword` 最长 100 字符，仅在该组内筛选主机名称/技术名称；最多返回 100 台，超过提示缩小范围 |
| GET | `/host-items` | 必填正整数 host_id；可选 keyword 最长 100 字符，匹配监控项名称或键值；仅查询指定启用主机的启用监控项，最多 500 条，超过返回 truncated=true |
| PUT | `/settings` | 保存平台分类、主机与监控项范围；新增主机或改变监控项时验证上游归属和启用状态；仅分类修改/移除无需连接 Zabbix；revision 防并发覆盖 |
| GET | 空路径 | `history=false` 默认读取当前问题；true 读取近 7 天问题事件；返回顶部统计、分类健康、列表、更新时间及上限标识 |
| GET | `/{eventid}` | 正整数事件 ID；返回定位、指标、建议、恢复时间、处置记录 |
| GET | `/{eventid}/metrics/{itemid}/history` | 必填 Unix 秒 `time_from>=0`、`time_till>time_from`，单次最长 7 天；仅查询该事件触发器关联且属于已纳管主机的数值指标（value_type 0/3） |
| POST | `/{eventid}/actions` | 提交事件操作；再次读取状态并检查关闭能力 |

查询响应示例（字段省略以 `…` 表示）：

指标历史独立校验上述 GET 路由权限，同时打开弹窗需要事件详情 GET 权限。管理员权限通过启动时 API 同步授予，其他角色需授权新路由。调用 Zabbix `history.get`，按采样时间升序返回最新最多 10,000 点，超限 `truncated=true`，不做平均或趋势替代；无历史时返回空 points。历史保留由 Zabbix 管理。接口遵循 [Zabbix history.get](https://www.zabbix.com/documentation/7.4/en/manual/api/reference/history/get) 的指标类型和时间参数。

历史响应示例：`{"code":200,"data":{"item":{"itemid":"30","name":"CPU","units":"%","value_type":"0"},"points":[{"clock":1800000000,"ns":0,"value":95.5}],"time_from":1799996400,"time_till":1800003600,"truncated":false,"event_clock":1800000000,"recovery_clock":0}}`。401 未登录；403 无接口权限；404 事件/指标不可见、未纳管或指标与事件无关联；422 范围无效/超过 7 天/非数值指标；502 上游失败；503 未配置 Zabbix。不会更改上游监控数据。

```json
{"code":200,"msg":"OK","data":{"summary":{"hosts":300,"abnormal_hosts":95,"problems":255,"critical":13,"suppressed":36},"categories":[{"key":"pve","label":"PVE 虚拟化","total":20,"abnormal":2,"events":3}],"rows":[{"id":"10","name":"CPU high","severity":4,"recovered":false,"acknowledged":false,"suppressed":false,"hosts":[],"categories":["pve"]}],"truncated":false,"updated_at":1800000000,"version":"7.4.11"}}
```

处置请求：

```json
{"action":"suppress","message":"维护变更期间暂时抑制，完成后核实","minutes":60}
```

`action` 支持 `acknowledge`、`unacknowledge`、`comment`、`suppress`、`unsuppress`、`close`、`severity`；`message` 必填，去空格后 1–1500 字符。抑制 `minutes` 为 1–10080 整数，默认 60，不提供无限期抑制；调整级别必须传 `severity:0..5`。所有操作附加 `[FinWork user:用户ID]` 写入 Zabbix 备注，并记录本地操作日志的操作类型、事件 ID 和用户 ID。

返回 `{"code":200,"msg":"操作已提交至 Zabbix，请刷新查看最新状态","data":{"eventid":"10","submitted":true}}`。提交成功不代表设备已修复。恢复自动同步自 Zabbix；`close` 仅在触发器允许手动关闭时可用。已恢复事件只能备注/确认/取消确认。解除手动抑制不会取消维护窗口。

状态码：401 未登录；403 无对应 API 权限；404 事件不存在或上游不可见；409 事件状态改变或不允许关闭；422 请求校验失败；503 未配置；502 上游网络、权限、协议或响应异常。上游原始错误不透传，不自动重试变更请求；失败时应刷新核实是否已被 Zabbix 接受再操作。

## 验证

`python -m unittest tests.test_monitor_events` 覆盖统计、历史范围、主机定位、恢复时间、七类动作位、限时抑制、恢复后拒绝操作、禁止手动关闭、鉴权、只读角色、菜单权限、身份认证版本及敏感错误处理。写操作仅使用模拟 Zabbix 测试，未对真实告警抑制/关闭。真实环境只读验证仪表盘和详情；部署后由授权操作员对测试告警验证回写。

协议依据：[Zabbix event.acknowledge](https://www.zabbix.com/documentation/current/en/manual/api/reference/event/acknowledge)、[Zabbix problem.get](https://www.zabbix.com/documentation/current/en/manual/api/reference/problem/get)。

## 分类与监控范围

初始为空范围，仪表盘返回 `configured:false`、统计为 0，完全不连接 Zabbix。纳管弹窗先选主机组，再选主机，并分配本地分类和监控项。未选组不加载候选主机；未选主机不查询监控项。新纳管默认指定监控项、至少勾选一项，也可显式选择全部。监控项搜索保留已选项，支持移除已选项。保存、查询期间禁用重复提交与关闭弹窗。

保存请求：

```json
{"revision":0,"categories":[{"key":"network","label":"网络设备"}],"hosts":[{"hostid":"123","category":"network","itemids":["456","457"]}]}
```

响应 data 包含递增 revision、categories、hosts（hostid/name/category/itemids/tags 快照）和 category_source=platform。category_tag 字段仅保留兼容，不参与分类。categories 最多 50 个，key 为 1–64 位字母数字下划线/横线（unclassified 保留），label 去首尾空格后 1–40 字符且不重复。每台主机 category 为现有分类 key 或 null。主机最多 1000 台；itemids=null 表示全部（含未来新增），数组为指定监控项，不能为空、不能重复，单主机最多 2000 项、总计 20000 项。旧客户端省略 categories/category/itemids 时保留原值，避免将指定范围意外扩大为全部。

响应示例：`{"code":200,"data":{"revision":1,"category_source":"platform","categories":[{"key":"network","label":"网络设备"}],"hosts":[{"hostid":"123","name":"Router","category":"network","itemids":["456"],"tags":[]}]}}`。

配置与监控项查询均沿用登录及对应 API 权限：401 未登录；403 无权限；host-items 404 表示主机不可见或停用；保存非法分类、重复/空监控项、跨主机监控项、停用或不可见的新监控项返回 422；revision 冲突 409；上游失败 502、未配置 503。纯分类 CRUD、移除主机不调用上游。分类被主机引用时不能删除，除非同一请求先将这些主机分配到其他分类或未分类。

指定监控项时，通过 trigger.get 的 itemids 找到引用任一已选项的触发器（OR 语义），与整机纳管触发器取并集，在 problem.get/event.get 查询阶段使用 objectids 限制，而非仅前端筛选。没有匹配触发器时返回空事件，绝不退回查询全部。详情、处置和指标历史也执行相同校验；详情只返回纳管范围内的监控项。主机数仍反映纳管主机数量，告警统计仅覆盖纳管触发器。协议依据：[Zabbix trigger.get](https://www.zabbix.com/documentation/7.4/en/manual/api/reference/trigger/get)。

仪表盘增加 `configured`、`selected_hosts`、`unavailable_hosts`；停用、删除或权限变化的主机无法读取时明确显示数量，管理员可移除或重新选择。配置操作只写 FinWork，不修改上游主机或分组。

本次复用已有 JSON 字段，无数据库结构或历史迁移文件改动。首次读取旧配置时，在事务行锁内补齐 host.category/itemids 并递增 revision：已有分类关联保留；无关联时将旧标签快照对应的分类一次性转为本地分类（多个旧标签值取排序后的首个），随后不再随 Zabbix 标签变化；旧主机 itemids=null 保留原整机纳管范围。转换幂等，不查询或写入 Zabbix。

配置页面需要 GET `/settings`、PUT `/settings`；主机纳管额外需要 GET `/host-groups`、GET `/host-options`、GET `/host-items`。普通角色需配置新增监控项查询权限。所有配置操作仅写 FinWork，绝不新增/删除上游主机、监控项或标签。

标签协议依据：[Zabbix 7.4 host.get 的 selectTags / selectInheritedTags](https://www.zabbix.com/documentation/7.4/en/manual/api/reference/host/get)。

### 已有配置表但缺少迁移记录

若启动迁移 189 报 `monitor_event_config` 已存在，先执行 `python scripts/reconcile_monitor_event_migration.py` 只读校验，成功后执行同一命令加 `--apply`。脚本仅适用于 PostgreSQL，会核验所有字段类型、非空约束、默认值、主键和该迁移索引，并拒绝存在更早未执行迁移的情况；验证一致才在事务中补齐迁移 189 的 Aerich 记录，不删除表、不修改配置内容、不修改历史迁移文件。结构不匹配时停止，不能直接忽略异常或标记成功。

