<template>
  <CommonPage show-footer title="空闲设备">
    <template #action>
      <n-button :loading="loading" secondary @click="loadData">刷新</n-button>
    </template>

    <div class="free-device-page">
      <section class="toolbar">
        <n-input
          v-model:value="query.keyword"
          clearable
          placeholder="搜索资产编号、型号、IP、配置"
          @keyup.enter="loadData"
        />
        <n-button type="primary" @click="loadData">查询</n-button>
      </section>

      <section class="summary-band">
        <div class="summary-main">
          <span>可售设备</span>
          <strong>{{ summary.total || 0 }}</strong>
        </div>
        <div class="summary-main">
          <span>覆盖地区</span>
          <strong>{{ summary.regions || 0 }}</strong>
        </div>
        <div class="summary-main summary-main--right">
          <span>型号数量</span>
          <strong>{{ summary.models?.length || 0 }}</strong>
        </div>
      </section>

      <n-spin :show="loading">
        <div v-if="regionGroups.length" class="device-board">
          <div v-for="(lane, laneIndex) in boardLanes" :key="laneIndex" class="board-lane">
            <section
              v-for="group in lane"
              :key="group.key"
              class="board-column"
              :class="[`tone-${group.tone}`, { collapsed: isRegionCollapsed(group.key) }]"
            >
              <header class="column-header">
                <div class="column-title">
                  <span class="column-dot"></span>
                  <div>
                    <strong>{{ group.region }}</strong>
                    <span>{{ group.subtitle }}</span>
                  </div>
                </div>
                <div class="column-actions">
                  <n-tag size="small" round :bordered="false">{{ group.count }} 台</n-tag>
                  <n-button size="tiny" quaternary circle @click="toggleRegion(group.key)">
                    <template #icon>
                      <TheIcon :icon="isRegionCollapsed(group.key) ? 'mdi:chevron-right' : 'mdi:chevron-down'" :size="18" />
                    </template>
                  </n-button>
                </div>
              </header>

              <div v-show="!isRegionCollapsed(group.key)" class="column-body">
                <div v-if="group.models.length" class="model-strip">
                  <span v-for="model in group.models.slice(0, 6)" :key="model.name">
                    {{ model.name }} x {{ model.count }}
                  </span>
                </div>

                <article v-for="device in group.devices" :key="device.id" class="device-card">
                  <div class="device-card__head">
                    <div>
                      <span>{{ device.asset_no || device.serial_no || '未录入资产号' }}</span>
                      <strong>{{ device.name || device.model || '-' }}</strong>
                    </div>
                    <n-tag size="small" :bordered="false">{{ device.is_four_node ? '四合一节点' : (device.brand || '设备') }}</n-tag>
                  </div>

                  <div v-if="device.is_four_node" class="device-spec">
                    <span>母机</span>
                    <strong>{{ device.parent_name || '-' }} / {{ device.node_name || '-' }}</strong>
                  </div>

                  <div class="device-spec">
                    <span>型号</span>
                    <strong>{{ [device.brand, device.model].filter(Boolean).join(' ') || '-' }}</strong>
                  </div>

                  <div class="device-spec">
                    <span>配置</span>
                    <strong>{{ formatDeviceConfig(device) }}</strong>
                  </div>

                  <footer>
                    <span>{{ device.location || '-' }}</span>
                    <strong>{{ device.cabinet || '-' }} / {{ device.u_position ? `U${device.u_position}` : '-' }}</strong>
                  </footer>
                </article>
              </div>
            </section>
          </div>
        </div>
        <n-empty v-else description="暂无空闲设备" />
      </n-spin>
    </div>
  </CommonPage>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { NButton, NEmpty, NInput, NSpin, NTag } from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import api from '@/api'

defineOptions({ name: 'ResourceFreeDevices' })

const laneCount = 4
const tones = ['blue', 'green', 'amber', 'rose', 'violet', 'cyan']
const loading = ref(false)
const regions = ref([])
const summary = ref({})
const query = reactive({ keyword: '' })
const collapsedRegions = ref(new Set())

const regionGroups = computed(() => regions.value
  .map((region, index) => {
    const key = String(region.region_id || region.region || index)
    const subtitle = [region.country, region.city].filter(Boolean).join(' / ') || '未设置地区信息'
    return {
      ...region,
      key,
      subtitle,
      tone: tones[index % tones.length],
      count: Number(region.count || region.devices?.length || 0),
      devices: [...(region.devices || [])],
      models: [...(region.models || [])],
    }
  })
  .sort((a, b) => {
    if (b.count !== a.count) return b.count - a.count
    return String(a.region || '').localeCompare(String(b.region || ''), 'zh-Hans-CN')
  }))

const boardLanes = computed(() => {
  const lanes = Array.from({ length: laneCount }, () => [])
  const laneHeights = Array.from({ length: laneCount }, () => 0)

  for (const group of regionGroups.value) {
    const targetIndex = laneHeights.indexOf(Math.min(...laneHeights))
    lanes[targetIndex].push(group)
    laneHeights[targetIndex] += getGroupWeight(group)
  }

  return lanes
})

function getGroupWeight(group) {
  return isRegionCollapsed(group.key) ? 1 : group.count + 1
}

function isRegionCollapsed(key) {
  return collapsedRegions.value.has(key)
}

function toggleRegion(key) {
  const next = new Set(collapsedRegions.value)
  if (next.has(key)) {
    next.delete(key)
  } else {
    next.add(key)
  }
  collapsedRegions.value = next
}

function pickAttribute(attributes, keys) {
  const source = attributes && typeof attributes === 'object' ? attributes : {}
  for (const key of keys) {
    const value = source[key]
    if (value !== undefined && value !== null && String(value).trim()) return String(value).trim()
  }
  return ''
}

function formatDeviceConfig(device) {
  if (device?.config) return device.config
  const attributes = device?.attributes || {}
  const cpu = pickAttribute(attributes, ['CPU型号', 'CPU Model', 'cpu_model', 'processor', 'Processor'])
  const cpuCount = pickAttribute(attributes, ['CPU数量', 'CPU颗数', 'CPU核心数', 'cpu_count', 'cpu_cores'])
  const memory = pickAttribute(attributes, ['内存容量', '内存大小', '内存', 'memory', 'Memory'])
  const disk = pickAttribute(attributes, ['磁盘', '硬盘', '硬盘容量', '磁盘大小', 'disk', 'Disk', 'disk_size', 'disk_capacity'])
  const diskCount = pickAttribute(attributes, ['磁盘数量', '硬盘数量', 'disk_count'])
  const parts = []
  if (cpuCount || cpu) parts.push([cpuCount, cpu].filter(Boolean).join(' / '))
  if (memory) parts.push(memory)
  if (diskCount || disk) parts.push([diskCount, disk].filter(Boolean).join(' / '))
  return parts.join(' | ') || '配置未补充'
}

function isFreeDevice(device) {
  return Number(device?.status) === 0
}

function summarizeModels(devices) {
  const modelCount = new Map()
  for (const device of devices) {
    const model = String(device.model || '').trim()
    if (model) modelCount.set(model, (modelCount.get(model) || 0) + 1)
  }
  return [...modelCount.entries()]
    .sort((a, b) => a[0].localeCompare(b[0], 'zh-Hans-CN'))
    .map(([name, count]) => ({ name, count }))
}

function normalizeFreeDeviceRegions(sourceRegions) {
  return (sourceRegions || [])
    .map((region) => {
      const devices = (region.devices || []).filter(isFreeDevice)
      return {
        ...region,
        devices,
        count: devices.length,
        models: summarizeModels(devices),
      }
    })
    .filter((region) => region.count > 0)
}

function summarizeFreeDeviceRegions(sourceRegions) {
  const modelSet = new Set()
  let total = 0
  for (const region of sourceRegions) {
    total += Number(region.count || 0)
    for (const model of region.models || []) {
      if (model.name) modelSet.add(model.name)
    }
  }
  return {
    total,
    regions: sourceRegions.length,
    models: [...modelSet].sort((a, b) => a.localeCompare(b, 'zh-Hans-CN')),
  }
}

async function loadData() {
  loading.value = true
  try {
    const res = await api.resourceApi.freeDevices({ keyword: query.keyword })
    const nextRegions = normalizeFreeDeviceRegions(res?.data?.regions || [])
    regions.value = nextRegions
    summary.value = summarizeFreeDeviceRegions(nextRegions)
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.free-device-page {
  display: grid;
  gap: 16px;
}

.toolbar {
  display: grid;
  grid-template-columns: minmax(260px, 1fr) auto;
  gap: 10px;
  align-items: center;
}

.summary-band {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  overflow: hidden;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
}

.summary-main {
  padding: 18px 22px;
}

.summary-main + .summary-main {
  border-left: 1px solid #eef2f7;
}

.summary-main--right {
  text-align: right;
}

.summary-main span {
  color: #64748b;
  font-size: 13px;
}

.summary-main strong {
  display: block;
  margin-top: 8px;
  color: #0f172a;
  font-size: 30px;
  font-weight: 700;
  line-height: 1.1;
}

.device-board {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  align-items: start;
}

.board-lane {
  display: grid;
  gap: 12px;
  align-content: start;
}

.board-column {
  overflow: hidden;
  border: 1px solid #e2e8f0;
  border-top: 3px solid var(--tone);
  border-radius: 8px;
  background: var(--tone-soft);
}

.board-column.collapsed {
  background: #fff;
}

.column-header {
  display: flex;
  min-height: 58px;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid color-mix(in srgb, var(--tone) 18%, #e2e8f0);
  background: #fff;
  padding: 0 12px;
}

.board-column.collapsed .column-header {
  border-bottom: 0;
}

.column-title {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 8px;
}

.column-dot {
  width: 8px;
  height: 8px;
  flex: 0 0 auto;
  border-radius: 50%;
  background: var(--tone);
}

.column-title > div {
  display: grid;
  min-width: 0;
  gap: 2px;
}

.column-title strong {
  overflow: hidden;
  color: #0f172a;
  font-size: 14px;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.column-title span,
.device-card span {
  color: #64748b;
  font-size: 12px;
}

.board-column.collapsed .column-title span {
  display: none;
}

.column-actions {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 8px;
}

.column-actions :deep(.n-tag),
.device-card__head :deep(.n-tag) {
  color: var(--tone-strong);
  background: var(--tone-tag);
}

.column-body {
  display: grid;
  gap: 10px;
  padding: 10px;
}

.model-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.model-strip span {
  padding: 3px 8px;
  border-radius: 999px;
  background: #fff;
  color: #475569;
  font-size: 12px;
  box-shadow: inset 0 0 0 1px #e2e8f0;
}

.device-card {
  display: grid;
  gap: 12px;
  border: 1px solid #dbe3ef;
  border-radius: 8px;
  background: #fff;
  padding: 12px;
  box-shadow: 0 1px 2px rgb(15 23 42 / 6%);
}

.device-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.device-card__head > div,
.device-spec {
  display: grid;
  min-width: 0;
  gap: 5px;
}

.device-card__head strong,
.device-spec strong {
  color: #111827;
  font-size: 15px;
  font-weight: 700;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.device-spec strong {
  font-size: 14px;
}

.device-card footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border-top: 1px solid #eef2f7;
  padding-top: 10px;
}

.device-card footer strong {
  color: #0f172a;
  font-size: 13px;
  font-weight: 700;
  white-space: nowrap;
}

.tone-blue {
  --tone: #2563eb;
  --tone-strong: #1d4ed8;
  --tone-soft: #eff6ff;
  --tone-tag: #dbeafe;
}

.tone-green {
  --tone: #16a34a;
  --tone-strong: #15803d;
  --tone-soft: #f0fdf4;
  --tone-tag: #dcfce7;
}

.tone-amber {
  --tone: #d97706;
  --tone-strong: #b45309;
  --tone-soft: #fffbeb;
  --tone-tag: #fef3c7;
}

.tone-rose {
  --tone: #e11d48;
  --tone-strong: #be123c;
  --tone-soft: #fff1f2;
  --tone-tag: #ffe4e6;
}

.tone-violet {
  --tone: #7c3aed;
  --tone-strong: #6d28d9;
  --tone-soft: #f5f3ff;
  --tone-tag: #ede9fe;
}

.tone-cyan {
  --tone: #0891b2;
  --tone-strong: #0e7490;
  --tone-soft: #ecfeff;
  --tone-tag: #cffafe;
}

@media (max-width: 720px) {
  .toolbar,
  .summary-band {
    grid-template-columns: 1fr;
  }

  .summary-main + .summary-main {
    border-top: 1px solid #eef2f7;
    border-left: 0;
  }

  .summary-main--right {
    text-align: left;
  }

  .device-board {
    grid-template-columns: 1fr;
  }
}

@media (min-width: 721px) and (max-width: 1180px) {
  .device-board {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
