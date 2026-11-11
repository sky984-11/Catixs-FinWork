# 客户中心主体管理

入口：客户中心 → 主体管理（`/customer-center/signing-entities`）。支持新增、编辑、启用／停用，不提供物理删除。维护名称、全称、编号、国家／地区、注册地址、税号、注册号、Logo 地址及备注；Logo 使用站内路径或 http(s) 图片地址，不涉及文件上传。编号、名称会参与新客户编号前缀推导，修改前应确认编号规则；已有客户编号不会改变。

接口沿用登录和 `DependPermission` 路由权限校验；菜单及权限按客户中心既有初始化策略注册，管理角色默认具有写权限，其他角色需要显式分配 POST／PUT 权限。部署后重启后端刷新接口权限和菜单，前端重新登录刷新菜单。没有数据库结构变更。

| 方法 | 路由（前缀 `/api/v1/customer-center`） | 参数 |
| --- | --- | --- |
| GET | `/signing-entities` | `include_inactive` 布尔值，默认 false，仅返回启用主体；管理页传 true |
| POST | `/signing-entities` | JSON 主体字段，新增 |
| PUT | `/signing-entities/{entity_id}` | 完整 JSON 主体字段，编辑或变更 status |

请求示例：`{"name":"Catixs Ltd","legal_name":"Catixs Ltd","code":"CATIXS-LTD","country":"United Kingdom","address":"6 Watergate Walk, London","tax_no":"","registration_no":"13745695","logo_url":"/logos/catixs.png","status":true,"remark":""}`。

name 必填，去除首尾空格后长度 1–120；legal_name ≤200，code ≤50（空值归一为 null），country ≤80，address ≤255，tax_no / registration_no ≤80，logo_url ≤255，remark ≤500；status 默认 true。名称与非空编号唯一，Logo 拒绝脚本协议、协议相对 URL 和反斜杠。成功响应为 `{"code":200,"msg":"OK","data":{"id":1,"name":"Catixs Ltd","status":true,"logo_url":"/logos/catixs.png"}}`（data 还包含其他主体字段及时间戳）；GET 的 data 为数组。

错误码：401 未登录；403 无路由权限；404 主体不存在；409 名称或编号冲突；422 字段无效。保存失败保持表单，可修改后重试。操作日志仅记录主体 ID、用户 ID 和启用状态。

初始化仅在主体表为空时插入三个默认主体；已有记录不会被覆盖或因改名重新创建。停用不删除历史关联，客户中心选项继续只返回启用主体。新账单使用当前主体资料，已有账单保留名称与地址快照，预览展示的主体名称、地址及 Logo 按账单关联主体读取当前配置。
