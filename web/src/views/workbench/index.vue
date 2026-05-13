<template>
  <AppPage :show-footer="false">
    <div class="workbench-page">
      <section class="toolbar-panel">
        <div class="user-cluster">
          <img class="user-avatar" :src="userStore.avatar" alt="avatar" />
          <div class="user-copy">
            <span class="eyebrow">IDC 运维中心</span>
            <h1>{{ greetingText }}</h1>
            <p>聚合故障响应、服务请求、变更窗口与维护计划。</p>
          </div>
        </div>
        <div class="toolbar-actions">
          <n-button secondary :loading="loading" @click="loadDashboard">
            <template #icon>
              <TheIcon icon="material-symbols:refresh-rounded" :size="18" />
            </template>
            刷新
          </n-button>
          <n-button type="primary" @click="goTicket">
            <template #icon>
              <TheIcon icon="mdi:ticket-confirmation-outline" :size="18" />
            </template>
            进入工单
          </n-button>
        </div>
      </section>

      <n-alert v-if="loadError" class="mb-15" type="warning" :show-icon="false">
        {{ loadError }}
      </n-alert>

      <section class="metric-grid">
        <article v-for="item in metricCards" :key="item.key" class="metric-card">
          <div class="metric-icon" :style="{ color: item.color, background: item.bg }">
            <TheIcon :icon="item.icon" :size="24" />
          </div>
          <div>
            <p class="metric-label">{{ item.label }}</p>
            <strong>{{ item.value }}</strong>
            <span>{{ item.hint }}</span>
          </div>
        </article>
      </section>

      <section class="dashboard-grid">
        <article class="panel status-panel">
          <header class="panel-header">
            <div>
              <span class="panel-kicker">Ticket Flow</span>
              <h2>工单态势</h2>
            </div>
            <n-tag round :type="healthTagType">完成率 {{ completionRate }}%</n-tag>
          </header>

          <div v-if="loading" class="skeleton-list">
            <n-skeleton v-for="i in 4" :key="i" height="34px" round />
          </div>
          <div v-else class="status-list">
            <div v-for="item in statusRows" :key="item.value" class="status-row">
              <div class="row-title">
                <span class="status-dot" :style="{ background: item.color }"></span>
                <span>{{ item.label }}</span>
                <strong>{{ item.count }}</strong>
              </div>
              <n-progress
                type="line"
                :height="8"
                :percentage="item.percent"
                :color="item.color"
                :show-indicator="false"
                rail-color="#edf1f7"
              />
            </div>
          </div>
        </article>

        <article class="panel">
          <header class="panel-header">
            <div>
              <span class="panel-kicker">IDC Queue</span>
              <h2>运维队列</h2>
            </div>
            <n-tag round :type="dashboard.riskCount ? 'warning' : 'success'">
              {{ dashboard.riskCount ? '需关注' : '稳定' }}
            </n-tag>
          </header>

          <div class="queue-list">
            <button v-for="item in queueRows" :key="item.value" class="queue-item" @click="goTicket">
              <span class="queue-icon" :style="{ color: item.color, background: item.bg }">
                <TheIcon :icon="item.icon" :size="20" />
              </span>
              <span class="queue-copy">
                <strong>{{ item.label }}</strong>
                <em>{{ item.desc }}</em>
              </span>
              <span class="queue-value">{{ item.count }}</span>
            </button>
          </div>
        </article>
      </section>

      <section class="lower-grid">
        <article class="panel recent-panel">
          <header class="panel-header">
            <div>
              <span class="panel-kicker">Recent Tickets</span>
              <h2>最近工单</h2>
            </div>
            <n-button text type="primary" @click="goTicket">查看全部</n-button>
          </header>

          <div v-if="loading" class="skeleton-list">
            <n-skeleton v-for="i in 5" :key="i" height="52px" round />
          </div>
          <n-empty v-else-if="!recentTickets.length" description="暂无工单数据" />
          <div v-else class="ticket-list">
            <button v-for="ticket in recentTickets" :key="ticket.id" class="ticket-row" @click="goTicket">
              <span class="ticket-main">
                <span class="ticket-no">{{ ticket.ticketNo }}</span>
                <strong>{{ ticket.title }}</strong>
              </span>
              <span class="ticket-meta">
                <n-tag size="small" :bordered="false" :color="getTypeColor(ticket.type)">
                  {{ getTypeName(ticket.type) }}
                </n-tag>
                <n-tag size="small" :type="getStatusTagType(ticket.status)">
                  {{ getStatusName(ticket.status) }}
                </n-tag>
                <em>{{ formatDate(ticket.createdAt) }}</em>
              </span>
            </button>
          </div>
        </article>

        <article class="panel focus-panel">
          <header class="panel-header">
            <div>
              <span class="panel-kicker">Pending Work</span>
              <h2>待处理队列</h2>
            </div>
          </header>

          <n-empty v-if="!loading && !waitingTickets.length" description="当前无待处理工单" />
          <div v-else class="waiting-list">
            <div v-if="loading" class="skeleton-list">
              <n-skeleton v-for="i in 4" :key="i" height="46px" round />
            </div>
            <button v-for="ticket in waitingTickets" v-else :key="ticket.id" class="waiting-row" @click="goTicket">
              <span>
                <strong>{{ ticket.title }}</strong>
                <em>{{ ticket.ticketNo }} · {{ getTypeName(ticket.type) }}</em>
              </span>
              <n-tag size="small" :type="getAgeTagType(ticket.createdAt)">
                {{ getTicketAge(ticket.createdAt) }}
              </n-tag>
            </button>
          </div>

          <div class="type-block">
            <h3>类型分布</h3>
            <div v-for="item in typeRows" :key="item.value" class="type-row">
              <span>{{ item.label }}</span>
              <div class="type-bar">
                <i :style="{ width: `${item.percent}%`, background: item.color }"></i>
              </div>
              <strong>{{ item.count }}</strong>
            </div>
          </div>
        </article>
      </section>
    </div>
  </AppPage>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/api'
import TheIcon from '@/components/icon/TheIcon.vue'
import { useUserStore } from '@/store'

defineOptions({ name: 'Workbench' })

const router = useRouter()
const userStore = useUserStore()
const loading = ref(false)
const loadError = ref('')

const emptyCountMap = () => ({ 0: 0, 1: 0, 2: 0, 3: 0 })

const dashboard = reactive({
  total: 0,
  statusCounts: emptyCountMap(),
  typeCounts: emptyCountMap(),
  activeTypeCounts: emptyCountMap(),
  todayCreated: 0,
  riskCount: 0,
  recentTickets: [],
  waitingTickets: [],
})

const statusMeta = [
  { value: 2, label: '未开始', color: '#2563eb' },
  { value: 1, label: '进行中', color: '#06b6d4' },
  { value: 0, label: '已完成', color: '#16a34a' },
  { value: 3, label: '已关闭', color: '#94a3b8' },
]

const typeMeta = [
  {
    value: 0,
    label: '故障响应',
    desc: '链路、服务器、网络异常',
    icon: 'mdi:server-network',
    color: '#ef4444',
    bg: 'rgba(239, 68, 68, .1)',
  },
  {
    value: 1,
    label: '服务请求',
    desc: '带宽、资源、权限类需求',
    icon: 'mdi:clipboard-text-clock-outline',
    color: '#2563eb',
    bg: 'rgba(37, 99, 235, .1)',
  },
  {
    value: 2,
    label: '变更窗口',
    desc: '割接、配置、路由调整',
    icon: 'mdi:source-branch-sync',
    color: '#7c3aed',
    bg: 'rgba(124, 58, 237, .1)',
  },
  {
    value: 3,
    label: '维护计划',
    desc: '巡检、升级、资产维护',
    icon: 'mdi:shield-check-outline',
    color: '#0f9f6e',
    bg: 'rgba(15, 159, 110, .1)',
  },
]

const greetingText = computed(() => {
  const name = userStore.name || '用户'
  return `${name}，今日工单概览`
})

const activeTotal = computed(() => {
  return getStatusCount(1) + getStatusCount(2)
})

const completionRate = computed(() => {
  if (!dashboard.total) return 0
  return Math.round((getStatusCount(0) / dashboard.total) * 100)
})

const healthTagType = computed(() => {
  if (dashboard.riskCount > 0) return 'warning'
  if (completionRate.value >= 70) return 'success'
  return 'info'
})

const metricCards = computed(() => [
  {
    key: 'total',
    label: '工单总量',
    value: dashboard.total,
    hint: '当前可见范围',
    icon: 'mdi:ticket-confirmation-outline',
    color: '#2563eb',
    bg: 'rgba(37, 99, 235, .1)',
  },
  {
    key: 'active',
    label: '待推进',
    value: activeTotal.value,
    hint: `${getStatusCount(2)} 个未开始 / ${getStatusCount(1)} 个进行中`,
    icon: 'mdi:progress-clock',
    color: '#06b6d4',
    bg: 'rgba(6, 182, 212, .1)',
  },
  {
    key: 'today',
    label: '今日新增',
    value: dashboard.todayCreated,
    hint: '当天提交工单',
    icon: 'mdi:calendar-plus-outline',
    color: '#16a34a',
    bg: 'rgba(22, 163, 74, .1)',
  },
  {
    key: 'risk',
    label: '超时关注',
    value: dashboard.riskCount,
    hint: '超过 24 小时未闭环',
    icon: 'mdi:alert-decagram-outline',
    color: '#f97316',
    bg: 'rgba(249, 115, 22, .12)',
  },
])

const statusRows = computed(() => {
  return statusMeta.map((item) => {
    const count = getStatusCount(item.value)
    return {
      ...item,
      count,
      percent: getPercent(count, dashboard.total),
    }
  })
})

const typeRows = computed(() => {
  return typeMeta.map((item) => {
    const count = getTypeCount(item.value)
    return {
      ...item,
      count,
      percent: getPercent(count, dashboard.total),
    }
  })
})

const queueRows = computed(() => {
  return typeMeta.map((item) => ({
    ...item,
    count: getActiveTypeCount(item.value),
  }))
})

const recentTickets = computed(() => dashboard.recentTickets.map(formatTicket))
const waitingTickets = computed(() => dashboard.waitingTickets.map(formatTicket))

function getStatusCount(status) {
  return Number(dashboard.statusCounts?.[status] || 0)
}

function getTypeCount(type) {
  return Number(dashboard.typeCounts?.[type] || 0)
}

function getActiveTypeCount(type) {
  return Number(dashboard.activeTypeCounts?.[type] || 0)
}

function getPercent(value, total) {
  if (!total) return 0
  return Math.min(100, Math.round((value / total) * 100))
}

function normalizeCountMap(value) {
  const source = value || {}
  return {
    0: Number(source[0] || 0),
    1: Number(source[1] || 0),
    2: Number(source[2] || 0),
    3: Number(source[3] || 0),
  }
}

function formatTicket(ticket) {
  return {
    id: ticket.id,
    ticketNo: ticket.ticket_no || '-',
    title: ticket.title || '未命名工单',
    type: Number(ticket.type ?? 0),
    status: Number(ticket.status ?? 2),
    createdAt: ticket.created_at,
    location: ticket.location,
  }
}

function getStatusName(status) {
  const map = { 0: '已完成', 1: '进行中', 2: '未开始', 3: '已关闭' }
  return map[status] || '未知'
}

function getStatusTagType(status) {
  const map = { 0: 'success', 1: 'info', 2: 'warning', 3: 'default' }
  return map[status] || 'default'
}

function getTypeName(type) {
  return typeMeta.find((item) => item.value === type)?.label || '工单'
}

function getTypeColor(type) {
  const meta = typeMeta.find((item) => item.value === type)
  return {
    color: meta?.bg || 'rgba(37, 99, 235, .1)',
    textColor: meta?.color || '#2563eb',
    borderColor: 'transparent',
  }
}

function formatDate(value) {
  if (!value) return '-'
  const date = new Date(String(value).replace(/-/g, '/'))
  if (Number.isNaN(date.getTime())) return value
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hour = String(date.getHours()).padStart(2, '0')
  const minute = String(date.getMinutes()).padStart(2, '0')
  return `${month}-${day} ${hour}:${minute}`
}

function getTicketAge(value) {
  if (!value) return '未知'
  const date = new Date(String(value).replace(/-/g, '/'))
  const diff = Date.now() - date.getTime()
  if (Number.isNaN(diff)) return '未知'
  const minutes = Math.max(1, Math.floor(diff / 60000))
  if (minutes < 60) return `${minutes} 分钟`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} 小时`
  return `${Math.floor(hours / 24)} 天`
}

function getAgeTagType(value) {
  const date = new Date(String(value || '').replace(/-/g, '/'))
  const diff = Date.now() - date.getTime()
  if (Number.isNaN(diff)) return 'default'
  if (diff >= 24 * 60 * 60 * 1000) return 'warning'
  return 'info'
}

async function loadDashboard() {
  loading.value = true
  loadError.value = ''
  try {
    const res = await api.ticketApi.dashboard()
    const data = res?.data || {}
    dashboard.total = Number(data.total || 0)
    dashboard.statusCounts = normalizeCountMap(data.status_counts)
    dashboard.typeCounts = normalizeCountMap(data.type_counts)
    dashboard.activeTypeCounts = normalizeCountMap(data.active_type_counts)
    dashboard.todayCreated = Number(data.today_created || 0)
    dashboard.riskCount = Number(data.risk_count || 0)
    dashboard.recentTickets = data.recent_tickets || []
    dashboard.waitingTickets = data.waiting_tickets || []
  } catch (error) {
    loadError.value = '工单看板数据加载失败，请确认后端服务和数据库连接正常。'
  } finally {
    loading.value = false
  }
}

function goTicket() {
  router.push('/ticket')
}

onMounted(() => {
  loadDashboard()
})
</script>

<style scoped>
.workbench-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
}

.toolbar-panel,
.metric-card,
.panel {
  border: 1px solid rgba(148, 163, 184, .22);
  border-radius: 8px;
  background: rgba(255, 255, 255, .96);
  box-shadow: 0 12px 30px rgba(15, 23, 42, .06);
}

.toolbar-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 20px;
}

.user-cluster {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 14px;
}

.user-avatar {
  width: 52px;
  height: 52px;
  flex: none;
  border-radius: 50%;
  object-fit: cover;
}

.user-copy {
  min-width: 0;
}

.eyebrow,
.panel-kicker {
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}

.user-copy h1 {
  margin: 4px 0;
  color: #0f172a;
  font-size: 22px;
  font-weight: 700;
  line-height: 1.2;
}

.user-copy p {
  margin: 0;
  color: #64748b;
  font-size: 14px;
}

.toolbar-actions {
  display: flex;
  flex: none;
  gap: 10px;
}

.metric-grid,
.dashboard-grid,
.lower-grid {
  display: grid;
  gap: 16px;
}

.metric-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.metric-card {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 14px;
  padding: 16px;
}

.metric-icon,
.queue-icon {
  display: inline-flex;
  flex: none;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
}

.metric-icon {
  width: 44px;
  height: 44px;
}

.metric-card p,
.metric-card span {
  margin: 0;
  color: #64748b;
  font-size: 13px;
}

.metric-card strong {
  display: block;
  margin: 4px 0 3px;
  color: #0f172a;
  font-size: 28px;
  font-weight: 800;
  line-height: 1;
}

.dashboard-grid {
  grid-template-columns: minmax(0, 1.35fr) minmax(320px, .65fr);
}

.lower-grid {
  grid-template-columns: minmax(0, 1.35fr) minmax(320px, .65fr);
  align-items: start;
}

.panel {
  min-width: 0;
  padding: 18px;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.panel-header h2 {
  margin: 3px 0 0;
  color: #0f172a;
  font-size: 17px;
  font-weight: 700;
}

.skeleton-list,
.status-list,
.queue-list,
.ticket-list,
.waiting-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.status-row {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.row-title {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 8px;
  color: #334155;
  font-size: 14px;
}

.row-title strong {
  color: #0f172a;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
}

.queue-item,
.ticket-row,
.waiting-row {
  width: 100%;
  border: 0;
  border-radius: 8px;
  background: #f8fafc;
  color: inherit;
  cursor: pointer;
  text-align: left;
  transition: background .2s ease, transform .2s ease;
}

.queue-item:hover,
.ticket-row:hover,
.waiting-row:hover {
  background: #eef6ff;
  transform: translateY(-1px);
}

.queue-item {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  padding: 12px;
}

.queue-icon {
  width: 38px;
  height: 38px;
}

.queue-copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 3px;
}

.queue-copy strong,
.ticket-main strong,
.waiting-row strong {
  overflow: hidden;
  color: #0f172a;
  font-size: 14px;
  font-style: normal;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.queue-copy em,
.ticket-meta em,
.waiting-row em {
  overflow: hidden;
  color: #64748b;
  font-size: 12px;
  font-style: normal;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.queue-value {
  color: #0f172a;
  font-size: 20px;
  font-weight: 800;
}

.ticket-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 14px;
  align-items: center;
  padding: 12px 14px;
}

.ticket-main {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 5px;
}

.ticket-no {
  color: #2563eb;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  font-weight: 700;
}

.ticket-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.waiting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 11px 12px;
}

.waiting-row span:first-child {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
}

.type-block {
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px solid #e2e8f0;
}

.type-block h3 {
  margin: 0 0 12px;
  color: #0f172a;
  font-size: 15px;
  font-weight: 700;
}

.type-row {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr) 32px;
  align-items: center;
  gap: 10px;
  margin-bottom: 11px;
  color: #334155;
  font-size: 13px;
}

.type-row strong {
  color: #0f172a;
  text-align: right;
}

.type-bar {
  height: 8px;
  overflow: hidden;
  border-radius: 999px;
  background: #edf1f7;
}

.type-bar i {
  display: block;
  height: 100%;
  min-width: 3px;
  border-radius: inherit;
}

:deep(.n-button) {
  border-radius: 8px;
}

html.dark .toolbar-panel,
html.dark .metric-card,
html.dark .panel {
  border-color: rgba(148, 163, 184, .16);
  background: rgba(24, 24, 28, .96);
  box-shadow: none;
}

html.dark .user-copy h1,
html.dark .panel-header h2,
html.dark .metric-card strong,
html.dark .row-title strong,
html.dark .queue-value,
html.dark .queue-copy strong,
html.dark .ticket-main strong,
html.dark .waiting-row strong,
html.dark .type-block h3,
html.dark .type-row strong {
  color: #f8fafc;
}

html.dark .user-copy p,
html.dark .metric-card p,
html.dark .metric-card span,
html.dark .queue-copy em,
html.dark .ticket-meta em,
html.dark .waiting-row em,
html.dark .eyebrow,
html.dark .panel-kicker {
  color: #94a3b8;
}

html.dark .queue-item,
html.dark .ticket-row,
html.dark .waiting-row {
  background: rgba(30, 41, 59, .62);
}

html.dark .queue-item:hover,
html.dark .ticket-row:hover,
html.dark .waiting-row:hover {
  background: rgba(37, 99, 235, .18);
}

html.dark .type-block {
  border-top-color: rgba(148, 163, 184, .18);
}

@media (max-width: 1180px) {
  .metric-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .dashboard-grid,
  .lower-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .workbench-page {
    padding: 12px;
  }

  .toolbar-panel,
  .ticket-row {
    align-items: stretch;
    grid-template-columns: 1fr;
  }

  .toolbar-panel,
  .toolbar-actions,
  .ticket-row,
  .ticket-meta {
    flex-direction: column;
  }

  .toolbar-actions {
    display: grid;
    grid-template-columns: 1fr 1fr;
  }

  .metric-grid {
    grid-template-columns: 1fr;
  }

  .ticket-meta {
    align-items: flex-start;
  }
}
</style>
