<template>
  <AppPage class="events-page">
    <section class="events-panel">
      <header class="page-header">
        <div>
          <h2>{{ historyPage ? '历史事件' : '事件列表' }} <span class="brand">MonitorOps</span></h2>
          <p>
            {{
              historyPage
                ? '回溯近 7 天事件 · 恢复记录、持续时间与指标历史'
                : '处理当前未确认告警 · 定位、研判与处置'
            }}
          </p>
        </div>
        <n-space align="center">
          <CButton
            v-if="canConfigure"
            show-save
            save-text="监控主机"
            :disabled="acting || loading"
            @save="router.push('/events/hosts')"
          />
          <span class="updated">{{ updatedAt ? `更新于 ${date(updatedAt)}` : '等待同步' }}</span>
          <n-switch v-model:value="autoRefresh" :disabled="acting" /><span>30 秒刷新</span>
          <CButton
            show-save
            save-text="刷新"
            :save-loading="loading"
            :disabled="loading || acting"
            @save="refresh"
          />
        </n-space>
      </header>
      <n-alert v-if="error" type="error" class="notice"
        >{{ error }}；下方如有数据，为上次成功同步结果。</n-alert
      >
      <n-alert v-if="snapshot.truncated" type="warning" class="notice"
        >数据达到读取上限，统计仅覆盖已加载范围，请在 Zabbix 核实完整数据。</n-alert
      >
      <div v-if="!historyPage" class="metrics">
        <div v-for="metric in metrics" :key="metric.key" class="metric" :class="metric.key">
          <span>{{ metric.label }}</span
          ><strong>{{ snapshot.summary?.[metric.key] ?? '—' }}</strong>
        </div>
      </div>
      <n-alert v-if="snapshot.configured === false" type="info"
        >尚未纳管主机，请在“事件管理 → 监控主机”中添加；无配置权限时请联系管理员。</n-alert
      >
      <n-alert v-if="snapshot.unavailable_hosts" type="warning"
        >有
        {{ snapshot.unavailable_hosts }}
        台已选主机无法读取，请在配置中核查是否已停用、删除或权限变化。</n-alert
      >
      <div v-if="!historyPage" class="health-section">
        <div class="section-title">
          <h3>业务分类健康情况</h3>
          <span>平台分类 · 点击筛选</span>
        </div>
        <div class="health-grid">
          <button
            v-for="item in snapshot.categories || []"
            :key="item.key"
            class="health-row"
            :class="{ selected: category === item.key }"
            :aria-pressed="category === item.key"
            @click="chooseCategory(item.key)"
          >
            <span>{{ item.label }}</span>
            <n-progress
              type="line"
              :percentage="
                item.total ? Math.round(((item.total - item.abnormal) / item.total) * 100) : 0
              "
              :show-indicator="false"
              color="#269b76"
              :rail-color="item.total ? '#eda640' : '#e7edf4'"
              :height="7"
            />
            <small>{{ item.abnormal }} 异常 / {{ item.total }} 台</small>
          </button>
        </div>
      </div>
      <div class="section-title">
        <h3>{{ historyPage ? '历史事件记录' : '各类型最新告警' }}</h3>
        <span>{{
          historyPage
            ? '同一主机、同一告警合并展示最新记录 · 双击查看近 7 天同类历史'
            : '同一主机、同一触发器仅显示最新一条 · 双击行查看近 7 天历史'
        }}</span>
      </div>
      <div class="filters">
        <n-input
          v-model:value="keyword"
          clearable
          placeholder="搜索告警、主机、IP、站点、标签、事件 ID"
          @update:value="page = 1"
        />
        <n-select
          v-model:value="category"
          clearable
          :options="categoryOptions"
          placeholder="业务分类"
          @update:value="page = 1"
        />
        <n-select
          v-model:value="severity"
          clearable
          :options="severityOptions"
          placeholder="严重程度"
          @update:value="page = 1"
        />
        <n-select
          v-model:value="state"
          :options="stateOptions"
          :disabled="loading || acting"
          @update:value="changeState"
        />
      </div>
      <n-data-table
        class="event-table"
        size="small"
        striped
        flex-height
        :loading="loading"
        :columns="columns"
        :data="pageRows"
        :scroll-x="1550"
        :row-key="(row) => row.id"
        :row-props="historyRowProps"
      >
        <template #empty
          ><n-empty :description="error ? '无法获取事件，请检查连接后重试' : '当前条件下没有事件'"
        /></template>
      </n-data-table>
      <footer class="list-footer">
        <span>共 {{ filtered.length }} 类 · {{ snapshot.scope || '等待同步' }}</span>
        <n-pagination
          v-model:page="page"
          :item-count="filtered.length"
          :page-size="20"
          :page-slot="5"
        />
      </footer>
    </section>

    <n-modal
      v-model:show="typeHistoryOpen"
      preset="card"
      title="同类告警历史"
      style="width: min(1450px, calc(100vw - 24px))"
    >
      <p>
        {{ typeHistoryTarget?.hosts.map((host) => host.name).join(' / ') }} ·
        {{ typeHistoryTarget?.name }}
      </p>
      <p class="muted">同一主机、同一触发器 · 近 7 天发生的告警 · 按发生时间从新到旧排列</p>
      <n-alert v-if="typeHistoryError" type="error">{{ typeHistoryError }}</n-alert>
      <n-alert v-if="typeHistoryTruncated" type="warning"
        >历史查询达到读取上限，以下记录可能不完整。</n-alert
      >
      <n-data-table
        :columns="historyColumns"
        :data="typeHistoryRows"
        :loading="typeHistoryLoading"
        :row-key="(row) => row.id"
        :scroll-x="1550"
        :max-height="480"
        :pagination="{ pageSize: 10 }"
        size="small"
        striped
        class="event-history-table"
      />
    </n-modal>
    <MetricHistory v-model:show="metricOpen" :event="metricTarget" />
    <n-drawer
      v-model:show="detailOpen"
      :width="Math.min(900, viewportWidth - 24)"
      :mask-closable="!acting"
      :close-on-esc="!acting"
    >
      <n-drawer-content title="事件定位与处置" :closable="!acting">
        <n-spin :show="detailLoading">
          <n-alert v-if="detailError" type="error">{{ detailError }}</n-alert>
          <template v-if="selected">
            <div class="detail-heading">
              <n-tag :type="severityType(selected.severity)">{{
                severityNames[selected.severity]
              }}</n-tag>
              <h3>{{ selected.name }}</h3>
              <span>{{ status(selected) }} · #{{ selected.id }}</span>
            </div>
            <n-descriptions bordered :column="2" class="notice">
              <n-descriptions-item label="发生时间">{{ date(selected.clock) }}</n-descriptions-item>
              <n-descriptions-item label="持续时间">{{ duration(selected) }}</n-descriptions-item>
              <n-descriptions-item label="恢复时间">{{
                selected.recovered ? date(selected.recovery_clock) : '尚未恢复'
              }}</n-descriptions-item>
              <n-descriptions-item label="确认状态">{{
                selected.acknowledged ? '已确认' : '未确认'
              }}</n-descriptions-item>
            </n-descriptions>
            <h3>目标定位</h3>
            <article v-for="host in selected.hosts" :key="host.hostid" class="host-card">
              <strong>{{ host.name }}</strong
              ><span v-if="host.maintenance"> · 维护中</span>
              <p>主机名：{{ host.technical_name }} · 主机 ID：{{ host.hostid }}</p>
              <p>地址：{{ host.addresses.join(' / ') || '未配置' }}</p>
              <p>站点：{{ host.location || '未维护位置' }}</p>
              <p>主机组：{{ host.groups.join(' / ') || '未分组' }}</p>
              <p v-for="field in host.attributes || []" :key="field.key">
                {{ field.label }}：{{ field.value }}
              </p>
              <CButton show-save save-text="复制定位信息" @save="copyHost(host)" />
            </article>
            <n-empty
              v-if="!selected.hosts.length"
              description="主机不可见或已删除，请在 Zabbix 核实"
            />
            <n-space class="notice"
              ><n-tag v-for="(tag, index) in selected.tags" :key="index" size="small"
                >{{ tag.tag }}: {{ tag.value }}</n-tag
              ></n-space
            >
            <h3>触发条件与指标</h3>
            <pre class="expression">{{ selected.expression || '无可见触发条件' }}</pre>
            <p v-if="selected.recovery_expression">恢复条件：{{ selected.recovery_expression }}</p>
            <p v-if="selected.opdata">运行数据：{{ selected.opdata }}</p>
            <p v-if="selected.description" class="preserve">{{ selected.description }}</p>
            <n-data-table
              :columns="itemColumns"
              :data="selected.items || []"
              :scroll-x="640"
              size="small"
            />
            <p class="muted">指标为最新采样值，并非告警发生时的历史值；请结合采样时间判断。</p>
            <n-alert type="info" :title="`告警建议 · ${selected.advice.type}`" class="notice">
              <p>{{ selected.advice.basis }}</p>
              <ol>
                <li v-for="step in selected.advice.steps" :key="step">{{ step }}</li>
              </ol>
            </n-alert>
            <h3>同主机相关事件</h3>
            <div v-for="event in related" :key="event.id" class="related">
              <span>{{ event.name }} · {{ status(event) }}</span>
              <CButton show-save save-text="查看" :disabled="acting" @save="openDetail(event)" />
            </div>
            <p v-if="!related.length" class="muted">当前加载范围内没有其他相关事件。</p>
            <h3>抑制状态</h3>
            <p v-if="!selected.recovered && !selected.manual_close" class="muted">
              此触发器未允许手动关闭，请排除故障后等待 Zabbix 自动恢复。
            </p>
            <p>{{ selected.suppressed ? '已抑制（不代表故障恢复）' : '未抑制' }}</p>
            <p v-for="(suppression, index) in selected.suppression" :key="index">
              {{ suppression.maintenanceid !== '0' ? '维护窗口' : '手动抑制' }} ·
              {{
                Number(suppression.suppress_until)
                  ? `至 ${date(suppression.suppress_until)}`
                  : '无固定结束时间'
              }}
            </p>
            <h3>处置记录</h3>
            <article
              v-for="(record, index) in selected.history || []"
              :key="index"
              class="history-card"
            >
              <strong>{{ date(record.clock) }} · {{ actionNames(record.action) }}</strong>
              <p>{{ record.username || `Zabbix 用户 ${record.userid}` }}</p>
              <p class="preserve">{{ record.message || '无备注' }}</p>
            </article>
            <p v-if="!selected.history?.length" class="muted">暂无处置记录</p>
          </template>
        </n-spin>
        <template #footer>
          <n-space v-if="selected">
            <CButton
              v-if="canAct"
              show-save
              save-text="处置事件"
              :disabled="acting || detailLoading || !!detailError"
              @save="openAction(selected)"
            />
            <CButton show-save save-text="在 Zabbix 中查看" :disabled="acting" @save="openZabbix" />
            <CButton
              show-cancel
              cancel-text="关闭"
              :disabled="acting"
              @cancel="detailOpen = false"
            />
          </n-space>
        </template>
      </n-drawer-content>
    </n-drawer>
    <n-modal
      v-model:show="actionOpen"
      preset="card"
      title="事件处置"
      style="width: min(560px, calc(100vw - 24px))"
      :closable="!acting"
      :mask-closable="!acting"
      :close-on-esc="!acting"
    >
      <p>{{ actionTarget?.name }}</p>
      <n-form label-placement="top" :disabled="acting">
        <n-form-item label="操作"
          ><n-select v-model:value="actionForm.action" :options="actionOptions"
        /></n-form-item>
        <n-form-item v-if="actionForm.action === 'suppress'" label="抑制时长（分钟，到期自动解除）">
          <n-input-number v-model:value="actionForm.minutes" :min="1" :max="10080" :precision="0"
        /></n-form-item>
        <n-form-item v-if="actionForm.action === 'severity'" label="严重程度"
          ><n-select v-model:value="actionForm.severity" :options="severityOptions"
        /></n-form-item>
        <n-form-item label="处置说明（必填，写入 Zabbix）"
          ><n-input v-model:value="actionForm.message" type="textarea" :maxlength="1500" show-count
        /></n-form-item>
      </n-form>
      <n-alert v-if="actionForm.action === 'close'" type="warning"
        >手动关闭仅关闭本次问题事件，不会修复设备；请确认问题已处理。实际恢复状态以 Zabbix
        为准。</n-alert
      >
      <n-alert v-if="actionForm.action === 'unsuppress'" type="info"
        >解除手动抑制后，维护窗口造成的抑制仍可能继续生效。</n-alert
      >
      <n-alert v-if="actionError" type="error" class="notice">{{ actionError }}</n-alert>
      <template #footer>
        <n-space justify="end">
          <CButton show-cancel :disabled="acting" @cancel="actionOpen = false" />
          <CButton
            show-save
            save-text="确认提交"
            :save-loading="acting"
            :disabled="acting || !actionForm.message.trim()"
            @save="submitAction"
          />
        </n-space>
      </template>
    </n-modal>
  </AppPage>
</template>

<script setup>
import { computed, h, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { NButton, NSpace, NTag, NTooltip } from 'naive-ui'
import MetricHistory from './MetricHistory.vue'
import { useRouter } from 'vue-router'
import CButton from '@/components/public/CButton.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import api from '@/api/monitor-events'
import { usePermissionStore, useUserStore } from '@/store'

const permissions = usePermissionStore(),
  user = useUserStore()
const props = defineProps({ historyPage: Boolean })
const router = useRouter()
const canAct = computed(
  () =>
    user.isSuperUser || permissions.apis.includes('post/api/v1/monitor-events/{eventid}/actions')
)
const canConfigure = computed(
  () => user.isSuperUser || permissions.apis.includes('put/api/v1/monitor-events/settings')
)
const canViewMetrics = computed(
  () =>
    user.isSuperUser ||
    permissions.apis.includes('get/api/v1/monitor-events/{eventid}/metrics/{itemid}/history')
)
const metricOpen = ref(false),
  metricTarget = ref(null)
function openMetricHistory(row) {
  metricTarget.value = row
  metricOpen.value = true
}
const snapshot = ref({ rows: [], categories: [] }),
  loading = ref(false),
  error = ref(''),
  updatedAt = ref(0)
const keyword = ref(''),
  category = ref(null),
  severity = ref(null),
  state = ref(props.historyPage ? 'recovered' : 'unacknowledged'),
  page = ref(1)
const autoRefresh = ref(true),
  viewportWidth = ref(window.innerWidth)
const detailOpen = ref(false),
  detailLoading = ref(false),
  detailError = ref(''),
  selected = ref(null)
const actionOpen = ref(false),
  acting = ref(false),
  actionError = ref(''),
  actionTarget = ref(null)
const actionForm = reactive({ action: 'acknowledge', message: '', minutes: 60, severity: 3 })
const severityNames = ['未分类', '信息', '警告', '一般严重', '严重', '灾难']
const severityOptions = severityNames.map((label, value) => ({ label, value }))
const stateOptions = [
  { label: '全部状态', value: 'all' },
  { label: '未确认', value: 'unacknowledged' },
  { label: '已确认', value: 'acknowledged' },
  { label: '已抑制', value: 'suppressed' },
  { label: '未抑制', value: 'unsuppressed' },
  { label: '已恢复', value: 'recovered' },
].filter((option) => props.historyPage || option.value !== 'recovered')
const metrics = [
  { key: 'hosts', label: '监控主机' },
  { key: 'abnormal_hosts', label: '异常主机' },
  { key: 'problems', label: '当前问题' },
  { key: 'critical', label: '严重 / 灾难' },
  { key: 'suppressed', label: '已抑制问题' },
]
const categoryOptions = computed(() =>
  snapshot.value.categories.map((item) => ({ label: item.label, value: item.key }))
)
function date(value) {
  return Number(value)
    ? new Date(Number(value) * 1000).toLocaleString('zh-CN', { hour12: false })
    : '—'
}
function severityType(value) {
  return value >= 4 ? 'error' : value >= 2 ? 'warning' : 'info'
}
function status(row) {
  return row.recovered
    ? '已恢复'
    : row.suppressed
    ? '已抑制'
    : row.acknowledged
    ? '已确认'
    : '待处理'
}
function statusTag(row) {
  const type = row.recovered
    ? 'success'
    : row.suppressed
    ? 'warning'
    : row.acknowledged
    ? 'info'
    : 'error'
  return h(
    NTag,
    { type, size: 'small', bordered: false, round: true },
    { default: () => status(row) }
  )
}
function timeCell(value) {
  if (!Number(value)) return h('span', { class: 'event-secondary' }, '—')
  const timestamp = new Date(Number(value) * 1000)
  return h('div', { class: 'event-time', title: date(value) }, [
    h('span', timestamp.toLocaleTimeString('zh-CN', { hour12: false })),
    h('span', { class: 'event-secondary' }, timestamp.toLocaleDateString('zh-CN')),
  ])
}
function hostCell(row) {
  if (!row.hosts.length) return '不可见'
  return h(
    'div',
    { class: 'event-hosts' },
    row.hosts.map((host) => {
      const [name, ...path] = host.name.split(/\s+PATH\s*/)
      return h('div', { title: host.name }, [
        h('div', { class: 'event-host-name' }, name),
        ...(host.attributes || []).map((field) =>
          h('div', { class: 'event-secondary' }, `${field.label}：${field.value}`)
        ),
        path.length
          ? h('div', { class: 'event-secondary event-path' }, `路径：${path.join(' PATH ')}`)
          : null,
      ])
    })
  )
}
function duration(row) {
  if (row.recovered && !row.recovery_clock) return '恢复时间不可用'
  const seconds = Math.max(
    0,
    Math.floor((row.recovered ? row.recovery_clock : Date.now() / 1000) - row.clock)
  )
  if (seconds < 60) return `${seconds} 秒`
  const minutes = Math.max(
    0,
    Math.floor(((row.recovered ? row.recovery_clock : Date.now() / 1000) - row.clock) / 60)
  )
  return minutes >= 1440
    ? `${Math.floor(minutes / 1440)} 天 ${Math.floor((minutes % 1440) / 60)} 小时`
    : minutes >= 60
    ? `${Math.floor(minutes / 60)} 小时 ${minutes % 60} 分`
    : `${minutes} 分 ${seconds % 60} 秒`
}
function eventTypeKey(row) {
  return JSON.stringify([row.trigger_id, row.hosts.map((host) => host.hostid).sort()])
}
function groupEvents(rows) {
  const latest = new Map()
  const counts = new Map()
  for (const row of rows) {
    const key = eventTypeKey(row)
    counts.set(key, (counts.get(key) || 0) + 1)
    const previous = latest.get(key)
    if (
      !previous ||
      row.clock > previous.clock ||
      (row.clock === previous.clock && BigInt(row.id) > BigInt(previous.id))
    )
      latest.set(key, row)
  }
  return [...latest.entries()].map(([key, row]) => ({ ...row, event_count: counts.get(key) }))
}
const latestRows = computed(() => groupEvents(snapshot.value.rows))
const matchingRows = computed(() =>
  (props.historyPage ? snapshot.value.rows : latestRows.value)
    .filter((row) => {
      const text = [
        row.id,
        row.name,
        ...row.hosts.flatMap((host) => [
          host.name,
          host.technical_name,
          host.location,
          ...host.addresses,
          ...host.groups,
        ]),
        ...row.tags.map((tag) => `${tag.tag}:${tag.value}`),
      ]
        .join(' ')
        .toLowerCase()
      return (
        (!keyword.value || text.includes(keyword.value.toLowerCase())) &&
        (!category.value || row.categories.includes(category.value)) &&
        (severity.value == null || row.severity === severity.value) &&
        (state.value === 'all' ||
          (state.value === 'recovered'
            ? row.recovered
            : !row.recovered &&
              {
                unacknowledged: !row.acknowledged,
                acknowledged: row.acknowledged,
                suppressed: row.suppressed,
                unsuppressed: !row.suppressed,
              }[state.value]))
      )
    })
    .sort((a, b) =>
      props.historyPage ? b.clock - a.clock : b.severity - a.severity || b.clock - a.clock
    )
)
const filtered = computed(() =>
  props.historyPage ? groupEvents(matchingRows.value) : matchingRows.value
)
const pageRows = computed(() => filtered.value.slice((page.value - 1) * 20, page.value * 20))
watch(
  () => filtered.value.length,
  (length) => {
    page.value = Math.max(1, Math.min(page.value, Math.ceil(length / 20)))
  }
)
const related = computed(() =>
  !selected.value
    ? []
    : snapshot.value.rows
        .filter(
          (row) =>
            row.id !== selected.value.id &&
            row.hosts.some((host) => selected.value.hosts.some((h) => h.hostid === host.hostid))
        )
        .slice(0, 20)
)
function actionButton(label, icon, callback) {
  return h(NTooltip, null, {
    trigger: () =>
      h(
        NButton,
        {
          size: 'small',
          circle: true,
          quaternary: true,
          disabled: acting.value,
          'aria-label': label,
          onClick: (event) => {
            event.stopPropagation()
            callback()
          },
        },
        { icon: () => h(TheIcon, { icon, size: 17 }) }
      ),
    default: () => label,
  })
}
const columns = [
  {
    title: '级别',
    key: 'severity',
    width: 90,
    align: 'center',
    render: (row) =>
      h(
        NTag,
        { type: severityType(row.severity), size: 'small', bordered: false },
        { default: () => severityNames[row.severity] }
      ),
  },
  {
    title: '告警 / 事件',
    key: 'name',
    width: 280,
    ellipsis: false,
    render: (row) =>
      h('div', null, [
        h('div', { class: 'event-name', title: row.name }, row.name),
        props.historyPage && row.event_count
          ? h(
              'span',
              { class: 'event-secondary' },
              `${row.event_count} 次 · 当前筛选范围 · 双击查看同类历史`
            )
          : null,
      ]),
  },
  {
    title: '目标主机',
    key: 'hosts',
    width: 300,
    ellipsis: false,
    render: hostCell,
  },
  {
    title: 'IP / 地址',
    key: 'address',
    width: 150,
    render: (row) =>
      h(
        'span',
        { class: 'event-address' },
        row.hosts.flatMap((h) => h.addresses).join(' / ') || '—'
      ),
  },
  { title: '状态', key: 'state', width: 100, align: 'center', render: statusTag },
  {
    title: '发生时间',
    key: 'clock',
    width: 120,
    ellipsis: false,
    render: (row) => timeCell(row.clock),
  },
  {
    title: '恢复时间',
    key: 'recovery_clock',
    width: 120,
    ellipsis: false,
    render: (row) => timeCell(row.recovery_clock),
  },
  {
    title: '持续时间',
    key: 'duration',
    width: 150,
    render: (row) => h('span', { class: 'event-duration' }, duration(row)),
  },
  {
    title: '排查方向',
    key: 'advice',
    width: 110,
    render: (row) => h('span', { class: 'event-secondary' }, row.advice.type),
  },
].map((col) => ({ resizable: true, ellipsis: { tooltip: true }, ...col }))
columns.push({
  title: '操作',
  key: 'actions',
  width: 130,
  align: 'center',
  fixed: 'right',
  render: (row) =>
    h(
      NSpace,
      { wrap: false, size: 4, justify: 'center' },
      {
        default: () => [
          actionButton('定位 / 查看建议', 'mdi:target', () => openDetail(row)),
          canViewMetrics.value
            ? actionButton('指标历史', 'mdi:chart-line', () => openMetricHistory(row))
            : null,
          canAct.value
            ? actionButton('处置事件', 'mdi:clipboard-check-outline', () => openAction(row))
            : null,
        ],
      }
    ),
})
const historyColumns = columns
const typeHistoryOpen = ref(false),
  typeHistoryLoading = ref(false),
  typeHistoryError = ref(''),
  typeHistoryTruncated = ref(false),
  typeHistoryTarget = ref(null),
  typeHistoryRows = ref([])
let typeHistoryRequest = 0
function historyRowProps(row) {
  return {
    style: 'cursor: pointer',
    onDblclick: (event) => {
      if (!event.target.closest('button')) openTypeHistory(row)
    },
  }
}
async function openTypeHistory(row) {
  const request = ++typeHistoryRequest
  typeHistoryTarget.value = row
  typeHistoryOpen.value = true
  typeHistoryLoading.value = true
  typeHistoryError.value = ''
  typeHistoryRows.value = []
  typeHistoryTruncated.value = false
  try {
    const result = await api.list({ history: true })
    if (request !== typeHistoryRequest) return
    typeHistoryRows.value = result.data.rows
      .filter((event) => eventTypeKey(event) === eventTypeKey(row))
      .sort((a, b) => b.clock - a.clock || (BigInt(a.id) > BigInt(b.id) ? -1 : 1))
    typeHistoryTruncated.value = result.data.truncated
  } catch (e) {
    if (request === typeHistoryRequest)
      typeHistoryError.value = e.message || '历史记录加载失败，请重新打开重试'
  } finally {
    if (request === typeHistoryRequest) typeHistoryLoading.value = false
  }
}
const itemColumns = [
  { title: '指标', key: 'name', width: 280 },
  {
    title: '最新值',
    key: 'lastvalue',
    width: 140,
    render: (row) => `${row.lastvalue ?? '—'} ${row.units || ''}`,
  },
  { title: '采样时间', key: 'lastclock', width: 220, render: (row) => date(row.lastclock) },
].map((col) => ({ ...col, resizable: true, ellipsis: { tooltip: true } }))
const actionOptions = computed(() => [
  { label: '确认告警', value: 'acknowledge' },
  { label: '取消确认', value: 'unacknowledge' },
  { label: '添加备注', value: 'comment' },
  ...(!actionTarget.value?.recovered
    ? [
        { label: '限时抑制', value: 'suppress' },
        { label: '解除手动抑制', value: 'unsuppress' },
        { label: '调整严重程度', value: 'severity' },
        ...(actionTarget.value?.manual_close ? [{ label: '手动关闭问题', value: 'close' }] : []),
      ]
    : []),
])
function actionNames(value) {
  return (
    [
      [1, '关闭问题'],
      [2, '确认'],
      [4, '备注'],
      [8, '调整级别'],
      [16, '取消确认'],
      [32, '抑制'],
      [64, '解除抑制'],
      [128, '标为原因'],
      [256, '标为症状'],
    ]
      .filter(([bit]) => Number(value) & bit)
      .map(([, name]) => name)
      .join(' / ') || '更新'
  )
}
function chooseCategory(key) {
  category.value = category.value === key ? null : key
  page.value = 1
}
function changeState() {
  page.value = 1
}
async function refresh() {
  if (loading.value || acting.value) return
  loading.value = true
  error.value = ''
  try {
    const result = await api.list({ history: props.historyPage })
    snapshot.value = result.data
    updatedAt.value = result.data.updated_at
  } catch (e) {
    error.value = e.message || '事件加载失败'
  } finally {
    loading.value = false
  }
}
let detailRequest = 0
async function openDetail(row) {
  const id = ++detailRequest
  detailOpen.value = true
  detailLoading.value = true
  detailError.value = ''
  selected.value = null
  try {
    const result = await api.detail(row.id)
    if (id === detailRequest) selected.value = result.data
  } catch (e) {
    if (id === detailRequest) detailError.value = e.message || '详情加载失败'
  } finally {
    if (id === detailRequest) detailLoading.value = false
  }
}
function openAction(row) {
  actionTarget.value = row
  actionForm.action = 'acknowledge'
  actionForm.message = ''
  actionError.value = ''
  actionOpen.value = true
}
async function submitAction() {
  if (acting.value || !actionForm.message.trim()) return
  const target = actionTarget.value
  acting.value = true
  actionError.value = ''
  try {
    await api.action(target.id, { ...actionForm })
    actionOpen.value = false
    window.$message?.success('操作已提交，请以刷新后的 Zabbix 状态为准')
  } catch (e) {
    actionError.value = e.message || '提交失败，请刷新核实后重试'
    return
  } finally {
    acting.value = false
  }
  await refresh()
  if (detailOpen.value) await openDetail(target)
}
async function copyHost(host) {
  try {
    await navigator.clipboard.writeText(
      `${host.name}\n${host.technical_name}\n${host.addresses.join(' / ')}\n${
        host.location
      }\n${host.groups.join(' / ')}`
    )
    window.$message?.success('定位信息已复制')
  } catch {
    window.$message?.error('无法访问剪贴板，请选择文本复制')
  }
}
function openZabbix() {
  if (selected.value?.url) window.open(selected.value.url, '_blank', 'noopener,noreferrer')
}
function resize() {
  viewportWidth.value = window.innerWidth
}
let timer
onMounted(() => {
  refresh()
  timer = setInterval(() => {
    if (autoRefresh.value && !document.hidden && !actionOpen.value) refresh()
  }, 30000)
  window.addEventListener('resize', resize)
})
onUnmounted(() => {
  clearInterval(timer)
  window.removeEventListener('resize', resize)
  detailRequest++
})
</script>

<style scoped>
.events-page.app-page-shell {
  min-height: 0;
  overflow: auto;
}
.events-panel {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 650px;
  min-width: 0;
  background: #fff;
  border: 1px solid #e6ebf1;
  border-radius: 12px;
  padding: 20px;
  gap: 14px;
}
.page-header,
.section-title,
.list-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  flex-shrink: 0;
}
h2,
h3,
p {
  margin: 0;
}
h2 {
  font-size: 22px;
}
h3 {
  font-size: 15px;
}
.brand {
  font-size: 12px;
  font-weight: 400;
  color: #8491a4;
  margin-left: 10px;
}
.page-header p,
.updated,
.section-title > span,
.list-footer,
.muted {
  font-size: 12px;
  color: #7d899a;
}
.page-header p {
  margin-top: 5px;
}
.metrics {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
  flex-shrink: 0;
}
.metric {
  display: flex;
  flex-direction: column;
  padding: 14px 18px;
  border-radius: 9px;
  background: #f6f8fb;
  gap: 6px;
}
.metric span {
  font-size: 12px;
  color: #758297;
}
.metric strong {
  font-size: 27px;
}
.metric.critical strong {
  color: #e25959;
}
.metric.abnormal_hosts strong {
  color: #d98b24;
}
.health-section {
  border-bottom: 1px solid #edf0f5;
  padding-bottom: 14px;
}
.health-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px 24px;
  margin-top: 10px;
}
.health-row {
  display: grid;
  grid-template-columns: 110px 1fr 105px;
  align-items: center;
  gap: 10px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 7px;
  padding: 8px;
  cursor: pointer;
  color: inherit;
  text-align: left;
  font: inherit;
  font-size: 12px;
}
.health-row:hover,
.health-row.selected {
  background: #edf7f3;
  border-color: #b8dccd;
}
.health-row small {
  text-align: right;
  color: #7d899a;
}
.filters {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  flex-shrink: 0;
}
.filters > .n-input {
  flex: 1;
  min-width: 240px;
}
.filters > .n-select {
  width: 155px;
}
.event-table {
  flex: 1;
  min-height: 180px;
}
:deep(.event-name) {
  font-weight: 600;
  line-height: 1.6;
  white-space: normal;
  overflow-wrap: anywhere;
}
:deep(.event-host-name) {
  white-space: normal;
  overflow-wrap: anywhere;
  line-height: 1.5;
}
:deep(.event-secondary) {
  color: var(--n-th-text-color, #7d899a);
  opacity: 0.75;
  font-size: 12px;
}
:deep(.event-path) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-top: 3px;
}
:deep(.event-time),
:deep(.event-hosts) {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
:deep(.event-time),
:deep(.event-address),
:deep(.event-duration) {
  font-variant-numeric: tabular-nums;
}
:deep(.event-address) {
  font-family: ui-monospace, Consolas, monospace;
  font-size: 12px;
}
:deep(.event-duration) {
  font-weight: 600;
}
.event-table :deep(.n-data-table-td),
.event-history-table :deep(.n-data-table-td) {
  padding-top: 12px;
  padding-bottom: 12px;
}
.list-footer {
  padding-top: 4px;
}
.notice {
  margin: 12px 0;
}
.detail-heading {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.detail-heading h3 {
  font-size: 18px;
}
.host-card,
.history-card {
  padding: 14px;
  border: 1px solid #e7edf4;
  border-radius: 8px;
  margin: 10px 0;
}
.host-card p,
.history-card p {
  margin: 6px 0;
}
.expression {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  background: #f6f8fb;
  padding: 12px;
  border-radius: 6px;
}
.preserve {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.related {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 0;
}
li {
  margin: 6px 0;
}
:global(html.dark) .events-panel {
  background: #181c24;
  border-color: #303744;
}
:global(html.dark) .metric,
:global(html.dark) .expression {
  background: #222936;
}
:global(html.dark) .health-row.selected,
:global(html.dark) .health-row:hover {
  background: #213c32;
}
@media (max-width: 900px) {
  .health-grid {
    grid-template-columns: 1fr;
  }
  .metrics {
    grid-template-columns: repeat(3, 1fr);
  }
  .events-panel {
    padding: 12px;
    min-height: 800px;
  }
  .filters > .n-select {
    width: calc(50% - 5px);
  }
  .updated {
    display: none;
  }
}
</style>
