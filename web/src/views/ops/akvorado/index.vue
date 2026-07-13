<template>
  <AppPage :show-footer="false">
    <div class="akvorado-page">
      <aside class="region-panel">
        <!-- <div class="panel-head">
          <strong>Akvorado</strong>
        </div> -->

        <div class="region-list">
          <button
            v-for="region in filteredRegions"
            :key="region.code"
            class="region-item"
            :class="{ active: selectedRegion.code === region.code }"
            @click="selectRegion(region)"
          >
            <span>
              <strong>{{ region.code }}</strong>
            </span>
          </button>
        </div>
      </aside>

      <main class="traffic-panel">
        <section class="traffic-toolbar">
          <strong>{{ selectedRegion.code }}</strong>
          <n-space>
            <n-button quaternary size="small" @click="reloadFrame">
              <template #icon>
                <TheIcon icon="mdi:reload" :size="18" />
              </template>
            </n-button>
            <n-button quaternary size="small" tag="a" :href="selectedRegion.url" target="_blank" rel="noopener">
              <template #icon>
                <TheIcon icon="mdi:open-in-new" :size="18" />
              </template>
            </n-button>
          </n-space>
        </section>

        <section class="iframe-shell">
          <div v-if="frameLoading" class="frame-loading">
            <n-spin size="large" />
            <span>正在加载 {{ selectedRegion.code }} 流量面板</span>
          </div>
          <iframe
            :key="frameKey"
            :src="selectedFrameUrl"
            :title="`${selectedRegion.code} Akvorado`"
            @load="frameLoading = false"
          />
        </section>
      </main>
    </div>
  </AppPage>
</template>

<script setup>
import { computed, ref } from 'vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import { getToken } from '@/utils'

defineOptions({ name: 'OpsAkvorado' })

const rawRegions = [
  { code: 'SZ', name: 'Shenzhen', url: 'http://10.0.10.99:8081' },
  { code: 'TW', name: 'Taiwan', url: 'http://10.9.10.99:8081' },
  { code: 'LA3', name: 'Los Angeles 3', url: 'http://10.3.10.90:8081' },
  { code: 'DE', name: 'Germany', url: 'http://10.7.10.89:8081' },
  { code: 'HK', name: 'Hong Kong', url: 'http://10.4.10.39:8081' },
  { code: 'SG', name: 'Singapore', url: 'http://10.6.10.53:8081' },
  { code: 'LON', name: 'London', url: 'http://10.1.10.208:8081' },
  { code: 'JP', name: 'Japan', url: 'http://10.5.10.17:8081' },
]
const regions = rawRegions.map((region) => ({
  ...region,
  proxyBaseUrl: `${import.meta.env.VITE_BASE_API}/akvorado/proxy/${region.code}/`,
}))

const selectedRegion = ref(regions[0])
const frameKey = ref(0)
const frameLoading = ref(true)

const filteredRegions = computed(() => {
  return regions
})

function selectRegion(region) {
  selectedRegion.value = region
  reloadFrame()
}

function reloadFrame() {
  frameLoading.value = true
  frameKey.value += 1
}

const selectedFrameUrl = computed(() => {
  const token = getToken()
  const tokenQuery = token ? `?token=${encodeURIComponent(token)}` : ''
  return `${selectedRegion.value.proxyBaseUrl}${tokenQuery}`
})
</script>

<style scoped>
.akvorado-page {
  box-sizing: border-box;
  display: grid;
  height: calc(100vh - 92px);
  min-height: 0;
  grid-template-columns: 72px minmax(0, 1fr);
  gap: 8px;
  padding: 8px;
  background: #f5f7fb;
}

.region-panel,
.traffic-panel {
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 12px 30px rgba(15, 23, 42, 0.04);
}

.region-panel {
  display: flex;
  min-height: 0;
  flex-direction: column;
  padding: 8px;
}

.panel-head,
.traffic-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.panel-head {
  margin-bottom: 8px;
}

.panel-head strong,
.traffic-toolbar strong {
  color: #0f172a;
  font-weight: 700;
  letter-spacing: 0;
}

.panel-head strong {
  font-size: 12px;
}

.region-list {
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  gap: 8px;
  overflow-y: auto;
  padding-right: 2px;
}

.region-item {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: center;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  color: #0f172a;
  cursor: pointer;
  padding: 10px 4px;
  text-align: center;
}

.region-item:hover,
.region-item.active {
  border-color: #fb5b2f;
  background: #fff7ed;
}

.region-item span {
  display: flex;
  min-width: 0;
  flex-direction: column;
}

.region-item strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}

.traffic-panel {
  display: flex;
  min-width: 0;
  min-height: 0;
  flex-direction: column;
  padding: 8px;
}

.traffic-toolbar {
  flex-shrink: 0;
  min-height: 32px;
  margin-bottom: 8px;
}

.iframe-shell {
  position: relative;
  flex: 1;
  overflow: hidden;
  border-radius: 6px;
  background: #fff;
}

.iframe-shell iframe {
  display: block;
  width: 100%;
  height: 100%;
  border: 0;
  background: #fff;
}

.frame-loading {
  position: absolute;
  inset: 0;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 12px;
  background: rgba(248, 250, 252, 0.82);
  color: #64748b;
}

html.dark .akvorado-page {
  background: #0f172a;
}

html.dark .region-panel,
html.dark .traffic-panel,
html.dark .region-item {
  border-color: rgba(148, 163, 184, 0.22);
  background: rgba(17, 24, 39, 0.9);
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.2);
}

html.dark .region-item:hover,
html.dark .region-item.active {
  border-color: #fb5b2f;
  background: rgba(124, 45, 18, 0.36);
}

html.dark .panel-head strong,
html.dark .traffic-toolbar strong,
html.dark .region-item {
  color: #e5e7eb;
}

@media (max-width: 960px) {
  .akvorado-page {
    grid-template-columns: 60px minmax(0, 1fr);
  }

  .traffic-toolbar {
    align-items: center;
    flex-direction: row;
  }
}
</style>
