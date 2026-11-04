# 产品管理与价格版本

产品管理采用左侧分类树、右侧产品列表。SKU 继续使用现有字段 `code`，现有产品接口保持兼容。产品价格版本是产品目录报价，不会自动改写资源价格、客户订阅或账单。

旧 IDC 初始化曾为每个叶子分类创建同名预置产品（例如 `IP.ASN / ASN`）。应用启动完成数据库迁移后，会清理符合旧目录编码、名称、分类及初始字段值，且没有规格、价格、历史价格、价格版本、DHCP、IDC 工单/服务、账单模板或订阅关联的预置产品。分类本身、用户自建产品及已修改/关联业务的产品保留；此清理不在列表查询中执行。

所有接口前缀为 `/api/v1/product-center`，沿用登录 token 和 `DependPermission` 的路由/方法权限。超级管理员及管理员沿用现有权限规则；其他角色需具备相应 API 权限。启动刷新 API 权限目录后，新路由按现有产品中心授权规则分配。

## 产品

- `GET /products`：`page`、`page_size`、`keyword`、`category_id`、`status`、`region` 沿用现有参数；选中父分类时包含全部后代分类。
- `POST /products`：新增产品。
- `PUT /products/{product_id}`：更新产品，可调整分类；未提交的既有地区、计费模式等字段不改变。
- `DELETE /products/{product_id}`：有价格方案历史、手动规格配置或资源价格时拒绝删除，历史报价不会级联丢失。

新增/编辑请求示例：

```json
{"name":"IP Transit","code":"NET-001","category_id":1,"billing_unit":"mbps","min_contract_months":12,"status":"active"}
```

`name` 和有效的 `category_id` 必填；新增时 `code` 留空（或仅空白）按所选分类生成 `分类编码-三位流水号`，例如 `NET.TRANSIT-001`；超过 999 后继续生成 1000，不截断。分类编码为空或超过 60 字符时，使用 `CAT{分类ID}` 作为前缀。按前缀下现存纯数字后缀最大值加一，忽略非数字后缀；分类之间独立编号，手动占用的同前缀编号也会跳过。分类行锁与事务保护同分类并发创建，SKU 唯一约束冲突自动重试，仍冲突返回 409。手动填写的非空 SKU 保留且不允许重复。已有 SKU 不回填，修改分类不会重新生成 SKU。`billing_unit` 为 1–40 字符，默认 `month`，支持现有单位或自定义单位；`min_contract_months` 为 1–1200 的整数，默认 1；`status` 为 `active` 或 `offline`。地区不再必填，原字段和数据保留。新增字段同样包含于列表及保存响应的 `data`。

## 价格方案和版本历史

`GET /products/{product_id}/price-versions`

- 不再按客户筛选。旧客户端传入的 `customer_id` 查询参数忽略，返回该产品的全部价格版本。
- `page`：从 1 开始；`page_size`：默认 20，范围 1–100。
- 返回全部价格版本，按产品内版本号降序，不再区分生效、失效或未来状态。

```json
{"code":200,"msg":null,"data":[{"id":1,"product_id":1,"version":1,"currency":"CNY","mrc":"100.00","nrc":"50.00","period_months":3,"billing_unit":"mbps","created_at":"2026-11-01 10:00:00","updated_at":"2026-11-01 10:00:00"}],"total":1,"page":1,"page_size":20}
```

`POST /products/{product_id}/price-versions`

```json
{"currency":"CNY","mrc":"100.00","nrc":"50.00","period_months":3}
```

- 价格方案仅关联产品，不接受客户定价关联；旧客户端提交的 `customer_id`、`customer_name` 作为额外字段忽略，新记录的客户字段始终为空。订单阶段再关联客户。
- `currency`：`CNY`（默认）、`USD`、`EUR`、`JPY`、`HKD`。
- `mrc`：必填，每计费单位月费；`nrc`：默认 0，一次性开通费。两者为非负有限十进制数，最大 14 位整数、2 位小数；响应使用字符串保留精度。
- `period_months`：1（默认）、3、6、12、24 或 36；周期不改变 MRC 的含义，也不等同于最短合同期。
- 成功响应 `{"code":200,"msg":"价格版本已创建，历史版本保留","data":{...}}`，`data` 结构同列表记录。
- 版本创建后不可覆盖修改，可通过指定版本删除接口移除；计费单位保存快照。后续改价直接新增价格版本，未删除的原记录保持不变。
- 价格方案是产品级价格；本接口不执行订单客户关联、自动选价或账单结算。

## 错误和迁移

- 401：未登录；403：无对应路由/方法权限。
- 404：产品不存在；422：非法金额、周期或请求字段。
- 409：SKU 重复；400：产品存在关联数据不能删除等业务校验失败。
- 价格版本没有 PUT 路由，不能覆盖原价；DELETE 仅支持指定版本，不支持批量删除。
- `/api/v1/customer-center/customers/{customer_id}` 的 DELETE 在客户有关联产品价格版本时返回 409；可停用客户，避免删除历史报价的客户关联。

Aerich 迁移 `180_20261104094924_product_price_versions.py` 新增 `product_item.billing_unit`、`product_item.min_contract_months` 和 `product_price_version` 表。既有产品默认按 `month`、1 个月合同期补齐；旧资源价格不自动转换为版本。迁移由 Aerich 基于改动前后模型生成，使用 PostgreSQL 方言，未修改历史迁移。部署需执行 `aerich upgrade`（项目启动也会执行待运行迁移）；不要将此迁移的降级用于有需保留价格历史的数据库。

## 已下线功能

价格管理、客户历史价格和规格配置的菜单、页面及接口已移除。以下路由不再注册（返回 HTTP 404），原请求参数与响应不再适用，所有角色均无法使用：

- `/api/v1/product-center/prices` 及其子路由（GET、POST、PUT、DELETE，含资源选项及通知设置）。
- `/api/v1/product-center/price-history` 及 `/{history_id}`（GET、DELETE）。
- `/api/v1/product-center/spec-configs` 及 `/{config_id}`（GET、POST、PUT、DELETE）。
- `/api/v1/product-center/spec-config-groups/update`、`/delete`（POST）。
- `/api/v1/product-center/products/{product_id}/sync-physical-servers`（POST）。

启动时清理对应菜单、API 权限和角色授权；停止价格提醒及产品、设备变更触发的规格同步。产品选项不再返回 `spec_configs`。云主机关机不再受历史价格关联限制，其登录及操作权限保持不变。

数据库表和历史记录保留，不执行数据清空或资源释放；历史引用仍参与产品和规格属性删除保护。产品管理、规格属性及产品价格版本接口继续可用。上述功能下线不涉及数据库迁移。

## 删除价格方案版本

`DELETE /api/v1/product-center/products/{product_id}/price-versions/{version_id}`

- 路径参数均为整数；无请求体。沿用登录与 `DependPermission` 校验，需要该 DELETE 路由权限（管理员按既有规则授权）。
- 可删除指定产品下的价格版本，不区分生效状态。删除为永久删除，前端需确认，其他版本不变；不修改账单、订阅或实际资源。
- 使用产品行锁，与同一产品的新增版本操作串行处理。剩余版本不重排；新版本仍按现存最大版本号加一，删除最高版本后该编号可能再次使用，全部删除后从 V1 开始。
- 成功示例：`{"code":200,"msg":"价格版本已删除","data":{"id":12,"product_id":3}}`。
- 错误：401 未登录；403 无删除权限；404 产品不存在、版本不存在或不属于指定产品；422 路径参数非法。失败时前端保留可重试状态。
- 删除全部版本后，产品和客户的版本引用保护随之解除；其他关联数据仍按原规则校验。删除接口本身不涉及数据库迁移，重启后端后刷新 API 权限目录。

## 产品级定价调整

列表及创建响应不再包含 `customer_id`、`customer_name`，前端同步移除客户筛选、客户列、关联客户表单和客户选项传递。请求路径、其他金额与计费字段、鉴权和删除方式保持不变。已有价格记录全部保留并正常展示，历史记录不再参与有效期重叠校验，也不自动合并或覆盖。

数据库的历史客户列及外键暂时保留以兼容已有数据，不清空旧关联；新建版本不再写入客户。旧关联仍沿用客户删除保护。客户字段调整不涉及表结构迁移，也不实现订单管理功能；日期列的迁移见下节。

## 取消价格有效期

价格列表与新增表单移除生效日、失效日和状态。POST 不再要求 `effective_date`、`expiry_date`，旧客户端传入这两个字段或 `status` 时忽略；GET/POST 响应均不再返回这三个字段。相同产品、币种和周期可连续创建多个版本，通过产品行锁分配版本号，不再执行日期先后或重叠校验。权限、金额校验和删除规则不变。

新版本的历史日期列保存为 NULL，旧日期原值保留。新增 Aerich 迁移 `181_20261104120000_price_version_optional_dates.py` 由前后模型差异生成，仅将这两列改为可空，无数据清空；部署运行 `aerich upgrade`（应用启动也会执行待运行迁移）后使用新接口。降级会恢复 NOT NULL，有新建的空日期记录时会被数据库拒绝，不能直接降级。
