<template>
  <CommonPage show-footer title="层峰价格">
    <template #action>
      <n-button :loading="loading" secondary @click="loadData">刷新</n-button>
    </template>

    <div class="pricing-page">
      <section class="pricing-toolbar">
        <n-input v-model:value="keyword" clearable placeholder="搜索区域、起点、终点" />
        <n-select v-model:value="bandwidth" :options="bandwidthOptions" />
      </section>

      <section class="pricing-note">
        <strong>SDN 价格参考</strong>
        <span>{{ note }}</span>
      </section>

      <div class="pricing-grid">
        <article v-for="row in filteredRows" :key="`${row.from}-${row.to}-${row.bandwidth}`" class="price-card">
          <div>
            <span>{{ row.area }}</span>
            <h2>{{ row.from }} → {{ row.to }}</h2>
          </div>
          <div class="price-card__price">
            <strong>${{ scalePrice(row.monthly_usd) }}</strong>
            <span>/ 月</span>
          </div>
          <footer>
            <span>{{ bandwidth }}</span>
            <em>{{ row.unit }}</em>
          </footer>
        </article>
      </div>
    </div>
  </CommonPage>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { NButton, NInput, NSelect } from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import api from '@/api'

defineOptions({ name: 'ResourceZenlayerPricing' })

const loading = ref(false)
const rows = ref([])
const note = ref('')
const keyword = ref('')
const bandwidth = ref('100M')
const bandwidthOptions = ['50M', '100M', '200M', '500M', '1G', '10G'].map((item) => ({ label: item, value: item }))

const bandwidthRatio = computed(() => {
  const value = bandwidth.value
  if (value.endsWith('G')) return (Number(value.replace('G', '')) * 1000) / 100
  return Number(value.replace('M', '')) / 100
})

const filteredRows = computed(() => {
  const key = keyword.value.trim().toLowerCase()
  if (!key) return rows.value
  return rows.value.filter((row) => [row.area, row.from, row.to].join(' ').toLowerCase().includes(key))
})

function scalePrice(price) {
  return Math.round(Number(price || 0) * bandwidthRatio.value).toLocaleString()
}

async function loadData() {
  loading.value = true
  try {
    const res = await api.resourceApi.zenlayerPricing()
    rows.value = res?.data?.rows || []
    note.value = res?.data?.note || ''
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.pricing-page {
  display: grid;
  gap: 14px;
}

.pricing-toolbar {
  display: grid;
  grid-template-columns: minmax(260px, 1fr) 180px;
  gap: 10px;
}

.pricing-note {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: #f8fafc;
}

.pricing-note span,
.price-card span,
.price-card em {
  color: #64748b;
}

.pricing-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 14px;
}

.price-card {
  display: grid;
  gap: 18px;
  padding: 16px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
}

.price-card h2 {
  margin: 4px 0 0;
  font-size: 18px;
}

.price-card__price strong {
  font-size: 32px;
  color: #0f172a;
}

.price-card footer {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  border-top: 1px solid #edf2f7;
  padding-top: 10px;
}

.price-card em {
  font-style: normal;
}

@media (max-width: 720px) {
  .pricing-toolbar,
  .pricing-note {
    grid-template-columns: 1fr;
    display: grid;
  }
}
</style>
