<template>
  <section class="vm-overview">
    <header class="vm-header">
      <div>
        <h2>客户虚拟机概览</h2>
        <p>仅统计已分配客户且未关机的虚拟机，不含模板和容器 · 展开客户可查看单台配置</p>
      </div>
      <n-space>
        <n-button secondary size="small" :loading="loading" @click="refresh()">刷新</n-button>
        <n-button secondary size="small" :disabled="sync.refreshing" @click="refresh(true)"
          >立即同步</n-button
        >
      </n-space>
    </header>
    <n-alert v-if="error" type="warning" :show-icon="true" class="vm-alert">{{ error }}</n-alert>
    <n-alert
      v-if="sync.refreshing || sync.error || !sync.synced_at"
      class="vm-alert"
      :type="sync.error ? 'warning' : 'info'"
    >
      {{
        sync.refreshing
          ? '正在后台同步云资源，当前显示本地快照…'
          : sync.error || '尚无成功同步的数据，请点击立即同步。'
      }}
    </n-alert>
    <n-spin :show="loading">
      <template v-if="!error">
        <div class="vm-metrics">
          <article>
            <span>虚拟机</span><strong>{{ fleet.length }}<small>台</small></strong>
          </article>
          <article>
            <span>已关联客户</span><strong>{{ customerCount }}<small>家</small></strong>
          </article>
          <article>
            <span>运行中</span><strong>{{ runningCount }}<small>台</small></strong>
          </article>
          <article>
            <span>覆盖地区</span><strong>{{ regionCount }}<small>个</small></strong>
          </article>
        </div>
        <div v-if="regionRows.length" class="vm-regions">
          <div v-for="region in regionRows" :key="region.name" class="vm-region">
            <div>
              <span>{{ region.name }}</span
              ><strong>{{ region.count }} 台</strong>
            </div>
            <n-progress
              type="line"
              :percentage="region.percent"
              :show-indicator="false"
              :height="6"
            />
          </div>
        </div>
        <div class="vm-filters">
          <n-input v-model:value="keyword" clearable placeholder="搜索客户名称" />
          <n-select
            v-model:value="selectedRegion"
            clearable
            :options="regionOptions"
            placeholder="全部地区"
          />
        </div>
        <n-data-table
          :columns="columns"
          :data="customers"
          :row-key="(row) => row.key"
          :pagination="{ pageSize: 8 }"
          :scroll-x="1130"
          size="small"
        >
          <template #empty
            ><n-empty :description="fleet.length ? '没有匹配的客户或地区' : '暂无虚拟机数据'"
          /></template>
        </n-data-table>
        <p v-if="updatedAt" class="vm-updated">
          最近读取：{{ updatedAt }} · 地区来自节点关联信息，未关联资源单独列示
        </p>
      </template>
    </n-spin>
  </section>
</template>

<script setup>
import { computed, h, onBeforeUnmount, onMounted, ref } from 'vue'
import { NTag } from 'naive-ui'
import api from '@/api'
import { groupVmCustomers, summarizeVmFleet } from './vm-overview'

const loading = ref(false)
const error = ref('')
const fleet = ref([])
const keyword = ref('')
const selectedRegion = ref(null)
const updatedAt = ref('')
const sync = ref({})
let refreshTimer
let disposed = false
const formatNumber = (value) => Number(value.toFixed(2)).toLocaleString('zh-CN')
const configText = (vm) =>
  `${vm.cores || '未知'} 核 / ${vm.memory ? formatNumber(vm.memory) : '未知'} GiB 内存 / ${
    vm.storage ? formatNumber(vm.storage) : '未知'
  } GiB 磁盘`
const customerCount = computed(
  () =>
    new Set(
      fleet.value.filter((vm) => vm.customer_id || vm.customer_name).map((vm) => vm.customerKey)
    ).size
)
const runningCount = computed(() => fleet.value.filter((vm) => vm.status === 'running').length)
const regionCount = computed(
  () => new Set(fleet.value.filter((vm) => vm.region !== '未关联地区').map((vm) => vm.region)).size
)
const regionRows = computed(() => {
  const counts = new Map()
  fleet.value.forEach((vm) => counts.set(vm.region, (counts.get(vm.region) || 0) + 1))
  return [...counts]
    .map(([name, count]) => ({ name, count, percent: (count / fleet.value.length) * 100 }))
    .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name, 'zh-CN'))
})
const regionOptions = computed(() =>
  regionRows.value.map((region) => ({ label: region.name, value: region.name }))
)
const customers = computed(() =>
  groupVmCustomers(
    fleet.value.filter(
      (vm) =>
        (!selectedRegion.value || vm.region === selectedRegion.value) &&
        vm.customerName.toLowerCase().includes(keyword.value.trim().toLowerCase())
    )
  )
)

function distribution(items, label) {
  const counts = new Map()
  items.forEach((vm) => {
    const name = label(vm)
    counts.set(name, (counts.get(name) || 0) + 1)
  })
  return h(
    'div',
    { class: 'vm-cell-lines' },
    [...counts].map(([name, count]) => h('div', `${name} × ${count}`))
  )
}

const columns = [
  {
    type: 'expand',
    width: 40,
    renderExpand: (row) =>
      h(
        'div',
        { class: 'vm-details' },
        row.items.map((vm) =>
          h('div', { class: 'vm-detail' }, [
            h('strong', `${vm.name} · #${vm.vmid}`),
            h('span', configText(vm)),
            h('span', `${vm.region} · ${vm.remote} / ${vm.node}`),
            h(
              NTag,
              {
                size: 'small',
                bordered: false,
                type: vm.status === 'running' ? 'success' : 'default',
              },
              {
                default: () =>
                  ({ running: '运行中', stopped: '已停止', paused: '已暂停' }[vm.status] ||
                  '状态未知'),
              }
            ),
          ])
        )
      ),
  },
  { title: '客户', key: 'name', width: 180, resizable: true, ellipsis: { tooltip: true } },
  {
    title: '数量',
    key: 'count',
    width: 80,
    resizable: true,
    sorter: (a, b) => a.items.length - b.items.length,
    render: (row) => row.items.length,
  },
  {
    title: '运行中',
    key: 'running',
    width: 85,
    resizable: true,
    render: (row) => row.items.filter((vm) => vm.status === 'running').length,
  },
  {
    title: '配置组合（核 / 内存 / 磁盘）',
    key: 'configs',
    width: 350,
    resizable: true,
    render: (row) => distribution(row.items, configText),
  },
  {
    title: '资源合计',
    key: 'resources',
    width: 215,
    resizable: true,
    render: (row) =>
      h('div', { class: 'vm-cell-lines' }, [
        h('div', `${formatNumber(row.cores)} 核 CPU`),
        h('div', `${formatNumber(row.memory)} GiB 内存 · ${formatNumber(row.storage)} GiB 磁盘`),
        row.items.some((vm) => !vm.cores || !vm.memory || !vm.storage)
          ? h('small', '部分配置未知，仅合计已知值')
          : null,
      ]),
  },
  {
    title: '地区分布',
    key: 'regions',
    width: 180,
    resizable: true,
    render: (row) => distribution(row.items, (vm) => vm.region),
  },
]

async function refresh(force = false) {
  if (loading.value) return
  loading.value = true
  error.value = ''
  try {
    const vms = await api.virtualMachineApi.pveVms({ refresh: force === true })
    fleet.value = summarizeVmFleet(vms.data?.items || [], vms.data?.nodes || [])
    sync.value = vms.data?.sync || {}
    updatedAt.value = sync.value.synced_at
      ? new Date(sync.value.synced_at).toLocaleString('zh-CN', { hour12: false })
      : ''
    clearTimeout(refreshTimer)
    if (sync.value.refreshing && !disposed) refreshTimer = setTimeout(() => refresh(), 3000)
  } catch (cause) {
    error.value =
      Number(cause?.code) === 403
        ? '暂无虚拟机概览查看权限，请联系管理员配置虚拟机及节点列表权限。'
        : '虚拟机概览加载失败，请稍后刷新重试。'
  } finally {
    loading.value = false
  }
}

defineExpose({ refresh })
onMounted(refresh)
onBeforeUnmount(() => {
  disposed = true
  clearTimeout(refreshTimer)
})
</script>

<style scoped>
.vm-overview {
  margin: 16px 0;
  padding: 20px;
  border: 1px solid var(--border-color, #e5e9f0);
  border-radius: 16px;
  background: var(--card-color, #fff);
}
.vm-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}
.vm-header h2 {
  margin: 0;
  font-size: 18px;
}
.vm-header p,
.vm-updated {
  margin: 6px 0 0;
  color: #7b8798;
  font-size: 12px;
}
.vm-alert {
  margin-bottom: 14px;
}
.vm-metrics {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}
.vm-metrics article {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 16px;
  background: rgba(32, 128, 240, 0.05);
  border-radius: 10px;
}
.vm-metrics span {
  color: #7b8798;
  font-size: 13px;
}
.vm-metrics strong {
  font-size: 26px;
}
.vm-metrics small {
  margin-left: 6px;
  font-size: 12px;
  font-weight: normal;
}
.vm-regions {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 16px;
  margin: 20px 0;
}
.vm-region > div {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
  font-size: 12px;
}
.vm-filters {
  display: flex;
  gap: 12px;
  margin: 16px 0;
}
.vm-filters > * {
  max-width: 260px;
}
:deep(.vm-cell-lines) {
  display: flex;
  flex-direction: column;
  gap: 5px;
  font-size: 12px;
}
:deep(.vm-details) {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
}
:deep(.vm-detail) {
  display: grid;
  grid-template-columns: 1fr 2fr 1fr auto;
  gap: 16px;
  align-items: center;
  padding: 10px;
  border-bottom: 1px solid #edf0f5;
  font-size: 12px;
}
.vm-updated {
  margin-top: 12px;
}
@media (max-width: 768px) {
  .vm-overview {
    padding: 16px;
    margin: 16px;
  }
  .vm-metrics {
    grid-template-columns: repeat(2, 1fr);
  }
  .vm-filters {
    flex-direction: column;
  }
  .vm-filters > * {
    max-width: none;
  }
  :deep(.vm-detail) {
    grid-template-columns: 1fr;
  }
}
</style>
