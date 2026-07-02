<template>
  <AppPage :show-footer="false">
    <div class="ipam-page">
      <section class="ipam-toolbar">
        <div class="toolbar-filters">
          <n-select
            v-model:value="filters.supplier"
            clearable
            filterable
            placeholder="供应商"
            :options="filterOptions.suppliers"
            @update:value="fetchOverview"
          />
          <n-select
            v-model:value="filters.customer"
            clearable
            filterable
            placeholder="客户"
            :options="filterOptions.customers"
            @update:value="fetchOverview"
          />
          <n-select
            v-model:value="filters.region"
            clearable
            filterable
            placeholder="地区"
            :options="filterOptions.regions"
            @update:value="fetchOverview"
          />
        </div>
      </section>

      <section class="tree-table-panel">
        <n-data-table
          size="small"
          :loading="loading"
          :columns="prefixColumns"
          :data="prefixTreeData"
          :pagination="false"
          :row-key="prefixRowKey"
          :bordered="false"
          striped
        />
      </section>

      <n-modal
        v-model:show="showIpModal"
        preset="card"
        :title="selectedPrefix?.prefix || 'IP Addresses'"
        class="ip-detail-modal"
        :bordered="false"
      >
        <template v-if="selectedPrefix">
          <div class="detail-head">
            <div>
              <span class="eyebrow">IP Addresses</span>
              <h3>{{ selectedPrefix.prefix }}</h3>
              <p>{{ prefixSubtitle(selectedPrefix) }}</p>
            </div>
            <div class="detail-meter">
              <n-progress
                type="circle"
                :percentage="Math.min(selectedPrefix.utilization || 0, 100)"
                :status="progressStatus(selectedPrefix.utilization)"
              />
              <span>{{ formatNumber(selectedPrefix.used) }} / {{ formatNumber(selectedPrefix.usable) }}</span>
            </div>
          </div>

          <n-data-table
            size="small"
            :columns="ipColumns"
            :data="selectedPrefixIps"
            :pagination="ipPagination"
            :row-key="(row) => row.id || row.address"
            striped
          />
        </template>
      </n-modal>
    </div>
  </AppPage>
</template>

<script setup>
import { computed, h, onMounted, reactive, ref } from 'vue'
import { NProgress, NTag, useMessage } from 'naive-ui'
import api from '@/api'

defineOptions({ name: 'OpsIpam' })

const message = useMessage()
const loading = ref(false)
const prefixes = ref([])
const selectedPrefix = ref(null)
const showIpModal = ref(false)
const summary = reactive({
  prefix_count: 0,
  ip_count: 0,
  used: 0,
  usable: 0,
  available: 0,
  utilization: 0,
  customer_count: 0,
  supplier_count: 0,
})

const filters = reactive({
  region: null,
  customer: null,
  supplier: null,
})

const filterOptions = reactive({
  regions: [],
  customers: [],
  suppliers: [],
})

const ipPagination = reactive({
  pageSize: 12,
  showSizePicker: true,
  pageSizes: [12, 24, 48],
})

const prefixTreeData = computed(() => buildPrefixTree(prefixes.value))
const selectedPrefixIps = computed(() => collectPrefixIps(selectedPrefix.value))

const prefixColumns = [
  {
    title: 'IP 前缀',
    key: 'prefix',
    resizable: true,
    width: 260,
    minWidth: 240,
    render(row) {
      return h(
        'button',
        {
          class: 'prefix-link',
          onClick: (event) => {
            event.stopPropagation()
            selectPrefix(row)
          },
        },
        [
          h(NTag, { size: 'tiny', round: true, type: prefixTypeTag(row).type }, { default: () => prefixTypeTag(row).text }),
          h('span', row.prefix || '-'),
        ]
      )
    },
  },
  {
    title: '状态',
    key: 'status',
    resizable: true,
    width: 90,
    minWidth: 82,
    render(row) {
      return h(NTag, { size: 'small', round: true, type: statusTagType(row.status) }, {
        default: () => mapPrefixStatus(row),
      })
    },
  },
  {
    title: '子网',
    key: 'child_prefix_count',
    resizable: true,
    width: 60,
    minWidth: 52,
    render(row) {
      return Number(row.child_prefix_count || 0)
    },
  },
  {
    title: '利用率',
    key: 'utilization',
    resizable: true,
    width: 150,
    minWidth: 130,
    render(row) {
      return h('div', { class: 'usage-cell' }, [
        h(NProgress, {
          type: 'line',
          percentage: Math.min(Number(row.utilization || 0), 100),
          height: 18,
          borderRadius: 4,
          fillBorderRadius: 4,
          showIndicator: false,
          status: progressStatus(row.utilization),
        }),
        h('span', formatPercent(row.utilization)),
      ])
    },
  },
  {
    title: '供应商',
    key: 'supplier',
    resizable: true,
    width: 130,
    minWidth: 110,
    ellipsis: { tooltip: true },
    render(row) {
      return row.supplier || row.owner || '未知'
    },
  },
  {
    title: '客户',
    key: 'customer',
    resizable: true,
    width: 120,
    minWidth: 100,
    ellipsis: { tooltip: true },
    render(row) {
      return row.customer || '—'
    },
  },
  {
    title: '地区',
    key: 'region',
    resizable: true,
    width: 90,
    minWidth: 72,
    ellipsis: { tooltip: true },
    render(row) {
      return row.region || row.scope || row.site || '—'
    },
  },
  {
    title: 'VLAN',
    key: 'vlan',
    resizable: true,
    width: 90,
    minWidth: 72,
    ellipsis: { tooltip: true },
    render(row) {
      return row.vlan || '—'
    },
  },
  {
    title: '描述',
    key: 'description',
    resizable: true,
    width: 320,
    minWidth: 260,
    ellipsis: { tooltip: true },
    render(row) {
      return row.description || '—'
    },
  },
]

const ipColumns = [
  { title: 'IP 地址', key: 'address', width: 170 },
  {
    title: '客户',
    key: 'customer',
    minWidth: 160,
    render(row) {
      return h(NTag, { size: 'small', round: true, type: row.customer === '未归属' ? 'warning' : 'success' }, {
        default: () => row.customer || '未归属',
      })
    },
  },
  {
    title: '状态',
    key: 'status',
    width: 110,
    render(row) {
      return h(NTag, { size: 'small', round: true, type: statusTagType(row.status) }, {
        default: () => row.status_label || mapIpStatus(row.status),
      })
    },
  },
  { title: '说明', key: 'description', minWidth: 220, ellipsis: { tooltip: true } },
]

function prefixRowKey(row) {
  return row.id || row.prefix
}

function statusTagType(status) {
  if (status === 'active') return 'success'
  if (status === 'reserved') return 'warning'
  if (status === 'deprecated') return 'error'
  if (status === 'container') return 'info'
  return 'default'
}

function mapIpStatus(status) {
  return {
    active: '已用',
    reserved: '预留/空闲',
    deprecated: '废弃',
    dhcp: 'DHCP',
    slaac: 'SLAAC',
  }[String(status || '').toLowerCase()] || status || '未知'
}

function mapPrefixStatus(prefix) {
  return prefix?.status_label || {
    active: '启用',
    reserved: '预留',
    deprecated: '废弃',
    container: '容器',
  }[String(prefix?.status || '').toLowerCase()] || prefix?.status || '未知'
}

function prefixTypeTag(row) {
  if (row.children?.length) return { text: '父级', type: 'info' }
  if (row.parent_prefix) return { text: '子级', type: 'success' }
  return { text: '前缀', type: 'default' }
}

function prefixSortValue(prefix) {
  const value = String(prefix?.prefix || '')
  const [address = '', mask = '0'] = value.split('/')
  const versionWeight = value.includes(':') ? 6 : 4
  const addressParts = address.split('.')
  const addressWeight = addressParts.length === 4 && addressParts.every((part) => /^\d+$/.test(part))
    ? addressParts.reduce((total, part) => total * 256 + Number(part || 0), 0)
    : Number.MAX_SAFE_INTEGER
  return [versionWeight, addressWeight, Number(mask || 0), value]
}

function comparePrefixes(left, right) {
  const leftValue = prefixSortValue(left)
  const rightValue = prefixSortValue(right)
  for (let index = 0; index < leftValue.length; index += 1) {
    if (leftValue[index] < rightValue[index]) return -1
    if (leftValue[index] > rightValue[index]) return 1
  }
  return 0
}

function buildPrefixTree(items) {
  const clones = new Map()
  const roots = []

  items.forEach((item) => {
    if (!item?.prefix) return
    clones.set(item.prefix, { ...item, children: [] })
  })

  clones.forEach((item) => {
    const parent = item.parent_prefix
    if (parent && parent !== item.prefix && clones.has(parent)) {
      clones.get(parent).children.push(item)
    } else {
      roots.push(item)
    }
  })

  const sortTree = (nodes) => {
    nodes.sort(comparePrefixes)
    nodes.forEach((node) => {
      sortTree(node.children)
      if (!node.children.length) delete node.children
    })
  }
  sortTree(roots)
  return roots
}

function collectPrefixIps(prefix) {
  if (!prefix) return []
  const ipMap = new Map()
  const addIp = (ip) => {
    if (!ip?.address && !ip?.ip) return
    ipMap.set(ip.id || ip.address || ip.ip, ip)
  }

  ;(prefix.ips || []).forEach(addIp)
  ;(prefix.ip_ranges || []).forEach((range) => {
    ;(range.ips || []).forEach(addIp)
  })

  return Array.from(ipMap.values())
}

function progressStatus(value) {
  const current = Number(value || 0)
  if (current >= 90) return 'error'
  if (current >= 70) return 'warning'
  return 'success'
}

function formatPercent(value) {
  return `${Number(value || 0).toFixed(1)}%`
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString()
}

function prefixSubtitle(prefix) {
  const supplier = prefix.supplier && prefix.supplier !== '未指定' ? `供应商: ${prefix.supplier}` : ''
  const parent = prefix.parent_prefix ? `父前缀: ${prefix.parent_prefix}` : ''
  const region = prefix.region || prefix.scope || prefix.site
  return [supplier, parent, region, prefix.role, prefix.vlan, prefix.vrf].filter(Boolean).join(' / ') || '未分类'
}

function selectPrefix(prefix) {
  selectedPrefix.value = prefix
  showIpModal.value = true
}

async function fetchOverview() {
  loading.value = true
  try {
    const res = await api.netboxApi.ipamOverview({
      region: filters.region || undefined,
      customer: filters.customer || undefined,
      supplier: filters.supplier || undefined,
    })
    Object.assign(summary, res.data?.summary || {})
    Object.assign(filterOptions, res.data?.filter_options || { regions: [], customers: [], suppliers: [] })
    prefixes.value = res.data?.prefixes || []
    const currentPrefix = selectedPrefix.value?.prefix
    selectedPrefix.value = currentPrefix ? prefixes.value.find((item) => item.prefix === currentPrefix) || null : null
    if (!selectedPrefix.value) showIpModal.value = false
  } catch (error) {
    message.error(error.message || '读取 NetBox IPAM 数据失败')
  } finally {
    loading.value = false
  }
}

onMounted(fetchOverview)
</script>

<style scoped>
.ipam-page {
  box-sizing: border-box;
  min-height: calc(100vh - 92px);
  padding: 12px;
  background: #f4f7fb;
}

.ipam-toolbar,
.tree-table-panel {
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 12px 30px rgba(15, 23, 42, 0.04);
}

.ipam-toolbar {
  padding: 12px;
}

.detail-head h3 {
  margin: 0;
  color: #0f172a;
  letter-spacing: 0;
}

.eyebrow {
  color: #64748b;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}

.toolbar-filters {
  display: grid;
  width: 100%;
  grid-template-columns: repeat(3, minmax(180px, 1fr));
  gap: 8px;
}

.tree-table-panel {
  margin-top: 8px;
  padding: 12px;
}

.detail-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}

.detail-head p {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 12px;
}

.prefix-link {
  display: inline-flex;
  max-width: 100%;
  align-items: center;
  gap: 8px;
  border: 0;
  background: transparent;
  color: #0369a1;
  cursor: pointer;
  font: inherit;
  font-weight: 700;
  padding: 0;
}

.prefix-link span:last-child {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.usage-cell {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 48px;
  align-items: center;
  gap: 8px;
}

.usage-cell span {
  color: #334155;
  font-size: 12px;
  text-align: right;
}

.detail-meter {
  display: grid;
  justify-items: center;
  gap: 6px;
  min-width: 120px;
  color: #475569;
}

html.dark .ipam-page {
  background: #0f172a;
}

html.dark .ipam-toolbar,
html.dark .tree-table-panel {
  border-color: rgba(148, 163, 184, 0.22);
  background: rgba(17, 24, 39, 0.92);
  box-shadow: none;
}

html.dark .detail-head h3 {
  color: #e5e7eb;
}

html.dark .prefix-link {
  color: #7dd3fc;
}

:deep(.ip-detail-modal) {
  width: min(1080px, calc(100vw - 48px));
}

@media (max-width: 1180px) {
  .toolbar-filters {
    grid-template-columns: repeat(3, minmax(160px, 1fr));
  }
}

@media (max-width: 760px) {
  .ipam-toolbar,
  .detail-head {
    align-items: stretch;
    flex-direction: column;
  }

  .toolbar-filters {
    grid-template-columns: 1fr;
  }
}
</style>
