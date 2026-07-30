<template>
  <CommonPage show-footer title="IPXO">
    <template #action>
      <n-button :loading="loading" secondary @click="loadData(true)">刷新</n-button>
    </template>

    <div class="ipxo-page">
      <section class="summary-band">
        <div class="summary-main">
          <span>Active IP 资源</span>
          <strong>{{ summary.count || 0 }}</strong>
        </div>
        <div class="summary-main summary-main--right">
          <span>月费合计</span>
          <strong>${{ formatMoney(summary.monthly_total) }}</strong>
        </div>
      </section>

      <n-alert v-if="errors.length" type="warning" :bordered="false">
        IPXO 部分接口不可用：{{ errors.map((item) => item.source || item.status || item.error).join(' / ') }}
      </n-alert>

      <n-spin :show="loading">
        <div v-if="regionGroups.length" class="ipxo-board">
          <div v-for="(lane, laneIndex) in boardLanes" :key="laneIndex" class="board-lane">
            <section
              v-for="group in lane"
              :key="group.name"
              class="board-column"
              :class="[`tone-${group.tone}`, { collapsed: isRegionCollapsed(group.name) }]"
            >
              <header class="column-header">
                <div class="column-title">
                  <span class="column-dot"></span>
                  <div>
                    <strong>{{ group.name }}</strong>
                    <span>{{ group.items.length }} 个 IP 段</span>
                  </div>
                </div>
                <div class="column-actions">
                  <n-tag size="small" round :bordered="false">USD {{ formatMoney(group.total) }}</n-tag>
                  <n-button size="tiny" quaternary circle @click="toggleRegion(group.name)">
                    <template #icon>
                      <TheIcon :icon="isRegionCollapsed(group.name) ? 'mdi:chevron-right' : 'mdi:chevron-down'" :size="18" />
                    </template>
                  </n-button>
                </div>
              </header>

              <div v-show="!isRegionCollapsed(group.name)" class="ip-list">
                <article v-for="item in group.items" :key="item.uuid || item.notation" class="ip-card">
                  <div class="ip-card__main">
                    <span>IP 段</span>
                    <strong>{{ item.notation || `${item.address}/${item.cidr}` }}</strong>
                  </div>
                  <footer>
                    <span>月费</span>
                    <strong>{{ item.currency || 'USD' }} {{ formatMoney(item.monthly_price) }}</strong>
                  </footer>
                </article>
              </div>
            </section>
          </div>
        </div>
        <n-empty v-else description="暂无 IPXO 资源数据" />
      </n-spin>
    </div>
  </CommonPage>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { NAlert, NButton, NEmpty, NSpin, NTag } from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import api from '@/api'

defineOptions({ name: 'ResourceIpxo' })

const laneCount = 4
const tones = ['blue', 'green', 'amber', 'rose', 'violet', 'cyan']
const loading = ref(false)
const items = ref([])
const summary = ref({})
const errors = ref([])
const source = ref('')
const collapsedRegions = ref(new Set())

const regionGroups = computed(() => {
  const groups = new Map()
  for (const item of items.value) {
    const name = item.region || item.country || '未识别地区'
    if (!groups.has(name)) {
      groups.set(name, { name, items: [], total: 0 })
    }
    const group = groups.get(name)
    group.items.push(item)
    group.total += Number(item.monthly_price || 0)
  }

  return [...groups.values()]
    .map((group) => ({
      ...group,
      total: Number(group.total.toFixed(2)),
      items: [...group.items].sort((a, b) => getIpSortValue(a).localeCompare(getIpSortValue(b), undefined, { numeric: true })),
    }))
    .sort((a, b) => {
      if (b.items.length !== a.items.length) return b.items.length - a.items.length
      return a.name.localeCompare(b.name, 'zh-Hans-CN')
    })
    .map((group, index) => ({
      ...group,
      tone: tones[index % tones.length],
    }))
})

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
  return isRegionCollapsed(group.name) ? 1 : group.items.length + 1
}

function getIpSortValue(item) {
  return item.notation || `${item.address || ''}/${item.cidr || ''}`
}

function isRegionCollapsed(name) {
  return collapsedRegions.value.has(name)
}

function toggleRegion(name) {
  const next = new Set(collapsedRegions.value)
  if (next.has(name)) {
    next.delete(name)
  } else {
    next.add(name)
  }
  collapsedRegions.value = next
}

function formatMoney(value) {
  return Number(value || 0).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

async function loadData(refresh = false) {
  loading.value = true
  try {
    const res = await api.resourceApi.ipxoResources({ limit: 200, refresh })
    items.value = res?.data?.items || []
    summary.value = res?.data?.summary || {}
    errors.value = res?.data?.errors || []
    source.value = res?.data?.source || ''
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.ipxo-page {
  display: grid;
  gap: 16px;
}

.summary-band {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
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

.ipxo-board {
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
.ip-card span {
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

.ip-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 10px;
}

.ip-card {
  display: grid;
  gap: 12px;
  border: 1px solid #dbe3ef;
  border-radius: 8px;
  background: #fff;
  padding: 12px;
  box-shadow: 0 1px 2px rgb(15 23 42 / 6%);
}

.ip-card__main {
  display: grid;
  gap: 5px;
}

.ip-card__main strong {
  color: #111827;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
  font-size: 18px;
  font-weight: 700;
  line-height: 1.25;
  overflow-wrap: anywhere;
}

.ip-card footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border-top: 1px solid #eef2f7;
  padding-top: 10px;
}

.ip-card footer strong {
  color: #0f172a;
  font-size: 15px;
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

  .ipxo-board {
    grid-template-columns: 1fr;
  }
}

@media (min-width: 721px) and (max-width: 1180px) {
  .ipxo-board {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
