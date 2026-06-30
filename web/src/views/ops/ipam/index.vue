<template>
  <AppPage :show-footer="false">
    <div class="ipam-page">
      <section class="ipam-toolbar">
        <div class="toolbar-title">
          <span class="eyebrow">NetBox IPAM</span>
          <h2>IP 管理</h2>
        </div>
        <div class="toolbar-filters">
          <n-input v-model:value="filters.search" clearable placeholder="搜索子网 / 客户 / 供应商 / 地址" @keyup.enter="fetchOverview">
            <template #prefix>
              <TheIcon icon="mdi:magnify" :size="18" />
            </template>
          </n-input>
          <n-select v-model:value="filters.family" clearable placeholder="IP 版本" :options="familyOptions" />
          <n-select v-model:value="filters.status" clearable placeholder="状态" :options="statusOptions" />
          <n-button secondary round @click="resetFilters">
            <template #icon>
              <TheIcon icon="mdi:refresh" :size="18" />
            </template>
            重置
          </n-button>
          <n-button type="primary" round :loading="loading" @click="fetchOverview">
            <template #icon>
              <TheIcon icon="mdi:database-search-outline" :size="18" />
            </template>
            同步
          </n-button>
        </div>
      </section>

      <section class="summary-grid">
        <article>
          <span>子网数量</span>
          <strong>{{ summary.prefix_count || 0 }}</strong>
        </article>
        <article>
          <span>已登记 IP</span>
          <strong>{{ summary.ip_count || 0 }}</strong>
        </article>
        <article>
          <span>可用容量</span>
          <strong>{{ formatNumber(summary.usable) }}</strong>
        </article>
        <article>
          <span>整体利用率</span>
          <strong>{{ formatPercent(summary.utilization) }}</strong>
        </article>
        <article>
          <span>客户数量</span>
          <strong>{{ summary.customer_count || 0 }}</strong>
        </article>
        <article>
          <span>供应商数量</span>
          <strong>{{ summary.supplier_count || 0 }}</strong>
        </article>
      </section>

      <section class="ipam-layout">
        <aside class="prefix-panel">
          <div class="panel-head">
            <h3>子网划分</h3>
            <n-tag round size="small">{{ prefixes.length }}</n-tag>
          </div>
          <div class="prefix-list">
            <button
              v-for="prefix in prefixes"
              :key="prefix.id || prefix.prefix"
              class="prefix-item"
              :class="{ active: selectedPrefix?.prefix === prefix.prefix }"
              @click="selectPrefix(prefix)"
            >
              <span class="prefix-main">
                <strong>{{ prefix.prefix }}</strong>
                <em>{{ prefixMaskMeta(prefix) }}</em>
              </span>
              <span class="prefix-meta">
                <n-progress
                  type="line"
                  :percentage="Math.min(prefix.utilization || 0, 100)"
                  :height="6"
                  :show-indicator="false"
                  :status="progressStatus(prefix.utilization)"
                />
                <b>{{ formatPercent(prefix.utilization) }}</b>
              </span>
            </button>
            <n-empty v-if="!prefixes.length && !loading" description="暂无子网数据" />
          </div>
        </aside>

        <main class="detail-panel">
          <n-spin :show="loading">
            <template v-if="selectedPrefix">
              <div class="detail-head">
                <div>
                  <span class="eyebrow">Prefix</span>
                  <h2>{{ selectedPrefix.prefix }}</h2>
                  <p>{{ prefixSubtitle(selectedPrefix) }}</p>
                </div>
                <div class="detail-meter">
                  <n-progress
                    type="circle"
                    :percentage="Math.min(selectedPrefix.utilization || 0, 100)"
                    :status="progressStatus(selectedPrefix.utilization)"
                  />
                  <span>{{ selectedPrefix.used }} / {{ selectedPrefix.usable }}</span>
                </div>
              </div>

              <div class="prefix-stats">
                <article>
                  <span>可用</span>
                  <strong>{{ formatNumber(selectedPrefix.available) }}</strong>
                </article>
                <article>
                  <span>已用</span>
                  <strong>{{ formatNumber(selectedPrefix.used) }}</strong>
                </article>
                <article>
                  <span>客户</span>
                  <strong>{{ selectedPrefix.top_customers?.length || 0 }}</strong>
                </article>
                <article>
                  <span>状态</span>
                  <strong>{{ mapPrefixStatus(selectedPrefix) }}</strong>
                </article>
              </div>

              <n-data-table
                size="small"
                :columns="ipColumns"
                :data="selectedPrefix.ips || []"
                :pagination="ipPagination"
                :row-key="(row) => row.id || row.address"
              />
            </template>
            <n-empty v-else description="请选择一个子网" />
          </n-spin>
        </main>
      </section>
    </div>
  </AppPage>
</template>

<script setup>
import { h, onMounted, reactive, ref } from 'vue'
import { NTag, useMessage } from 'naive-ui'
import api from '@/api'
import TheIcon from '@/components/icon/TheIcon.vue'

defineOptions({ name: 'OpsIpam' })

const message = useMessage()
const loading = ref(false)
const prefixes = ref([])
const selectedPrefix = ref(null)
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
  search: '',
  family: null,
  status: null,
})

const familyOptions = [
  { label: 'IPv4', value: 4 },
  { label: 'IPv6', value: 6 },
]

const statusOptions = [
  { label: '启用 / 已用', value: 'active' },
  { label: '预留', value: 'reserved' },
  { label: '废弃', value: 'deprecated' },
  { label: '容器', value: 'container' },
]

const ipPagination = reactive({
  pageSize: 12,
  showSizePicker: true,
  pageSizes: [12, 24, 48],
})

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
  { title: '说明', key: 'description', minWidth: 200 },
]

function statusTagType(status) {
  if (status === 'active') return 'success'
  if (status === 'reserved') return 'warning'
  if (status === 'deprecated') return 'error'
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
  return [supplier, prefix.site, prefix.role, prefix.vlan, prefix.vrf].filter(Boolean).join(' / ') || '未分类'
}

function prefixMaskMeta(prefix) {
  const supplier = prefix.supplier && prefix.supplier !== '未指定' ? `供应商: ${prefix.supplier}` : ''
  return [supplier].filter(Boolean).join(' / ') || '未归属'
}

function selectPrefix(prefix) {
  selectedPrefix.value = prefix
}

function resetFilters() {
  filters.search = ''
  filters.family = null
  filters.status = null
  fetchOverview()
}

async function fetchOverview() {
  loading.value = true
  try {
    const res = await api.netboxApi.ipamOverview({
      search: filters.search || undefined,
      family: filters.family || undefined,
      status: filters.status || undefined,
    })
    Object.assign(summary, res.data?.summary || {})
    prefixes.value = res.data?.prefixes || []
    if (!selectedPrefix.value || !prefixes.value.some((item) => item.prefix === selectedPrefix.value.prefix)) {
      selectedPrefix.value = prefixes.value[0] || null
    } else {
      selectedPrefix.value = prefixes.value.find((item) => item.prefix === selectedPrefix.value.prefix)
    }
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
.summary-grid article,
.prefix-panel,
.detail-panel {
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 12px 30px rgba(15, 23, 42, 0.04);
}

.ipam-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px;
}

.toolbar-title h2,
.detail-head h2,
.panel-head h3 {
  margin: 0;
  color: #0f172a;
  letter-spacing: 0;
}

.toolbar-title h2 {
  font-size: 20px;
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
  width: min(920px, 100%);
  grid-template-columns: minmax(220px, 1fr) 120px 140px auto auto;
  gap: 8px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 8px;
  margin-top: 8px;
}

.summary-grid article,
.prefix-stats article {
  padding: 12px;
}

.summary-grid span,
.prefix-stats span {
  display: block;
  color: #64748b;
  font-size: 12px;
}

.summary-grid strong,
.prefix-stats strong {
  display: block;
  margin-top: 4px;
  color: #0f172a;
  font-size: 24px;
  line-height: 1.1;
}

.prefix-panel,
.detail-panel {
  padding: 12px;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.panel-head h3 {
  font-size: 15px;
}

.ipam-layout {
  display: grid;
  grid-template-columns: 360px minmax(0, 1fr);
  gap: 8px;
  margin-top: 8px;
}

.prefix-panel,
.detail-panel {
  min-height: 0;
}

.prefix-list {
  display: grid;
  max-height: calc(100vh - 270px);
  gap: 8px;
  overflow-y: auto;
  padding-right: 2px;
}

.prefix-item {
  display: grid;
  width: 100%;
  grid-template-columns: minmax(0, 1fr) 110px;
  gap: 10px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
  padding: 10px;
  text-align: left;
}

.prefix-item:hover,
.prefix-item.active {
  border-color: #0ea5e9;
  background: #f0f9ff;
}

.prefix-main,
.prefix-meta {
  min-width: 0;
}

.prefix-main strong,
.prefix-main em {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.prefix-main strong {
  color: #0f172a;
  font-size: 14px;
}

.prefix-main em {
  margin-top: 3px;
  color: #64748b;
  font-size: 12px;
  font-style: normal;
}

.prefix-meta {
  display: grid;
  align-content: center;
  gap: 5px;
}

.prefix-meta b {
  color: #334155;
  font-size: 12px;
  text-align: right;
}

.detail-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.detail-head h2 {
  font-size: 24px;
}

.detail-head p {
  margin: 6px 0 0;
  color: #64748b;
}

.detail-meter {
  display: grid;
  justify-items: center;
  gap: 6px;
  min-width: 120px;
  color: #475569;
}

.prefix-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  margin: 12px 0;
}

.prefix-stats article {
  border-radius: 8px;
  background: #f8fafc;
}

html.dark .ipam-page {
  background: #0f172a;
}

html.dark .ipam-toolbar,
html.dark .summary-grid article,
html.dark .prefix-panel,
html.dark .detail-panel,
html.dark .prefix-item {
  border-color: rgba(148, 163, 184, 0.22);
  background: rgba(17, 24, 39, 0.92);
  box-shadow: none;
}

html.dark .toolbar-title h2,
html.dark .detail-head h2,
html.dark .panel-head h3,
html.dark .summary-grid strong,
html.dark .prefix-stats strong,
html.dark .prefix-main strong {
  color: #e5e7eb;
}

html.dark .prefix-item:hover,
html.dark .prefix-item.active,
html.dark .prefix-stats article {
  border-color: #38bdf8;
  background: rgba(14, 165, 233, 0.12);
}

@media (max-width: 1180px) {
  .toolbar-filters {
    grid-template-columns: 1fr 120px 140px;
  }

  .summary-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .ipam-layout {
    grid-template-columns: 1fr;
  }

  .prefix-list {
    max-height: 360px;
  }
}

@media (max-width: 760px) {
  .ipam-toolbar,
  .detail-head {
    align-items: stretch;
    flex-direction: column;
  }

  .toolbar-filters,
  .summary-grid,
  .prefix-stats {
    grid-template-columns: 1fr;
  }
}
</style>
