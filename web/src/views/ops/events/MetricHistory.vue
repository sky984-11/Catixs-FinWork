<template>
  <n-modal
    :show="show"
    preset="card"
    title="指标历史"
    style="width: min(1100px, calc(100vw - 24px))"
    @update:show="emit('update:show', $event)"
  >
    <p>{{ event?.hosts.map((host) => host.name).join(' / ') }} · {{ event?.name }}</p>
    <n-space class="controls" align="center">
      <n-select
        v-model:value="itemId"
        :options="itemOptions"
        :disabled="loadingItems"
        placeholder="选择告警关联指标"
        style="width: 340px; max-width: 80vw"
        @update:value="loadHistory"
      />
      <n-select
        v-model:value="period"
        :options="periodOptions"
        :disabled="loadingItems"
        style="width: 190px"
        @update:value="loadHistory"
      />
      <CButton
        show-save
        save-text="刷新"
        :save-loading="loading"
        :disabled="loadingItems || loading"
        @save="refresh"
      />
    </n-space>
    <n-alert v-if="error" type="error" class="notice">{{ error }}</n-alert>
    <n-alert v-if="data?.truncated" type="warning" class="notice"
      >仅显示该范围最新 10,000 个采样点，请缩短时间范围查看完整曲线。</n-alert
    >
    <n-spin :show="loading || loadingItems">
      <n-empty
        v-if="!loadingItems && !itemOptions.length && !error"
        description="此告警没有可绘图的数值指标"
        class="empty"
      />
      <n-empty
        v-else-if="!points.length"
        :description="
          error
            ? '历史数据加载失败，可点击刷新重试'
            : '该时间范围暂无历史采样，可能尚未采集或已超过保留期'
        "
        class="empty"
      />
      <div v-else>
        <div class="legend">
          <strong>{{ data.item.name }} {{ data.item.units ? `（${data.item.units}）` : '' }}</strong
          ><span>{{ points.length }} 个原始采样点</span>
        </div>
        <div class="chart-scroll">
          <svg
            viewBox="0 0 960 330"
            role="img"
            :aria-label="`${data.item.name}历史曲线`"
            @mousemove="hoverPoint"
            @mouseleave="hover = null"
          >
            <g v-for="tick in ticks" :key="tick.value">
              <line
                x1="85"
                x2="930"
                :y1="tick.y"
                :y2="tick.y"
                stroke="currentColor"
                opacity="0.12"
              />
              <text x="76" :y="tick.y + 4" text-anchor="end">{{ number(tick.value) }}</text>
            </g>
            <path :d="curve" fill="none" stroke="#2080f0" stroke-width="2" />
            <circle
              v-if="points.length === 1"
              :cx="x(points[0].clock)"
              :cy="y(points[0].value)"
              r="4"
              fill="#2080f0"
            />
            <g v-for="marker in markers" :key="marker.label">
              <line
                :x1="x(marker.clock)"
                :x2="x(marker.clock)"
                y1="30"
                y2="270"
                :stroke="marker.color"
                stroke-dasharray="5 4"
              />
              <text
                :x="x(marker.clock)"
                :y="marker.label === '发生' ? 15 : 28"
                text-anchor="middle"
                :style="{ fill: marker.color }"
              >
                {{ marker.label }}
              </text>
            </g>
            <text x="85" y="305">{{ time(data.time_from) }}</text>
            <text x="930" y="305" text-anchor="end">{{ time(data.time_till) }}</text>
            <g v-if="hover">
              <line
                :x1="x(hover.clock)"
                :x2="x(hover.clock)"
                y1="30"
                y2="270"
                stroke="currentColor"
                opacity="0.4"
              />
              <circle :cx="x(hover.clock)" :cy="y(hover.value)" r="4" fill="#2080f0" />
            </g>
          </svg>
        </div>
        <p class="reading">
          {{ time((hover || points[points.length - 1]).clock) }} ·
          {{ number((hover || points[points.length - 1]).value) }} {{ data.item.units }}
        </p>
        <p class="hint">
          移动鼠标查看采样值。红线为告警发生，绿线为恢复；数据直接读取 Zabbix
          历史，使用原始单位。明显采样间断处断开曲线。
        </p>
      </div>
    </n-spin>
  </n-modal>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import CButton from '@/components/public/CButton.vue'
import api from '@/api/monitor-events'

const props = defineProps({ show: Boolean, event: { type: Object, default: null } })
const emit = defineEmits(['update:show'])
const items = ref([]),
  itemId = ref(null),
  period = ref('event'),
  data = ref(null),
  error = ref('')
const loadingItems = ref(false),
  loading = ref(false),
  hover = ref(null)
let generation = 0,
  request = 0
const periodOptions = [
  { label: '告警发生前后 1 小时', value: 'event' },
  { label: '最近 1 小时', value: 'hour' },
  { label: '最近 24 小时', value: 'day' },
  { label: '最近 7 天', value: 'week' },
]
const itemOptions = computed(() =>
  items.value.map((item) => ({
    label: `${item.name}${item.units ? ` (${item.units})` : ''}`,
    value: item.itemid,
  }))
)
const points = computed(() => data.value?.points || [])
const bounds = computed(() => {
  if (!points.value.length) return [0, 1]
  const values = points.value.map((point) => point.value)
  const low = Math.min(...values),
    high = Math.max(...values)
  const padding = (high - low || Math.abs(low) || 1) * 0.1
  return [low - padding, high + padding]
})
const x = (clock) =>
  85 + ((clock - data.value.time_from) / (data.value.time_till - data.value.time_from)) * 845
const y = (value) => 270 - ((value - bounds.value[0]) / (bounds.value[1] - bounds.value[0])) * 240
const ticks = computed(() =>
  Array.from({ length: 5 }, (_, index) => {
    const value = bounds.value[0] + ((bounds.value[1] - bounds.value[0]) * index) / 4
    return { value, y: y(value) }
  })
)
const curve = computed(() => {
  const gaps = points.value
    .slice(1)
    .map((point, index) => point.clock - points.value[index].clock)
    .filter((gap) => gap > 0)
    .sort((a, b) => a - b)
  const gapLimit = (gaps[Math.floor(gaps.length / 2)] || Infinity) * 3
  return points.value
    .map(
      (point, index) =>
        `${index === 0 || point.clock - points.value[index - 1].clock > gapLimit ? 'M' : 'L'}${x(
          point.clock
        )},${y(point.value)}`
    )
    .join(' ')
})
const markers = computed(() =>
  data.value
    ? [
        { label: '发生', clock: data.value.event_clock, color: '#d03050' },
        { label: '恢复', clock: data.value.recovery_clock, color: '#18a058' },
      ].filter(
        (marker) =>
          marker.clock &&
          marker.clock >= data.value.time_from &&
          marker.clock <= data.value.time_till
      )
    : []
)
const number = (value) => Number(value).toLocaleString('zh-CN', { maximumSignificantDigits: 7 })
const time = (value) => new Date(value * 1000).toLocaleString('zh-CN', { hour12: false })
function hoverPoint(event) {
  const box = event.currentTarget.getBoundingClientRect()
  const coordinate = ((event.clientX - box.left) / box.width) * 960
  const clock =
    data.value.time_from + ((coordinate - 85) / 845) * (data.value.time_till - data.value.time_from)
  hover.value = points.value.reduce(
    (best, point) =>
      !best || Math.abs(point.clock - clock) < Math.abs(best.clock - clock) ? point : best,
    null
  )
}
async function loadHistory() {
  const id = ++request
  data.value = null
  hover.value = null
  error.value = ''
  if (!itemId.value || !props.show) {
    loading.value = false
    return
  }
  loading.value = true
  const now = Math.floor(Date.now() / 1000)
  const end = period.value === 'event' ? Math.min(now, props.event.clock + 3600) : now
  const start =
    period.value === 'event'
      ? Math.max(0, props.event.clock - 3600)
      : end - { hour: 3600, day: 86400, week: 604800 }[period.value]
  try {
    const result = await api.metricHistory(props.event.id, itemId.value, {
      time_from: start,
      time_till: end,
    })
    if (id === request) data.value = result.data
  } catch (e) {
    if (id === request) error.value = e.message || '指标历史加载失败'
  } finally {
    if (id === request) loading.value = false
  }
}
async function initialize() {
  const id = ++generation
  ++request
  items.value = []
  itemId.value = null
  data.value = null
  error.value = ''
  loading.value = false
  loadingItems.value = true
  try {
    const result = await api.detail(props.event.id)
    if (id !== generation) return
    items.value = result.data.items.filter((item) => ['0', '3'].includes(String(item.value_type)))
    itemId.value = items.value[0]?.itemid || null
    await loadHistory()
  } catch (e) {
    if (id === generation) error.value = e.message || '关联指标加载失败'
  } finally {
    if (id === generation) loadingItems.value = false
  }
}
function refresh() {
  if (!items.value.length) initialize()
  else loadHistory()
}
watch(
  () => [props.show, props.event?.id],
  () => {
    if (props.show && props.event) {
      period.value = 'event'
      initialize()
    } else {
      ++generation
      ++request
    }
  }
)
</script>

<style scoped>
.controls,
.notice {
  margin: 12px 0;
}
.empty {
  padding: 90px 0;
}
.legend {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin: 20px 0;
}
.chart-scroll {
  overflow-x: auto;
}
svg {
  width: 100%;
  min-width: 620px;
  display: block;
  color: inherit;
}
svg text {
  font-size: 12px;
  fill: currentColor;
}
.reading {
  font-variant-numeric: tabular-nums;
  font-weight: 600;
}
.hint {
  opacity: 0.7;
  font-size: 12px;
}
</style>
