# 资源成本库

入口：**产品中心 → 资源成本库**（`/product-center/resource-costs`）。新增、编辑、停用、历史版本、CSV 导入；在**产品管理 → 操作栏 → 关联成本资源**中选取记录。一个产品可关联多个站点或供应商的资源成本；同一产品对同一资源只保留一个明确选定的版本。

## 分类及字段

仅开放以下五类。Misc、Remote Hand 按用户要求暂不开放。

| 分类 | 字段 |
| --- | --- |
| IPT / DIA (DC) | Service Resource、Service、Vendor、B/W、Burst、Site A、Protection、XC/Cabling、Contract Terms、Currency、NRC、MRC、Price/Mbps MRC、Burst Price/Mbps、Note |
| PtP (DC) | Service Resource、Service、Vendor、B/W、Site A、Site B、Protection、XC/Cabling、Contract Terms、Currency、NRC、MRC、Price/Mbps MRC、Note |
| Retail Building | Service Resource、Service、Vendor、B/W、Burst、Site A、Site B、Protection、XC/Cabling、Contract Terms、Currency、NRC、MRC、Price/Mbps MRC、Note |
| XC | DC Name、Site Address、Vendor（可选补充）、Currency、Tax Rate、NRC、MRC、Remarks |
| Colo | Service Resource、Service、Vendor、B/W、Site A、Protection、XC/Cabling、Contract Terms、Currency、NRC、MRC、Note |

另有编号、启用状态、MRC 计价单位、生效日、失效日（不含）。Site A/B 和机房地址作为成本版本的一部分保存，不自动创建资产机房或物理线路。现有供应商数据来自 Company（role=2/3），不是旧 Vendor 表。选项包含停用供应商用于显示历史数据，新记录不能关联停用供应商。

金额使用 Decimal，最多 16 位、4 位小数，非负；`null` 表示未报价，`"0"` 表示免费。Tax Rate 为 0–100 的百分比。MRC `701/kVA` 拆成金额 `701` 与单位 `kVA`，不当成每机柜价格。支持 USD/HKD/CNY/EUR/GBP/JPY/SGD，不换汇、不自动按成本除以 0.8 生成售价，带宽单价按原表维护。

XC 必须填写 DC Name；其他类必须填写 Service 和 Site A，PtP 还需 Site B。有费用时必须填写币种。合同期 1–1200 月，失效日必须晚于生效日；非当前分类字段不允许携带非空值。其他可选值以 `/options` 返回的字段定义为准。

## 版本与产品关联

每次保存产生不可变成本版本；编辑需携带读取到的 `expected_revision`，过期版本编辑返回 409。停用通过编辑 `enabled=false` 完成，不提供物理删除成本记录接口，避免丢失历史。

产品关联固定一个 `version_id`。成本修改后，关联处显示“关联版本 / 最新版本”；用户再次选择最新记录并确认，才更新关联。停用、未生效、已失效或已被新版本替代的记录不能新增关联。解除关联保留所有成本版本。

关联记录带入来源字段和成本快照，供产品管理查看；不会改写产品规格、销售价格、已生成价格版本或订单，也不会把采购成本直接用于客户出账。

## CSV 导入

按分类下载模板，CSV 为 UTF-8，可选择文件或粘贴文本。每次最多 500 行、2 MiB；说明行、合并标题行需先去掉，逗号及换行地址按 CSV 规则加双引号。可用界面模板的中文/英文表头或下方 JSON 字段名。不直接解析 XLSX，先按页签另存 CSV。

Vendor 可填写供应商 ID、编号、简称或全称，必须唯一匹配启用供应商；不认识的供应商不会自动新建。供应商不确定可留空。`12 Months` 转为 12，`€50` / `£50` 仅在币种分别为 EUR / GBP 时转为金额；金额 `NA`、`N/A`、`—`、`-` 转为未报价，0 原样保留。

先调用预检，返回有效行及逐行错误，不写数据库。页面有任何错误时不允许确认；确认阶段重新校验并在同一事务内写入，任意行失败整批回滚。无编号行按规范化内容生成稳定的 `IMP-…` 编号，同一文件重试不会重复写入；已有编号请在列表编辑，不做隐式覆盖。手工新增未填编号时生成 `RC-…`。

## API

前缀 `/api/v1/resource-costs`，所有接口经登录与 `DependPermission` 校验。独立于原产品 API 权限，管理员／财务角色初始化时获得成本库权限；其他角色需显式授权相应接口及菜单。日志只记录操作、记录/版本/产品 ID、操作者 ID 和导入数量，不记录原始 CSV。

| 方法 | 路由 | 请求 / 用途 |
| --- | --- | --- |
| GET | `/options` | 五类字段元数据及供应商选项 |
| GET | 空路径 | `category`、`keyword`（≤200）、`vendor_id`、`enabled`、`page`≥1、`page_size` 1–100，返回分页最新版本 |
| POST | 空路径 | CostPayload，新增成本 |
| PUT | `/{resource_id}` | 完整 CostPayload，必须携带 `expected_revision`；分类不可更换 |
| GET | `/{resource_id}/versions` | 历史版本，按版本倒序 |
| POST | `/import/preview` | `{"category":"xc","csv_text":"DC Name,Currency,NRC,MRC\nTest DC,USD,0,50\n"}` |
| POST | `/import/commit` | `{"rows":[<预检返回行>]}`，全成功或全回滚 |
| GET | `/products/{product_id}/links` | 已关联固定版本及最新版本号 |
| POST | `/products/{product_id}/links` | `{"version_id":1}`，关联／更新同资源关联 |
| DELETE | `/products/{product_id}/links/{link_id}` | 解除匹配该产品的关联 |

CostPayload 字段：`category`（ipt_dia/ptp/retail/xc/colo）、`code`（≤80）、`expected_revision`、`enabled`、`service_resource`、`service`（≤120）、`vendor_id`、`bandwidth`/`burst`（≤100）、`site_a`/`site_b`/`site_address`（≤500）、`protection`、`xc_cabling`、`contract_months`、`currency`、`nrc`/`mrc`/`price_per_mbps`/`burst_price`、`mrc_unit`（≤40）、`dc_name`（≤200）、`tax_rate`、`note`（≤4000）、`effective_date`/`expiry_date`（YYYY-MM-DD）。未知字段拒绝。

新增示例：

```json
{"category":"xc","dc_name":"Test DC","site_address":"Test address","vendor_id":1,"currency":"USD","nrc":"0","mrc":"50","mrc_unit":"月","tax_rate":"0","enabled":true}
```

成功响应：`{"code":200,"msg":"OK","data":{"id":1,"code":"RC-…","category":"xc","title":"Test DC","vendor_name":"Test carrier","currency":"USD","nrc":"0","mrc":"50","revision":1,"latest_revision":1,"version_id":1,"enabled":true,"resource_enabled":true,"updated_at":"…"}}`（另包含完整成本字段）。列表额外包含 `total/page/page_size`。版本状态来自保存时快照，`resource_enabled` 表示资源当前状态。

预检响应：`{"code":200,"msg":"OK","data":{"rows":[...],"errors":[{"row":2,"message":"Vendor 未唯一匹配启用供应商…"}]}}`；导入成功返回 `data:{"count":10}`；关联成功返回 `data:{"id":1}`（关联 ID）；解除返回标准 Success。

错误：401 未登录；403 无权限；404 资源/产品/版本/匹配关联不存在；409 编号重复、并发版本冲突、成本版本不可关联；422 分类、字段、供应商、日期、金额或 CSV 格式非法。

## 部署与验证

XC 原始 CSV 使用 `--category xc`，字段为 DC Name、Site Address、Currency、Tax Rate、NRC、MRC、Remarks；表头前的说明不作为导入指令，不执行加价或汇率换算。明确币种为 EUR/GBP/USD 时，可识别对应的 € / £ / $ 金额前缀。空白报价仍为空，不视为免费；无标题列的非空数据保留到备注。分条件报价保留原值并停用，不取其中一个价格。

Retail Building 原始 CSV 使用 `--category retail`，支持 Burst、Site A、可选 Site B，以及 `USD/Mbps MRC` 原值（不进行汇率换算），并沿用供应商匹配、保留未关联原名、停用不完整记录及重复导入检查。

PtP 原始 CSV 使用 `--category ptp`，支持 Site A、Site B、Price/Mbps MRC；自动识别前 20 行内的表头，表头前的说明不作为成本数据或导入指令。`--allow-unlinked --preserve-incomplete` 可导入未匹配供应商的原始名称，并将缺失必填信息、非标准报价/保护类型/合同期限的记录停用，原值保留在备注。

已确认需要保留不完整原始记录时，导入脚本支持 `--preserve-incomplete`：无法直接表示的价格/保护类型保留在备注，相应字段置空，并将该记录停用；其他原字段不填造。停用记录允许缺失服务、站点或币种，启用时仍强制校验这些字段，停用记录不能关联产品。`--no-vendor-links` 对本次新增记录完全不关联供应商，只保存原供应商名称；不改动已存在的记录。

Colo 原始 CSV 可使用 `python scripts/import_resource_costs_csv.py "文件路径"` 只读预检；确认后加 `--commit` 整批录入。脚本支持尾部无标题列（非空值保存在备注）、千位分隔符、金额中的币种及单位，支持 MYR。`--vendor "原供应商名=ID"` 指定供应商，`--allow-unlinked` 保留原供应商名称但暂不关联未匹配/重名档案，`--currency-by-row "31=USD"` 仅用于已确认的缺失币种。行号按 CSV 记录计数，包含表头。上述映射参数必须以实际确认结果为准。

脚本以系统操作人 `created_by_id=0` 保存，按原始记录内容生成稳定编号，重复运行跳过已导入记录；验证有误时不写入任何数据，不自动创建供应商。完整导入后会回读核对新增数量。

`--vendor` 同时支持供应商编号，例如 `--vendor "Equinix=VU00036"`。使用 `--skip-vendor "名称"` 可明确跳过该原始供应商的所有记录，可重复传入多个；预检输出 `excluded_rows` 列出被跳过的 CSV 记录号。

IPT/DIA 原始 CSV 使用 `--category ipt_dia`，支持 Burst、Price/Mbps MRC、Burst Price/M 字段和 AUD 币种。经确认可加 `--skip-invalid`，仅写入通过校验且供应商匹配明确的记录，输出其他记录号与失败原因；默认仍遇错整批不写入。区间/条件报价不选取单个金额，超精度金额不自动舍入，缺失字段不推测补全。`NA`/`N/A` 金额保留为空值。

新增 Aerich 迁移 `188_20261113120000_resource_costs.py`，创建 `resource_cost`、`resource_cost_version`、`product_cost_link` 三张表及索引/外键/唯一约束，不改写历史迁移和现有业务数据。SQL 由当前 Tortoise PostgreSQL 模型生成，仅创建新表。降级会删除这三张新表，不能在已有成本数据时随意降级。

在测试 PostgreSQL 数据库审阅并执行 `aerich upgrade`（项目后端启动流程也会执行已提交迁移），然后部署前后端并重新登录刷新菜单。无需新增依赖。不要对真实用户数据运行本测试。

验证命令：`python -m unittest tests.test_resource_costs`，`python -m py_compile app/api/v1/resource_costs.py app/schemas/resource_cost.py app/models/resource_cost.py`，前端在 `web` 下执行 `npm run build`、`npm run lint`。
