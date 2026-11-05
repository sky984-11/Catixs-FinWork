# 产品规格组合与独立价格

产品维护名称、分类、产品编号、计费单位和最短合同期。产品下预先配置多个规格组合，每个组合有名称、参数值及独立价格版本，无需填写 SKU；不提供任意参数公式算价。

## 使用流程

1. 在“规格属性”中为分类配置参数及类型、必填项、枚举选项。
2. 新增产品，填写公共信息；产品列表操作“规格组合”新增名称和参数。

   参数从规格属性中多选，候选项通过 `/product-spec-fields?category_id={产品分类ID}` 按分类过滤，仅显示适用且启用的属性。必填属性自动选中且不能移除，可选属性按需添加；取消可选属性会移除该组合提交的对应参数值。编辑回显已选参数，已停用或不适用的历史参数单独提示并保留原值。已关联报价或订单的组合仍执行原参数保护规则。
3. 每个组合的“价格方案”维护 MRC、NRC、币种和计费周期。
4. 订单依次选择分类、产品、规格组合，继承该组合的最新公共价格，仍可调整订单 MRC/NRC。

## 鉴权与接口

前缀 `/api/v1/product-center`。全部沿用登录 token 及 `DependPermission`；启动时按现有产品中心规则注册菜单/API 权限。未登录 401、无路由权限 403。

| 方法 | 路由 | 行为 |
| --- | --- | --- |
| GET | `/products/{product_id}/variants` | 所有组合（含下架），按 ID 升序 |
| POST | `/products/{product_id}/variants` | 新增组合 |
| PUT | `/products/{product_id}/variants/{variant_id}` | 全量更新组合 |
| DELETE | `/products/{product_id}/variants/{variant_id}` | 删除未被价格或订单引用的组合 |

POST/PUT 请求：

```json
{"name":"32核 / 128GB","status":"active","spec_values":{"12":32,"15":128}}
```

名称必填、去除首尾空格后不超过 160 字；同一产品组合名称不可重复。`code` 为历史兼容字段，前端不再填写或展示：新增省略或传 null 时自动生成内部唯一编码，编辑省略或传 null 时保留原编码；旧客户端仍可提交不超过 80 字的非空唯一编码。`status` 为 `active` 或 `offline`，默认在售。`spec_values` 最多 200 项，按现有规格属性 ID 保存，校验分类适用范围、必填及文本、数字、单选、多选、开关、日期、资源标识类型。空字符串、空数组不满足必填，数字 0 / 布尔 false 是有效值。此调整不需要新增数据库迁移，历史订单 `variant_code` 快照及接口响应字段保留。

成功响应：

```json
{"code":200,"msg":"OK","data":{"id":1,"product_id":10,"name":"32核 / 128GB","code":"SERVER-128","status":"active","spec_values":{"12":32,"15":128},"spec_snapshot":[{"id":12,"name":"CPU核心数","unit":"核","value":32},{"id":15,"name":"内存","unit":"GB","value":128}],"created_at":"2026-11-05 12:00:00","updated_at":"2026-11-05 12:00:00"}}
```

GET 的 `data` 为上述组合数组；删除返回 `{"code":200,"msg":"规格组合已删除","data":null}`。404 产品或组合不存在/跨产品操作；409 SKU、组合名冲突或引用保护；422 参数格式、必填及类型校验失败。创建、更新、删除均使用产品行锁及事务；日志仅记录对象 ID。

组合一旦有价格版本或订单引用，不能覆盖参数值，需另建新组合；仍可改名称、下架。被引用组合不能删除。产品有组合时不能直接删除或更换分类，避免参数脱离分类及历史关联丢失。

## 产品接口兼容

现有 POST/PUT `/products` 新增请求选项 `parameterized: true`，表示仅维护公共信息，不在产品级要求填写规格值，新建产品的 `spec_values` 为 `{}`；编辑不会覆盖历史 `spec_values`。不传此选项的旧客户端继续按原规格校验逻辑处理。原路由、产品字段及旧数据保留。

## 价格接口扩展

- `GET /products/{product_id}/price-versions?variant_id=1` 按组合查价格；不传仍返回产品所有历史价格。
- `POST /products/{product_id}/price-versions` 增加可选 `variant_id`。未指定时仅当产品只有一个组合才自动选择；多组合返回 422；无组合的旧产品保留原行为。
- `GET /products/{product_id}/order-price?variant_id=1` 返回该组合最新公共价格，绝不从其他组合取价；无报价返回 null。省略组合时遵循相同单组合兼容规则。
- 原 DELETE 价格版本路由不变。价格响应新增 `variant_id`，价格版本号继续在产品内递增，组合过滤后的版本号允许有间隔，历史版本 ID/编号不重排。
- 组合必须属于路径产品，否则 404；币种/金额/计费周期校验及旧权限逻辑不变。币种、计费周期、单位和原价继续由服务端保存快照。

## 订单接口扩展

每条明细新增 `variant_id`，允许同产品的不同组合同时存在；同一组合重复提交返回 422。新订单省略组合时仅允许单组合自动匹配；编辑时旧客户端未传组合且原订单该产品仅有一条明细，则保留原组合。无组合的历史产品仍兼容旧接口。

```json
{"name":"服务器订单","customer_id":1,"items":[{"product_id":10,"variant_id":1,"quantity":2,"mrc":"95.00"},{"product_id":10,"variant_id":2,"quantity":1}]}
```

响应每条明细新增 `variant_id`、`variant_name`、`variant_code`、`spec_snapshot`。`product_name`、组合名称、SKU、参数名称/单位/值按下单时保存，后续修改产品和组合名称不改历史订单；原价、订单微调价快照规则继续有效。保存订单时校验组合归属及状态、价格版本与组合归属，跨组合引用价格返回 409；新增下架组合返回 400，已有订单可保留。订单更新/删除与明细在同一事务完成。

## 数据迁移与部署

新增 Aerich 迁移 `185_20261105120000_product_variants.py`：

- 新增 `product_variant` 表及价格、订单关联列，订单唯一约束改为“订单 + 产品 + 组合”。
- 每个已有产品生成一个“默认组合”，SKU 为 `LEGACY-{产品ID}`，保留原规格值；原产品编号不变。
- 原价格版本、订单关联到相应默认组合；价格 ID、版本号、MRC/NRC 不变，订单名称和参数根据迁移时的数据补快照。
- 不自动合并名字相似的旧产品，不删除任何历史产品、订单或报价。

部署需前后端同步更新，先 `aerich upgrade`（后端启动也会执行待运行迁移）再使用新界面。迁移已通过 PostgreSQL 独立测试 schema 验证，测试事务结束后全部回滚；没有对实际业务库执行该迁移。

降级会删除组合和参数快照；存在同订单同产品多组合时主动拒绝降级，防止退回旧唯一约束时丢数据。请勿在需要保留组合数据的环境降级。

验证命令：

```powershell
.venv-win\Scripts\python.exe -m unittest tests.test_product_variants tests.test_product_orders tests.test_product_price_versions tests.test_product_dynamic_specs tests.test_retired_product_catalog
$env:FINWORK_TEST_POSTGRES_MIGRATION='1'
.venv-win\Scripts\python.exe -m unittest tests.test_product_variants_migration
```
