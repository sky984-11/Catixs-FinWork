<template>
  <section class="cluster-card" :style="themeStyle" aria-label="节点负载">
    <header>
      <h2><TheIcon icon="mdi:gauge" :size="18" />节点负载</h2>
      <span class="scope">{{ node?.label || node?.remote || '尚未选择节点' }}</span>
    </header>
    <div class="gauges">
      <div v-for="metric in metrics" :key="metric.label" class="metric">
        <div
          class="dial"
          :style="{ '--load-color': loadColor(metric.percent) }"
          role="img"
          :aria-label="`${metric.label} ${label(metric.percent)}`"
        >
          <svg viewBox="0 0 120 120" aria-hidden="true">
            <circle class="track" cx="60" cy="60" r="49" />
            <circle
              class="fill"
              cx="60"
              cy="60"
              r="49"
              pathLength="100"
              :stroke-dasharray="`${metric.percent || 0} 100`"
            />
          </svg>
          <strong>{{ label(metric.percent) }}</strong>
        </div>
        <span class="metric-label"
          ><TheIcon :icon="metric.icon" :size="16" />{{ metric.label }}</span
        >
        <small>{{ metric.detail }}</small>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useThemeVars } from 'naive-ui'
import TheIcon from '@/components/icon/TheIcon.vue'
import { aggregateCluster, bytes } from '../utils/display.mjs'

const props = defineProps({
  node: { type: Object, default: null },
})
const theme = useThemeVars()
const themeStyle = computed(() => ({
  '--surface': theme.value.cardColor,
  '--border': theme.value.borderColor,
  '--text': theme.value.textColor1,
  '--muted': theme.value.textColor3,
  '--primary': theme.value.primaryColor,
  '--track': theme.value.progressRailColor,
}))
const totals = computed(() => aggregateCluster(props.node ? [props.node] : []))
const label = (value) => (value === null ? '—' : `${Number(value.toFixed(1))}%`)
const loadColor = (value) =>
  value >= 90
    ? theme.value.errorColor
    : value >= 75
    ? theme.value.warningColor
    : theme.value.primaryColor
const metrics = computed(() => [
  {
    ...totals.value.cpu,
    label: 'CPU',
    icon: 'mdi:cpu-64-bit',
    detail:
      totals.value.cpu.percent === null
        ? '暂无数据'
        : `${Number(totals.value.cpu.used.toFixed(1))} / ${totals.value.cpu.total} 核`,
  },
  {
    ...totals.value.memory,
    label: '内存',
    icon: 'mdi:memory',
    detail:
      totals.value.memory.percent === null
        ? '暂无数据'
        : `${bytes(totals.value.memory.used)} / ${bytes(totals.value.memory.total)}`,
  },
  {
    ...totals.value.storage,
    label: '存储',
    icon: 'mdi:harddisk',
    detail:
      totals.value.storage.percent === null
        ? '暂无数据'
        : `${bytes(totals.value.storage.used)} / ${bytes(totals.value.storage.total)}`,
  },
])
</script>

<style scoped>
.cluster-card {
  flex-shrink: 0;
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 12px 20px;
  background: var(--surface);
  color: var(--text);
}
header,
h2,
.metric-label {
  display: flex;
  align-items: center;
}
header {
  justify-content: space-between;
}
h2 {
  font-size: 15px;
  font-weight: 600;
  margin: 0;
  gap: 8px;
}
.scope {
  max-width: 65%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.scope,
small {
  color: var(--muted);
  font-size: 12px;
}
.gauges {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  padding: 8px 0 0;
}
.metric {
  display: grid;
  justify-items: center;
  align-content: start;
  gap: 5px;
  text-align: center;
}
.dial {
  position: relative;
  width: 88px;
  height: 88px;
}
.dial svg {
  width: 100%;
  height: 100%;
  transform: rotate(-90deg);
}
.dial circle {
  fill: none;
  stroke-width: 9;
}
.track {
  stroke: var(--track, #e5e7eb);
}
.fill {
  stroke: var(--load-color);
  stroke-linecap: round;
  transition: stroke-dasharray 0.4s;
}
.dial strong {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  color: var(--load-color);
  font-size: 24px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.metric-label {
  gap: 6px;
  font-size: 13px;
  font-weight: 500;
}
.metric-label :deep(svg) {
  color: var(--muted);
}
@media (max-width: 600px) {
  .cluster-card {
    padding: 14px 12px 10px;
  }
  .dial {
    width: 80px;
    height: 80px;
  }
  .dial strong {
    font-size: 19px;
  }
  .gauges {
    gap: 6px;
  }
  small {
    font-size: 10px;
  }
}
</style>
