<template>
  <AppPage :show-footer="false">
    <div class="vm-page">
      <section class="vm-layout">
        <aside class="vm-sidebar">
          <div class="panel-head">
            <div>
              <span class="eyebrow">PDM DATACENTER</span>
              <h2>节点列表</h2>
            </div>
            <n-button secondary circle :loading="loading.nodes" @click="refreshNodes">
              <template #icon>
                <TheIcon icon="mdi:refresh" :size="18" />
              </template>
            </n-button>
          </div>

          <n-input v-model:value="filters.nodeKeyword" clearable placeholder="搜索节点 / Remote" class="side-search">
            <template #prefix>
              <TheIcon icon="mdi:magnify" :size="18" />
            </template>
          </n-input>

          <n-spin :show="loading.nodes">
            <n-empty v-if="!filteredNodes.length" description="暂无节点" />
            <div v-else class="side-list">
              <button
                v-for="node in filteredNodes"
                :key="node.value"
                class="side-list-item"
                :class="{ active: selectedNode?.value === node.value }"
                @click="selectNode(node)"
              >
                <span>
                  <strong>{{ node.label }}</strong>
                  <em>{{ node.online_node_count || 0 }}/{{ node.node_count || 0 }} 节点在线</em>
                </span>
                <n-tag size="small" round :type="node.status === 'online' ? 'success' : 'warning'">
                  {{ node.vm_count || 0 }}
                </n-tag>
              </button>
            </div>
          </n-spin>
        </aside>

        <main class="vm-main">
          <section class="summary-band">
            <article>
              <span>Datacenter</span>
              <strong>PDM</strong>
            </article>
            <article>
              <span>节点总数</span>
              <strong>{{ nodeOptions.length }}</strong>
            </article>
            <article>
              <span>当前节点</span>
              <strong>{{ selectedNode?.label || '全部节点' }}</strong>
            </article>
            <article>
              <span>虚拟机</span>
              <strong>{{ vmSummary.total || vmList.length }}</strong>
            </article>
          </section>

          <section class="filter-panel">
            <n-input
              v-model:value="filters.vmKeyword"
              clearable
              placeholder="搜索：虚拟机名称 / VMID / 节点 / 状态"
              @keyup.enter="fetchVms"
            >
              <template #prefix>
                <TheIcon icon="mdi:magnify" :size="18" />
              </template>
            </n-input>
            <n-select
              v-model:value="filters.status"
              clearable
              placeholder="状态"
              :options="statusOptions"
              @update:value="fetchVms"
            />
            <n-button secondary round @click="resetFilters">
              <template #icon>
                <TheIcon icon="mdi:refresh" :size="18" />
              </template>
              重置
            </n-button>
            <n-button type="primary" round :loading="loading.vms" @click="fetchVms">
              <template #icon>
                <TheIcon icon="mdi:database-search-outline" :size="18" />
              </template>
              查询
            </n-button>
          </section>

          <section class="content-panel">
            <div class="panel-head">
              <div>
                <span class="eyebrow">{{ selectedNode?.label || '全部节点' }}</span>
                <h2>虚拟机列表</h2>
              </div>
              <div class="status-summary">
                <n-tag type="success" round>运行 {{ vmSummary.running || 0 }}</n-tag>
                <n-tag type="default" round>停止 {{ vmSummary.stopped || 0 }}</n-tag>
              </div>
            </div>

            <n-data-table
              remote
              :loading="loading.vms"
              :columns="columns"
              :data="vmList"
              :pagination="pagination"
              :scroll-x="1280"
              :row-key="(row) => row.id"
              :row-class-name="() => 'vm-table-row'"
              @update:page="pagination.page = $event"
              @update:page-size="pagination.pageSize = $event"
            />
          </section>
        </main>
      </section>
    </div>
  </AppPage>
</template>

<script setup>
import { computed, h, onMounted, reactive, ref } from 'vue'
import { NButton, NSpace, NTag, useMessage } from 'naive-ui'
import api from '@/api'
import TheIcon from '@/components/icon/TheIcon.vue'

const message = useMessage()

const loading = reactive({
  nodes: false,
  vms: false,
})

const filters = reactive({
  nodeKeyword: '',
  vmKeyword: '',
  status: null,
})

const nodeOptions = ref([])
const selectedNode = ref(null)
const vmList = ref([])
const vmSummary = reactive({
  total: 0,
  running: 0,
  stopped: 0,
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  showSizePicker: true,
  pageSizes: [20, 50, 100],
})

const statusOptions = [
  { label: '运行中', value: 'running' },
  { label: '已停止', value: 'stopped' },
]

const filteredNodes = computed(() => {
  const keyword = filters.nodeKeyword.trim().toLowerCase()
  if (!keyword) return nodeOptions.value
  return nodeOptions.value.filter((node) =>
    [node.label, node.remote, node.status].some((value) => String(value || '').toLowerCase().includes(keyword))
  )
})

const columns = [
  { title: 'VMID', key: 'vmid', width: 90 },
  {
    title: '虚拟机名称',
    key: 'name',
    minWidth: 300,
    ellipsis: { tooltip: true },
    render(row) {
      return h('div', { class: 'vm-name-cell' }, [
        h('strong', row.name || '-'),
      ])
    },
  },
  {
    title: '状态',
    key: 'status',
    width: 110,
    render(row) {
      const running = row.status === 'running'
      return h(
        NTag,
        { size: 'small', round: true, type: running ? 'success' : 'default' },
        { default: () => (running ? '运行中' : '已停止') }
      )
    },
  },
  {
    title: 'CPU',
    key: 'cpu',
    width: 150,
    render(row) {
      return `${row.cpu || 0}% / ${row.maxcpu || 0} 核`
    },
  },
  {
    title: '内存',
    key: 'mem',
    width: 260,
    render(row) {
      return `${formatBytes(row.mem)} / ${formatBytes(row.maxmem)}`
    },
  },
  {
    title: '磁盘',
    key: 'disk',
    width: 190,
    render(row) {
      const disk = formatBytes(row.disk)
      const maxdisk = formatBytes(row.maxdisk)
      if (disk === '-' && maxdisk !== '-') return maxdisk
      if (disk !== '-' && maxdisk !== '-') return `${disk} / ${maxdisk}`
      return disk
    },
  },
  {
    title: '运行时间',
    key: 'uptime',
    width: 140,
    render(row) {
      return formatUptime(row.uptime)
    },
  },
  {
    title: '备注',
    key: 'remark',
    minWidth: 140,
    ellipsis: { tooltip: true },
    render(row) {
      return row.remark || '暂无备注'
    },
  },
  {
    title: '操作',
    key: 'actions',
    width: 260,
    fixed: 'right',
    render(row) {
      return h(
        NSpace,
        { class: 'vm-row-actions', size: 6, wrap: false },
        {
          default: () => [
            actionButton('编辑', 'material-symbols:edit-outline-rounded', 'info', row),
            actionButton('删除', 'material-symbols:delete-outline-rounded', 'error', row),
            actionButton('迁移', 'material-symbols:send-rounded', 'warning', row, 'vm-button-send'),
          ],
        }
      )
    },
  },
]

function actionButton(label, icon, type, row, className = '') {
  return h(
    NButton,
    {
      class: className,
      size: 'tiny',
      round: true,
      secondary: true,
      type,
      onClick: (event) => {
        event.stopPropagation()
        message.info(`${label}功能后续实现：${row.name}`)
      },
    },
    {
      icon: () => h(TheIcon, { icon, size: 14 }),
      default: () => label,
    }
  )
}

async function fetchNodes() {
  loading.nodes = true
  try {
    const res = await api.virtualMachineApi.pveNodes()
    nodeOptions.value = res.data || []
  } catch (error) {
    nodeOptions.value = []
    message.error(error.message || '读取 PDM 节点列表失败')
  } finally {
    loading.nodes = false
  }
}

async function refreshNodes() {
  await fetchNodes()
  if (selectedNode.value && !nodeOptions.value.some((node) => node.value === selectedNode.value.value)) {
    selectedNode.value = null
  }
  await fetchVms()
}

async function fetchVms() {
  loading.vms = true
  try {
    const res = await api.virtualMachineApi.pveVms({
      node: selectedNode.value?.value || '',
      keyword: filters.vmKeyword || '',
      status: filters.status || '',
    })
    vmList.value = res.data?.items || []
    Object.assign(vmSummary, res.data?.summary || { total: 0, running: 0, stopped: 0 })
    pagination.page = 1
  } catch (error) {
    vmList.value = []
    Object.assign(vmSummary, { total: 0, running: 0, stopped: 0 })
    message.error(error.message || '读取 PDM 虚拟机失败')
  } finally {
    loading.vms = false
  }
}

function selectNode(node) {
  selectedNode.value = node
  fetchVms()
}

function resetFilters() {
  filters.nodeKeyword = ''
  filters.vmKeyword = ''
  filters.status = null
  selectedNode.value = null
  fetchVms()
}

function formatBytes(value) {
  const bytes = Number(value || 0)
  if (!bytes) return '-'
  const units = ['B', 'KiB', 'MiB', 'GiB', 'TiB']
  let size = bytes
  let index = 0
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024
    index += 1
  }
  return `${size.toFixed(index === 0 ? 0 : 2)} ${units[index]}`
}

function formatUptime(value) {
  const seconds = Number(value || 0)
  if (!seconds) return '-'
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  if (days) return `${days}天 ${hours}小时`
  if (hours) return `${hours}小时 ${minutes}分钟`
  return `${minutes}分钟`
}

onMounted(async () => {
  await fetchNodes()
  await fetchVms()
})
</script>

<style scoped>
.vm-page {
  min-height: 100%;
  background: #f5f7fb;
  padding: 16px;
}

.vm-layout {
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr);
  gap: 16px;
}

.vm-sidebar,
.content-panel,
.summary-band article {
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 12px 30px rgba(15, 23, 42, 0.04);
}

.vm-sidebar {
  min-height: calc(100vh - 128px);
  padding: 16px;
}

.vm-main {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 16px;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.panel-head h2 {
  margin: 4px 0 0;
  color: #0f172a;
  font-size: 18px;
  line-height: 1.25;
}

.eyebrow {
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}

.side-search {
  margin-bottom: 12px;
}

.side-list {
  display: flex;
  max-height: calc(100vh - 240px);
  flex-direction: column;
  gap: 8px;
  overflow: auto;
  padding-right: 2px;
}

.side-list-item {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  color: #0f172a;
  cursor: pointer;
  padding: 10px 12px;
  text-align: left;
}

.side-list-item:hover,
.side-list-item.active {
  border-color: #fb5b2f;
  background: #fff7ed;
}

.side-list-item span {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
}

.side-list-item strong,
.side-list-item em {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.side-list-item em {
  color: #64748b;
  font-size: 12px;
  font-style: normal;
}

.summary-band {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.summary-band article {
  padding: 14px 16px;
}

.summary-band span {
  display: block;
  color: #64748b;
  font-size: 13px;
}

.summary-band strong {
  display: block;
  overflow: hidden;
  margin-top: 6px;
  color: #0f172a;
  font-size: 24px;
  line-height: 1.2;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.filter-panel {
  display: grid;
  grid-template-columns: minmax(280px, 1fr) 160px auto auto;
  align-items: center;
  gap: 10px;
}

.content-panel {
  padding: 16px;
}

.content-panel :deep(.vm-row-actions) {
  display: flex;
  align-items: center;
  flex-flow: row nowrap !important;
  flex-wrap: nowrap;
  gap: 6px !important;
}

.content-panel :deep(.vm-button-send) {
  --n-text-color: #d4380d !important;
  --n-text-color-hover: #d4380d !important;
  --n-text-color-pressed: #ad2b08 !important;
  --n-text-color-focus: #d4380d !important;
  --n-color: rgba(250, 140, 22, 0.12) !important;
  --n-color-hover: rgba(250, 140, 22, 0.18) !important;
  --n-color-pressed: rgba(250, 140, 22, 0.24) !important;
  --n-color-focus: rgba(250, 140, 22, 0.18) !important;
  --n-border: 1px solid rgba(250, 140, 22, 0.28) !important;
  --n-border-hover: 1px solid rgba(250, 140, 22, 0.4) !important;
  --n-border-pressed: 1px solid rgba(250, 140, 22, 0.48) !important;
  --n-border-focus: 1px solid rgba(250, 140, 22, 0.4) !important;
}

.status-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.vm-name-cell {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 5px;
}

.vm-name-cell strong,
.vm-name-cell span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.vm-name-cell span {
  color: #64748b;
  font-size: 12px;
}

html.dark .vm-page {
  background: #0f172a;
}

html.dark .vm-sidebar,
html.dark .content-panel,
html.dark .summary-band article,
html.dark .side-list-item {
  border-color: rgba(148, 163, 184, 0.2);
  background: rgba(17, 24, 39, 0.86);
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.2);
}

html.dark .side-list-item:hover,
html.dark .side-list-item.active {
  border-color: #fb5b2f;
  background: rgba(124, 45, 18, 0.36);
}

html.dark .panel-head h2,
html.dark .summary-band strong,
html.dark .side-list-item {
  color: #e5e7eb;
}

html.dark .eyebrow,
html.dark .summary-band span,
html.dark .side-list-item em,
html.dark .vm-name-cell span {
  color: #94a3b8;
}

html.dark .content-panel :deep(.n-data-table-th) {
  background: #111827;
  color: #cbd5e1;
}

html.dark .content-panel :deep(.n-data-table-td) {
  color: #e5e7eb;
}

html.dark .content-panel :deep(.vm-table-row .n-data-table-td) {
  border-bottom-color: rgba(148, 163, 184, 0.16);
}

html.dark .content-panel :deep(.vm-table-row:hover .n-data-table-td) {
  background: rgba(30, 41, 59, 0.72);
}

@media (max-width: 960px) {
  .vm-layout,
  .summary-band,
  .filter-panel {
    grid-template-columns: 1fr;
  }

  .vm-sidebar {
    min-height: auto;
  }

  .side-list {
    max-height: 360px;
  }
}
</style>
