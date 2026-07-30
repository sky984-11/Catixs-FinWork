<template>
  <CommonPage show-footer title="空闲设备">
    <template #action>
      <n-button :loading="loading" secondary @click="loadData">刷新</n-button>
    </template>

    <div class="free-device-page">
      <section class="toolbar">
        <n-input v-model:value="query.keyword" clearable placeholder="搜索资产编号、型号、IP、配置" @keyup.enter="loadData" />
        <n-button type="primary" @click="loadData">查询</n-button>
      </section>

      <section class="summary-strip">
        <div>
          <span>可售设备</span>
          <strong>{{ summary.total || 0 }}</strong>
        </div>
        <div>
          <span>覆盖地区</span>
          <strong>{{ summary.regions || 0 }}</strong>
        </div>
        <div>
          <span>型号数量</span>
          <strong>{{ summary.models?.length || 0 }}</strong>
        </div>
      </section>

      <n-spin :show="loading">
        <div v-if="regions.length" class="region-grid">
          <article v-for="region in regions" :key="region.region_id || region.region" class="region-card">
            <header>
              <div>
                <span>{{ [region.country, region.city].filter(Boolean).join(' / ') || '未设置地区信息' }}</span>
                <h2>{{ region.region }}</h2>
              </div>
              <strong>{{ region.count }}</strong>
            </header>

            <div class="chip-row">
              <span v-for="model in region.models.slice(0, 5)" :key="model.name" class="chip">
                {{ model.name }} × {{ model.count }}
              </span>
            </div>

            <div class="device-list">
              <div v-for="device in region.devices" :key="device.id" class="device-row">
                <div>
                  <strong>{{ device.name }}</strong>
                  <span>{{ device.brand }} {{ device.model }} · {{ device.asset_no }}</span>
                  <em>{{ device.config || '配置未补充' }}</em>
                </div>
                <div class="device-meta">
                  <span>{{ device.location || '-' }}</span>
                  <span>{{ device.cabinet || '-' }} / {{ device.u_position ? `U${device.u_position}` : '-' }}</span>
                </div>
              </div>
            </div>
          </article>
        </div>
        <n-empty v-else description="暂无空闲设备" />
      </n-spin>
    </div>
  </CommonPage>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { NButton, NEmpty, NInput, NSpin } from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import api from '@/api'

defineOptions({ name: 'ResourceFreeDevices' })

const loading = ref(false)
const regions = ref([])
const summary = ref({})
const query = reactive({ keyword: '' })

async function loadData() {
  loading.value = true
  try {
    const res = await api.resourceApi.freeDevices({ keyword: query.keyword })
    regions.value = res?.data?.regions || []
    summary.value = res?.data?.summary || {}
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.free-device-page {
  display: grid;
  gap: 14px;
}

.toolbar,
.summary-strip {
  display: grid;
  grid-template-columns: minmax(240px, 1fr) auto;
  gap: 10px;
  align-items: center;
}

.summary-strip {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.summary-strip > div {
  padding: 14px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
}

.summary-strip span,
.region-card header span,
.device-row span,
.device-row em,
.device-meta {
  color: #64748b;
}

.summary-strip strong {
  display: block;
  margin-top: 4px;
  font-size: 26px;
  color: #0f172a;
}

.region-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
  gap: 14px;
}

.region-card {
  display: grid;
  gap: 14px;
  padding: 16px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
}

.region-card header {
  display: flex;
  justify-content: space-between;
  gap: 14px;
}

.region-card h2 {
  margin: 4px 0 0;
  font-size: 20px;
}

.region-card header > strong {
  font-size: 34px;
  color: #16a34a;
}

.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.chip {
  padding: 3px 8px;
  border-radius: 999px;
  background: #f1f5f9;
  color: #334155;
  font-size: 12px;
}

.device-list {
  display: grid;
  gap: 8px;
}

.device-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 140px;
  gap: 10px;
  padding: 10px;
  border: 1px solid #edf2f7;
  border-radius: 8px;
  background: #f8fafc;
}

.device-row strong,
.device-row span,
.device-row em,
.device-meta span {
  display: block;
}

.device-row em {
  font-style: normal;
  margin-top: 3px;
}

.device-meta {
  text-align: right;
}

@media (max-width: 760px) {
  .toolbar,
  .summary-strip,
  .device-row {
    grid-template-columns: 1fr;
  }

  .device-meta {
    text-align: left;
  }
}
</style>
