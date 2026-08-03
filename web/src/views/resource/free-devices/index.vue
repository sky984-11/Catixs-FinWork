<template>
  <CommonPage show-footer :show-header="false">
    <div class="free-device-page">
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
                    <span v-if="group.subtitle">{{ group.subtitle }}</span>
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
                    <div class="device-card__actions">
                      <n-button size="tiny" type="primary" secondary @click="openSellModal(device)">出售</n-button>
                    </div>
                  </div>

                  <div class="device-spec">
                    <span>型号</span>
                    <strong>{{ [device.brand, device.model].filter(Boolean).join(' ') || '-' }}</strong>
                  </div>

                  <div class="device-config-grid">
                    <div v-for="item in getDeviceConfigItems(device)" :key="item.label" class="device-config-item">
                      <span>{{ item.label }}</span>
                      <strong>{{ item.value }}</strong>
                    </div>
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
        <n-empty v-else description="暂无可售服务器" />
      </n-spin>
    </div>

    <n-modal
      v-model:show="sellModal.show"
      preset="card"
      title="出售设备"
      class="sell-modal"
      :style="{ width: '420px', maxWidth: 'calc(100vw - 32px)' }"
      :segmented="{ content: true, footer: true }"
    >
      <n-form label-placement="top">
        <n-form-item label="设备">
          <n-input :value="sellDeviceLabel" disabled />
        </n-form-item>
        <n-form-item label="机器描述" required>
          <n-input
            v-model:value="sellModal.form.description"
            type="textarea"
            placeholder="例如：交付给某客户 / 合同编号 / 交付备注"
            :autosize="{ minRows: 4, maxRows: 6 }"
          />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="sellModal.show = false">取消</n-button>
          <n-button type="primary" :loading="sellModal.submitting" @click="submitSellDevice">保存</n-button>
        </n-space>
      </template>
    </n-modal>
  </CommonPage>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { NButton, NEmpty, NForm, NFormItem, NInput, NModal, NSpace, NSpin, NTag } from 'naive-ui'

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
const sellModal = reactive({
  show: false,
  submitting: false,
  device: null,
  form: {
    description: '',
  },
})

const regionGroups = computed(() => regions.value
  .map((region, index) => {
    const key = String(region.region_id || region.region || index)
    const subtitle = formatRegionSubtitle(region)
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

function formatRegionSubtitle(region) {
  const title = String(region?.region || '').trim()
  const subtitle = [region?.country, region?.city].filter(Boolean).join(' / ')
  if (!subtitle) return '未设置地区信息'
  if (title && (title === subtitle || title.includes(subtitle) || subtitle.includes(title))) return ''
  return subtitle
}

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

const sellDeviceLabel = computed(() => {
  const device = sellModal.device
  if (!device) return ''
  const title = device.is_four_node
    ? `${device.parent_name || device.name || '-'} / ${device.node_name || '-'}`
    : (device.name || device.model || '-')
  const rack = [device.cabinet, device.u_position ? `U${device.u_position}` : ''].filter(Boolean).join(' / ')
  return [title, device.location, rack].filter(Boolean).join(' · ')
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
  const { cpuModel, cpuCount, cpuCores, memory, disk } = getDeviceConfigValues(device, attributes)
  const parts = []
  if (cpuCount || cpuModel) parts.push([cpuCount, cpuModel].filter(Boolean).join(' / '))
  if (cpuCores) parts.push(`${cpuCores}核`)
  if (memory) parts.push(memory)
  if (disk) parts.push(disk)
  return parts.join(' | ') || '配置未补充'
}

function splitConfigText(value) {
  return String(value || '')
    .split(/[|,，;；]/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function findConfigPart(device, matcher) {
  return splitConfigText(device?.config).find(matcher) || ''
}

function parseCpuBundle(value) {
  const text = String(value || '').trim()
  if (!text) return {}

  const parts = text
    .split('/')
    .map((item) => item.trim())
    .filter(Boolean)
  const candidates = parts.length > 1 ? parts : [text]
  const result = {}

  if (parts.length >= 3) {
    const [countPart, modelPart, coresPart] = parts
    if (/\d+\s*(颗|路|socket|sockets)/i.test(countPart)) result.cpuCount = countPart
    if (/xeon|epyc|ryzen|intel|amd/i.test(modelPart)) result.cpuModel = modelPart
    if (/\d+\s*(核|core|cores)/i.test(coresPart)) result.cpuCores = coresPart
  }

  for (const part of candidates) {
    if (!result.cpuCount && /(^|\s)\d+\s*(颗|路|socket|sockets)\s*$/i.test(part)) {
      result.cpuCount = part
      continue
    }
    if (!result.cpuCores && /(^|\s)\d+\s*(核|core|cores)\s*$/i.test(part)) {
      result.cpuCores = part
      continue
    }
    if (!result.cpuModel && /xeon|epyc|ryzen|intel|amd/i.test(part)) {
      result.cpuModel = part
    }
  }

  return result
}

function cleanCpuModel(value) {
  const parsed = parseCpuBundle(value)
  if (parsed.cpuModel && parsed.cpuModel !== String(value || '').trim()) return parsed.cpuModel
  const text = String(value || '').trim()
  return /xeon|epyc|ryzen|intel|amd/i.test(text) && !/^\d+\s*(颗|路|核|core|cores|socket|sockets)?\s*$/i.test(text)
    ? text
    : ''
}

function cleanCpuCount(value) {
  const parsed = parseCpuBundle(value)
  if (parsed.cpuCount) return parsed.cpuCount
  const text = String(value || '').trim()
  return /^\d+\s*(颗|路|socket|sockets)?$/i.test(text) ? text : ''
}

function cleanCpuCores(value) {
  const parsed = parseCpuBundle(value)
  if (parsed.cpuCores) return parsed.cpuCores
  const text = String(value || '').trim()
  return /^\d+\s*(核|core|cores)$/i.test(text) ? text : ''
}

function getDeviceConfigValues(device, sourceAttributes = null) {
  const attributes = sourceAttributes || device?.attributes || {}
  const rawCpuModel = pickAttribute(attributes, ['CPU型号', 'CPU Model', 'cpu_model', 'processor', 'Processor'])
  const rawCpuCount = pickAttribute(attributes, ['CPU数量', 'CPU颗数', 'cpu_count'])
  const rawCpuCores = pickAttribute(attributes, ['CPU核心数', 'CPU Cores', 'cpu_cores', 'cores'])
  const rawCpuConfig = findConfigPart(device, (part) => /xeon|epyc|ryzen|intel|amd|cpu|颗|核|core|cores/i.test(part))
  const parsedCpu = [rawCpuConfig, rawCpuModel, rawCpuCount, rawCpuCores].reduce((result, value) => {
    const next = parseCpuBundle(value)
    return {
      cpuModel: result.cpuModel || next.cpuModel,
      cpuCount: result.cpuCount || next.cpuCount,
      cpuCores: result.cpuCores || next.cpuCores,
    }
  }, {})
  const cpuModel = cleanCpuModel(rawCpuModel) || parsedCpu.cpuModel || cleanCpuModel(rawCpuConfig)
  const cpuCount = cleanCpuCount(rawCpuCount) || parsedCpu.cpuCount || cleanCpuCount(rawCpuConfig)
  const cpuCores = cleanCpuCores(rawCpuCores) || parsedCpu.cpuCores || cleanCpuCores(rawCpuConfig)
  const memory = pickAttribute(attributes, ['内存总数', '内存容量', '内存大小', '内存', 'memory', 'Memory', 'ram', 'RAM'])
    || findConfigPart(device, (part) => /内存|ram|memory|\d+\s*(g|gb|gib)\b/i.test(part))
  const disk = pickAttribute(attributes, [
    '磁盘总数',
    '磁盘',
    '硬盘',
    '硬盘容量',
    '磁盘容量',
    '磁盘大小',
    '硬盘大小',
    'storage',
    'Storage',
    'disk',
    'Disk',
    'disk_size',
    'disk_capacity',
  ]) || findConfigPart(device, (part) => /盘|硬盘|disk|storage|ssd|hdd|nvme|raid|\d+\s*(t|tb)\b/i.test(part))
  return { cpuModel, cpuCount, cpuCores, memory, disk }
}

function getDeviceConfigItems(device) {
  const values = getDeviceConfigValues(device)
  const items = [
    { label: 'CPU型号', value: values.cpuModel },
    { label: 'CPU数量', value: values.cpuCount },
    { label: 'CPU核心数', value: values.cpuCores },
    { label: '内存总数', value: values.memory },
    { label: '磁盘总数', value: values.disk },
  ].filter((item) => item.value)
  return items.length ? items : [{ label: '配置', value: formatDeviceConfig(device) }]
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

function openSellModal(device) {
  sellModal.device = device
  sellModal.form.description = ''
  sellModal.show = true
}

function removeSoldDevice(device) {
  const nextRegions = normalizeFreeDeviceRegions(regions.value.map((region) => ({
    ...region,
    devices: (region.devices || []).filter((item) => item.id !== device.id),
  })))
  regions.value = nextRegions
  summary.value = summarizeFreeDeviceRegions(nextRegions)
}

async function submitSellDevice() {
  const description = String(sellModal.form.description || '').trim()
  const device = sellModal.device
  if (!device) return
  if (!description) {
    window.$message?.warning('请填写机器描述')
    return
  }

  sellModal.submitting = true
  try {
    const deviceId = Number(String(device.parent_id || device.id).split(':')[0])
    const res = await api.resourceApi.sellFreeDevice({
      device_id: deviceId,
      node_name: device.is_four_node ? device.node_name : undefined,
      description,
    })
    if (res?.code && res.code !== 200) {
      window.$message?.error(res.msg || '出售失败')
      return
    }
    window.$message?.success(res?.msg || '出售成功')
    sellModal.show = false
    removeSoldDevice(device)
  } catch (error) {
    window.$message?.error(error?.response?.data?.msg || error?.message || '出售失败')
  } finally {
    sellModal.submitting = false
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

.column-actions :deep(.n-tag) {
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

.device-card__actions {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 6px;
}

.device-card__actions :deep(.n-button) {
  height: 24px;
  padding-inline: 8px;
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

.device-config-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.device-config-item {
  display: grid;
  min-width: 0;
  gap: 4px;
  border: 1px solid #e5edf7;
  border-radius: 6px;
  background: #f8fafc;
  padding: 8px 9px;
}

.device-config-item span {
  color: #64748b;
  font-size: 12px;
}

.device-config-item strong {
  color: #0f172a;
  font-size: 13px;
  font-weight: 700;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.device-config-item:first-child {
  grid-column: 1 / -1;
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

.sell-modal {
  width: min(520px, calc(100vw - 32px));
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
