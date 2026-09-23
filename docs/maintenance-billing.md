# 按次施工运维报价

客户管理不再展示或编辑运维小时单价和报价币种。旧数据库字段和接口字段仅保留兼容，运维计价不再读取这些字段，历史记录已保存报价不丢失。

## 计划与记录报价

计划创建/更新、运维记录创建/更新均接收 `customer_pricing`：

```json
{"customer_pricing":{"kind":"fixed","fixed_fee":"500.00","currency":"USD","expenses_included":false,"note":"本次设备安装，含人工、交通及税费"}}
```

- `kind: pending`：报价待确认。
- `kind: internal`：本次使用工程师规则。
- `kind: hourly`：本次小时报价，填写 `hourly_rate`、`currency`，替换基础人工价或固定档位；工时最低值、取整、通勤、夜班等规则继续适用。不再与客户档案单价绑定，也不对每次议价设置工程师成本下限。
- `kind: fixed`：本次一口价，填写 `fixed_fee`、`currency`。不再叠加工时、通勤、夜班、紧急或工程师规则税费。报价可独立于工程师和起止时间确认。
- `expenses_included`：仅一口价使用。true 表示现场报销包含在报价中，明细保留但不重复累加；false（默认）表示现场报销另计。
- `note`：报价范围、含税与其他约定，最长1000字。金额为非负、最多两位小数，可空表示待确认；币种为 USD/CNY/GBP/EUR/HKD/SGD/JPY。

外部客户新施工默认待确认，Catixs默认工程师规则。切换客户时前端重置报价；同一客户不同施工可填写不同报价。计划完成后报价带入记录，现场可以继续调整。记录编辑省略或null报价时保留同一客户既有快照；计划更新省略报价时同样保留。显式发送 `kind: pending` 可取消原确认报价。刷新工程师规则不会覆盖本次施工报价。

## 接口与响应

- `POST /api/v1/remote-assistance/plans`、`PUT /api/v1/remote-assistance/plans/{plan_id}`：保存本次 `customer_pricing`，概览计划响应返回同名字段。
- `POST /api/v1/remote-assistance/plans/{plan_id}/complete`：将计划报价复制到生成记录的费用快照。
- `POST /api/v1/remote-assistance/remote-hands`、`PUT /api/v1/remote-assistance/remote-hands/{item_id}`：接收 `customer_pricing` 和 `billing_context`，后端校验报价结构并计算，响应仍返回 `customer_pricing_snapshot`、`billing_context`、`billing_result`；记录快照不会随客户或工程师档案改价自动改变。
- `POST /api/v1/remote-assistance/billing/preview`：接受同结构报价。一口价时 `rules` 可空，`arrived_at`、`left_at` 可省略；按工时计价仍须有效规则和时间。

一口价试算请求：`{"customer_pricing":{"kind":"fixed","fixed_fee":"500.00","currency":"USD"}}`。成功响应示意：`{"code":200,"data":{"status":"calculated","currency":"USD","total":"500.00","totals":{"USD":"500.00"},"lines":[{"label":"本次施工一口价","amount":"500.00","currency":"USD"}],"notices":[]}}`。

现场 `billing_context.expenses` 最多50项，每项 `{name,amount,currency,note}`。名称1–100字，说明最多500字；金额空为待确认，0为无费用。各规则都可录入携带大件打车、材料费等实报实销；不要重复录入原固定交通费或 `reimbursed_transport`。可通过记录附件上传凭证。通勤继续支持 `actual_commute_minutes`，洛杉矶现场作业按整小时、往返实际通勤按半小时分别向上取整。

多币种按 `totals` 分别汇总，不换汇、不直接相加；此时 `total:null`，`status:calculated`。待确认的价格或报销为 `status:pending`，没有最终totals。一口价已含报销时，报销明细未确认不影响约定一口价合计。报价不自动创建账单或改变结算状态。

写接口沿用对应路由/方法角色权限；试算仅要求登录。无token422、无效token401、无权限403、金额/币种等字段校验失败422；业务错误沿用code400。报价不完整的试算返回HTTP200和pending。

## 部署

执行 `aerich upgrade` 应用 `178_20260923150000_plan_maintenance_quote.py`，仅新增计划报价JSON字段，不删除客户旧字段，不回填历史报价。177及之前的迁移保持兼容；回滚178会移除计划报价字段。已有记录的历史报价快照继续有效。
