# 云资源页面改版与接口兼容说明

## 设计参考

按用户指定的 [ProxMate 源码](https://github.com/r0073d-l053r/ProxMate/tree/44da4916ae7d31eb7151c1723732cdabd51d0e72) 检查以下页面结构，并使用 FinWork 既有 Vue 3、Naive UI 和业务接口实现：

- `frontend/src/components/dashboard/cluster-load-card.tsx`：CPU、内存、存储三个环形仪表，已用/总量、趋势及节点数量。
- `frontend/src/app/(dashboard)/vms/page.tsx`：名称链接、状态标签、紧凑资源描述和系统/IP/创建时间列。
- `frontend/src/app/(dashboard)/vms/[id]/page.tsx`：标题与操作区、概览、监控、配置与连接信息分区。

不引入 ProxMate 的 React/Next.js 运行时或依赖。

## 页面行为

`/ops/virtual-machine` 顶部旧统计卡片替换为“节点负载”面板，随左侧选择显示对应 PVE 节点的 CPU、内存、存储负载及已用/总量。缺少数据或节点不可用时显示“—”。移除趋势线和节点/虚拟机数量栏，搜索、状态筛选和操作按钮合并为紧凑工具栏，腾出空间给列表。

移除“本地资源快照”“后台同步”“最近同步”等实现说明，保留“刷新”按钮和必要的操作失败提示。后端缓存及异步同步继续工作。

虚拟机列表按 **名称、用户、状态、资源、系统、IP、运行时间** 排列，末尾保留固定宽度的图标操作。运行时间使用现有 `uptime` 秒值，显示天/小时/分钟，缺失时显示“—”；用户取既有客户关联；业务列支持拖拽列宽及横向滚动。支持名称/用户/IP搜索、状态筛选、分页，窄屏使用相同信息的卡片。

点击名称进入 `/virtual-machine/detail?remote=…&vmid=…&type=pve-qemu`。详情提供：

- 概览：运行状态、使用率、配置、用户、IP、节点、创建时间、备注。
- 监控：复用已有 Grafana 监控。
- 网络与磁盘：显示既有 PVE 配置接口返回的网卡和磁盘。
- 设置：编辑配置、重启、迁移及删除；迁移使用现有任务弹窗，编辑后返回同一虚拟机详情。
- 控制台与开关机继续调用原接口，删除须停机并输入名称确认。删除成功后清除对应页面缓存并返回列表，不触发全量同步。

详情定时读取现有列表数据；配置只在首次进入/手动刷新读取，隐藏页面不轮询。异步响应按当前虚拟机标识校验，避免切换详情后覆盖其他虚拟机。

## API 增量

没有新增公开路由、权限豁免或数据库字段。

### GET `/api/v1/pve/vms`

沿用 `node`、`refresh` 请求参数，`data.items[]` 后台补充可用的 `os_type` 和 `created_at`。列表读取仍从现有资源数据返回，不对每次列表请求逐台访问 PVE。

### GET `/api/v1/pve/vms/config`

请求参数保持 `remote`、`vmid`、`type`，权限继续使用现有 `/pve` 路由 `DependPermission` 与 token。响应 `data` 保留原 CPU、内存、磁盘、网卡、客户字段，并增加：

```json
{
  "name": "example-vm",
  "os_type": "l26",
  "created_at": "2024-08-30T06:40:00+00:00",
  "description": "业务备注"
}
```

`os_type` 来自 PVE 的 `ostype`；`l26` 显示 Linux，不根据虚拟机名称猜测具体发行版。`created_at` 优先解析 PVE `meta` 中的 `ctime`，其次明确的 `creation_time` / `ctime` Unix 秒值；无法确认时返回 null，绝不使用本地元数据记录创建时间或首次发现时间。旧快照可能暂未包含这两个字段，刷新后补充；PVE 本身缺少数据时仍显示未知。

后台采集采用6并发、单次3秒请求超时、整批30秒预算，成功结果缓存15分钟、失败结果缓存1分钟，仅保存展示字段，不复制 PVE 配置中的密码等字段。采集失败不阻断已有虚拟机列表；失败节点继续保留已有数据。

错误响应、token 校验和路由权限保持原样：无效登录401、无接口权限403、缺少必填参数422；PVE配置访问失败沿用原 `Fail` 响应（400）。未启用或不可访问的 Grafana/PVE 服务仍会显示已有接口的失败状态。

## 验证

```text
python -m unittest discover -s tests -p "test_cloud*.py"
python -m unittest discover -s tests -p "test_pve*.py"
cd web
node --test tests/cloud-display.test.mjs
npm run build
npm run lint
```

测试使用模拟 PVE 响应和内存数据库，不操作真实虚拟机。生产 PVE、Grafana 与控制台交互需部署后使用实际授权账户验收；本次未执行部署。
