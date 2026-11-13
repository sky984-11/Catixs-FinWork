# 事件管理

入口：一级菜单“事件管理”（保留 `/ops/events` 路由）。数据实时读取用户已选的 Zabbix 主机，不创建本地事件副本。支持当前问题、近 7 天发生的问题及恢复事件、分类/级别/状态筛选和定位信息查询。

## 配置与权限

后端读取 `.env` 的 `ZABBIX_URL`、`ZABBIX_TOKEN`；不返回或记录 token。可选 `ZABBIX_VERIFY_TLS` 默认为 false，与原集成一致，有受信证书时可设为 true。迁移 189 保存已选主机与配置版本；新增迁移 `190_20261113190000_monitor_category_tag.py` 增加分类标签名 `category_tag`，默认 `business_category`。启动初始化一级菜单；管理员默认具备权限，其他角色须单独授予读取、处置或配置权限。

共享 Zabbix 账号决定候选主机可见范围；分类与主机选择为系统共享配置，获授事件读取权限的用户仅能查看已选主机事件，不提供客户级数据隔离。Zabbix 账号还需对应 API 和主机操作权限。已验证 Zabbix 7.4.11；7.2+ 使用 Bearer，旧版兼容 JSON-RPC auth，但旧版抑制能力未验证。

## 仪表盘与定位

- 列表默认读取近 7 天，按同一主机集合和同一触发器归类，仅展示每类最新事件，再应用状态等筛选；双击行打开该类型近 7 天的历史（不继承列表的状态筛选），按发生时间倒序排列。达到 2,000 条读取上限时提示历史可能不完整。
- 列表和详情批量读取恢复事件时间，返回 `recovery_clock` 和 `duration_seconds`。已恢复告警持续时间为恢复时间减发生时间，未恢复时为查询时刻减发生时间；无法读取恢复事件时 `duration_seconds=null`，不将未知时长显示为零。记录来源为 Zabbix，FinWork 不另存历史副本，历史可用性取决于 Zabbix 保留策略。
- 顶部统计始终针对当前未恢复问题（包括抑制），不随历史列表切换而改变；异常主机按 ID 去重。
- 分类来源为用户指定的 Zabbix 主机标签名，标签值自动成为分类名称；主机自身标签与模板继承标签合并去重。缺少该标签或值为空时归为“未分类”。一个主机同名标签有多个不同值时可归属多个分类，每类内部去重，顶部总数不重复计算。原本地分类不再参与归类，也不再支持在 FinWork 手动指定主机分类。
- 明细聚合目标 IP、主机名、Zabbix ID、主机组、库存位置、触发/恢复表达式、指标现值及采样时间、标签、同主机事件、抑制来源、处置历史；支持复制定位信息和跳转原事件。
- 指标值是最新采样而非告警发生时快照。规则建议按名称关键词覆盖连通性、存储、CPU、内存、网络线路及硬件环境；明确标注建议依据，不生成未经证实的根因。
- 页面可每 30 秒刷新，后台页和操作弹窗期间暂停自动刷新。错误时保留上次成功数据并标注错误及更新时间，不以空数据冒充健康。
- 最多选择 1,000 台主机，每次展示不超过 2,000 条事件；超过读取上限会明确提示。业务列可调宽，操作列固定右侧。

## API

统一前缀 `/api/v1/monitor-events`，携带现有 `token` 请求头或 API token Bearer。

| 方法 | 路径 | 参数 / 用途 |
| --- | --- | --- |
| GET | `/settings` | 读取 category_tag、已选主机及其当前 tags、revision；首次主机为空。标签刷新失败时返回 tags_warning，仍可修改或清空范围 |
| GET | `/host-groups` | 返回当前 Zabbix 账号可见、包含启用主机的主机组，不加载主机列表 |
| GET | `/host-options` | 必填正整数 `group_id`；可选 `keyword` 最长 100 字符，仅在该组内筛选主机名称/技术名称；最多返回 100 台，超过提示缩小范围 |
| PUT | `/settings` | 保存 category_tag 与主机范围；校验主机可见且启用、标签名非空及 revision；不会修改上游标签 |
| GET | 空路径 | `history=false` 默认读取当前问题；true 读取近 7 天问题事件；返回顶部统计、分类健康、列表、更新时间及上限标识 |
| GET | `/{eventid}` | 正整数事件 ID；返回定位、指标、建议、恢复时间、处置记录 |
| POST | `/{eventid}/actions` | 提交事件操作；再次读取状态并检查关闭能力 |

查询响应示例（字段省略以 `…` 表示）：

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

初始为空范围，仪表盘返回 `configured:false`、统计为 0，完全不连接 Zabbix。先选择 Zabbix 主机组，再勾选组内主机；分类标签下拉框汇总已选主机和当前组候选的标签名，可选择如 business_category、class、type、env。选组后才加载该组候选，可再用名称筛选；缺少 group_id 返回 422。切换组清空候选勾选，不影响已添加主机。候选不自动纳入范围，必须添加并保存。当前/历史事件和详情仍按已选 hostids 查询，标签不会扩大监控范围。

保存请求：

```json
{"revision":0,"category_tag":"business_category","hosts":[{"hostid":"123"}]}
```

响应 `data` 包含递增 revision、category_tag 和 hosts（增加服务端获取的 name、tags）。category_tag 为 1–255 字符的标签名，名称精确匹配；主机不重复且最多 1000 台。保留旧 categories 和 host.category 请求字段以兼容旧调用方，但不会用它们替代 Zabbix 标签。事务行锁及 revision 防止覆盖配置，冲突返回 409；非法标签名或主机返回 422。空 hosts 可在 Zabbix 不可用时保存，停止事件读取。

仪表盘增加 `configured`、`selected_hosts`、`unavailable_hosts`；停用、删除或权限变化的主机无法读取时明确显示数量，管理员可移除或重新选择。配置操作只写 FinWork，不修改上游主机或分组。

部署需执行迁移 190 并重启后端，已选主机保留。进入“分类与监控范围”选择分类标签与主机。配置入口需要 GET `/settings`、GET `/host-groups`、GET `/host-options` 与 PUT `/settings` 权限。标签维护在 Zabbix，刷新时自动同步；FinWork 不写入或删除上游标签。已选标签在全部主机上不存在时，所有已选主机会显示未分类，请选择实际存在的标签名。

标签协议依据：[Zabbix 7.4 host.get 的 selectTags / selectInheritedTags](https://www.zabbix.com/documentation/7.4/en/manual/api/reference/host/get)。

### 已有配置表但缺少迁移记录

若启动迁移 189 报 `monitor_event_config` 已存在，先执行 `python scripts/reconcile_monitor_event_migration.py` 只读校验，成功后执行同一命令加 `--apply`。脚本仅适用于 PostgreSQL，会核验所有字段类型、非空约束、默认值、主键和该迁移索引，并拒绝存在更早未执行迁移的情况；验证一致才在事务中补齐迁移 189 的 Aerich 记录，不删除表、不修改配置内容、不修改历史迁移文件。结构不匹配时停止，不能直接忽略异常或标记成功。

