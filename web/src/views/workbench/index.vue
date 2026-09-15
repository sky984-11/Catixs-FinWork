<template>
  <AppPage :show-footer="false">
    <div class="workbench-page">
      <header class="dashboard-header">
        <div>
          <span class="eyebrow">资源与运维总览</span>
          <h1>{{ userStore.name || '用户' }}，欢迎回来</h1>
          <p>查看客户虚拟机、物理机配置及地区分布。</p>
        </div>
        <n-button secondary :loading="loading" @click="loadDashboard">刷新概览</n-button>
      </header>
      <section class="ticket-summary">
        <div class="ticket-title">
          <TheIcon icon="mdi:ticket-confirmation-outline" :size="20" /><strong>工单概况</strong>
        </div>
        <n-spin :show="loading">
          <n-space :size="16">
            <span
              >待处理 <b>{{ counts.active }}</b></span
            >
            <span
              >今日新增 <b>{{ counts.today }}</b></span
            >
            <span :class="{ 'has-risk': counts.risk > 0 }"
              >超时关注 <b>{{ counts.risk }}</b></span
            >
          </n-space>
        </n-spin>
        <n-button text type="primary" @click="router.push('/ticket')">进入工单 →</n-button>
      </section>
      <n-alert v-if="loadError" type="warning" :show-icon="false">{{ loadError }}</n-alert>
      <VmOverview ref="vmOverview" />
      <PhysicalOverview ref="physicalOverview" />
    </div>
  </AppPage>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/api'
import { useUserStore } from '@/store'
import TheIcon from '@/components/icon/TheIcon.vue'
import VmOverview from './VmOverview.vue'
import PhysicalOverview from './PhysicalOverview.vue'

defineOptions({ name: 'Workbench' })
const router = useRouter()
const userStore = useUserStore()
const vmOverview = ref(null)
const physicalOverview = ref(null)
const loading = ref(false)
const loadError = ref('')
const counts = reactive({ active: 0, today: 0, risk: 0 })

async function loadDashboard() {
  vmOverview.value?.refresh()
  physicalOverview.value?.refresh()
  if (loading.value) return
  loading.value = true
  loadError.value = ''
  try {
    const result = await api.ticketApi.dashboard()
    const data = result.data || {}
    counts.active = Number(data.status_counts?.[1] || 0) + Number(data.status_counts?.[2] || 0)
    counts.today = Number(data.today_created || 0)
    counts.risk = Number(data.risk_count || 0)
  } catch {
    loadError.value = '工单概况加载失败，请稍后刷新重试。'
  } finally {
    loading.value = false
  }
}
onMounted(loadDashboard)
</script>

<style scoped>
.workbench-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}
.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 8px 4px;
}
.eyebrow {
  color: #64748b;
  font-size: 12px;
}
h1 {
  margin: 5px 0;
  font-size: 22px;
}
p {
  margin: 0;
  color: #7b8798;
  font-size: 13px;
}
.ticket-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 20px;
  border: 1px solid var(--border-color, #e5e9f0);
  border-radius: 12px;
  background: var(--card-color, #fff);
  font-size: 13px;
}
.ticket-title {
  display: flex;
  align-items: center;
  gap: 8px;
}
.ticket-summary b {
  margin-left: 6px;
  font-size: 18px;
}
.has-risk {
  color: #d97706;
}
.workbench-page :deep(.vm-overview) {
  margin: 0;
}
@media (max-width: 768px) {
  .dashboard-header {
    align-items: flex-start;
  }
  h1 {
    font-size: 19px;
  }
  .ticket-summary {
    flex-wrap: wrap;
    padding: 12px;
    gap: 12px;
  }
}
</style>
