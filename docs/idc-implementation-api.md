# IDC 工单、客户产品与账单实现说明

## 入口与上线

新增菜单 **IDC业务 → IDC工单 / 客户产品 / IDC账单**。原工单列表提供 IDC 入口，结构化工单仍使用原 `ticket` 编号；原账单管理可以查询、发送和收款，但不能直接改写 IDC 账单或绕过审批。原有工单、价格、订阅及账单数据不自动转换。

数据库新增 14 张 `idc_*` 表；不重写旧表。新增 Aerich 迁移为 `174_20260921120000_idc_workflow.py`，使用 Aerich PostgreSQL DDL 生成。现有启动流程会执行迁移并补充目录和菜单。上线应先在测试 PostgreSQL 上验证迁移，再部署前后端；本地业务测试使用独立内存 SQLite，不连接生产数据库。

首次使用：

1. 财务在“IDC工单 → 客户账务映射”关联 **CRM客户、该客户签约主体、原账单公司**。这三个 ID 不可互相替代；已有工单后禁止改变映射身份。
2. 管理员分配菜单及 API 权限。启动自动补充已有管理员、sales/销售/商务、noc/运维/技术、finance/财务角色的对应权限；自定义角色按下表配置。
3. 如客户本人使用系统，另配置客户角色，并在映射中填写授权用户。没有客户映射的外部用户不能读取该客户工单、产品或账单。
4. 填写工单，选择业务动作、产品分类、数量及动态参数。询价允许先提交不完整需求，正式报价前补齐。
5. 商务报价 → 审批 → 客户确认（或授权商务登记确认依据）→ 运维/采购任务 → 回填实际交付 → 客户逐明细验收 → 自动生成客户产品与费用版本。
6. 财务选择月份预览，处理缺失用量等阻断项，再生成待审核账单；审核后在原账单管理进行发送、收款。

## 产品与动态参数

目录覆盖整柜整租、散柜机位、Cross Connect、物理服务器、云主机、IPv4、IPv6、ASN、IX Peering、Cloud Connect、IP Transit、DIA Datacenter / Retail Building、China Route、IEPL、Wave、Remote Hands，另有本地传输附加明细。

分类采用“大类 → 产品”，DIA 使用“大类 → DIA → Datacenter / Retail Building”。业务动作独立于产品分类；故障生成 INC，维护生成 MTN，其余生成 REQ。`GET /catalog` 返回前后端共用的字段定义，工单保存版本快照，避免以后修改目录改变历史需求。

- A/Z 端支持 On-net、Off-net、待勘查。本地传输必须选择我方提供、主产品已含、客户自备等来源；Off-net 不允许“不需要”。我方提供必须添加对应端别的本地传输子明细，且先验收子明细。
- Retail Building 与 Off-net 报价必须填写勘查或采购询价依据。
- 突发参数条件显示，承诺带宽不超过端口速率，突发上限介于两者之间；突发产品必须有用量费用组件或明确已含组件。
- 价格候选只返回当前有效的本客户价和标准价，客户价优先展示。规格、地区、币种及单位仍由商务核对，不能因产品名称相同而自动套价。候选非月/季/年/一次性单位时须人工换算。

## 工作流与资源

报价、需求分别递增版本。旧版本提交返回 409；报价确认后禁止直接改需求。未验收明细可由内部人员“撤回重新报价”，清除待交付结果、重置任务、释放该明细预留，保留审计记录，重新审批及客户确认。已实施的取消请求被阻止，应核对已发生费用后通过退订或调整处理。

验收必须完成全部交付任务，提供确认依据、起租日和可选结束边界；重试相同验收不重复创建服务。变更/续约/暂停/恢复/退订保持同一个服务 ID，新增版本，按生效日截断上一版本；已出账区间不能直接回改。暂停费由新确认的报价决定，免费暂停应明确录入 0 元组件。退订只允许一次性费用。

资源绑定键：`device` 为设备 ID 或 `设备ID:节点名`；`vm` 为已有快照中的 `remote:vmid`；`cabinet` 为机柜 ID；`ip` 为规范 CIDR；`circuit` / `port` 为业务资源标识。设备、VM、IP 不允许共享。系统校验设备与节点、VM、机柜是否存在，防止重复独占、设备整机与节点冲突、IP 前缀重叠。资源预约在事务中串行检查。

非空资源清单表示此次交付使用的完整资源清单；已有服务传空清单沿用上一版本资源。新版本生效时释放已替换资源，未来版本保留预约，退订或到期后可用“释放到期资源锁”清理。锁仅管理 IDC 业务绑定，不自动删除虚拟机、不向运营商自动下单，也不改写旧资产模块的客户分配；实体交付仍由运维在现有资源模块完成并回填。

## 计费规则

- 未验收、仅询价、故障和维护不会产生客户产品费用。需要收费的支持工作另开一次性服务请求。
- 费用组件分 NRC、周期费、用量费；包含关系分单独计费/已含/免费/客户自备，后三项价格必须明确为 0。
- 周期支持月、季、年，价格为整个选定周期的单价，周期锚点为首次起租月份第一天。可选预付/后付及实际自然日、30天、整周期折算。整周期规则即按合同收取完整周期，不用于自动按天折算。
- 内部使用 Decimal，JPY 舍入至整数，其他币种两位；写入既有账单金额字段时保持原浮点接口兼容，精确金额与费用依据保存于 IDC 分摊快照。
- 计费区间为 `[starts_on, ends_before)`；旧账单显示结束日为 `ends_before - 1天`。9月10日起租、月费300、NRC100，9月应收为 `300×21/30+100=310`。
- 用量须覆盖完整连续结算区间，不能缺样默认为0；95计费使用一个完整区间的已核实结果，不能相加分段百分位。工时可按进位、最低量、包内额度、金额封顶结算。此实现接收核实后的计量结果，不连接监控系统自动采样。
- NRC 每个费用组件只收一次。账单按映射客户、月份、币种归组；重复生成更新未审核草稿，已审核项跳过。已锁定月份新增费用须登记下一期调整项。
- 作废仅限未审核且未收款草稿；历史账单、明细与分摊快照保留，重新生成采用新账单编号。正式账单通过关联原账单的调整/贷项处理。
- 预付款、调整、贷项为显式费用事件；预付款抵扣须由财务登记关联原账单的负数贷项，累计贷项不得超过原账单未税金额及税额，不自动推断抵扣。合同期限保存于报价，结束边界由验收明确填写，不根据合同月数自动退订。

可供外部定时任务调用的批处理入口（默认预览，增加 `--apply` 才保存待审核草稿）：

```bash
python -m scripts.generate_idc_bills --month 2026-09-01 --operator-id 1
python -m scripts.generate_idc_bills --month 2026-09-01 --operator-id 1 --account-id 2 --apply
```

`operator-id` 必须是实际具有 IDC 出账权限的在用用户。脚本不会自动审批或发送；存在缺失用量/冲突时返回非零退出码。调度器需根据业务账期传入月份，仓库不自动启用生产定时出账。

## API

统一前缀 `/api/v1/idc`，使用现有请求头 `token`。所有路由均经 `DependPermission`；内部操作另检查内部业务权限，客户读取及操作再校验映射授权。成功响应 `{"code":200,"msg":"OK","data":...}`，具体 msg 沿用项目封装。请求字段完整约束见 `app/schemas/idc.py` 及 OpenAPI。

| 方法及路径 | 参数 / 结果 | 权限与校验 |
|---|---|---|
| GET `/catalog` | products、actions、capabilities | 登录及该接口权限 |
| GET `/accounts` | 可访问客户映射数组 | 外部用户仅授权映射 |
| GET `/account-options` | CRM客户、主体、账单公司、用户选项 | 内部人员 |
| POST `/accounts` | id?、customer_id、signing_entity_id、company_id、user_ids、active | 内部；身份映射不可随历史工单改写 |
| GET `/orders` | account_id?、page=1、page_size=20≤100；items、total | 客户隔离 |
| POST `/orders` | request_key、account_id、title、contact、action、requested_date?、reference、description、lines | 每个line含product_code、quantity、parameters、source_service_id?、parent_index? |
| GET `/orders/{order_id}` | 工单、客户、lines、报价历史、任务、资源 | 客户隔离 |
| POST `/lines/{line_id}` | revision及LineInput字段 | 未确认版本；不允许替换产品与原服务 |
| GET `/lines/{line_id}/prices` | 当前有效客户/标准价候选 | 内部 |
| POST `/lines/{line_id}/quotes` | revision、currency、valid_until、contract_months、payment_days、terms、procurement_reference、charges | 内部；完整参数、有效日期及费用组件 |
| POST `/lines/{line_id}/decision` | version、action=approve/confirm/reject/cancel/revise、evidence | approve/reject/revise必须内部；其他仍校验客户授权 |
| POST `/tasks/{task_id}` | status=pending/working/done/failed、assignee_id?、evidence | 内部交付人员 |
| POST `/lines/{line_id}/delivery` | revision、actual_parameters、values、evidence、resources | 内部；参数与确认需求一致；values键来自delivery_fields |
| POST `/lines/{line_id}/accept` | revision、quote_version、starts_on、ends_before?、evidence、accept=true | 客户授权；accept=false退回交付 |
| POST `/lines/{line_id}/support-complete` | status、evidence、assignee_id? | 内部；仅故障/维护；不计费 |
| GET `/services` | account_id?、page、page_size；items含versions、charges、resources | 客户隔离 |
| POST `/resources/reconcile` | 无请求体；released数量 | 内部资源权限 |
| POST `/usage` | charge_id、starts_on、ends_before、quantity、evidence | 内部；防重复区间、已出账修改 |
| POST `/billing/generate` | account_id、month、dry_run=true；blocked/previews/created/skipped | 内部财务；缺用量不生成 |
| GET `/billing` | account_id?、page、page_size；账单items含费用来源快照 | 客户隔离；当前版本，历史账单保留在原账单模块 |
| POST `/billing/{bill_id}/decision` | action=approve/reject/void、comment | 内部财务 |
| POST `/billing/events` | request_key、account_id、service_id?、source_bill_id?、currency、amount、tax、due_on、kind、description | 内部财务；credit/adjustment必须关联原正式账单 |
| GET `/audit` | object_type=line/service、object_id、page；每页50条 | 按对象校验客户归属 |

报价费用组件示例：

```json
{"code":"mrc","name":"DIA月费","kind":"recurring","amount":"300","tax_rate":"0","treatment":"separate","unit":"线路","interval":1,"proration":"actual_days","timing":"arrears"}
```

出账响应示例（预览时 created 为空）：

```json
{"code":200,"data":{"blocked":[],"previews":[{"account_id":2,"currency":"USD","month":"2026-09-01","net_amount":"310.00","vat_amount":"0.00","total_amount":"310.00","items":[]}],"created":[],"skipped":[]}}
```

错误通过 HTTP 状态返回：401 无效登录，403 路由权限或客户归属不符，404 对象不存在，409 版本/状态/资源/重复请求冲突，422 字段、计量区间或业务约束错误。沿用原鉴权：缺少必填 token 请求头返回422。缺失用量属于可展示的出账阻断，HTTP200且 `data.blocked` 非空。

## 验证与边界

`tests/test_idc_workflow.py` 用内存数据库与 ASGI 请求验证工作流、幂等出账、历史保护、计费、资源冲突和权限；不会删除或修改真实业务数据。前端执行生产构建与 ESLint；全库既有 lint 问题单独报告。

本次没有执行生产迁移或部署，未连接真实云平台、运营商或计量平台。历史自由文本工单不会被自动解析为合同产品，避免推断价格、客户归属与起租时间。历史产品接入新账务需人工确认并通过结构化工单验收，原订阅应由财务停用以避免两套账务重复收取。
