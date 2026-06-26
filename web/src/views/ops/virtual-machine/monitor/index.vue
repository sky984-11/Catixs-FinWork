<template>
  <AppPage :show-footer="false">
    <div class="monitor-page">
      <div class="monitor-header">
        <div>
          <span class="monitor-eyebrow">GRAFANA</span>
          <h2>{{ monitorTitle }}</h2>
        </div>
        <n-date-picker
          v-model:value="timeRange"
          type="datetimerange"
          :shortcuts="monitorRangeShortcuts"
          :time-picker-props="monitorTimePickerProps"
          :update-value-on-close="true"
          format="yyyy-MM-dd HH:00"
          clearable
          class="monitor-date-range"
          start-placeholder="开始时间"
          end-placeholder="结束时间"
        />
      </div>

      <div class="monitor-frame-wrap">
        <iframe class="monitor-frame" :src="monitorUrl" title="Grafana Monitor" />
      </div>
    </div>
  </AppPage>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { getToken } from '@/utils/auth'

const route = useRoute()

const grafanaDashboardUrls = {
  vm: '/api/v1/pve/grafana/proxy/d/zbx-pve-vm-metrics/zabbix-pve-vm-metrics',
  node: '/api/v1/pve/grafana/proxy/d/zbx-pve-node-metrics/zabbix-pve-node-metrics',
}

const timeRange = ref(recentRange(6 * 60 * 60 * 1000))

const monitorRangeShortcuts = {
  '最近 1 小时': () => recentRange(60 * 60 * 1000),
  '最近 3 小时': () => recentRange(3 * 60 * 60 * 1000),
  '最近 6 小时': () => recentRange(6 * 60 * 60 * 1000),
  '最近 12 小时': () => recentRange(12 * 60 * 60 * 1000),
  '最近 24 小时': () => recentRange(24 * 60 * 60 * 1000),
  '最近 2 天': () => recentRange(2 * 24 * 60 * 60 * 1000),
  '最近 7 天': () => recentRange(7 * 24 * 60 * 60 * 1000),
  '最近 15 天': () => recentRange(15 * 24 * 60 * 60 * 1000),
  '最近 30 天': () => recentRange(30 * 24 * 60 * 60 * 1000),
  '最近 90 天': () => recentRange(90 * 24 * 60 * 60 * 1000),
}

const monitorTimePickerProps = {
  format: 'HH:00',
}

const monitorType = computed(() => (route.query.type === 'node' ? 'node' : 'vm'))
const monitorRemote = computed(() => String(route.query.remote || ''))
const monitorName = computed(() => String(route.query.name || ''))

const monitorTitle = computed(() => {
  if (monitorType.value === 'node') return `节点监控 · ${monitorName.value || monitorRemote.value || '节点'}`
  return `虚拟机监控 · ${monitorName.value || '虚拟机'}`
})

const monitorUrl = computed(() => {
  const url = new URL(grafanaDashboardUrls[monitorType.value] || grafanaDashboardUrls.vm, window.location.origin)
  const [from, to] = resolveMonitorTimeRange()
  url.searchParams.set('orgId', '1')
  url.searchParams.set('from', from)
  url.searchParams.set('to', to)
  url.searchParams.set('timezone', 'browser')
  url.searchParams.set('var-DS_ZABBIX', 'bflbfxqfe1vk0d')
  url.searchParams.set('var-group', 'PVE')
  url.searchParams.set('var-host', monitorRemote.value)
  url.searchParams.set('var-item_tag', monitorType.value === 'node' ? '$__all' : `name: ${monitorName.value}`)
  url.searchParams.set('refresh', '1m')
  url.searchParams.set('kiosk', '')
  url.searchParams.set('catixs_embed', '1')
  const token = getToken()
  if (token) {
    url.searchParams.set('token', token)
  }
  return url.toString()
})

function resolveMonitorTimeRange() {
  if (Array.isArray(timeRange.value)) {
    const [from, to] = timeRange.value
    if (from && to) return [String(toHourStart(from)), String(toHourStart(to))]
  }
  const [from, to] = recentRange(6 * 60 * 60 * 1000)
  return [String(from), String(to)]
}

function recentRange(duration) {
  const now = toHourStart(Date.now())
  return [now - duration, now]
}

function toHourStart(value) {
  const date = new Date(value)
  date.setMinutes(0, 0, 0)
  return date.getTime()
}
</script>

<style scoped>
.monitor-page {
  min-height: calc(100vh - 118px);
  padding: 12px;
  background: #f5f7fb;
}

.monitor-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}

.monitor-eyebrow {
  display: block;
  margin-bottom: 6px;
  color: #63738a;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0;
}

.monitor-header h2 {
  margin: 0;
  color: #0f172a;
  font-size: 22px;
  font-weight: 800;
}

.monitor-date-range {
  width: 420px;
  max-width: 100%;
}

.monitor-frame-wrap {
  width: 100%;
  height: calc(100vh - 190px);
  min-height: 680px;
  overflow: hidden;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #0b0f19;
}

.monitor-frame {
  width: 128.21%;
  height: 128.21%;
  border: 0;
  background: #0b0f19;
  transform: scale(0.78);
  transform-origin: left top;
}
</style>
