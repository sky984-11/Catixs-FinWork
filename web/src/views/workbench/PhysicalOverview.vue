<template>
  <section class="physical-overview">
    <header>
      <div>
        <h2>客户物理机概览</h2>
        <p>按资产登记配置统计；四合一设备按节点所属客户展示，台数按机箱计</p>
      </div>
      <n-button secondary size="small" :loading="loading" @click="refresh">刷新</n-button>
    </header>
    <n-alert v-if="error" type="warning">{{ error }}</n-alert>
    <n-spin :show="loading">
      <template v-if="!error">
        <n-space class="physical-summary">
          <n-tag :bordered="false" type="info">物理设备 {{ devices.length }} 台</n-tag>
          <n-tag :bordered="false">关联客户 {{ allCustomers.length }} 家</n-tag>
          <n-tag :bordered="false"
            >覆盖地区 {{ regions.filter((item) => item.value !== '未关联地区').length }} 个</n-tag
          >
        </n-space>
        <n-alert v-if="unmappedNodes" type="warning" style="margin-bottom: 16px">
          {{ unmappedNodes }}
          个四合一节点尚未映射客户，请在机柜管理中设置；这些节点暂不计入客户配置。
        </n-alert>
        <div class="physical-filters">
          <n-input v-model:value="keyword" clearable placeholder="搜索客户名称" />
          <n-select v-model:value="region" clearable :options="regions" placeholder="全部地区" />
        </div>
        <n-data-table
          :columns="columns"
          :data="rows"
          :row-key="(row) => row.id"
          :scroll-x="1050"
          :pagination="{ pageSize: 6 }"
          size="small"
        >
          <template #empty
            ><n-empty
              :description="devices.length ? '没有匹配的客户或地区' : '暂无已关联客户的物理机'"
          /></template>
        </n-data-table>
      </template>
    </n-spin>
  </section>
</template>

<script setup>
import { computed, h, onMounted, ref } from 'vue'
import api from '@/api'

const devices = ref([])
const loading = ref(false)
const error = ref('')
const keyword = ref('')
const region = ref(null)
const unmappedNodes = computed(() =>
  devices.value
    .filter((device) => device.form_factor === 'four_node')
    .reduce(
      (count, device) =>
        count + device.configurations.filter((config) => !config.customer_id).length,
      0
    )
)
const location = (device) => device.region_name || '未关联地区'
const regions = computed(() =>
  [...new Set(devices.value.map(location))].sort().map((value) => ({ label: value, value }))
)

function groupCustomers(items) {
  const groups = new Map()
  items.forEach((device) =>
    device.customer_ids.forEach((id, index) => {
      const configurations =
        device.form_factor === 'four_node'
          ? device.configurations.filter((config) => Number(config.customer_id) === Number(id))
          : device.configurations
      if (!configurations.length) return
      if (!groups.has(id))
        groups.set(id, { id, name: device.customer_names[index] || `客户 #${id}`, devices: [] })
      groups.get(id).devices.push({ ...device, configurations })
    })
  )
  return [...groups.values()].sort(
    (a, b) => b.devices.length - a.devices.length || a.name.localeCompare(b.name, 'zh-CN')
  )
}

const allCustomers = computed(() => groupCustomers(devices.value))
const rows = computed(() =>
  groupCustomers(
    devices.value.filter((device) => !region.value || location(device) === region.value)
  ).filter((row) => row.name.toLowerCase().includes(keyword.value.trim().toLowerCase()))
)

function configText(config) {
  const cpu = [
    config.cpu_count ? `${config.cpu_count}颗` : '',
    config.cpu_model,
    config.cpu_cores ? `${config.cpu_cores}核` : '',
  ]
    .filter(Boolean)
    .join(' ')
  return `CPU ${cpu || '未登记'} / 内存 ${config.memory || '未登记'} / 磁盘 ${
    config.disk || '未登记'
  }`
}

function configLines(row) {
  const counts = new Map()
  row.devices.forEach((device) =>
    device.configurations.forEach((config) => {
      const text = configText(config)
      counts.set(text, (counts.get(text) || 0) + 1)
    })
  )
  return h(
    'div',
    { class: 'physical-lines' },
    [...counts].map(([text, count]) => h('div', `${text} × ${count}`))
  )
}

const columns = [
  {
    type: 'expand',
    width: 40,
    renderExpand: (row) =>
      h(
        'div',
        { class: 'physical-details' },
        row.devices.map((device) =>
          h('article', [
            h('strong', `${device.name} · ${device.asset_no}`),
            h(
              'div',
              [
                device.brand,
                device.model,
                location(device),
                device.location_name,
                device.cabinet_name,
              ]
                .filter(Boolean)
                .join(' / ')
            ),
            ...device.configurations.map((config) =>
              h('div', `${config.name}：${configText(config)}`)
            ),
          ])
        )
      ),
  },
  { title: '客户', key: 'name', width: 180, resizable: true, ellipsis: { tooltip: true } },
  {
    title: '物理设备',
    key: 'count',
    width: 100,
    resizable: true,
    render: (row) => `${row.devices.length} 台`,
  },
  {
    title: '型号',
    key: 'models',
    width: 180,
    resizable: true,
    render: (row) =>
      [
        ...new Set(
          row.devices.map(
            (device) => [device.brand, device.model].filter(Boolean).join(' ') || '未登记'
          )
        ),
      ].join(' / '),
  },
  {
    title: '配置组合（整机或四合一节点）',
    key: 'configs',
    width: 390,
    resizable: true,
    render: configLines,
  },
  {
    title: '地区分布',
    key: 'regions',
    width: 160,
    resizable: true,
    render: (row) => {
      const counts = new Map()
      row.devices.forEach((device) =>
        counts.set(location(device), (counts.get(location(device)) || 0) + 1)
      )
      return h(
        'div',
        { class: 'physical-lines' },
        [...counts].map(([name, count]) => h('div', `${name} × ${count}`))
      )
    },
  },
]

async function refresh() {
  if (loading.value) return
  loading.value = true
  error.value = ''
  try {
    const result = await api.assetApi.devices({ overview: true })
    devices.value = result.data || []
  } catch (cause) {
    error.value =
      Number(cause?.code) === 403
        ? '暂无物理机查看权限，请联系管理员配置设备列表权限。'
        : '物理机概览加载失败，请刷新重试。'
  } finally {
    loading.value = false
  }
}
defineExpose({ refresh })
onMounted(refresh)
</script>

<style scoped>
.physical-overview {
  padding: 20px;
  border: 1px solid var(--border-color, #e5e9f0);
  border-radius: 16px;
  background: var(--card-color, #fff);
}
header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}
h2 {
  margin: 0;
  font-size: 18px;
}
p {
  margin: 6px 0 0;
  font-size: 12px;
  color: #7b8798;
}
.physical-summary {
  margin: 16px 0;
}
.physical-filters {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}
.physical-filters > * {
  max-width: 260px;
}
:deep(.physical-lines) {
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 12px;
}
:deep(.physical-details) {
  display: grid;
  gap: 12px;
  padding: 12px;
  font-size: 12px;
}
:deep(.physical-details article) {
  display: grid;
  gap: 6px;
  border-bottom: 1px solid #edf0f5;
  padding-bottom: 12px;
}
@media (max-width: 768px) {
  .physical-overview {
    padding: 16px;
  }
  .physical-filters {
    flex-direction: column;
  }
  .physical-filters > * {
    max-width: none;
  }
}
</style>
