# Catixs FinWork REST API 文档

版本：`0.1.0`

本文档由后端 FastAPI OpenAPI schema 生成，面向外部项目调用。接口基础路径为 `/api/v1`，完整机器可读 OpenAPI 文件见 [openapi.json](./openapi.json)。

## 快速接入

- Base URL：`http(s)://<host>/api/v1`
- 数据格式：默认使用 `application/json`；上传/导入类接口使用 `multipart/form-data`。
- 认证方式：多数业务接口需要在请求头携带 `token: <access_token>`。
- 获取 Token：`POST /api/v1/base/access_token`。
- 公开文档接口：`GET /api/v1/api/docs`，OpenAPI JSON：`GET /api/v1/api/docs/openapi` 或项目静态文件 `docs/openapi.json`。

## 认证示例

```bash
curl -X POST 'http://localhost:9999/api/v1/base/access_token' \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"your-password"}'
```

后续请求：

```bash
curl 'http://localhost:9999/api/v1/finance/quote/list?page=1&page_size=20' \
  -H 'token: <access_token>'
```

## 通用响应

普通响应：

```json
{"code": 200, "msg": "OK", "data": {}}
```

分页响应：

```json
{"code": 200, "msg": null, "data": [], "total": 0, "page": 1, "page_size": 20}
```

## 分页与查询约定

- 常见列表接口使用 `page`、`page_size` 作为分页参数。
- `GET` 接口参数通常放在 Query String。
- `POST/PUT/PATCH` 接口通常提交 JSON body，少数上传接口提交表单文件。
- 删除接口多数使用 `DELETE` + Query 参数或路径参数。

## 接口总览（215 个分组条目，205 个唯一操作）

### API文档

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `GET` | `/api/v1/api/docs` | 公开API文档 | - | application/json: - |

### API模块

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `POST` | `/api/v1/api/create` | 创建Api | application/json: ApiCreate | application/json: - |
| `DELETE` | `/api/v1/api/delete` | 删除Api | - | application/json: - |
| `GET` | `/api/v1/api/get` | 查看Api | - | application/json: - |
| `GET` | `/api/v1/api/list` | 查看API列表 | - | application/json: - |
| `POST` | `/api/v1/api/refresh` | 刷新API列表 | - | application/json: - |
| `POST` | `/api/v1/api/update` | 更新Api | application/json: ApiUpdate | application/json: - |

### Akvorado

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `GET` | `/api/v1/akvorado/proxy/{region}/{path}` | Proxy Akvorado region UI | - | application/json: - |
| `POST` | `/api/v1/akvorado/proxy/{region}/{path}` | Proxy Akvorado region UI | - | application/json: - |
| `PUT` | `/api/v1/akvorado/proxy/{region}/{path}` | Proxy Akvorado region UI | - | application/json: - |
| `PATCH` | `/api/v1/akvorado/proxy/{region}/{path}` | Proxy Akvorado region UI | - | application/json: - |
| `DELETE` | `/api/v1/akvorado/proxy/{region}/{path}` | Proxy Akvorado region UI | - | application/json: - |
| `OPTIONS` | `/api/v1/akvorado/proxy/{region}/{path}` | Proxy Akvorado region UI | - | application/json: - |

### NetBox IPAM

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `GET` | `/api/v1/netbox/ipam/filter-options` | NetBox IPAM filter options | - | application/json: - |
| `GET` | `/api/v1/netbox/ipam/filter-options` | NetBox IPAM filter options | - | application/json: - |
| `POST` | `/api/v1/netbox/ipam/ip-addresses` | Create NetBox IP address | application/json: object | application/json: - |
| `POST` | `/api/v1/netbox/ipam/ip-addresses` | Create NetBox IP address | application/json: object | application/json: - |
| `PATCH` | `/api/v1/netbox/ipam/ip-addresses/{ip_id}` | Update NetBox IP address | application/json: object | application/json: - |
| `PATCH` | `/api/v1/netbox/ipam/ip-addresses/{ip_id}` | Update NetBox IP address | application/json: object | application/json: - |
| `DELETE` | `/api/v1/netbox/ipam/ip-addresses/{ip_id}` | Delete NetBox IP address | - | application/json: - |
| `DELETE` | `/api/v1/netbox/ipam/ip-addresses/{ip_id}` | Delete NetBox IP address | - | application/json: - |
| `GET` | `/api/v1/netbox/ipam/overview` | NetBox IPAM overview | - | application/json: - |
| `GET` | `/api/v1/netbox/ipam/overview` | NetBox IPAM overview | - | application/json: - |
| `GET` | `/api/v1/netbox/ipam/prefix-ips` | NetBox IPAM prefix IP list | - | application/json: - |
| `GET` | `/api/v1/netbox/ipam/prefix-ips` | NetBox IPAM prefix IP list | - | application/json: - |
| `GET` | `/api/v1/netbox/ipam/prefix-options` | NetBox prefix edit options | - | application/json: - |
| `GET` | `/api/v1/netbox/ipam/prefix-options` | NetBox prefix edit options | - | application/json: - |
| `POST` | `/api/v1/netbox/ipam/prefixes` | Create NetBox prefix | application/json: object | application/json: - |
| `POST` | `/api/v1/netbox/ipam/prefixes` | Create NetBox prefix | application/json: object | application/json: - |
| `PATCH` | `/api/v1/netbox/ipam/prefixes/{prefix_id}` | Update NetBox prefix | application/json: object | application/json: - |
| `PATCH` | `/api/v1/netbox/ipam/prefixes/{prefix_id}` | Update NetBox prefix | application/json: object | application/json: - |
| `DELETE` | `/api/v1/netbox/ipam/prefixes/{prefix_id}` | Delete NetBox prefix | - | application/json: - |
| `DELETE` | `/api/v1/netbox/ipam/prefixes/{prefix_id}` | Delete NetBox prefix | - | application/json: - |
| `POST` | `/api/v1/netbox/ipam/sync-pve-ips` | Schedule PVE guest-agent IP sync to NetBox | - | application/json: - |
| `POST` | `/api/v1/netbox/ipam/sync-pve-ips` | Schedule PVE guest-agent IP sync to NetBox | - | application/json: - |
| `POST` | `/api/v1/netbox/ipam/sync-pve-ips/run-now` | Run PVE IP sync immediately | - | application/json: - |
| `POST` | `/api/v1/netbox/ipam/sync-pve-ips/run-now` | Run PVE IP sync immediately | - | application/json: - |

### PVE Datacenter模块

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `GET` | `/api/v1/pve/nodes` | PDM remote list | - | application/json: - |
| `POST` | `/api/v1/pve/nodes/add` | Add PVE remote to PDM | application/json: PDMAddRemoteRequest | application/json: - |
| `POST` | `/api/v1/pve/nodes/probe` | Probe PVE remote TLS | application/json: PDMProbeRemoteRequest | application/json: - |
| `GET` | `/api/v1/pve/nodes/realms` | PVE remote realms | - | application/json: - |
| `PUT` | `/api/v1/pve/nodes/remote/{remote}` | Update PVE remote | application/json: PDMUpdateRemoteRequest | application/json: - |
| `DELETE` | `/api/v1/pve/nodes/remote/{remote}` | Delete PVE remote | - | application/json: - |
| `GET` | `/api/v1/pve/nodes/remote/{remote}/remark` | Read PVE node remark | - | application/json: - |
| `PUT` | `/api/v1/pve/nodes/remote/{remote}/remark` | Update PVE node remark | application/json: PDMRemoteRemarkRequest | application/json: - |
| `GET` | `/api/v1/pve/tasks/status` | PDM remote task status | - | application/json: - |
| `GET` | `/api/v1/pve/vms` | PDM virtual machine list | - | application/json: - |
| `GET` | `/api/v1/pve/vms/config` | Read PVE virtual machine core config | - | application/json: - |
| `POST` | `/api/v1/pve/vms/config` | Update PVE virtual machine core config | application/json: VMConfigUpdateRequest | application/json: - |
| `POST` | `/api/v1/pve/vms/create` | PVE virtual machine create | application/json: VMCreateRequest | application/json: - |
| `GET` | `/api/v1/pve/vms/create-options` | PVE virtual machine create options | - | application/json: - |
| `POST` | `/api/v1/pve/vms/delete` | Delete PDM virtual machine | application/json: VMDeleteRequest | application/json: - |
| `GET` | `/api/v1/pve/vms/ips` | PVE virtual machine guest-agent IP list | - | application/json: - |
| `POST` | `/api/v1/pve/vms/migrate` | PDM virtual machine remote migration | application/json: VMMigrateRequest | application/json: - |
| `GET` | `/api/v1/pve/vms/migration-options` | PDM virtual machine migration options | - | application/json: - |
| `POST` | `/api/v1/pve/vms/novnc` | PDM virtual machine noVNC console | application/json: NoVNCRequest | application/json: - |
| `POST` | `/api/v1/pve/vms/power` | Start or shutdown PDM virtual machine | application/json: VMPowerRequest | application/json: - |
| `POST` | `/api/v1/pve/vms/reboot` | Reboot PVE virtual machine | application/json: VMDeleteRequest | application/json: - |

### PVE Grafana

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `GET` | `/api/v1/pve/grafana/proxy/{path}` | Proxy Grafana with service account token | - | application/json: - |
| `POST` | `/api/v1/pve/grafana/proxy/{path}` | Proxy Grafana with service account token | - | application/json: - |
| `PUT` | `/api/v1/pve/grafana/proxy/{path}` | Proxy Grafana with service account token | - | application/json: - |
| `PATCH` | `/api/v1/pve/grafana/proxy/{path}` | Proxy Grafana with service account token | - | application/json: - |
| `DELETE` | `/api/v1/pve/grafana/proxy/{path}` | Proxy Grafana with service account token | - | application/json: - |
| `OPTIONS` | `/api/v1/pve/grafana/proxy/{path}` | Proxy Grafana with service account token | - | application/json: - |

### Syslog日志管理模块

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `GET` | `/api/v1/syslog/devices` | Syslog 设备目录 | - | application/json: - |
| `GET` | `/api/v1/syslog/files` | Syslog 日志文件列表 | - | application/json: - |
| `GET` | `/api/v1/syslog/logs` | Syslog 日志查询 | - | application/json: - |
| `GET` | `/api/v1/syslog/raw` | Syslog 原始日志 | - | application/json: - |

### 仪表盘模块

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `GET` | `/api/v1/ticket/dashboard` | 工单仪表盘 | - | application/json: - |

### 供应商模块

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `POST` | `/api/v1/vendor/create` | 创建供应商 | application/json: VendorCreate | application/json: - |
| `DELETE` | `/api/v1/vendor/delete` | 删除供应商 | - | application/json: - |
| `GET` | `/api/v1/vendor/export` | 导出供应商 | - | application/json: - |
| `GET` | `/api/v1/vendor/get` | 查看供应商 | - | application/json: - |
| `POST` | `/api/v1/vendor/import` | 导入供应商 | multipart/form-data: Body_import_vendor_api_v1_vendor_import_post | application/json: - |
| `GET` | `/api/v1/vendor/list` | 查看供应商列表 | - | application/json: - |
| `POST` | `/api/v1/vendor/update` | 更新供应商 | application/json: VendorUpdate | application/json: - |

### 公司模块

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `POST` | `/api/v1/company/create` | 创建公司 | application/json: CompanyCreate | application/json: - |
| `DELETE` | `/api/v1/company/delete` | 删除公司 | - | application/json: - |
| `GET` | `/api/v1/company/get` | 查看公司 | - | application/json: - |
| `GET` | `/api/v1/company/list` | 查看公司列表 | - | application/json: - |
| `POST` | `/api/v1/company/update` | 更新公司 | application/json: CompanyUpdate | application/json: - |

### 基础模块

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `POST` | `/api/v1/base/access_token` | 获取token | application/json: CredentialsSchema | application/json: - |
| `POST` | `/api/v1/base/avatar` | 上传当前用户头像 | application/json: UserAvatarUpload | application/json: - |
| `POST` | `/api/v1/base/profile` | 更新当前用户信息 | application/json: UserProfileUpdate | application/json: - |
| `POST` | `/api/v1/base/update_password` | 修改密码 | application/json: UpdatePassword | application/json: - |
| `GET` | `/api/v1/base/userapi` | 查看用户API | - | application/json: - |
| `GET` | `/api/v1/base/userinfo` | 查看用户信息 | - | application/json: - |
| `GET` | `/api/v1/base/usermenu` | 查看用户菜单 | - | application/json: - |

### 定时任务模块

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `POST` | `/api/v1/task/create` | 创建定时任务 | application/json: ScheduledTaskCreate | application/json: - |
| `DELETE` | `/api/v1/task/delete` | 删除定时任务 | - | application/json: - |
| `GET` | `/api/v1/task/get` | 查看定时任务 | - | application/json: - |
| `GET` | `/api/v1/task/list` | 查看定时任务列表 | - | application/json: - |
| `GET` | `/api/v1/task/logs` | 查看定时任务执行日志 | - | application/json: - |
| `DELETE` | `/api/v1/task/logs` | 清理定时任务执行日志 | - | application/json: - |
| `POST` | `/api/v1/task/run` | 手动执行定时任务 | - | application/json: - |
| `POST` | `/api/v1/task/toggle` | 启停定时任务 | application/json: ScheduledTaskToggle | application/json: - |
| `POST` | `/api/v1/task/update` | 更新定时任务 | application/json: ScheduledTaskUpdate | application/json: - |

### 审计日志模块

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `GET` | `/api/v1/auditlog/list` | 查看操作日志 | - | application/json: - |

### 客户项目看板

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `DELETE` | `/api/v1/project/attachment/delete` | 删除项目截图资料 | - | application/json: - |
| `POST` | `/api/v1/project/attachment/upload` | 上传项目截图资料 | application/json: ProjectAttachmentUpload | application/json: - |
| `POST` | `/api/v1/project/create` | 创建客户项目 | application/json: CustomerProjectCreate | application/json: - |
| `DELETE` | `/api/v1/project/delete` | 删除客户项目 | - | application/json: - |
| `POST` | `/api/v1/project/discussion/create` | 新增项目讨论 | application/json: ProjectDiscussionCreate | application/json: - |
| `DELETE` | `/api/v1/project/discussion/delete` | 删除项目讨论 | - | application/json: - |
| `GET` | `/api/v1/project/get` | 查看客户项目 | - | application/json: - |
| `GET` | `/api/v1/project/list` | 查看客户项目列表 | - | application/json: - |
| `POST` | `/api/v1/project/status` | 更新客户项目看板状态 | application/json: CustomerProjectStatusUpdate | application/json: - |
| `POST` | `/api/v1/project/task/create` | 创建项目任务 | application/json: ProjectTaskCreate | application/json: - |
| `DELETE` | `/api/v1/project/task/delete` | 删除项目任务 | - | application/json: - |
| `POST` | `/api/v1/project/task/update` | 更新项目任务 | application/json: ProjectTaskUpdate | application/json: - |
| `POST` | `/api/v1/project/update` | 更新客户项目 | application/json: CustomerProjectUpdate | application/json: - |

### 工单模块

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `POST` | `/api/v1/ticket/create` | 创建工单 | application/json: TicketCreate | application/json: - |
| `DELETE` | `/api/v1/ticket/delete` | 删除工单 | - | application/json: - |
| `GET` | `/api/v1/ticket/get` | 查看工单详情 | - | application/json: - |
| `GET` | `/api/v1/ticket/get_by_no` | 根据工单编号查询工单 | - | application/json: - |
| `GET` | `/api/v1/ticket/list` | 查看工单列表 | - | application/json: - |
| `POST` | `/api/v1/ticket/reply` | 回复工单 | application/json: TicketReplyCreate | application/json: - |
| `POST` | `/api/v1/ticket/reply/create` | 回复工单 | application/json: TicketReplyCreate | application/json: - |
| `GET` | `/api/v1/ticket/reply/list` | 查看工单回复 | - | application/json: - |
| `POST` | `/api/v1/ticket/reply_create` | 回复工单 | application/json: TicketReplyCreate | application/json: - |
| `POST` | `/api/v1/ticket/send_email` | 发送工单邮件通知 | application/json: TicketEmailSend | application/json: - |
| `POST` | `/api/v1/ticket/update` | 更新工单 | application/json: TicketUpdate | application/json: - |
| `POST` | `/api/v1/ticket/upload` | 上传工单附件图片 | application/json: TicketAttachmentUpload | application/json: - |
| `GET` | `/api/v1/ticket/users` | 查看工单用户选项 | - | application/json: - |

### 报价系统

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `POST` | `/api/v1/finance/quote/create` | 创建报价 | application/json: FinanceQuoteCreate | application/json: - |
| `DELETE` | `/api/v1/finance/quote/delete` | 删除报价 | - | application/json: - |
| `GET` | `/api/v1/finance/quote/field-options` | 报价字段选项 | - | application/json: - |
| `GET` | `/api/v1/finance/quote/get` | 查看报价 | - | application/json: - |
| `GET` | `/api/v1/finance/quote/list` | 查看报价列表 | - | application/json: - |
| `GET` | `/api/v1/finance/quote/site-options` | 站点选项 | - | application/json: - |
| `POST` | `/api/v1/finance/quote/update` | 更新报价 | application/json: FinanceQuoteUpdate | application/json: - |

### 用户模块

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `POST` | `/api/v1/user/create` | 创建用户 | application/json: UserCreate | application/json: - |
| `DELETE` | `/api/v1/user/delete` | 删除用户 | - | application/json: - |
| `GET` | `/api/v1/user/get` | 查看用户 | - | application/json: - |
| `GET` | `/api/v1/user/list` | 查看用户列表 | - | application/json: - |
| `POST` | `/api/v1/user/reset_password` | 重置密码 | application/json: Body_reset_password_api_v1_user_reset_password_post | application/json: - |
| `POST` | `/api/v1/user/update` | 更新用户 | application/json: UserUpdate | application/json: - |

### 菜单模块

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `POST` | `/api/v1/menu/create` | 创建菜单 | application/json: MenuCreate | application/json: - |
| `DELETE` | `/api/v1/menu/delete` | 删除菜单 | - | application/json: - |
| `GET` | `/api/v1/menu/get` | 查看菜单 | - | application/json: - |
| `GET` | `/api/v1/menu/list` | 查看菜单列表 | - | application/json: - |
| `POST` | `/api/v1/menu/update` | 更新菜单 | application/json: MenuUpdate | application/json: - |

### 角色模块

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `GET` | `/api/v1/role/authorized` | 查看角色权限 | - | application/json: - |
| `POST` | `/api/v1/role/authorized` | 更新角色权限 | application/json: RoleUpdateMenusApis | application/json: - |
| `POST` | `/api/v1/role/create` | 创建角色 | application/json: RoleCreate | application/json: - |
| `DELETE` | `/api/v1/role/delete` | 删除角色 | - | application/json: - |
| `GET` | `/api/v1/role/get` | 查看角色 | - | application/json: - |
| `GET` | `/api/v1/role/list` | 查看角色列表 | - | application/json: - |
| `POST` | `/api/v1/role/update` | 更新角色 | application/json: RoleUpdate | application/json: - |

### 账单模块

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `POST` | `/api/v1/bill/create` | 创建账单 | application/json: BillCreate | application/json: - |
| `DELETE` | `/api/v1/bill/delete` | 删除账单 | - | application/json: - |
| `GET` | `/api/v1/bill/get` | 查看账单 | - | application/json: - |
| `GET` | `/api/v1/bill/list` | 查看账单列表 | - | application/json: - |
| `POST` | `/api/v1/bill/update` | 更新账单 | application/json: BillUpdate | application/json: - |
| `POST` | `/api/v1/bill/upload_voucher` | 上传付款凭证 | multipart/form-data: Body_upload_payment_voucher_api_v1_bill_upload_voucher_post | application/json: - |

### 资产管理模块

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `POST` | `/api/v1/asset/cabinet/create` | 创建机柜 | application/json: AssetCabinetCreate | application/json: - |
| `DELETE` | `/api/v1/asset/cabinet/delete` | 删除机柜 | - | application/json: - |
| `GET` | `/api/v1/asset/cabinet/get` | 机柜详情 | - | application/json: - |
| `GET` | `/api/v1/asset/cabinet/list` | 机柜列表 | - | application/json: - |
| `POST` | `/api/v1/asset/cabinet/update` | 更新机柜 | application/json: AssetCabinetUpdate | application/json: - |
| `POST` | `/api/v1/asset/device-brand/create` | 创建设备品牌 | application/json: AssetDeviceBrandCreate | application/json: - |
| `DELETE` | `/api/v1/asset/device-brand/delete` | 删除设备品牌 | - | application/json: - |
| `GET` | `/api/v1/asset/device-brand/list` | 设备品牌型号列表 | - | application/json: - |
| `POST` | `/api/v1/asset/device-model/create` | 创建设备型号 | application/json: AssetDeviceModelCreate | application/json: - |
| `DELETE` | `/api/v1/asset/device-model/delete` | 删除设备型号 | - | application/json: - |
| `POST` | `/api/v1/asset/device/create` | 创建设备 | application/json: AssetDeviceCreate | application/json: - |
| `DELETE` | `/api/v1/asset/device/delete` | 删除设备 | - | application/json: - |
| `GET` | `/api/v1/asset/device/get` | 设备详情 | - | application/json: - |
| `GET` | `/api/v1/asset/device/list` | 设备列表 | - | application/json: - |
| `POST` | `/api/v1/asset/device/update` | 更新设备 | application/json: AssetDeviceUpdate | application/json: - |
| `POST` | `/api/v1/asset/inventory-category/create` | 创建库存分类 | application/json: AssetInventoryCategoryCreate | application/json: - |
| `DELETE` | `/api/v1/asset/inventory-category/delete` | 删除库存分类 | - | application/json: - |
| `GET` | `/api/v1/asset/inventory-category/list` | 库存分类列表 | - | application/json: - |
| `POST` | `/api/v1/asset/inventory-category/update` | 更新库存分类 | application/json: AssetInventoryCategoryUpdate | application/json: - |
| `GET` | `/api/v1/asset/inventory-flow/list` | 库存流水列表 | - | application/json: - |
| `POST` | `/api/v1/asset/inventory-sale/cancel` | 取消库存销售单 | application/json: AssetInventorySaleCancel | application/json: - |
| `POST` | `/api/v1/asset/inventory-sale/create` | 创建库存销售单 | application/json: AssetInventorySaleCreate | application/json: - |
| `GET` | `/api/v1/asset/inventory-sale/list` | 库存销售单列表 | - | application/json: - |
| `POST` | `/api/v1/asset/inventory/create` | 创建库存 | application/json: AssetInventoryCreate | application/json: - |
| `DELETE` | `/api/v1/asset/inventory/delete` | 删除库存 | - | application/json: - |
| `GET` | `/api/v1/asset/inventory/export` | 导出库存 | - | application/json: - |
| `GET` | `/api/v1/asset/inventory/get` | 库存详情 | - | application/json: - |
| `POST` | `/api/v1/asset/inventory/import` | 导入库存 | multipart/form-data: Body_import_inventory_api_v1_asset_inventory_import_post | application/json: - |
| `GET` | `/api/v1/asset/inventory/list` | 库存列表 | - | application/json: - |
| `POST` | `/api/v1/asset/inventory/update` | 更新库存 | application/json: AssetInventoryUpdate | application/json: - |
| `POST` | `/api/v1/asset/location/create` | 创建位置 | application/json: AssetLocationCreate | application/json: - |
| `DELETE` | `/api/v1/asset/location/delete` | 删除位置 | - | application/json: - |
| `GET` | `/api/v1/asset/location/list` | 位置列表 | - | application/json: - |
| `POST` | `/api/v1/asset/location/update` | 更新位置 | application/json: AssetLocationUpdate | application/json: - |
| `POST` | `/api/v1/asset/region/create` | 创建区域 | application/json: AssetRegionCreate | application/json: - |
| `DELETE` | `/api/v1/asset/region/delete` | 删除区域 | - | application/json: - |
| `GET` | `/api/v1/asset/region/get` | 区域详情 | - | application/json: - |
| `GET` | `/api/v1/asset/region/list` | 区域列表 | - | application/json: - |
| `POST` | `/api/v1/asset/region/update` | 更新区域 | application/json: AssetRegionUpdate | application/json: - |
| `GET` | `/api/v1/asset/tree` | 资产位置树 | - | application/json: - |

### 运维记录模块

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `POST` | `/api/v1/remote-assistance/engineers` | 新增工程师 | application/json: EngineerPayload | application/json: - |
| `PUT` | `/api/v1/remote-assistance/engineers/{engineer_id}` | 更新工程师 | application/json: EngineerPayload | application/json: - |
| `DELETE` | `/api/v1/remote-assistance/engineers/{engineer_id}` | 删除工程师 | - | application/json: - |
| `GET` | `/api/v1/remote-assistance/overview` | 运维记录页面数据 | - | application/json: - |
| `POST` | `/api/v1/remote-assistance/remote-hands` | 新增运维记录 | application/json: RemoteHandsPayload | application/json: - |
| `PUT` | `/api/v1/remote-assistance/remote-hands/{item_id}` | 更新运维记录 | application/json: RemoteHandsPayload | application/json: - |
| `DELETE` | `/api/v1/remote-assistance/remote-hands/{item_id}` | 删除运维记录 | - | application/json: - |

### 部门模块

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `POST` | `/api/v1/dept/create` | 创建部门 | application/json: DeptCreate | application/json: - |
| `DELETE` | `/api/v1/dept/delete` | 删除部门 | - | application/json: - |
| `GET` | `/api/v1/dept/get` | 查看部门 | - | application/json: - |
| `GET` | `/api/v1/dept/list` | 查看部门列表 | - | application/json: - |
| `POST` | `/api/v1/dept/update` | 更新部门 | application/json: DeptUpdate | application/json: - |

### 银行模块

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `POST` | `/api/v1/bank/create` | 创建银行 | application/json: BankCreate | application/json: - |
| `DELETE` | `/api/v1/bank/delete` | 删除银行 | - | application/json: - |
| `GET` | `/api/v1/bank/list` | 查看银行列表 | - | application/json: - |
| `POST` | `/api/v1/bank/update` | 更新银行 | application/json: BankUpdate | application/json: - |

### 银行账户模块

| Method | Path | Summary | Request Body | Response |
|---|---|---|---|---|
| `POST` | `/api/v1/bank_account/create` | 创建银行账户 | application/json: BankAccountCreate | application/json: - |
| `DELETE` | `/api/v1/bank_account/delete` | 删除银行账户 | - | application/json: - |
| `GET` | `/api/v1/bank_account/list` | 查看银行账户列表 | - | application/json: - |
| `POST` | `/api/v1/bank_account/update` | 更新银行账户 | application/json: BankAccountUpdate | application/json: - |

## 接口明细

### API文档

#### `GET /api/v1/api/docs`

- 摘要：公开API文档
- Operation ID：`get_api_docs_api_v1_api_docs_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| path | query | 否 | string | API路径 |
| method | query | 否 | string | 请求方式 |
| tags | query | 否 | string | API模块 |
| include_public | query | 否 | boolean | 是否包含无需权限的公开接口 |

### API模块

#### `POST /api/v1/api/create`

- 摘要：创建Api
- Operation ID：`create_api_api_v1_api_create_post`
- Request Body：application/json: ApiCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/api/delete`

- 摘要：删除Api
- Operation ID：`delete_api_api_v1_api_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| api_id | query | 是 | integer | ApiID |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/api/get`

- 摘要：查看Api
- Operation ID：`get_api_api_v1_api_get_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| id | query | 是 | integer | Api |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/api/list`

- 摘要：查看API列表
- Operation ID：`list_api_api_v1_api_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| page | query | 否 | integer | 页码 |
| page_size | query | 否 | integer | 每页数量 |
| path | query | 否 | string | API路径 |
| summary | query | 否 | string | API简介 |
| tags | query | 否 | string | API模块 |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/api/refresh`

- 摘要：刷新API列表
- Operation ID：`refresh_api_api_v1_api_refresh_post`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/api/update`

- 摘要：更新Api
- Operation ID：`update_api_api_v1_api_update_post`
- Request Body：application/json: ApiUpdate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

### Akvorado

#### `GET /api/v1/akvorado/proxy/{region}/{path}`

- 摘要：Proxy Akvorado region UI
- Operation ID：`akvorado_proxy_api_v1_akvorado_proxy__region___path__get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| region | path | 是 | string |  |
| path | path | 是 | string |  |
| token | query | 否 | string |  |

#### `POST /api/v1/akvorado/proxy/{region}/{path}`

- 摘要：Proxy Akvorado region UI
- Operation ID：`akvorado_proxy_api_v1_akvorado_proxy__region___path__get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| region | path | 是 | string |  |
| path | path | 是 | string |  |
| token | query | 否 | string |  |

#### `PUT /api/v1/akvorado/proxy/{region}/{path}`

- 摘要：Proxy Akvorado region UI
- Operation ID：`akvorado_proxy_api_v1_akvorado_proxy__region___path__get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| region | path | 是 | string |  |
| path | path | 是 | string |  |
| token | query | 否 | string |  |

#### `PATCH /api/v1/akvorado/proxy/{region}/{path}`

- 摘要：Proxy Akvorado region UI
- Operation ID：`akvorado_proxy_api_v1_akvorado_proxy__region___path__get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| region | path | 是 | string |  |
| path | path | 是 | string |  |
| token | query | 否 | string |  |

#### `DELETE /api/v1/akvorado/proxy/{region}/{path}`

- 摘要：Proxy Akvorado region UI
- Operation ID：`akvorado_proxy_api_v1_akvorado_proxy__region___path__get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| region | path | 是 | string |  |
| path | path | 是 | string |  |
| token | query | 否 | string |  |

#### `OPTIONS /api/v1/akvorado/proxy/{region}/{path}`

- 摘要：Proxy Akvorado region UI
- Operation ID：`akvorado_proxy_api_v1_akvorado_proxy__region___path__get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| region | path | 是 | string |  |
| path | path | 是 | string |  |
| token | query | 否 | string |  |

### NetBox IPAM

#### `GET /api/v1/netbox/ipam/filter-options`

- 摘要：NetBox IPAM filter options
- Operation ID：`ipam_filter_options_api_v1_netbox_ipam_filter_options_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| search | query | 否 | string |  |
| family | query | 否 | integer | null |  |
| status | query | 否 | string |  |
| refresh | query | 否 | boolean |  |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/netbox/ipam/filter-options`

- 摘要：NetBox IPAM filter options
- Operation ID：`ipam_filter_options_api_v1_netbox_ipam_filter_options_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| search | query | 否 | string |  |
| family | query | 否 | integer | null |  |
| status | query | 否 | string |  |
| refresh | query | 否 | boolean |  |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/netbox/ipam/ip-addresses`

- 摘要：Create NetBox IP address
- Operation ID：`create_ip_address_api_v1_netbox_ipam_ip_addresses_post`
- Request Body：application/json: object
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/netbox/ipam/ip-addresses`

- 摘要：Create NetBox IP address
- Operation ID：`create_ip_address_api_v1_netbox_ipam_ip_addresses_post`
- Request Body：application/json: object
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `PATCH /api/v1/netbox/ipam/ip-addresses/{ip_id}`

- 摘要：Update NetBox IP address
- Operation ID：`update_ip_address_api_v1_netbox_ipam_ip_addresses__ip_id__patch`
- Request Body：application/json: object
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| ip_id | path | 是 | integer |  |
| token | header | 是 | string | token验证 |

#### `PATCH /api/v1/netbox/ipam/ip-addresses/{ip_id}`

- 摘要：Update NetBox IP address
- Operation ID：`update_ip_address_api_v1_netbox_ipam_ip_addresses__ip_id__patch`
- Request Body：application/json: object
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| ip_id | path | 是 | integer |  |
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/netbox/ipam/ip-addresses/{ip_id}`

- 摘要：Delete NetBox IP address
- Operation ID：`delete_ip_address_api_v1_netbox_ipam_ip_addresses__ip_id__delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| ip_id | path | 是 | integer |  |
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/netbox/ipam/ip-addresses/{ip_id}`

- 摘要：Delete NetBox IP address
- Operation ID：`delete_ip_address_api_v1_netbox_ipam_ip_addresses__ip_id__delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| ip_id | path | 是 | integer |  |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/netbox/ipam/overview`

- 摘要：NetBox IPAM overview
- Operation ID：`ipam_overview_api_v1_netbox_ipam_overview_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| search | query | 否 | string |  |
| family | query | 否 | integer | null |  |
| status | query | 否 | string |  |
| region | query | 否 | string |  |
| customer | query | 否 | string |  |
| supplier | query | 否 | string |  |
| page | query | 否 | integer |  |
| page_size | query | 否 | integer |  |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/netbox/ipam/overview`

- 摘要：NetBox IPAM overview
- Operation ID：`ipam_overview_api_v1_netbox_ipam_overview_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| search | query | 否 | string |  |
| family | query | 否 | integer | null |  |
| status | query | 否 | string |  |
| region | query | 否 | string |  |
| customer | query | 否 | string |  |
| supplier | query | 否 | string |  |
| page | query | 否 | integer |  |
| page_size | query | 否 | integer |  |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/netbox/ipam/prefix-ips`

- 摘要：NetBox IPAM prefix IP list
- Operation ID：`ipam_prefix_ips_api_v1_netbox_ipam_prefix_ips_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| prefix | query | 是 | string |  |
| prefix_id | query | 否 | string |  |
| page | query | 否 | integer |  |
| page_size | query | 否 | integer |  |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/netbox/ipam/prefix-ips`

- 摘要：NetBox IPAM prefix IP list
- Operation ID：`ipam_prefix_ips_api_v1_netbox_ipam_prefix_ips_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| prefix | query | 是 | string |  |
| prefix_id | query | 否 | string |  |
| page | query | 否 | integer |  |
| page_size | query | 否 | integer |  |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/netbox/ipam/prefix-options`

- 摘要：NetBox prefix edit options
- Operation ID：`prefix_options_api_v1_netbox_ipam_prefix_options_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `GET /api/v1/netbox/ipam/prefix-options`

- 摘要：NetBox prefix edit options
- Operation ID：`prefix_options_api_v1_netbox_ipam_prefix_options_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/netbox/ipam/prefixes`

- 摘要：Create NetBox prefix
- Operation ID：`create_prefix_api_v1_netbox_ipam_prefixes_post`
- Request Body：application/json: object
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/netbox/ipam/prefixes`

- 摘要：Create NetBox prefix
- Operation ID：`create_prefix_api_v1_netbox_ipam_prefixes_post`
- Request Body：application/json: object
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `PATCH /api/v1/netbox/ipam/prefixes/{prefix_id}`

- 摘要：Update NetBox prefix
- Operation ID：`update_prefix_api_v1_netbox_ipam_prefixes__prefix_id__patch`
- Request Body：application/json: object
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| prefix_id | path | 是 | integer |  |
| token | header | 是 | string | token验证 |

#### `PATCH /api/v1/netbox/ipam/prefixes/{prefix_id}`

- 摘要：Update NetBox prefix
- Operation ID：`update_prefix_api_v1_netbox_ipam_prefixes__prefix_id__patch`
- Request Body：application/json: object
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| prefix_id | path | 是 | integer |  |
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/netbox/ipam/prefixes/{prefix_id}`

- 摘要：Delete NetBox prefix
- Operation ID：`delete_prefix_api_v1_netbox_ipam_prefixes__prefix_id__delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| prefix_id | path | 是 | integer |  |
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/netbox/ipam/prefixes/{prefix_id}`

- 摘要：Delete NetBox prefix
- Operation ID：`delete_prefix_api_v1_netbox_ipam_prefixes__prefix_id__delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| prefix_id | path | 是 | integer |  |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/netbox/ipam/sync-pve-ips`

- 摘要：Schedule PVE guest-agent IP sync to NetBox
- Operation ID：`sync_pve_ips_to_netbox_api_v1_netbox_ipam_sync_pve_ips_post`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/netbox/ipam/sync-pve-ips`

- 摘要：Schedule PVE guest-agent IP sync to NetBox
- Operation ID：`sync_pve_ips_to_netbox_api_v1_netbox_ipam_sync_pve_ips_post`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/netbox/ipam/sync-pve-ips/run-now`

- 摘要：Run PVE IP sync immediately
- Operation ID：`run_pve_ip_sync_now_api_v1_netbox_ipam_sync_pve_ips_run_now_post`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| node | query | 否 | string |  |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/netbox/ipam/sync-pve-ips/run-now`

- 摘要：Run PVE IP sync immediately
- Operation ID：`run_pve_ip_sync_now_api_v1_netbox_ipam_sync_pve_ips_run_now_post`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| node | query | 否 | string |  |
| token | header | 是 | string | token验证 |

### PVE Datacenter模块

#### `GET /api/v1/pve/nodes`

- 摘要：PDM remote list
- Operation ID：`list_nodes_api_v1_pve_nodes_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/pve/nodes/add`

- 摘要：Add PVE remote to PDM
- Operation ID：`add_pve_remote_api_v1_pve_nodes_add_post`
- Request Body：application/json: PDMAddRemoteRequest
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/pve/nodes/probe`

- 摘要：Probe PVE remote TLS
- Operation ID：`probe_pve_remote_api_v1_pve_nodes_probe_post`
- Request Body：application/json: PDMProbeRemoteRequest
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `GET /api/v1/pve/nodes/realms`

- 摘要：PVE remote realms
- Operation ID：`pve_remote_realms_api_v1_pve_nodes_realms_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| hostname | query | 是 | string |  |
| fingerprint | query | 否 | string |  |
| token | header | 是 | string | token验证 |

#### `PUT /api/v1/pve/nodes/remote/{remote}`

- 摘要：Update PVE remote
- Operation ID：`update_pve_remote_api_v1_pve_nodes_remote__remote__put`
- Request Body：application/json: PDMUpdateRemoteRequest
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| remote | path | 是 | string |  |
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/pve/nodes/remote/{remote}`

- 摘要：Delete PVE remote
- Operation ID：`delete_pve_remote_api_v1_pve_nodes_remote__remote__delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| remote | path | 是 | string |  |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/pve/nodes/remote/{remote}/remark`

- 摘要：Read PVE node remark
- Operation ID：`get_pve_remote_remark_api_v1_pve_nodes_remote__remote__remark_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| remote | path | 是 | string |  |
| host | query | 否 | string |  |
| token | header | 是 | string | token验证 |

#### `PUT /api/v1/pve/nodes/remote/{remote}/remark`

- 摘要：Update PVE node remark
- Operation ID：`update_pve_remote_remark_api_v1_pve_nodes_remote__remote__remark_put`
- Request Body：application/json: PDMRemoteRemarkRequest
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| remote | path | 是 | string |  |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/pve/tasks/status`

- 摘要：PDM remote task status
- Operation ID：`task_status_api_v1_pve_tasks_status_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| upid | query | 是 | string |  |
| remote | query | 否 | string |  |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/pve/vms`

- 摘要：PDM virtual machine list
- Operation ID：`list_vms_api_v1_pve_vms_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| node | query | 否 | string |  |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/pve/vms/config`

- 摘要：Read PVE virtual machine core config
- Operation ID：`vm_config_api_v1_pve_vms_config_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| remote | query | 是 | string |  |
| vmid | query | 是 | integer |  |
| type | query | 否 | string |  |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/pve/vms/config`

- 摘要：Update PVE virtual machine core config
- Operation ID：`update_vm_config_api_v1_pve_vms_config_post`
- Request Body：application/json: VMConfigUpdateRequest
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/pve/vms/create`

- 摘要：PVE virtual machine create
- Operation ID：`create_vm_api_v1_pve_vms_create_post`
- Request Body：application/json: VMCreateRequest
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `GET /api/v1/pve/vms/create-options`

- 摘要：PVE virtual machine create options
- Operation ID：`create_options_api_v1_pve_vms_create_options_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| node_ip | query | 是 | string | PVE node IP or PDM remote name |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/pve/vms/delete`

- 摘要：Delete PDM virtual machine
- Operation ID：`delete_vm_api_v1_pve_vms_delete_post`
- Request Body：application/json: VMDeleteRequest
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `GET /api/v1/pve/vms/ips`

- 摘要：PVE virtual machine guest-agent IP list
- Operation ID：`list_vm_ips_api_v1_pve_vms_ips_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| node | query | 否 | string |  |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/pve/vms/migrate`

- 摘要：PDM virtual machine remote migration
- Operation ID：`migrate_vm_api_v1_pve_vms_migrate_post`
- Request Body：application/json: VMMigrateRequest
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `GET /api/v1/pve/vms/migration-options`

- 摘要：PDM virtual machine migration options
- Operation ID：`migration_options_api_v1_pve_vms_migration_options_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| remote | query | 是 | string |  |
| vmid | query | 是 | integer |  |
| type | query | 否 | string |  |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/pve/vms/novnc`

- 摘要：PDM virtual machine noVNC console
- Operation ID：`novnc_console_api_v1_pve_vms_novnc_post`
- Request Body：application/json: NoVNCRequest
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/pve/vms/power`

- 摘要：Start or shutdown PDM virtual machine
- Operation ID：`power_vm_api_v1_pve_vms_power_post`
- Request Body：application/json: VMPowerRequest
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/pve/vms/reboot`

- 摘要：Reboot PVE virtual machine
- Operation ID：`reboot_vm_api_v1_pve_vms_reboot_post`
- Request Body：application/json: VMDeleteRequest
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

### PVE Grafana

#### `GET /api/v1/pve/grafana/proxy/{path}`

- 摘要：Proxy Grafana with service account token
- Operation ID：`grafana_proxy_api_v1_pve_grafana_proxy__path__get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| path | path | 是 | string |  |
| token | query | 否 | string |  |

#### `POST /api/v1/pve/grafana/proxy/{path}`

- 摘要：Proxy Grafana with service account token
- Operation ID：`grafana_proxy_api_v1_pve_grafana_proxy__path__get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| path | path | 是 | string |  |
| token | query | 否 | string |  |

#### `PUT /api/v1/pve/grafana/proxy/{path}`

- 摘要：Proxy Grafana with service account token
- Operation ID：`grafana_proxy_api_v1_pve_grafana_proxy__path__get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| path | path | 是 | string |  |
| token | query | 否 | string |  |

#### `PATCH /api/v1/pve/grafana/proxy/{path}`

- 摘要：Proxy Grafana with service account token
- Operation ID：`grafana_proxy_api_v1_pve_grafana_proxy__path__get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| path | path | 是 | string |  |
| token | query | 否 | string |  |

#### `DELETE /api/v1/pve/grafana/proxy/{path}`

- 摘要：Proxy Grafana with service account token
- Operation ID：`grafana_proxy_api_v1_pve_grafana_proxy__path__get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| path | path | 是 | string |  |
| token | query | 否 | string |  |

#### `OPTIONS /api/v1/pve/grafana/proxy/{path}`

- 摘要：Proxy Grafana with service account token
- Operation ID：`grafana_proxy_api_v1_pve_grafana_proxy__path__get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| path | path | 是 | string |  |
| token | query | 否 | string |  |

### Syslog日志管理模块

#### `GET /api/v1/syslog/devices`

- 摘要：Syslog 设备目录
- Operation ID：`list_syslog_devices_api_v1_syslog_devices_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `GET /api/v1/syslog/files`

- 摘要：Syslog 日志文件列表
- Operation ID：`list_syslog_files_api_v1_syslog_files_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| device | query | 是 | string |  |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/syslog/logs`

- 摘要：Syslog 日志查询
- Operation ID：`query_syslog_logs_api_v1_syslog_logs_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| page | query | 否 | integer |  |
| page_size | query | 否 | integer |  |
| device | query | 是 | string |  |
| file | query | 是 | string |  |
| keyword | query | 否 | string |  |
| level | query | 否 | string |  |
| vendor | query | 否 | string |  |
| tail | query | 否 | integer |  |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/syslog/raw`

- 摘要：Syslog 原始日志
- Operation ID：`get_syslog_raw_api_v1_syslog_raw_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| device | query | 是 | string |  |
| file | query | 是 | string |  |
| tail | query | 否 | integer |  |
| token | header | 是 | string | token验证 |

### 仪表盘模块

#### `GET /api/v1/ticket/dashboard`

- 摘要：工单仪表盘
- Operation ID：`ticket_dashboard_api_v1_ticket_dashboard_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

### 供应商模块

#### `POST /api/v1/vendor/create`

- 摘要：创建供应商
- Operation ID：`create_vendor_api_v1_vendor_create_post`
- Request Body：application/json: VendorCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/vendor/delete`

- 摘要：删除供应商
- Operation ID：`delete_vendor_api_v1_vendor_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| vendor_id | query | 是 | integer | 供应商ID |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/vendor/export`

- 摘要：导出供应商
- Operation ID：`export_vendor_api_v1_vendor_export_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `GET /api/v1/vendor/get`

- 摘要：查看供应商
- Operation ID：`get_vendor_api_v1_vendor_get_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| vendor_id | query | 是 | integer | 供应商ID |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/vendor/import`

- 摘要：导入供应商
- Operation ID：`import_vendor_api_v1_vendor_import_post`
- Request Body：multipart/form-data: Body_import_vendor_api_v1_vendor_import_post
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `GET /api/v1/vendor/list`

- 摘要：查看供应商列表
- Operation ID：`list_vendor_api_v1_vendor_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| page | query | 否 | integer | 页码 |
| page_size | query | 否 | integer | 每页数量 |
| name | query | 否 | string | 供应商名称，用于搜索 |
| code | query | 否 | string | 供应商编号 |
| status | query | 否 | boolean | null | 启用状态 |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/vendor/update`

- 摘要：更新供应商
- Operation ID：`update_vendor_api_v1_vendor_update_post`
- Request Body：application/json: VendorUpdate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

### 公司模块

#### `POST /api/v1/company/create`

- 摘要：创建公司
- Operation ID：`create_company_api_v1_company_create_post`
- Request Body：application/json: CompanyCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/company/delete`

- 摘要：删除公司
- Operation ID：`delete_company_api_v1_company_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| company_id | query | 是 | integer | 公司ID |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/company/get`

- 摘要：查看公司
- Operation ID：`get_company_api_v1_company_get_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| company_id | query | 是 | integer | 公司ID |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/company/list`

- 摘要：查看公司列表
- Operation ID：`list_company_api_v1_company_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| page | query | 否 | integer | 页码 |
| page_size | query | 否 | integer | 每页数量 |
| name | query | 否 | string | 公司简称/全称，用于搜索 |
| code | query | 否 | string | 公司编号 |
| role | query | 否 | integer | null | 角色：0=签约主体, 1=客户, 2=供应商, 3=客户+供应商 |
| status | query | 否 | boolean | null | 启用状态 |
| business_only | query | 否 | boolean | 仅查询客户和供应商 |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/company/update`

- 摘要：更新公司
- Operation ID：`update_company_api_v1_company_update_post`
- Request Body：application/json: CompanyUpdate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

### 基础模块

#### `POST /api/v1/base/access_token`

- 摘要：获取token
- Operation ID：`login_access_token_api_v1_base_access_token_post`
- Request Body：application/json: CredentialsSchema
- Response：application/json: -

参数：

无

#### `POST /api/v1/base/avatar`

- 摘要：上传当前用户头像
- Operation ID：`upload_user_avatar_api_v1_base_avatar_post`
- Request Body：application/json: UserAvatarUpload
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/base/profile`

- 摘要：更新当前用户信息
- Operation ID：`update_user_profile_api_v1_base_profile_post`
- Request Body：application/json: UserProfileUpdate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/base/update_password`

- 摘要：修改密码
- Operation ID：`update_user_password_api_v1_base_update_password_post`
- Request Body：application/json: UpdatePassword
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `GET /api/v1/base/userapi`

- 摘要：查看用户API
- Operation ID：`get_user_api_api_v1_base_userapi_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `GET /api/v1/base/userinfo`

- 摘要：查看用户信息
- Operation ID：`get_userinfo_api_v1_base_userinfo_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `GET /api/v1/base/usermenu`

- 摘要：查看用户菜单
- Operation ID：`get_user_menu_api_v1_base_usermenu_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

### 定时任务模块

#### `POST /api/v1/task/create`

- 摘要：创建定时任务
- Operation ID：`create_task_api_v1_task_create_post`
- Request Body：application/json: ScheduledTaskCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/task/delete`

- 摘要：删除定时任务
- Operation ID：`delete_task_api_v1_task_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| id | query | 是 | integer | 任务ID |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/task/get`

- 摘要：查看定时任务
- Operation ID：`get_task_api_v1_task_get_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| id | query | 是 | integer | 任务ID |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/task/list`

- 摘要：查看定时任务列表
- Operation ID：`list_task_api_v1_task_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| page | query | 否 | integer | 页码 |
| page_size | query | 否 | integer | 每页数量 |
| name | query | 否 | string | 任务名称 |
| task_type | query | 否 | string | 任务类型 |
| is_enabled | query | 否 | boolean | 是否启用 |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/task/logs`

- 摘要：查看定时任务执行日志
- Operation ID：`list_task_logs_api_v1_task_logs_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| page | query | 否 | integer | 页码 |
| page_size | query | 否 | integer | 每页数量 |
| task_id | query | 否 | integer | 任务ID |
| status | query | 否 | string | 执行状态 |
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/task/logs`

- 摘要：清理定时任务执行日志
- Operation ID：`clear_task_logs_api_v1_task_logs_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| task_id | query | 否 | integer | 任务ID |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/task/run`

- 摘要：手动执行定时任务
- Operation ID：`run_task_api_v1_task_run_post`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| id | query | 是 | integer | 任务ID |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/task/toggle`

- 摘要：启停定时任务
- Operation ID：`toggle_task_api_v1_task_toggle_post`
- Request Body：application/json: ScheduledTaskToggle
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/task/update`

- 摘要：更新定时任务
- Operation ID：`update_task_api_v1_task_update_post`
- Request Body：application/json: ScheduledTaskUpdate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

### 审计日志模块

#### `GET /api/v1/auditlog/list`

- 摘要：查看操作日志
- Operation ID：`get_audit_log_list_api_v1_auditlog_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| page | query | 否 | integer | 页码 |
| page_size | query | 否 | integer | 每页数量 |
| username | query | 否 | string | 操作人名称 |
| module | query | 否 | string | 功能模块 |
| method | query | 否 | string | 请求方法 |
| summary | query | 否 | string | 接口描述 |
| path | query | 否 | string | 请求路径 |
| status | query | 否 | integer | 状态码 |
| start_time | query | 否 | string | 开始时间 |
| end_time | query | 否 | string | 结束时间 |
| token | header | 是 | string | token验证 |

### 客户项目看板

#### `DELETE /api/v1/project/attachment/delete`

- 摘要：删除项目截图资料
- Operation ID：`delete_project_attachment_api_v1_project_attachment_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| attachment_id | query | 是 | integer | 附件ID |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/project/attachment/upload`

- 摘要：上传项目截图资料
- Operation ID：`upload_project_attachment_api_v1_project_attachment_upload_post`
- Request Body：application/json: ProjectAttachmentUpload
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/project/create`

- 摘要：创建客户项目
- Operation ID：`create_project_api_v1_project_create_post`
- Request Body：application/json: CustomerProjectCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/project/delete`

- 摘要：删除客户项目
- Operation ID：`delete_project_api_v1_project_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| project_id | query | 是 | integer | 项目ID |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/project/discussion/create`

- 摘要：新增项目讨论
- Operation ID：`create_project_discussion_api_v1_project_discussion_create_post`
- Request Body：application/json: ProjectDiscussionCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/project/discussion/delete`

- 摘要：删除项目讨论
- Operation ID：`delete_project_discussion_api_v1_project_discussion_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| discussion_id | query | 是 | integer | 讨论ID |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/project/get`

- 摘要：查看客户项目
- Operation ID：`get_project_api_v1_project_get_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| project_id | query | 是 | integer | 项目ID |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/project/list`

- 摘要：查看客户项目列表
- Operation ID：`list_project_api_v1_project_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| page | query | 否 | integer | 页码 |
| page_size | query | 否 | integer | 每页数量 |
| keyword | query | 否 | string | 项目名、编号、合同号或负责人 |
| customer_id | query | 否 | integer | null | 客户ID |
| status | query | 否 | string | 项目状态 |
| priority | query | 否 | string | 优先级 |
| health | query | 否 | string | 健康度 |
| owner | query | 否 | string | 负责人 |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/project/status`

- 摘要：更新客户项目看板状态
- Operation ID：`update_project_status_api_v1_project_status_post`
- Request Body：application/json: CustomerProjectStatusUpdate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/project/task/create`

- 摘要：创建项目任务
- Operation ID：`create_project_task_api_v1_project_task_create_post`
- Request Body：application/json: ProjectTaskCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/project/task/delete`

- 摘要：删除项目任务
- Operation ID：`delete_project_task_api_v1_project_task_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| task_id | query | 是 | integer | 任务ID |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/project/task/update`

- 摘要：更新项目任务
- Operation ID：`update_project_task_api_v1_project_task_update_post`
- Request Body：application/json: ProjectTaskUpdate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/project/update`

- 摘要：更新客户项目
- Operation ID：`update_project_api_v1_project_update_post`
- Request Body：application/json: CustomerProjectUpdate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

### 工单模块

#### `POST /api/v1/ticket/create`

- 摘要：创建工单
- Operation ID：`create_ticket_api_v1_ticket_create_post`
- Request Body：application/json: TicketCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/ticket/delete`

- 摘要：删除工单
- Operation ID：`delete_ticket_api_v1_ticket_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| ticket_id | query | 是 | integer | 工单ID |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/ticket/get`

- 摘要：查看工单详情
- Operation ID：`get_ticket_api_v1_ticket_get_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| ticket_id | query | 是 | integer | 工单ID |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/ticket/get_by_no`

- 摘要：根据工单编号查询工单
- Operation ID：`get_ticket_by_no_api_v1_ticket_get_by_no_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| ticket_no | query | 是 | string | 工单编号 |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/ticket/list`

- 摘要：查看工单列表
- Operation ID：`list_tickets_api_v1_ticket_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| page | query | 否 | integer | 页码 |
| page_size | query | 否 | integer | 每页数量 |
| title | query | 否 | string | 工单标题，用于搜索 |
| status | query | 否 | integer | null | 工单状态：0-已完成, 1-进行中, 2-未开始, 3-已关闭 |
| type | query | 否 | integer | null | 工单类型：0-故障工单, 1-服务请求, 2-维护工单 |
| user_id | query | 否 | integer | null | 用户ID |
| assignee_id | query | 否 | integer | null | 处理人ID |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/ticket/reply`

- 摘要：回复工单
- Operation ID：`create_ticket_reply_api_v1_ticket_reply_post`
- Request Body：application/json: TicketReplyCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/ticket/reply/create`

- 摘要：回复工单
- Operation ID：`create_ticket_reply_api_v1_ticket_reply_create_post`
- Request Body：application/json: TicketReplyCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `GET /api/v1/ticket/reply/list`

- 摘要：查看工单回复
- Operation ID：`list_ticket_replies_api_v1_ticket_reply_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| ticket_id | query | 是 | integer | 工单ID |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/ticket/reply_create`

- 摘要：回复工单
- Operation ID：`create_ticket_reply_api_v1_ticket_reply_create_post`
- Request Body：application/json: TicketReplyCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/ticket/send_email`

- 摘要：发送工单邮件通知
- Operation ID：`send_ticket_email_api_v1_ticket_send_email_post`
- Request Body：application/json: TicketEmailSend
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/ticket/update`

- 摘要：更新工单
- Operation ID：`update_ticket_api_v1_ticket_update_post`
- Request Body：application/json: TicketUpdate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/ticket/upload`

- 摘要：上传工单附件图片
- Operation ID：`upload_ticket_attachment_api_v1_ticket_upload_post`
- Request Body：application/json: TicketAttachmentUpload
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| ticket_id | query | 否 | integer | null | 工单ID |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/ticket/users`

- 摘要：查看工单用户选项
- Operation ID：`list_ticket_users_api_v1_ticket_users_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

### 报价系统

#### `POST /api/v1/finance/quote/create`

- 摘要：创建报价
- Operation ID：`create_quote_api_v1_finance_quote_create_post`
- Request Body：application/json: FinanceQuoteCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/finance/quote/delete`

- 摘要：删除报价
- Operation ID：`delete_quote_api_v1_finance_quote_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| quote_id | query | 是 | integer | 报价ID |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/finance/quote/field-options`

- 摘要：报价字段选项
- Operation ID：`list_field_options_api_v1_finance_quote_field_options_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| quote_type | query | 否 | string | 报价类型 |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/finance/quote/get`

- 摘要：查看报价
- Operation ID：`get_quote_api_v1_finance_quote_get_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| quote_id | query | 是 | integer | 报价ID |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/finance/quote/list`

- 摘要：查看报价列表
- Operation ID：`list_quote_api_v1_finance_quote_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| page | query | 否 | integer | 页码 |
| page_size | query | 否 | integer | 每页数量 |
| quote_type | query | 否 | string | 报价类型 |
| region | query | 否 | string | 地区 |
| status | query | 否 | integer | null | 状态 |
| keyword | query | 否 | string | 关键字 |
| sort_field | query | 否 | string | 排序字段 |
| sort_order | query | 否 | string | 排序方向 |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/finance/quote/site-options`

- 摘要：站点选项
- Operation ID：`list_site_options_api_v1_finance_quote_site_options_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| quote_type | query | 否 | string | 报价类型 |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/finance/quote/update`

- 摘要：更新报价
- Operation ID：`update_quote_api_v1_finance_quote_update_post`
- Request Body：application/json: FinanceQuoteUpdate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

### 用户模块

#### `POST /api/v1/user/create`

- 摘要：创建用户
- Operation ID：`create_user_api_v1_user_create_post`
- Request Body：application/json: UserCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/user/delete`

- 摘要：删除用户
- Operation ID：`delete_user_api_v1_user_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| user_id | query | 是 | integer | 用户ID |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/user/get`

- 摘要：查看用户
- Operation ID：`get_user_api_v1_user_get_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| user_id | query | 是 | integer | 用户ID |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/user/list`

- 摘要：查看用户列表
- Operation ID：`list_user_api_v1_user_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| page | query | 否 | integer | 页码 |
| page_size | query | 否 | integer | 每页数量 |
| username | query | 否 | string | 用户名称，用于搜索 |
| email | query | 否 | string | 邮箱地址 |
| dept_id | query | 否 | integer | 部门ID |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/user/reset_password`

- 摘要：重置密码
- Operation ID：`reset_password_api_v1_user_reset_password_post`
- Request Body：application/json: Body_reset_password_api_v1_user_reset_password_post
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/user/update`

- 摘要：更新用户
- Operation ID：`update_user_api_v1_user_update_post`
- Request Body：application/json: UserUpdate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

### 菜单模块

#### `POST /api/v1/menu/create`

- 摘要：创建菜单
- Operation ID：`create_menu_api_v1_menu_create_post`
- Request Body：application/json: MenuCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/menu/delete`

- 摘要：删除菜单
- Operation ID：`delete_menu_api_v1_menu_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| id | query | 是 | integer | 菜单id |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/menu/get`

- 摘要：查看菜单
- Operation ID：`get_menu_api_v1_menu_get_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| menu_id | query | 是 | integer | 菜单id |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/menu/list`

- 摘要：查看菜单列表
- Operation ID：`list_menu_api_v1_menu_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| page | query | 否 | integer | 页码 |
| page_size | query | 否 | integer | 每页数量 |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/menu/update`

- 摘要：更新菜单
- Operation ID：`update_menu_api_v1_menu_update_post`
- Request Body：application/json: MenuUpdate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

### 角色模块

#### `GET /api/v1/role/authorized`

- 摘要：查看角色权限
- Operation ID：`get_role_authorized_api_v1_role_authorized_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| id | query | 是 | integer | 角色ID |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/role/authorized`

- 摘要：更新角色权限
- Operation ID：`update_role_authorized_api_v1_role_authorized_post`
- Request Body：application/json: RoleUpdateMenusApis
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/role/create`

- 摘要：创建角色
- Operation ID：`create_role_api_v1_role_create_post`
- Request Body：application/json: RoleCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/role/delete`

- 摘要：删除角色
- Operation ID：`delete_role_api_v1_role_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| role_id | query | 是 | integer | 角色ID |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/role/get`

- 摘要：查看角色
- Operation ID：`get_role_api_v1_role_get_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| role_id | query | 是 | integer | 角色ID |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/role/list`

- 摘要：查看角色列表
- Operation ID：`list_role_api_v1_role_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| page | query | 否 | integer | 页码 |
| page_size | query | 否 | integer | 每页数量 |
| role_name | query | 否 | string | 角色名称，用于查询 |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/role/update`

- 摘要：更新角色
- Operation ID：`update_role_api_v1_role_update_post`
- Request Body：application/json: RoleUpdate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

### 账单模块

#### `POST /api/v1/bill/create`

- 摘要：创建账单
- Operation ID：`create_bill_api_v1_bill_create_post`
- Request Body：application/json: BillCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/bill/delete`

- 摘要：删除账单
- Operation ID：`delete_bill_api_v1_bill_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| bill_id | query | 是 | integer | 账单ID |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/bill/get`

- 摘要：查看账单
- Operation ID：`get_bill_api_v1_bill_get_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| bill_id | query | 是 | integer | 账单ID |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/bill/list`

- 摘要：查看账单列表
- Operation ID：`list_bill_api_v1_bill_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| page | query | 否 | integer | 页码 |
| page_size | query | 否 | integer | 每页数量 |
| company_id | query | 否 | integer | null | 公司ID |
| bill_type | query | 否 | integer | null | 账单类型(1客户/2供应商) |
| bill_month | query | 否 | string | null | 账单月份 |
| invoice_no | query | 否 | string | 账单编号 |
| customer_name | query | 否 | string | 客户/供应商名称 |
| is_settled | query | 否 | boolean | null | 是否结清 |
| sort_field | query | 否 | string | 排序字段 |
| sort_order | query | 否 | string | 排序方向 |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/bill/update`

- 摘要：更新账单
- Operation ID：`update_bill_api_v1_bill_update_post`
- Request Body：application/json: BillUpdate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/bill/upload_voucher`

- 摘要：上传付款凭证
- Operation ID：`upload_payment_voucher_api_v1_bill_upload_voucher_post`
- Request Body：multipart/form-data: Body_upload_payment_voucher_api_v1_bill_upload_voucher_post
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| bill_id | query | 是 | integer | 账单ID |
| token | header | 是 | string | token验证 |

### 资产管理模块

#### `POST /api/v1/asset/cabinet/create`

- 摘要：创建机柜
- Operation ID：`create_cabinet_api_v1_asset_cabinet_create_post`
- Request Body：application/json: AssetCabinetCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/asset/cabinet/delete`

- 摘要：删除机柜
- Operation ID：`delete_cabinet_api_v1_asset_cabinet_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| cabinet_id | query | 是 | integer |  |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/asset/cabinet/get`

- 摘要：机柜详情
- Operation ID：`get_cabinet_api_v1_asset_cabinet_get_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| cabinet_id | query | 是 | integer |  |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/asset/cabinet/list`

- 摘要：机柜列表
- Operation ID：`list_cabinet_api_v1_asset_cabinet_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| page | query | 否 | integer |  |
| page_size | query | 否 | integer |  |
| location_id | query | 否 | integer | null |  |
| name | query | 否 | string |  |
| code | query | 否 | string |  |
| status | query | 否 | boolean | null |  |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/asset/cabinet/update`

- 摘要：更新机柜
- Operation ID：`update_cabinet_api_v1_asset_cabinet_update_post`
- Request Body：application/json: AssetCabinetUpdate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/asset/device-brand/create`

- 摘要：创建设备品牌
- Operation ID：`create_device_brand_api_v1_asset_device_brand_create_post`
- Request Body：application/json: AssetDeviceBrandCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/asset/device-brand/delete`

- 摘要：删除设备品牌
- Operation ID：`delete_device_brand_api_v1_asset_device_brand_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| brand_id | query | 是 | integer |  |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/asset/device-brand/list`

- 摘要：设备品牌型号列表
- Operation ID：`list_device_brands_api_v1_asset_device_brand_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/asset/device-model/create`

- 摘要：创建设备型号
- Operation ID：`create_device_model_api_v1_asset_device_model_create_post`
- Request Body：application/json: AssetDeviceModelCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/asset/device-model/delete`

- 摘要：删除设备型号
- Operation ID：`delete_device_model_api_v1_asset_device_model_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| model_id | query | 是 | integer |  |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/asset/device/create`

- 摘要：创建设备
- Operation ID：`create_device_api_v1_asset_device_create_post`
- Request Body：application/json: AssetDeviceCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/asset/device/delete`

- 摘要：删除设备
- Operation ID：`delete_device_api_v1_asset_device_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| device_id | query | 是 | integer |  |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/asset/device/get`

- 摘要：设备详情
- Operation ID：`get_device_api_v1_asset_device_get_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| device_id | query | 是 | integer |  |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/asset/device/list`

- 摘要：设备列表
- Operation ID：`list_device_api_v1_asset_device_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| page | query | 否 | integer |  |
| page_size | query | 否 | integer |  |
| region_id | query | 否 | integer | null |  |
| location_id | query | 否 | integer | null |  |
| cabinet_id | query | 否 | integer | null |  |
| keyword | query | 否 | string |  |
| type | query | 否 | integer | null |  |
| status | query | 否 | integer | null |  |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/asset/device/update`

- 摘要：更新设备
- Operation ID：`update_device_api_v1_asset_device_update_post`
- Request Body：application/json: AssetDeviceUpdate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/asset/inventory-category/create`

- 摘要：创建库存分类
- Operation ID：`create_inventory_category_api_v1_asset_inventory_category_create_post`
- Request Body：application/json: AssetInventoryCategoryCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/asset/inventory-category/delete`

- 摘要：删除库存分类
- Operation ID：`delete_inventory_category_api_v1_asset_inventory_category_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| category_id | query | 是 | integer |  |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/asset/inventory-category/list`

- 摘要：库存分类列表
- Operation ID：`list_inventory_categories_api_v1_asset_inventory_category_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/asset/inventory-category/update`

- 摘要：更新库存分类
- Operation ID：`update_inventory_category_api_v1_asset_inventory_category_update_post`
- Request Body：application/json: AssetInventoryCategoryUpdate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `GET /api/v1/asset/inventory-flow/list`

- 摘要：库存流水列表
- Operation ID：`list_inventory_flows_api_v1_asset_inventory_flow_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| page | query | 否 | integer |  |
| page_size | query | 否 | integer |  |
| inventory_id | query | 否 | integer | null |  |
| flow_type | query | 否 | string |  |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/asset/inventory-sale/cancel`

- 摘要：取消库存销售单
- Operation ID：`cancel_inventory_sale_api_v1_asset_inventory_sale_cancel_post`
- Request Body：application/json: AssetInventorySaleCancel
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/asset/inventory-sale/create`

- 摘要：创建库存销售单
- Operation ID：`create_inventory_sale_api_v1_asset_inventory_sale_create_post`
- Request Body：application/json: AssetInventorySaleCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `GET /api/v1/asset/inventory-sale/list`

- 摘要：库存销售单列表
- Operation ID：`list_inventory_sales_api_v1_asset_inventory_sale_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| page | query | 否 | integer |  |
| page_size | query | 否 | integer |  |
| keyword | query | 否 | string |  |
| status | query | 否 | integer | null |  |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/asset/inventory/create`

- 摘要：创建库存
- Operation ID：`create_inventory_api_v1_asset_inventory_create_post`
- Request Body：application/json: AssetInventoryCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/asset/inventory/delete`

- 摘要：删除库存
- Operation ID：`delete_inventory_api_v1_asset_inventory_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| inventory_id | query | 是 | integer |  |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/asset/inventory/export`

- 摘要：导出库存
- Operation ID：`export_inventory_api_v1_asset_inventory_export_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `GET /api/v1/asset/inventory/get`

- 摘要：库存详情
- Operation ID：`get_inventory_api_v1_asset_inventory_get_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| inventory_id | query | 是 | integer |  |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/asset/inventory/import`

- 摘要：导入库存
- Operation ID：`import_inventory_api_v1_asset_inventory_import_post`
- Request Body：multipart/form-data: Body_import_inventory_api_v1_asset_inventory_import_post
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `GET /api/v1/asset/inventory/list`

- 摘要：库存列表
- Operation ID：`list_inventory_api_v1_asset_inventory_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| page | query | 否 | integer |  |
| page_size | query | 否 | integer |  |
| region_id | query | 否 | integer | null |  |
| location_id | query | 否 | integer | null |  |
| keyword | query | 否 | string |  |
| type | query | 否 | string |  |
| subtype | query | 否 | string |  |
| status | query | 否 | boolean | null |  |
| only_low_stock | query | 否 | boolean |  |
| only_available | query | 否 | boolean |  |
| sort_by | query | 否 | string |  |
| sort_order | query | 否 | string |  |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/asset/inventory/update`

- 摘要：更新库存
- Operation ID：`update_inventory_api_v1_asset_inventory_update_post`
- Request Body：application/json: AssetInventoryUpdate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/asset/location/create`

- 摘要：创建位置
- Operation ID：`create_location_api_v1_asset_location_create_post`
- Request Body：application/json: AssetLocationCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/asset/location/delete`

- 摘要：删除位置
- Operation ID：`delete_location_api_v1_asset_location_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| location_id | query | 是 | integer |  |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/asset/location/list`

- 摘要：位置列表
- Operation ID：`list_location_api_v1_asset_location_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| page | query | 否 | integer |  |
| page_size | query | 否 | integer |  |
| region_id | query | 否 | integer | null |  |
| type | query | 否 | integer | null |  |
| name | query | 否 | string |  |
| status | query | 否 | boolean | null |  |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/asset/location/update`

- 摘要：更新位置
- Operation ID：`update_location_api_v1_asset_location_update_post`
- Request Body：application/json: AssetLocationUpdate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/asset/region/create`

- 摘要：创建区域
- Operation ID：`create_region_api_v1_asset_region_create_post`
- Request Body：application/json: AssetRegionCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/asset/region/delete`

- 摘要：删除区域
- Operation ID：`delete_region_api_v1_asset_region_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| region_id | query | 是 | integer |  |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/asset/region/get`

- 摘要：区域详情
- Operation ID：`get_region_api_v1_asset_region_get_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| region_id | query | 是 | integer |  |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/asset/region/list`

- 摘要：区域列表
- Operation ID：`list_region_api_v1_asset_region_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| page | query | 否 | integer |  |
| page_size | query | 否 | integer |  |
| name | query | 否 | string |  |
| code | query | 否 | string |  |
| status | query | 否 | boolean | null |  |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/asset/region/update`

- 摘要：更新区域
- Operation ID：`update_region_api_v1_asset_region_update_post`
- Request Body：application/json: AssetRegionUpdate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `GET /api/v1/asset/tree`

- 摘要：资产位置树
- Operation ID：`asset_tree_api_v1_asset_tree_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

### 运维记录模块

#### `POST /api/v1/remote-assistance/engineers`

- 摘要：新增工程师
- Operation ID：`create_engineer_api_v1_remote_assistance_engineers_post`
- Request Body：application/json: EngineerPayload
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `PUT /api/v1/remote-assistance/engineers/{engineer_id}`

- 摘要：更新工程师
- Operation ID：`update_engineer_api_v1_remote_assistance_engineers__engineer_id__put`
- Request Body：application/json: EngineerPayload
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| engineer_id | path | 是 | integer |  |
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/remote-assistance/engineers/{engineer_id}`

- 摘要：删除工程师
- Operation ID：`delete_engineer_api_v1_remote_assistance_engineers__engineer_id__delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| engineer_id | path | 是 | integer |  |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/remote-assistance/overview`

- 摘要：运维记录页面数据
- Operation ID：`overview_api_v1_remote_assistance_overview_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `POST /api/v1/remote-assistance/remote-hands`

- 摘要：新增运维记录
- Operation ID：`create_remote_hands_api_v1_remote_assistance_remote_hands_post`
- Request Body：application/json: RemoteHandsPayload
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `PUT /api/v1/remote-assistance/remote-hands/{item_id}`

- 摘要：更新运维记录
- Operation ID：`update_remote_hands_api_v1_remote_assistance_remote_hands__item_id__put`
- Request Body：application/json: RemoteHandsPayload
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| item_id | path | 是 | integer |  |
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/remote-assistance/remote-hands/{item_id}`

- 摘要：删除运维记录
- Operation ID：`delete_remote_hands_api_v1_remote_assistance_remote_hands__item_id__delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| item_id | path | 是 | integer |  |
| token | header | 是 | string | token验证 |

### 部门模块

#### `POST /api/v1/dept/create`

- 摘要：创建部门
- Operation ID：`create_dept_api_v1_dept_create_post`
- Request Body：application/json: DeptCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/dept/delete`

- 摘要：删除部门
- Operation ID：`delete_dept_api_v1_dept_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| dept_id | query | 是 | integer | 部门ID |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/dept/get`

- 摘要：查看部门
- Operation ID：`get_dept_api_v1_dept_get_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| id | query | 是 | integer | 部门ID |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/dept/list`

- 摘要：查看部门列表
- Operation ID：`list_dept_api_v1_dept_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| name | query | 否 | string | 部门名称 |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/dept/update`

- 摘要：更新部门
- Operation ID：`update_dept_api_v1_dept_update_post`
- Request Body：application/json: DeptUpdate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

### 银行模块

#### `POST /api/v1/bank/create`

- 摘要：创建银行
- Operation ID：`create_bank_api_v1_bank_create_post`
- Request Body：application/json: BankCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/bank/delete`

- 摘要：删除银行
- Operation ID：`delete_bank_api_v1_bank_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| bank_id | query | 是 | integer | 银行ID |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/bank/list`

- 摘要：查看银行列表
- Operation ID：`list_bank_api_v1_bank_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| page | query | 否 | integer | 页码 |
| page_size | query | 否 | integer | 每页数量 |
| name | query | 否 | string | 银行名称，用于搜索 |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/bank/update`

- 摘要：更新银行
- Operation ID：`update_bank_api_v1_bank_update_post`
- Request Body：application/json: BankUpdate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

### 银行账户模块

#### `POST /api/v1/bank_account/create`

- 摘要：创建银行账户
- Operation ID：`create_bank_account_api_v1_bank_account_create_post`
- Request Body：application/json: BankAccountCreate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

#### `DELETE /api/v1/bank_account/delete`

- 摘要：删除银行账户
- Operation ID：`delete_bank_account_api_v1_bank_account_delete_delete`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| bank_account_id | query | 是 | integer | 银行账户ID |
| token | header | 是 | string | token验证 |

#### `GET /api/v1/bank_account/list`

- 摘要：查看银行账户列表
- Operation ID：`list_bank_account_api_v1_bank_account_list_get`
- Request Body：-
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| page | query | 否 | integer | 页码 |
| page_size | query | 否 | integer | 每页数量 |
| company_id | query | 是 | integer | 公司ID |
| token | header | 是 | string | token验证 |

#### `POST /api/v1/bank_account/update`

- 摘要：更新银行账户
- Operation ID：`update_bank_account_api_v1_bank_account_update_post`
- Request Body：application/json: BankAccountUpdate
- Response：application/json: -

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
|---|---|---:|---|---|
| token | header | 是 | string | token验证 |

## 数据模型索引

| 模型 | 类型 | 必填字段 | 字段 |
|---|---|---|---|
| `ApiCreate` | object | path, method, tags | path:string, summary:string, method:MethodType, tags:string |
| `ApiUpdate` | object | path, method, tags, id | path:string, summary:string, method:MethodType, tags:string, id:integer |
| `AssetCabinetCreate` | object | location_id, name | location_id:integer, name:string, code:string, row:string, column:string, capacity_u:integer, remark:string, status:boolean |
| `AssetCabinetUpdate` | object | location_id, name, id | location_id:integer, name:string, code:string, row:string, column:string, capacity_u:integer, remark:string, status:boolean, id:integer |
| `AssetDeviceBrandCreate` | object | name | name:string, sort:integer, status:boolean |
| `AssetDeviceCreate` | object | cabinet_id, asset_no, name | cabinet_id:integer, asset_no:string, name:string, type:integer, brand:string, model:string, serial_no:string, u_position:integer \| null, u_height:integer, status:integer, mgmt_ip:string, business_ip:string, owner:string, purchase_date:string \| null, warranty_expire:string \| null, attributes:object, remark:string |
| `AssetDeviceModelCreate` | object | brand_id, name | brand_id:integer, name:string, sort:integer, status:boolean |
| `AssetDeviceUpdate` | object | cabinet_id, asset_no, name, id | cabinet_id:integer, asset_no:string, name:string, type:integer, brand:string, model:string, serial_no:string, u_position:integer \| null, u_height:integer, status:integer, mgmt_ip:string, business_ip:string, owner:string, purchase_date:string \| null, warranty_expire:string \| null, attributes:object, remark:string, id:integer |
| `AssetInventoryCategoryCreate` | object | name | name:string, parent_id:integer \| null, sort:integer, status:boolean |
| `AssetInventoryCategoryUpdate` | object | name, id | name:string, parent_id:integer \| null, sort:integer, status:boolean, id:integer |
| `AssetInventoryCreate` | object | location_id, type | location_id:integer, type:string, subtype:string, quantity:integer, threshold:integer, cost_price:number, cost_price_currency:string, sale_price:number, sale_price_currency:string, attributes:object, remark:string, status:boolean |
| `AssetInventorySaleCancel` | object | id | id:integer, reason:string |
| `AssetInventorySaleCreate` | object | items | customer_name:string, customer_contact:string, sale_date:string \| null, remark:string, items:array[AssetInventorySaleItemIn] |
| `AssetInventorySaleItemIn` | object | inventory_id, quantity | inventory_id:integer, quantity:integer, unit_price:number, remark:string |
| `AssetInventoryUpdate` | object | location_id, type, id | location_id:integer, type:string, subtype:string, quantity:integer, threshold:integer, cost_price:number, cost_price_currency:string, sale_price:number, sale_price_currency:string, attributes:object, remark:string, status:boolean, id:integer |
| `AssetLocationCreate` | object | region_id, name | region_id:integer, name:string, type:integer, address:string, remark:string, status:boolean |
| `AssetLocationUpdate` | object | region_id, name, id | region_id:integer, name:string, type:integer, address:string, remark:string, status:boolean, id:integer |
| `AssetRegionCreate` | object | name, code | name:string, code:string, remark:string, status:boolean |
| `AssetRegionUpdate` | object | name, code, id | name:string, code:string, remark:string, status:boolean, id:integer |
| `BankAccountCreate` | object | company_id | company_id:integer, bank_id:integer \| null, bank_code:string, branch_code:string, account_name:string, account_number:string, swift_code:string, iban:string, sort_code:string, currency:string |
| `BankAccountUpdate` | object | id, company_id | id:integer, company_id:integer, bank_id:integer \| null, bank_code:string, branch_code:string, account_name:string, account_number:string, swift_code:string, iban:string, sort_code:string, currency:string |
| `BankCreate` | object | name | name:string, country:string, swift_code:string, bank_address:string |
| `BankUpdate` | object | id, name | id:integer, name:string, country:string, swift_code:string, bank_address:string |
| `BillCreate` | object | company_id | company_id:integer, invoice_no:string, customer_name:string, bill_month:string \| null, invoice_date:string \| null, due_date:string \| null, billing_start_date:string \| null, billing_end_date:string \| null, currency:string, net_amount:number \| null, vat_amount:number \| null, total_amount:number \| null, paid_amount:number \| null, unpaid_amount:number \| null, is_settled:boolean, payment_voucher_url:string, owner:string, remark:string, bill_type:integer, items:array[BillItemIn] |
| `BillItemIn` | object | - | id:integer \| null, service_id:string \| null, service:string \| null, item:string \| null, location:string \| null, start_date:string \| null, end_date:string \| null, nrc_amount:number \| null, mrc_amount:number \| null, amount:number \| null |
| `BillUpdate` | object | company_id, id | company_id:integer, invoice_no:string, customer_name:string, bill_month:string \| null, invoice_date:string \| null, due_date:string \| null, billing_start_date:string \| null, billing_end_date:string \| null, currency:string, net_amount:number \| null, vat_amount:number \| null, total_amount:number \| null, paid_amount:number \| null, unpaid_amount:number \| null, is_settled:boolean, payment_voucher_url:string, owner:string, remark:string, bill_type:integer, items:array[BillItemIn], id:integer |
| `Body_import_inventory_api_v1_asset_inventory_import_post` | object | file | file:string |
| `Body_import_vendor_api_v1_vendor_import_post` | object | file | file:string |
| `Body_reset_password_api_v1_user_reset_password_post` | object | user_id | user_id:integer |
| `Body_upload_payment_voucher_api_v1_bill_upload_voucher_post` | object | file | file:string |
| `CompanyCreate` | object | name | role:integer \| null, name:string, legal_name:string \| null, logo_url:string \| null, code:string \| null, country:string \| null, address:string \| null, noc_email:string \| null, noc_phone:string \| null, remark:string \| null, tax_no:string \| null, company_email:string \| null, bill_email:string \| null, contact_person:string \| null, company_phone:string \| null, registration_no:string \| null, contract_company_id:integer \| null, status:boolean |
| `CompanyUpdate` | object | id, name | id:integer, role:integer \| null, name:string, legal_name:string \| null, logo_url:string \| null, code:string \| null, country:string \| null, address:string \| null, noc_email:string \| null, noc_phone:string \| null, remark:string \| null, tax_no:string \| null, company_email:string \| null, bill_email:string \| null, contact_person:string \| null, company_phone:string \| null, registration_no:string \| null, contract_company_id:integer \| null, status:boolean |
| `CredentialsSchema` | object | username, password | username:string, password:string |
| `CustomerProjectCreate` | object | name | name:string, code:string \| null, customer_id:integer \| null, status:string, priority:string, health:string, owner:string \| null, contract_no:string \| null, start_date:string \| null, due_date:string \| null, progress:integer, budget_amount:number \| null, budget_currency:string, description:string \| null, sort_order:integer |
| `CustomerProjectStatusUpdate` | object | id, status | id:integer, status:string, sort_order:integer |
| `CustomerProjectUpdate` | object | name, id | name:string, code:string \| null, customer_id:integer \| null, status:string, priority:string, health:string, owner:string \| null, contract_no:string \| null, start_date:string \| null, due_date:string \| null, progress:integer, budget_amount:number \| null, budget_currency:string, description:string \| null, sort_order:integer, id:integer |
| `DeptCreate` | object | name | name:string, desc:string, order:integer, parent_id:integer |
| `DeptUpdate` | object | name, id | name:string, desc:string, order:integer, parent_id:integer, id:integer |
| `EngineerPayload` | object | - | name:string, contact:string, wechat_id:string, wechat_group:string, region:string, is_active:integer, note:string |
| `FinanceQuoteCreate` | object | - | quote_type:string, service_resource:string, region:string, service_name:string, cpu_model:string, cpu_cores:string, memory:string, disk:string, bandwidth:string, burst:string, traffic:string, site_a:string, protection:string, xc_cabling:string, contract_terms:string, delivery_time:string, ip_count:string, provider:string, currency:string, nrc:number, mrc:number, usd_per_mbps_nrc:string, usd_per_mbps_mrc:number, cost_price:number, target_price:number, sale_price:number, status:integer, sort:integer, note:string, remark:string |
| `FinanceQuoteUpdate` | object | id | quote_type:string, service_resource:string, region:string, service_name:string, cpu_model:string, cpu_cores:string, memory:string, disk:string, bandwidth:string, burst:string, traffic:string, site_a:string, protection:string, xc_cabling:string, contract_terms:string, delivery_time:string, ip_count:string, provider:string, currency:string, nrc:number, mrc:number, usd_per_mbps_nrc:string, usd_per_mbps_mrc:number, cost_price:number, target_price:number, sale_price:number, status:integer, sort:integer, note:string, remark:string, id:integer |
| `HTTPValidationError` | object | - | detail:array[ValidationError] |
| `MenuCreate` | object | name, path, order | menu_type:MenuType, name:string, icon:string \| null, path:string, order:integer \| null, parent_id:integer \| null, is_hidden:boolean \| null, component:string, keepalive:boolean \| null, redirect:string \| null |
| `MenuType` | string | - | - |
| `MenuUpdate` | object | id, menu_type, name, path, order, parent_id, component | id:integer, menu_type:MenuType \| null, name:string \| null, icon:string \| null, path:string \| null, order:integer \| null, parent_id:integer \| null, is_hidden:boolean \| null, component:string, keepalive:boolean \| null, redirect:string \| null |
| `MethodType` | string | - | - |
| `NoVNCRequest` | object | remote, vmid | remote:string, vmid:integer, type:string, node:string \| null |
| `PDMAddRemoteRequest` | object | hostname | hostname:string, authid:string \| null, token:string \| null, fingerprint:string \| null, remote_id:string \| null, create_token:string \| null, web_url:string \| null |
| `PDMProbeRemoteRequest` | object | hostname | hostname:string, fingerprint:string \| null |
| `PDMRemoteRemarkRequest` | object | - | remark:string, host:string \| null |
| `PDMUpdateRemoteRequest` | object | hostname | hostname:string, fingerprint:string \| null, original_hostname:string \| null |
| `ProjectAttachmentUpload` | object | project_id, filename, content_type, data | project_id:integer, task_id:integer \| null, filename:string, content_type:string, data:string, remark:string \| null |
| `ProjectDiscussionCreate` | object | project_id, content | project_id:integer, content:string, task_id:integer \| null, attachment_id:integer \| null |
| `ProjectTaskCreate` | object | project_id, title | project_id:integer, title:string, assignee:string \| null, due_date:string \| null, is_done:boolean, sort_order:integer, remark:string \| null |
| `ProjectTaskUpdate` | object | project_id, title, id | project_id:integer, title:string, assignee:string \| null, due_date:string \| null, is_done:boolean, sort_order:integer, remark:string \| null, id:integer |
| `RemoteHandsPayload` | object | - | customer:string, ticket:string, engineer_id:integer \| null, engineer_name:string, engineer_contact:string, engineer_wechat:string, engineer_group:string, region:string, site:string, rack:string, timezone:string, arrived_at:string, left_at:string, work_minutes:integer, status:string, note:string |
| `RoleCreate` | object | name | name:string, desc:string |
| `RoleUpdate` | object | id, name | id:integer, name:string, desc:string |
| `RoleUpdateMenusApis` | object | id | id:integer, menu_ids:array[integer], api_infos:array[object] |
| `ScheduledTaskCreate` | object | name | name:string, task_type:string, script_path:string \| null, command:string \| null, schedule_type:string, day_of_week:integer \| null, hour:integer, minute:integer, interval_minutes:integer \| null, is_enabled:boolean |
| `ScheduledTaskToggle` | object | id, is_enabled | id:integer, is_enabled:boolean |
| `ScheduledTaskUpdate` | object | name, id | name:string, task_type:string, script_path:string \| null, command:string \| null, schedule_type:string, day_of_week:integer \| null, hour:integer, minute:integer, interval_minutes:integer \| null, is_enabled:boolean, id:integer |
| `TicketAttachmentUpload` | object | filename, content_type, data | filename:string, content_type:string, data:string |
| `TicketCreate` | object | title | title:string, type:integer, user_id:integer \| null, desc:string, location:string, start_time:string \| null, end_time:string \| null, attachment_url:string, assignee_id:integer \| null, completion_note:string \| null |
| `TicketEmailSend` | object | ticket_id | ticket_id:integer, user_ids:array[integer] |
| `TicketReplyCreate` | object | ticket_id, content | ticket_id:integer, content:string, parent_id:integer \| null, reply_to_ticket:boolean \| null |
| `TicketUpdate` | object | - | id:integer \| null, ticket_no:string \| null, title:string \| null, status:integer \| null, type:integer \| null, user_id:integer \| null, desc:string \| null, location:string \| null, start_time:string \| null, end_time:string \| null, attachment_url:string \| null, assignee_id:integer \| null, completion_note:string \| null |
| `UpdatePassword` | object | old_password, new_password | old_password:string, new_password:string |
| `UserAvatarUpload` | object | filename, content_type, data | filename:string, content_type:string, data:string |
| `UserCreate` | object | email, username, password | email:string, username:string, avatar:string \| null, password:string, is_active:boolean \| null, is_superuser:boolean \| null, role_ids:array[integer] \| null, dept_id:integer \| null |
| `UserProfileUpdate` | object | username, email | username:string, email:string, avatar:string \| null |
| `UserUpdate` | object | id, email, username | id:integer, email:string, username:string, avatar:string \| null, is_active:boolean \| null, is_superuser:boolean \| null, role_ids:array[integer] \| null, dept_id:integer \| null |
| `VMConfigUpdateRequest` | object | remote, vmid | remote:string, vmid:integer, type:string, node:string \| null, cores:integer \| null, memory_gb:number \| null, disk_gb:number \| null, disk_key:string \| null, networks:array[VMNetworkDeviceRequest] |
| `VMCreateRequest` | object | region, storage, vm_name, os_type, os_version, cpu_cores, memory_gb, disk_gb, password, network | region:string, storage:string, vm_name:string, description:string \| null, os_type:string, os_version:string, cpu_cores:integer, memory_gb:integer, disk_gb:integer, password:string, network:VMNetworkConfig |
| `VMDeleteRequest` | object | remote, vmid | remote:string, vmid:integer, type:string, node:string \| null, status:string \| null |
| `VMMigrateRequest` | object | remote, vmid, target, target_storage, target_bridge | remote:string, vmid:integer, type:string, target:string, target_vmid:integer \| null, target_storage:string, target_bridge:string, delete_source:boolean, online:boolean, bwlimit:integer \| null, node:string \| null, target_endpoint:string \| null |
| `VMNetworkConfig` | object | - | mode:string, ip:string \| null, mask:string \| null, dns:string \| null, gw:string \| null, vlan:integer \| null, rate_limit:number \| null |
| `VMNetworkDeviceRequest` | object | - | key:string \| null, model:string, macaddr:string \| null, bridge:string, vlan:integer \| null, mtu:integer \| null, rate:number \| null, firewall:boolean, delete:boolean |
| `VMPowerRequest` | object | remote, vmid, action | remote:string, vmid:integer, type:string, node:string \| null, action:string |
| `ValidationError` | object | loc, msg, type | loc:array[string \| integer], msg:string, type:string |
| `VendorCreate` | object | name | name:string, code:string, country:string, address:string, noc_email:string, noc_phone:string, remark:string, tax_no:string, company_email:string, company_phone:string, registration_no:string, contract_company_id:integer \| null, status:boolean |
| `VendorUpdate` | object | id, name | id:integer, name:string, code:string, country:string, address:string, noc_email:string, noc_phone:string, remark:string, tax_no:string, company_email:string, company_phone:string, registration_no:string, contract_company_id:integer \| null, status:boolean |
