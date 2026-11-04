# 产品管理与价格版本

订单集合与客户关联见 [订单管理 API](product-orders-api.md)。

产品管理采用左侧分类树、右侧产品列表。SKU 继续使用现有字段 `code`，现有产品接口保持兼容。产品价格版本是产品目录报价，不会自动改写资源价格、客户订阅或账单。

旧 IDC 初始化曾为每个叶子分类创建同名预置产品（例如 `IP.ASN / ASN`）。应用启动完成数据库迁移后，会清理符合旧目录编码、名称、分类及初始字段值，且没有规格、价格、历史价格、价格版本、DHCP、IDC 工单/服务、账单模板或订阅关联的预置产品。分类本身、用户自建产品及已修改/关联业务的产品保留；此清理不在列表查询中执行。

所有接口前缀为 `/api/v1/product-center`，沿用登录 token 和 `DependPermission` 的路由/方法权限。超级管理员及管理员沿用现有权限规则；其他角色需具备相应 API 权限。启动刷新 API 权限目录后，新路由按现有产品中心授权规则分配。

## 产品

- `GET /products`：`page`、`page_size`、`keyword`、`category_id`、`status`、`region` 沿用现有参数；选中父分类时包含全部后代分类。
- `POST /products`：新增产品。
- `PUT /products/{product_id}`：更新产品，可调整分类；未提交的既有地区、计费模式等字段不改变。
- `DELETE /products/{product_id}`：有订单明细、价格方案历史、手动规格配置或资源价格时拒绝删除，历史报价不会级联丢失。

新增/编辑请求示例：

```json
{"name":"IP Transit","code":"NET-001","category_id":1,"billing_unit":"mbps","min_contract_months":12,"status":"active"}
```

`name`、有效的 `category_id` 和手动填写的 `code`（SKU，1–80 字符）为新增必填项，不再自动生成 SKU。SKU 去除首尾空白后保存；新增缺失、空值或纯空白返回 422，重复返回 409。更新时省略 `code` 保留既有值，显式提交空值或纯空白返回 422。已有 SKU 不回填，修改分类不会重新生成 SKU。`billing_unit` 为 1–40 字符，默认 `month`，支持现有单位或自定义单位；`min_contract_months` 为 1–1200 的整数，默认 1；`status` 为 `active` 或 `offline`。地区不再必填，原字段和数据保留。新增字段同样包含于列表及保存响应的 `data`。

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

## 规格属性分类过滤

`GET /api/v1/product-center/attributes` 沿用登录及路由权限。页面仅保留可搜索的分类下拉框，选择/清空后自动回到第一页查询；请求使用 `category_id`、`page`、`page_size`。旧接口参数 `keyword`（属性名、编码、单位）与 `attr_type` 保持兼容，规格属性页面不再发送它们。

分类匹配同时检查属性的 `category_ids`（多分类）及旧数据的单分类回退。历史目录中祖先至叶子名称路径完全相同的分类视为等价过滤项，例如两套“计算资源 / 物理服务器”均能查到旧属性；不同父级下的同名分类不会混入。此查询不修改分类或属性数据。成功返回 `{"code":200,"data":[...],"total":5,"page":1,"page_size":20}`，每条属性结构不变；不存在的分类返回空列表，未登录返回 401，无接口权限返回 403。

## 产品动态规格字段

`GET /api/v1/product-center/product-spec-fields?category_id=29` 返回适用且启用的规格属性，不分页。分类按完整名称路径兼容旧目录别名，多分类属性同样适用。沿用登录 token 和 `DependPermission`；401 未登录、403 无权限、404 分类不存在、422 分类参数非法。

响应示例：`{"code":200,"msg":"OK","data":[{"id":12,"name":"CPU核心数","code":"cpu_core","attr_type":"number","unit":"核","required":true,"status":true,"select_options":[]}]}`（字段包含既有属性详情）。`select_options` 将属性的 JSON 数组（字符串或 `{label,value}` 对象）或每行一个选项解析为统一字符串选项；空/无效选项配置不会产生可选项。

产品 POST/PUT 增加 `spec_values` 对象，以规格属性 ID 字符串为键。例如 `{"name":"Server","code":"SERVER-001","category_id":29,"spec_values":{"12":32,"15":"Intel"}}`。产品列表及保存响应返回同一对象；旧产品没有值时返回 `{}`。创建时校验当前分类必填规格；更新时提交 `spec_values` 表示替换当前规格值。未提交且分类不变时保持原值，以兼容既有客户端；更换分类时仍校验新分类必填项，未提交规格则只保留仍适用的旧值。

支持文本、数值、单选、多选、开关、日期和资源引用（文本标识）。数值必须是有限 JSON 数字，开关必须是布尔值，0 与 false 均是有效必填值；日期格式为 `YYYY-MM-DD`。单/多选值必须来自属性选项。文本/资源标识最多 2000 字符，最多提交 200 个属性；不适用或停用属性、缺失必填项及类型/选项错误返回 422，产品不保存。选项配置由规格属性维护，不新增资源自动查询行为。

产品编辑弹窗切换分类后重新加载字段并保留交集属性的输入；加载期间禁用保存，失败可重试。产品列表的分类仅显示只读标签；需要调整分类时，通过编辑弹窗选择分类并确认规格后保存，取消不会改变产品分类。产品价格、SKU、分类目录及下线的规格配置功能不变。

Aerich 迁移 `182_20261104140000_product_spec_values.py` 由模型差异生成，新增可空 `product_item.spec_values` JSONB 列，已有产品不强制补值、不清空历史数据。部署先执行 `aerich upgrade`（应用启动也会执行待运行迁移）；降级会删除该列及已填规格值，不应用于需保留规格数据的数据库。
