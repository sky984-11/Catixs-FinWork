# 机柜客户机器 Ping 自动纳管

入口：事件管理 → 监控主机 → 机柜联动。选择 Ping 模板、主机组、新建主机的执行节点，开启后保存并同步。
默认每 5 分钟同步；已有主机保留其执行代理。跨机房私网地址须选择能访问目标网络的 Proxy。

## 清单与地址

- 自动覆盖机柜中关联客户、状态为使用 / 待维护 / 故障的设备；四节点服务器按节点客户、节点状态分别计算。
- 未指定监控地址时，标准设备读取属性中的 ipmi_host / IPMI地址；四节点读取各节点的 ipmi_host / ipmiHost / IPMI地址，不借用机箱地址。
- 指定监控地址优先于 IPMI 地址；IPMI 缺失或无效时提示补充，不再回退到业务 IP 或管理 IP。
- 页面可为每个设备 / 节点指定监控地址，保存在联动配置中，不改动资产原始记录。
- 缺少地址、重复地址、已有主机停用、Ping 项不支持或缺少触发器均提示失败。
- 按地址匹配已有主机；无匹配时创建稳定技术名称的主机，绑定选定模板；已有主机没有任何 Ping 项时追加模板。
- 成功纳管的 Ping 项自动加入事件范围，分类为“机柜客户机器”，告警包含客户、机房、机柜及 U 位 / 节点。
- 开启机柜联动后，“机柜客户机器”分类自动持久化到平台分类管理，同时创建客户、机房、机柜、U 位 / 节点属性。重复同步不重复创建，不覆盖用户后续修改的名称和字段；分类、主机编辑及通知配置共用该分类。
- 成功纳管的主机同时出现在“监控主机”主列表，计入总数，标识“自动纳管”，支持客户、机柜等属性搜索。支持单台调整分类、属性、全部或指定监控项，保存覆盖策略，后续同步不覆盖用户选择。
- 自动主机支持确认后移除，不删除 Zabbix 主机及历史；持久排除策略阻止自动重新纳管及纳管失败提醒。机柜联动清单显示“已移除”，可点击操作栏恢复纳管（保留原先自定义分类与监控项）。
- 下架、解除客户关联、关闭联动后退出自动事件范围，不删除 Zabbix 主机 / 历史，也不覆盖手动纳管范围。
- 地址变化创建新的确定性身份，旧 Zabbix 主机需运维核实后停用，不自动改写已有地址。

## 飞书提醒

失败提醒独立于 Ping 故障告警，使用通知管理的默认接收用户，尊重飞书通知总开关。
同一目标、原因、接收人每 24 小时最多提醒一次；每轮按接收人合并为汇总卡片（展示前 20 台，完整清单在界面中），避免逐台刷屏。发送失败保留错误，下轮重试。
不受故障严重度或通知分类筛选限制。目标尚未填 IP 也会提醒，避免漏监控。
Ping 故障 / 恢复通过原事件通知链路，受分类、严重度及接收人规则控制。

## API

统一前缀 `/api/v1/monitor-events/cabinet`，沿用 `DependPermission` 登录及 API 权限；配置和同步记录操作用户 ID。

`GET /api/v1/monitor-events/settings` 保持原有 `hosts`、`categories`、整数 `revision` 不变，新增只读 `automatic_hosts` 和 `automatic_categories` 数组。前端合并显示并按 hostid 去重；保存手动配置时不回传这些数组。自动范围只包含仍在当前机柜清单、地址一致且纳管成功的主机。

| 方法 / 路由 | 用途 |
| --- | --- |
| GET 空路径 | 配置、实时设备清单、上次纳管 / 通知错误 |
| GET /options | 可见 ICMP 模板、主机组、代理 |
| PUT 空路径 | 保存配置，乐观锁 revision |
| POST /sync | 提交后台同步，返回 `data: {queued: true}`；关闭联动时不会创建主机 |
| PUT /hosts | 调整自动主机，参数 hostid、revision（automatic_revision）、category、itemids（null 表示全部，否则非空 ID 数组）、attributes；校验当前主机和监控项权限及归属 |
| DELETE /hosts/{host_id}?revision=0 | 移除自动纳管，保存排除策略 |
| POST /hosts/{host_id}/restore?revision=0 | 取消排除，允许下轮同步重新纳管 |

主机策略接口均需要对应 API 权限，返回 `data: {revision: 1}`；404 表示自动主机不存在，409 表示配置版本冲突。单台编辑、移除与恢复不受自动同步租约阻挡；同步仅读取策略，写入监控状态时不覆盖策略。主列表 settings 新增 automatic_revision，供策略写入使用。迁移 `194_20261116163934_cabinet_host_policies.py` 增加可空 JSON 策略字段，兼容旧数据。

### 批量监控项

主机列表支持混选手动、自动主机，每批最多 50 台。相同监控键按各主机的实际 itemid 映射，也可逐台微调或统一选择全部监控项。

`PUT /api/v1/monitor-events/settings/items`（需要该路由的 API 写权限）：

```json
{"revision":3,"automatic_revision":2,"hosts":[{"hostid":"101","itemids":["501"]},{"hostid":"102","itemids":null}]}
```

revision、automatic_revision 来自 GET settings。itemids=null 为全部监控项，否则必须非空、不重复；最多 2000 项 / 主机、20000 项 / 批次。响应 `data: {revision:4,automatic_revision:3}`。
校验主机纳管范围、Zabbix 可见性、监控项启用状态及归属；手动配置和自动策略在同一数据库事务保存，失败不产生部分更新。仅修改监控项，保留分类、属性及未选中主机。自动同步期间允许保存。
401 未登录；403 无权限；422 主机 / 监控项无效；409 配置版本或清单冲突；502/503 上游不可用。不会修改 Zabbix 模板或原始监控项。

PUT 示例：
```json
{"revision":0,"enabled":true,"template_id":"10564","group_id":"37","proxy_id":"","overrides":{"7:device":"192.0.2.10"}}
```
ID 仅为示例，以 options 返回为准。proxy_id 空字符串表示 Zabbix Server。
响应统一 `{code:200,msg:"OK",data:{...}}`，配置数据包含 revision、enabled、template_id、group_id、proxy_id、overrides、last_checked、last_error、rows、counts。
rows 包含 key、device_id、name、ip、customer、location、cabinet、position、status（pending/managed/failed）、reason、host_id、checked_at、notification_error。

错误：401 未登录、403 无 API 权限、409 配置冲突 / 正在同步、422 地址或选项无效、502/503 Zabbix 不可用。
上游错误不返回原始响应或凭据。同步有数据库租约及超时；重试先检查确定性主机名，避免网络超时后重复创建。

迁移：`193_20261116150214_cabinet_ping_monitor.py`，新建联动配置和目标状态表。
实现参考 [Zabbix 7.4 host.create](https://www.zabbix.com/documentation/7.4/en/manual/api/reference/host/create) 与 [ICMP 检查](https://www.zabbix.com/documentation/7.4/en/manual/config/items/itemtypes/simple_checks)。
