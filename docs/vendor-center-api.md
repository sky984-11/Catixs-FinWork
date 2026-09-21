# 供应商信息与附件

供应商入口为一级菜单“供应商中心”（`/vendor-center`），仅保留“供应商管理”（`/vendor-center/vendors`）与“供应商联系人”（`/vendor-center/contacts`）。旧 `/vendor` 入口隐藏并重定向到供应商管理，不再放在隐藏的财务目录中。后端启动会幂等补齐菜单；更新后需重新加载前端菜单（刷新页面或重新登录）。

API 沿用 `/api/v1/vendor`，数据仍保存在 `company`（`role=2`），保留公司 ID、银行账户、账单及原字段。供应商编号为 V + 客户编号规则（科特思 VC、77 Telecom VH、Catixs VU + 五位流水号，如 VU00001），供应商独立递增，历史编号保持不变；自动编号取已有最大序号加一，手动重复编号返回 409。

供应商新增、编辑表单只维护基本资料、签约主体、所属地区和附件，不包含邮箱、电话或联系人字段，也不在保存请求中提交这些字段，因此不会覆盖已有联系人。注册号、税号和付款条件已从表单与展示中移除，更新请求不提交这三个字段，保留历史数据及 API/CSV 兼容性。

所属地区与新增客户共用级联选项构建、中文翻译和拼音搜索逻辑，数据来自 `GET /api/v1/asset/region/list?page=1&page_size=1000&status=true`（沿用地区列表响应及鉴权，启动时补齐供应商角色的该 GET 权限）。供应商仍使用既有 `country` 字段保存地区路径，如 `中国 / 香港`，长度上限沿用 50 字符，清空发送空字符串；已有地区补充到选项中用于编辑回显，不新增地区数据或修改数据库结构。

弹窗参照新增客户：760px 宽、顶部档案说明、基本信息/供应商属性/备注/附件分区、上置标签和双列布局，窄屏切换单列。供应商简称和签约主体在页面中必填；新增时选择主体自动预览编号，可手动修改或留空由保存接口生成；编辑时切换主体保留既有编号。快速切换主体、手动修改编号或关闭窗口后，过期预览请求不会覆盖当前输入。取消或点击关闭会清理未保存附件，失败保留窗口重试。

供应商联系人与客户联系人共用 `ContactEditorModal.vue` 新增/编辑弹窗，供应商仅替换所属对象标签和选项数据。两者均支持个人/组邮箱、多个所属对象、多个角色、姓名/组名、邮箱、电话、地址和备注；保存期间禁止关闭与重复提交。供应商列表按联系人逐条展示，支持供应商、角色、关键字筛选及分页。

联系人独立存储于 `vendor_contact`，通过 `vendor_contact_link` 关联多个供应商。新增同角色联系人不会覆盖已有联系人。旧公司、销售、账单、NOC 字段仍可被原 API/CSV 读取和修改；联系人列表以 `legacy:<供应商ID>:<字段>` 返回未转换的旧记录，原多行文本完整放入备注，不猜测拆分。首次编辑保存时，事务内创建独立记录、建立关联并清除对应旧字段，避免重复展示；其他角色与供应商基本资料不变。直接删除旧记录只清除对应旧字段。供应商详情的联系人页签显示新旧记录。

### 供应商联系人 API

四个接口均沿用供应商路由的登录与 API 权限控制；已有角色补齐 `GET /api/v1/vendor/contacts/list` 读取权限，管理员/NOC 获得写权限，其余角色无写权限返回 403。缺失 token 沿用项目 422，失效 token 返回 401。接口不会授予客户模块写权限。

| 路由 | 请求与响应 |
| --- | --- |
| `GET /api/v1/vendor/contacts/list` | 无参数；`{"code":200,"data":[联系人对象]}`，包含独立联系人及未转换的旧记录。前端本地筛选和分页。 |
| `POST /api/v1/vendor/contacts/create` | 下方 JSON；返回 `{"code":200,"data":联系人对象}`。 |
| `POST /api/v1/vendor/contacts/update` | 同创建字段，另传字符串 `id`；整体更新该联系人及其供应商关联，返回同创建。 |
| `DELETE /api/v1/vendor/contacts/delete` | 查询参数 `contact_id`（列表返回的字符串 ID）；成功返回 `{"code":200,"msg":"联系人已删除"}`。删除联系人及全部关联，不删除供应商或其他联系人。 |

```json
{
  "vendor_ids": [1, 2],
  "contact_type": "person",
  "name": "Alex",
  "roles": ["business", "finance"],
  "email": "alex@example.test",
  "phone": "+1 555 0100",
  "address": "Office address",
  "remark": "Billing copy"
}
```

返回对象另含 `id`、`vendor_name`（关联供应商名称）、时间戳；旧记录带 `legacy:true`。`vendor_ids` 必须包含 1–100 个有效供应商 ID（仅 `company.role=2`），重复 ID 去重；联系人类型为 `person/group`。角色与客户一致：`business/procurement/technical/finance/ops/emergency`，至少一个。姓名或邮箱至少一项非空；姓名/邮箱/电话/地址/备注上限分别为 100/200/100/500/10000 字符，邮箱格式校验。无效字段返回 422，无效供应商返回 400，不存在或已转换的旧 ID 返回 404。创建、更新、删除与关联处理均在事务内执行。关联仍存在时删除供应商返回 409，需先调整联系人关联。

新增 Aerich 迁移 `172_20260918010000_vendor_contact_records.py` 创建联系人及关联表；降级先删除关联表再删除联系人表，降级会删除独立联系人数据，不会还原已转换的旧文本字段。沿用项目启动时安全建表流程；现有生产库尚未在本次开发会话执行迁移。

菜单与角色授权参照客户中心：已有角色获得供应商中心两个菜单及查询权限，管理员/NOC 角色获得供应商模块管理接口权限；其他角色既有写权限不回收，也不因显示菜单额外授予写权限。

## 信息录入

供应商管理按服务端分页，默认每页20条，可切换20/50/100条，底部显示筛选后的总条数。关键字、签约主体、状态筛选或调整每页数量时回到第一页；删除末页最后一条后自动回退到有效页。列表接口示例：`GET /api/v1/vendor/list?page=1&page_size=20&keyword=network&signing_entity_id=1&status=true`，响应示例：`{"code":200,"data":[],"total":0,"page":1,"page_size":20}`。翻页与筛选均沿用供应商查询权限，无数据库迁移。

所有接口通过 `token` 请求头登录，并按 `DependPermission` 校验当前用户角色的接口权限。供应商模块采用共享档案权限，具有对应接口权限的用户可以操作任意供应商；不引入销售归属限制。获取、编辑、删除仅接受供应商 ID，内部公司或客户 ID 返回 404。

| 路由 | 参数与响应 |
| --- | --- |
| `GET /api/v1/vendor/list` | 保留 `page`（默认1）、`page_size`（默认10）、`name`、`code`、`status`；新增 `keyword`（名称或编号，不区分大小写）和 `signing_entity_id`（CRM主体ID）。返回 `{code:200,data:[供应商],total,page,page_size}`，按ID升序稳定分页，`total` 为筛选后总条数。主体筛选兼容可唯一映射到CRM主体的历史关联。页码、每页数量及主体ID必须为正数，否则422；鉴权权限沿用原接口。 |
| `GET /api/v1/vendor/get` | `vendor_id`；返回 `{code:200,data:供应商}`，包含 `attachments` 元数据列表。 |
| `GET /api/v1/vendor/next-code` | 必填 `signing_entity_id`（正整数、启用的 CRM 主体），返回 `{code:200,data:{code:"VU00001"}}`；只预览、不占用编号。缺少参数/格式错误 422，无效/停用主体 400，未授权 401/403（缺少 token 沿用 422）。需要对应 GET 接口权限，启动时按供应商查询权限补齐。 |
| `POST /api/v1/vendor/create` | JSON；名称必填，`signing_entity_id` 使用客户管理的 CRM 签约主体 ID。旧调用方仍可使用内部公司 `contract_company_id`，两类 ID 不混用。 |
| `POST /api/v1/vendor/update` | JSON；必填 `id`、`name`，旧调用方未传新增字段时保留原值，空编号不会清空现有编号。 |
| `DELETE /api/v1/vendor/delete` | `vendor_id`；有供应商附件时返回 409，需先在编辑窗口删除附件。 |
| `GET /api/v1/vendor/export` | CSV 保留原列，并追加付款条件、销售联系人、账单联系人、NOC联系信息。附件文件不包含在 CSV 内。 |
| `POST /api/v1/vendor/import` | 保留 multipart `file` CSV 上传，支持原中文列名及截图中的 `Vendor ID`、`Catixs Entity`、`Vendor Name`、`Payment Terms`、`Sales Contact`、`Billing Contact`、`NOC Contact`。签约主体优先匹配客户管理的启用主体名称，兼容唯一匹配的旧内部公司名称；逐行校验，响应 `msg` 报告成功数与失败行。 |

供应商表单、表格筛选和联系人页面统一通过 `GET /api/v1/customer-center/signing-entities` 获取启用主体，与客户管理使用同一张 `crm_signing_entity` 表及相同名称、排序。不再使用 `/company/list?role=0` 生成主体下拉选项。

新字段 `company.signing_entity_id` 外键关联 CRM 主体；旧 `contract_company_id` 保留用于兼容。查询旧供应商时，按注册号、税号、名称和三个既有主体编码映射进行唯一匹配，返回 `signing_entity_id`、`signing_entity_name`；不会按数字 ID 或模糊名称猜测。无法唯一匹配时保留原关联，返回 `legacy_signing_entity_unmatched: true`，表单提示重新选择，不静默清空旧数据。保存新的主体时同步唯一匹配的内部公司；没有可靠匹配则将旧关联置空，避免保留错误主体。

`signing_entity_id` 省略表示保持已有主体，显式 `null` 表示清空主体；不存在或已停用的主体返回 400，已保存的停用主体可保持原值。旧调用方改变 `contract_company_id` 时清除过期的 CRM 关联。CSV 导出统一输出解析后的 CRM 主体名称。当前供应商编号在编辑主体时保持不变。

创建示例（`signing_entity_id` 替换为客户管理中的实际主体 ID）：

```json
{
  "name": "Example Networks Ltd",
  "signing_entity_id": 1,
  "payment_terms": "30/30",
  "sales_contact": "Alex\nsales@example.test\n+1 555 0100",
  "billing_contact": "billing@example.test",
  "noc_contact": "24/7 service desk\nnoc@example.test\nhttps://support.example.test",
  "attachment_ids": [12]
}
```

`name` 去除首尾空格且不能为空，最长 100 字符；`code` 最长 50 字符；`payment_terms` 最长 200 字符；三类联系人各最长 10000 字符、支持换行，按纯文本显示。旧 `noc_email`、`noc_phone` 继续保留；没有新的 NOC 信息时，表格显示旧邮箱和电话。`attachment_ids` 最多 50 个，省略或移除 ID 不触发文件删除，删除必须调用专用接口。

新增/编辑支持可选 `legal_name`（供应商全称，最长 200 字符），复用既有 `company.legal_name` 字段，无需新增迁移。响应返回该字段，旧调用方更新时未传则保留已有全称。供应商简称、签约主体、付款条件等原字段和接口继续兼容。

创建和更新返回示例：

```json
{
  "code": 200,
  "msg": "Created Successfully",
  "data": {
    "id": 42,
    "name": "Example Networks Ltd",
    "role": 2,
    "code": "VU00001",
    "contract_company_id": 1,
    "signing_entity_id": 1,
    "signing_entity_name": "Catixs Ltd",
    "legacy_signing_entity_unmatched": false,
    "payment_terms": "30/30",
    "sales_contact": "Alex\nsales@example.test",
    "billing_contact": "billing@example.test",
    "noc_contact": "24/7 service desk",
    "attachments": [{"id":12,"name":"escalation.pdf","size":1024,"content_type":"application/pdf"}]
  }
}
```

实际响应保留原有国家、地址、税号等字段。错误码：400 无效主体/附件关联，401 登录无效，403 缺少权限，404 对象不存在，409 编号冲突或存在附件/受约束关联记录，422 字段校验失败。缺少 token 沿用现有鉴权依赖的 422 响应。

## 附件 API

新增三个接口均需配置对应角色权限，不取消鉴权来处理 403。

### `POST /api/v1/vendor/attachments/upload`

`Content-Type: application/json`，请求示例：

```json
{"filename":"example.txt","content_type":"text/plain","data":"data:text/plain;base64,aGVsbG8=","vendor_id":42}
```

`data` 支持纯 Base64 和 Base64 Data URL。文件必须非空且不超过 20MiB；同时限制请求体、编码长度、解码后长度。`filename` 最长 255 字符、仅作显示，磁盘名称由服务器生成。`content_type` 最长 200 字符，下载统一作为二进制附件处理。

新增供应商时 `vendor_id` 留空，附件属于上传用户；保存时通过 `attachment_ids` 在同一数据库事务内绑定。编辑供应商时上传即关联该供应商。不能跨供应商共享或挪用附件，不能绑定其他用户的未保存附件。

成功：`{"code":200,"data":{"id":12,"name":"example.txt","size":5,"content_type":"text/plain"}}`。

### `GET /api/v1/vendor/attachments/download?attachment_id=12`

返回附件文件并携带下载文件名。沿用请求封装传 token，通过 Blob 下载。未保存附件仅上传人可下载；已关联附件按供应商模块共享档案权限访问。

### `DELETE /api/v1/vendor/attachments/delete?attachment_id=12`

成功：`{"code":200,"msg":"附件已删除","data":null}`。删除数据库附件记录及磁盘文件；若物理删除失败则恢复记录和文件，保留重试能力。未保存附件只允许上传人删除；已保存附件按供应商模块权限操作。没有共享文件引用。

前端仅在接口成功后移除列表项。上传、删除、下载期间禁用重复操作、保存与关闭；新增表单取消时清理本次未保存附件，失败则保留窗口便于重试。编辑中的删除立即生效，取消不恢复；编辑中上传的附件也已保存。

附件错误码：400 无效编码/空文件/文件名，401 登录无效，403 无接口权限或访问其他用户的未保存附件，404 供应商/附件不存在，413 请求或文件过大，422 JSON/字段无效（不回显内容），500 文件删除失败。该附件接口为新接口，仅接收 JSON；既有供应商 CSV multipart 导入保持兼容。

## 数据库与部署

- 新增 `171_20260917150000_vendor_shared_signing_entity.py`，由 Aerich DDL 生成，仅增加可空 CRM 签约主体外键，不覆盖历史关联。启动兼容逻辑同步支持新增字段；更新后重启后端并刷新前端。真实 PostgreSQL 尚未执行该迁移。

- 新增 Aerich 迁移 `170_20260917120000_vendor_contacts_attachments.py`，由当前与变更前模型描述通过 Aerich PostgreSQL DDL 生成，新增四个可空公司字段及 `vendor_attachment` 表，不修改历史迁移。生成器使用 `ADD COLUMN IF NOT EXISTS`，兼容项目启动时补齐结构的流程。
- 部署时按项目流程执行 `aerich upgrade`，然后重启后端。现有 Docker 镜像不复制迁移历史，因此启动兼容逻辑也会补齐这四个字段，并通过既有 `generate_schemas(safe=True)` 创建附件表；SQLite 同样支持补齐字段。迁移尚未应用到真实数据库。降级会移除新增信息与附件元数据，部署前应审阅升级/降级 SQL。
- 附件位于仓库根目录下 `private_uploads/vendors/`，不挂载为静态目录。为此目录提供持久化存储，并纳入与数据库一致的备份；已有其他模块附件不移动。
- 仓库 `deploy/web.conf` 已配置 `client_max_body_size 30m`，满足单个 20MiB 文件的 Base64 JSON 请求；实际线上代理和 Cloudflare 配置仍需按部署环境验证。403 应依据响应及代理事件区分角色权限与代理拦截。
- 上传请求正文和下载内容不写入审计日志；上传校验错误不会回显 Base64。操作日志仅记录附件 ID、用户 ID、大小等元数据。

## 验证

隔离 SQLite 内存数据库和临时文件目录：`python -m unittest discover -s tests -p test_vendor_center.py`。覆盖新旧字段往返、编号与主体校验、新旧 CSV、纯 Base64/Data URL、无效/空/超限文件、登录与权限、跨用户及跨供应商附件限制、未保存附件删除、物理删除失败恢复、文件和记录同步删除，以及审计内容排除。不使用真实上传文件。
