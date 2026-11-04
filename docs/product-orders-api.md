# 产品中心：订单管理

订单关联一个客户和 1–200 条产品明细。相同产品合并数量，不重复添加。提供集合管理，不自动生成账单、合同或付款记录。

产品明细先选择产品分类，再选择具体产品；选择父分类包含其子分类产品，切换分类会清空该行原产品。列表及详情明细额外返回 `category_id`（可空）和 `category_name`（无分类时为“未分类”），用于编辑、查看时回显，包括已下架产品。提交仍仅使用 `product_id` 和 `quantity`。

## 权限

所有接口沿用项目 token 登录及 `DependPermission` 路由权限校验。启动后同步 API 和“产品中心 / 订单管理”菜单，并沿用产品中心现有的角色授权规则；调用者需具有对应接口权限。

## 接口

前缀：`/api/v1/product-center`。

| 方法 | 路由 | 参数 / 行为 |
| --- | --- | --- |
| GET | `/orders` | `page` 默认 1；`page_size` 默认 20，最大 100；`keyword` 搜索订单号、名称、客户简称；`customer_id` 按客户筛选 |
| GET | `/orders/{order_id}` | 返回订单及完整产品明细 |
| POST | `/orders` | 新增订单，自动生成唯一 `ORD-` 订单号 |
| PUT | `/orders/{order_id}` | 全量更新名称、客户、备注、产品明细，保留订单号 |
| DELETE | `/orders/{order_id}` | 删除订单及明细，不删除客户或产品 |

POST / PUT 请求示例：

```json
{"name":"香港资源订单","customer_id":1,"remark":"交付说明","items":[{"product_id":10,"quantity":2},{"product_id":11,"quantity":1}]}
```

`name` 去除首尾空格后必填，最长 160 字符；`customer_id`、`product_id` 为正整数；`remark` 可空，最长 5000 字符；`quantity` 为 1–1000000 的整数。

新增关联只允许有效且未终止的客户、在售产品。编辑允许保留原订单已有的停用客户或下架产品。名称、SKU 及客户简称跟随当前关联对象显示，不作为历史报价快照；订单不包含价格。

详情、新增、编辑响应示例：

```json
{"code":200,"msg":"OK","data":{"id":1,"order_no":"ORD-9D6907AC10F14A32A697A8712EA8B042","name":"香港资源订单","customer_id":1,"customer_name":"客户简称","signing_entity_name":"Catixs","remark":"交付说明","created_at":"2026-11-04 15:00:00","updated_at":"2026-11-04 15:00:00","items":[{"product_id":10,"product_name":"线路","product_code":"NET-1","product_status":"active","quantity":2}]}}
```

列表响应 `data` 为订单数组，额外包含 `total`、`page`、`page_size`。删除响应为 `{"code":200,"msg":"订单已删除","data":{"id":1}}`。

## 错误与关联保护

- 400：客户或产品不存在、尝试新增无效客户或下架产品。
- 401 / 403：未登录 / 缺少接口权限。
- 404：订单不存在。
- 409：关联数据发生冲突。
- 422：字段校验失败、空明细、重复产品、无效数量。

客户删除接口 `/api/v1/customer-center/customers/{customer_id}` 在存在订单时返回 409；产品删除接口 `/api/v1/product-center/products/{product_id}` 在存在订单明细时沿用引用保护，返回 400。数据库外键同时禁止删除被引用的客户及产品。

## 部署

先执行 `aerich upgrade`，应用新增迁移 `183_20261104150000_product_orders.py`，再重启后端以同步菜单与 API。迁移新增 `product_order`、`product_order_item` 表，不修改历史业务数据。降级会删除订单数据，应先备份。
