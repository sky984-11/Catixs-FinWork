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

### 节点存储补充采集

`GET /api/v1/pve/nodes` 的路由、参数、权限及响应结构保持不变。后台资源汇总缺少节点 `maxdisk` 时，补读已有 PDM 节点状态接口的 `rootfs.used/total`，填充 `disk`、`maxdisk`、`disk_usage`；仅补充存储，不覆盖已有 CPU、内存指标。存储表示节点根文件系统，不表示所有存储池总容量。

补读与资源采集共用4并发限制，每个远程节点最多等待6秒；失败不阻断虚拟机同步，缺少容量时前端继续显示暂无数据。部署后点击云资源“刷新”更新原有缓存即可，无需数据库迁移。

### 节点负载自动更新

页面可见时每30秒更新当前选中节点，切换节点、恢复可见时立即更新；离开页面停止，失败保留上次数据，不触发全量虚拟机同步。

沿用 `GET /api/v1/pve/nodes`，增加可选参数 `live_remote`（现有节点 remote 标识）。传入时仅读取该节点实时状态，返回 `data: [{remote, cpu_usage, cpu_total, mem, maxmem, mem_usage, disk, maxdisk, disk_usage, ...原节点字段}]`；未传入仍按原逻辑返回节点列表。请求总超时10秒，不修改资源缓存或虚拟机列表。沿用原登录及 `/pve/nodes` 权限；节点不存在404、状态不可用502，未登录401、无权限403。`refresh` 与 `live_remote` 同传时以实时负载读取为准。

### 开关机状态更新

参考 ProxMate 虚拟机详情的过渡状态与单台轮询方式。开关机期间仅当前行展示“启动中/关机中”，禁用冲突操作；每2秒检查任务及目标虚拟机实时状态，最多120秒。任务失败显示原因，超时提示核实，不将请求提交视作完成。详情页使用相同逻辑；离开页面或切换目标后忽略旧响应。

`POST /api/v1/pve/vms/power` 保持参数、返回的 `upid` 和价格管理关机限制不变，后台仅跟踪目标任务并更新对应虚拟机缓存，不再触发全量同步。

`GET /api/v1/pve/vms` 新增可选正整数 `vmid`，与 `node`（remote 标识）同时传入时直接读取该虚拟机状态并仅更新它的缓存，返回示例 `{"code":200,"data":{"items":[{"remote":"example","vmid":100,"status":"stopped","uptime":0}]}}`（实际保留原有虚拟机字段）。未传 `vmid` 时列表响应不变。沿用原登录与 `/pve/vms` 权限；缺少 node/无效 vmid 为422、虚拟机不存在404、实时状态不可用502。同步期间删除的虚拟机不会被恢复，其他虚拟机、IP、客户信息保持不变。

PDM 状态路径依据[官方 QEMU API 源码](https://github.com/proxmox/proxmox-datacenter-manager/blob/master/server/src/api/pve/qemu.rs)，使用 `/pve/remotes/{remote}/{qemu|lxc}/{vmid}/status`。

### 列表及详情的实时状态与资源

云资源列表请求 `GET /api/v1/pve/vms?node=<remote>&live=true`，每10秒直接读取当前节点的 QEMU、LXC 列表，状态、CPU、内存、磁盘容量/用量和运行时间以 PVE 为准。本地客户规格不能覆盖 PVE 实测数据，缺失指标显示未知。客户关联、备注和已加载 IP 保留。详情使用 `node + vmid` 每10秒单台查询，包含实时 CPU 核心数（PVE `cpus` 映射为 `maxcpu`）。节点总负载仍每30秒读取。

`live` 为新增可选布尔参数，默认 false，旧调用保持原响应；`vmid` 优先于 `live`。实时列表返回 `data.items`、`data.summary`、空 `data.sync`；例如 `{"code":200,"data":{"items":[],"summary":{"total":0,"running":0,"stopped":0},"sync":{}}}`。权限沿用 `/pve/vms`，未登录401、无权限403、缺少node或非法参数422、未知节点404、任一实时列表读取失败502。读取失败不清空缓存，前端提示当前数据已过期并重试，不将旧缓存宣称为实时数据。

自动更新不会刷新整张表的加载状态、重置分页或列宽；隐藏或离开列表时暂停，恢复后立即读取。同一时刻仅一个自动列表请求，开关机期间优先单台状态跟踪。成功读取只更新该节点的虚拟机缓存，并保留并发删除标记，无全量扫描。

### 刷新时保持行顺序

首次加载按 VMID 数值升序排列。后续实时或手动刷新按 remote、类型、VMID 匹配已有行，保留其顺序并更新内容，不随 PVE 响应顺序、状态或资源使用量重新排列；新发现的虚拟机按 VMID 排序后追加到末尾，已删除的行正常移除。桌面表格与移动端列表共用此规则。
