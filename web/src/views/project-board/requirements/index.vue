<script setup>
import { computed, h, onMounted, reactive, ref } from 'vue'
import {
  NButton,
  NCascader,
  NCollapse,
  NCollapseItem,
  NDataTable,
  NDatePicker,
  NForm,
  NFormItem,
  NGrid,
  NGridItem,
  NInput,
  NInputNumber,
  NModal,
  NPopconfirm,
  NSelect,
  NSpace,
  NTag,
  NTooltip,
  useMessage,
} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import api from '@/api'
import { buildPinyinSearchText, pinyinOptionFilter } from '@/utils/pinyin-search'

defineOptions({ name: '需求管理' })

const message = useMessage()
const loading = ref(false)
const saving = ref(false)
const modalVisible = ref(false)
const modalAction = ref('add')
const rows = ref([])
const customerList = ref([])
const projectList = ref([])
const userList = ref([])
const popRegionList = ref([])
const popLocationList = ref([])
const activeView = ref('board')

const query = reactive({
  keyword: '',
  customer_id: null,
  project_id: null,
  status: null,
  priority: null,
  owner: null,
  service_type: null,
  region: null,
})

const form = reactive(createEmptyForm())
const targetPriceValue = computed({
  get: () => {
    if (form.target_price === '' || form.target_price === null || form.target_price === undefined) return null
    const value = Number(form.target_price)
    return Number.isFinite(value) ? value : null
  },
  set: (value) => {
    form.target_price = value === null || value === undefined ? '' : String(value)
  },
})

const statusOptions = [
  { label: '新线索', value: 'lead', icon: 'mdi:radar', tone: 'slate' },
  { label: '需求确认', value: 'qualified', icon: 'mdi:account-check-outline', tone: 'blue' },
  { label: '方案中', value: 'solution', icon: 'mdi:file-cog-outline', tone: 'cyan' },
  { label: '报价中', value: 'quotation', icon: 'mdi:file-document-edit-outline', tone: 'amber' },
  { label: '谈判中', value: 'negotiation', icon: 'mdi:handshake-outline', tone: 'orange' },
  { label: '已成交', value: 'won', icon: 'mdi:trophy-outline', tone: 'green' },
  { label: '已丢单', value: 'lost', icon: 'mdi:close-circle-outline', tone: 'red' },
  { label: '搁置', value: 'shelved', icon: 'mdi:archive-clock-outline', tone: 'slate' },
]

const priorityOptions = [
  { label: '低', value: 'low' },
  { label: '中', value: 'medium' },
  { label: '高', value: 'high' },
  { label: '紧急', value: 'urgent' },
]

const sourceOptions = [
  { label: '客户询盘', value: 'customer' },
  { label: '销售录入', value: 'sales' },
  { label: '支持/工单', value: 'support' },
  { label: '运维转入', value: 'ops' },
  { label: '市场活动', value: 'market' },
  { label: '内部转介', value: 'internal' },
  { label: '其他', value: 'other' },
]

const serviceTypeOptions = [
  { label: '机柜托管', value: 'colocation' },
  { label: '独立服务器', value: 'server' },
  { label: '带宽/传输', value: 'bandwidth' },
  { label: 'IP资源', value: 'ip' },
  { label: '云资源', value: 'cloud' },
  { label: '托管运维', value: 'managed' },
  { label: '其他', value: 'other' },
]

const currencyOptions = ['USD', 'CNY', 'HKD', 'EUR', 'GBP', 'SGD', 'JPY'].map((item) => ({
  label: item,
  value: item,
}))

const viewOptions = [
  { label: '看板', value: 'board' },
  { label: '列表', value: 'table' },
]

const customerOptions = computed(() =>
  customerList.value.map((item) => {
    const shortName = item.name || item.code || item.legal_name || '-'
    const subjectName = item.contract_company_name || ''
    const codeName = item.code && item.code !== shortName ? item.code : ''
    return {
      label: [shortName, subjectName].filter(Boolean).join(' / '),
      value: item.id,
      shortName,
      subjectName,
      codeName,
      searchText: buildPinyinSearchText([shortName, subjectName, codeName]),
    }
  })
)

const projectOptions = computed(() =>
  projectList.value.map((item) => ({
    label: item.code ? `${item.name} (${item.code})` : item.name,
    value: item.id,
    customer_id: item.customer_id,
  }))
)

const filteredProjectOptions = computed(() => {
  if (!query.customer_id && !form.customer_id) return projectOptions.value
  const customerId = form.customer_id || query.customer_id
  return projectOptions.value.filter((item) => item.customer_id === customerId)
})

const userOptions = computed(() =>
  userList.value.map((item) => {
    const name = item.alias || item.username || item.email
    return { label: name, value: name }
  })
)

const regionOptions = computed(() => buildRegionCascaderOptions())

const summary = computed(() => {
  const openRows = rows.value.filter((item) => !['won', 'lost', 'shelved'].includes(item.status))
  const expectedMrr = openRows.reduce((sum, item) => sum + Number(item.expected_mrr || 0), 0)
  const weightedMrr = openRows.reduce(
    (sum, item) => sum + Number(item.expected_mrr || 0) * (Number(item.probability || 0) / 100),
    0
  )
  return {
    total: rows.value.length,
    open: openRows.length,
    urgent: rows.value.filter((item) => item.priority === 'urgent').length,
    won: rows.value.filter((item) => item.status === 'won').length,
    expectedMrr,
    weightedMrr,
  }
})

const boardRows = computed(() =>
  statusOptions.map((status) => ({
    ...status,
    rows: rows.value.filter((item) => item.status === status.value),
  }))
)

const specFieldVisibility = computed(() => {
  const type = form.requirement_type
  const isColocation = type === 'colocation'
  const isServer = type === 'server'
  const isBandwidth = type === 'bandwidth'
  const isIp = type === 'ip'
  const isCloud = type === 'cloud'
  const isManaged = type === 'managed'
  const isOther = type === 'other'
  return {
    circuit: isBandwidth || isManaged || isOther,
    location: isColocation || isServer || isCloud || isManaged || isBandwidth || isOther,
    datacenter: isColocation || isServer || isCloud || isManaged || isBandwidth || isOther,
    bandwidth: isBandwidth || isColocation || isManaged || isOther,
    ip: isIp || isColocation || isServer || isCloud || isOther,
    cabinet: isColocation,
    server: isServer || isCloud || isManaged,
  }
})

const columns = computed(() => [
  {
    title: '客户需求',
    key: 'title',
    minWidth: 260,
    render(row) {
      return h('div', { class: 'requirement-title-cell' }, [
        h('button', { class: 'title-button', onClick: () => openEdit(row) }, row.title),
        h('span', { class: 'muted-text' }, [row.code, row.customer_legal_name || row.customer_name].filter(Boolean).join(' / ')),
      ])
    },
  },
  { title: '服务', key: 'requirement_type', width: 120, render: (row) => serviceTypeLabel(row.requirement_type) },
  { title: 'A/Z端', key: 'a_end', width: 210, render: (row) => [row.a_end, row.z_end].filter(Boolean).join(' -> ') || '-' },
  { title: '区域/机房', key: 'region', width: 170, render: (row) => [row.region, row.datacenter].filter(Boolean).join(' / ') || '-' },
  { title: '带宽/IP', key: 'bandwidth', width: 150, render: (row) => [row.bandwidth, row.ip_count ? `${row.ip_count} IP` : ''].filter(Boolean).join(' / ') || '-' },
  {
    title: '阶段',
    key: 'status',
    width: 110,
    render: (row) => h(NTag, { size: 'small', type: statusTagType(row.status) }, () => statusLabel(row.status)),
  },
  {
    title: '优先级',
    key: 'priority',
    width: 100,
    render: (row) => h(NTag, { size: 'small', type: priorityTagType(row.priority) }, () => priorityLabel(row.priority)),
  },
  { title: '销售', key: 'owner', width: 110, render: (row) => row.owner || '-' },
  { title: '预计MRR', key: 'expected_mrr', width: 120, render: (row) => moneyText(row.expected_mrr, row.budget_currency) },
  { title: 'NRC', key: 'nrc_amount', width: 110, render: (row) => moneyText(row.nrc_amount, row.budget_currency) },
  { title: '概率', key: 'probability', width: 80, render: (row) => `${row.probability || 0}%` },
  { title: '下一步', key: 'next_action', width: 180, render: (row) => row.next_action || '-' },
  {
    title: '操作',
    key: 'actions',
    width: 136,
    fixed: 'right',
    render(row) {
      return h(NSpace, { size: 8 }, () => [
        h(
          NTooltip,
          null,
          {
            trigger: () =>
              h(
                NButton,
                { quaternary: true, circle: true, size: 'small', onClick: () => openEdit(row) },
                { icon: () => h(TheIcon, { icon: 'mdi:pencil-outline', size: 16 }) }
              ),
            default: () => '编辑',
          }
        ),
        h(
          NPopconfirm,
          { onPositiveClick: () => deleteRow(row) },
          {
            trigger: () =>
              h(
                NButton,
                { quaternary: true, circle: true, size: 'small', type: 'error' },
                { icon: () => h(TheIcon, { icon: 'mdi:trash-can-outline', size: 16 }) }
              ),
            default: () => '确认删除这条需求？',
          }
        ),
      ])
    },
  },
])

function createEmptyForm() {
  return {
    id: null,
    title: '',
    code: '',
    customer_id: null,
    project_id: null,
    source: 'customer',
    source_detail: '',
    requirement_type: 'colocation',
    status: 'lead',
    priority: 'medium',
    owner: '',
    requester: '',
    service_type: '',
    a_end: '',
    z_end: '',
    region: '',
    datacenter: '',
    bandwidth: '',
    ip_count: 0,
    cabinet_count: 0,
    server_count: 0,
    contract_term: '',
    budget_amount: null,
    budget_currency: 'USD',
    nrc_amount: null,
    expected_mrr: null,
    target_price: '',
    probability: 30,
    competitor: '',
    next_action: '',
    expected_at: null,
    planned_at: null,
    released_at: null,
    value_score: 50,
    effort_score: 20,
    confidence_score: 50,
    reach_score: 20,
    vote_count: 0,
    tags: [],
    related_links: [],
    description: '',
    acceptance_criteria: '',
    solution: '',
    sort_order: 0,
  }
}

function resetForm(row = null) {
  Object.assign(form, createEmptyForm(), row || {})
  form.tags = Array.isArray(form.tags) ? [...form.tags] : []
  form.related_links = Array.isArray(form.related_links) ? [...form.related_links] : []
  if (!form.service_type) form.service_type = form.requirement_type
}

async function loadRows() {
  loading.value = true
  try {
    const res = await api.requirementApi.list({
      page: 1,
      page_size: 500,
      ...query,
    })
    rows.value = res.data || []
  } finally {
    loading.value = false
  }
}

async function loadOptions() {
  const [customers, projects, users, regions, locations] = await Promise.all([
    api.getCompanyList({ page: 1, page_size: 9999, role: 1 }),
    api.projectApi.list({ page: 1, page_size: 9999 }),
    api.getUserList({ page: 1, page_size: 9999 }),
    api.assetApi.regions({ page: 1, page_size: 9999, status: true }),
    api.assetApi.locations({ page: 1, page_size: 9999, type: 1, status: true }),
  ])
  customerList.value = customers.data || []
  projectList.value = projects.data || []
  userList.value = users.data || []
  popRegionList.value = regions.data || []
  popLocationList.value = locations.data || []
}

function compactParts(parts) {
  const seen = new Set()
  return parts
    .map((item) => String(item || '').trim())
    .filter(Boolean)
    .filter((item) => {
      const key = item.toLowerCase()
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
}

function getBranch(children, label, value, searchParts = []) {
  let node = children.find((item) => item.value === value)
  if (!node) {
    node = {
      label,
      value,
      children: [],
      searchText: buildPinyinSearchText([label, value, ...searchParts]),
    }
    children.push(node)
  }
  return node
}

function makeRegionDisplay(region = {}) {
  const name = region.name || region.city || region.code || `POP-${region.id}`
  const code = region.code && region.code !== name ? region.code : ''
  return compactParts([code, name]).join(' - ') || '-'
}

function makeRegionValue(region = {}) {
  return compactParts([region.country, region.city, region.name || region.code]).join(' / ') || makeRegionDisplay(region)
}

function buildRegionCascaderOptions() {
  const roots = []
  const locationsByRegion = new Map()
  popLocationList.value.forEach((location) => {
    if (!location.region_id) return
    const list = locationsByRegion.get(location.region_id) || []
    list.push(location)
    locationsByRegion.set(location.region_id, list)
  })

  popRegionList.value.forEach((region) => {
    const country = String(region.country || '未设置国家').trim()
    const city = String(region.city || region.name || '未设置城市').trim()
    const countryNode = getBranch(roots, country, `country:${country}`, [region.code, region.name])
    const cityNode = getBranch(countryNode.children, city, `city:${country}:${city}`, [region.code, region.name])
    const regionLabel = makeRegionDisplay(region)
    const regionNode = getBranch(cityNode.children, regionLabel, `region:${region.id}`, [region.country, region.city, region.name, region.code])
    const regionValue = makeRegionValue(region)
    const locations = locationsByRegion.get(region.id) || []
    regionNode.children = [
      {
        label: '全部',
        value: regionValue,
        searchText: buildPinyinSearchText([regionValue, regionLabel, region.country, region.city, region.code]),
      },
      ...locations.map((location) => ({
        label: location.name || `机房-${location.id}`,
        value: compactParts([regionValue, location.name]).join(' / '),
        searchText: buildPinyinSearchText([regionValue, regionLabel, location.name, location.address, location.remark]),
      })),
    ]
  })

  return sortCascaderOptions(roots)
}

function sortCascaderOptions(options) {
  return options
    .sort((left, right) => String(left.label || '').localeCompare(String(right.label || ''), 'zh-Hans-CN'))
    .map((item) => ({
      ...item,
      children: item.children?.length ? sortCascaderOptions(item.children) : undefined,
    }))
}

function openAdd() {
  modalAction.value = 'add'
  resetForm()
  modalVisible.value = true
}

function openEdit(row) {
  modalAction.value = 'edit'
  resetForm(row)
  modalVisible.value = true
}

async function saveRow() {
  const title = String(form.title || '').trim()
  if (!title) {
    message.warning('请填写客户需求')
    return
  }
  saving.value = true
  try {
    const payload = { ...form, title }
    payload.service_type = payload.service_type || payload.requirement_type
    if (modalAction.value === 'add') {
      delete payload.code
    }
    await api.requirementApi[modalAction.value === 'add' ? 'create' : 'update'](payload)
    message.success(modalAction.value === 'add' ? '需求已创建' : '需求已更新')
    modalVisible.value = false
    await loadRows()
  } finally {
    saving.value = false
  }
}

async function changeStatus(row, status) {
  if (row.status === status) return
  await api.requirementApi.updateStatus({ id: row.id, status, sort_order: row.sort_order || 0 })
  row.status = status
  message.success('阶段已更新')
  await loadRows()
}

async function deleteRow(row) {
  await api.requirementApi.delete({ requirement_id: row.id })
  message.success('需求已删除')
  await loadRows()
}

function statusLabel(value) {
  return statusOptions.find((item) => item.value === value)?.label || value
}

function priorityLabel(value) {
  return priorityOptions.find((item) => item.value === value)?.label || value
}

function sourceLabel(value) {
  return sourceOptions.find((item) => item.value === value)?.label || value
}

function renderCustomerOptionLabel(option) {
  return h(
    'div',
    {
      style: {
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '12px',
        minWidth: 0,
        width: '100%',
      },
    },
    [
      h(
        'span',
        {
          style: {
            flex: '0 0 auto',
            maxWidth: '42%',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            fontWeight: 600,
            color: '#111827',
          },
        },
        option.shortName || option.label
      ),
      option.subjectName
        ? h(
            'span',
            {
              style: {
                flex: '1 1 auto',
                minWidth: 0,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                color: '#64748b',
                textAlign: 'right',
              },
            },
            option.subjectName
          )
        : null,
    ]
  )
}

function serviceTypeLabel(value) {
  return serviceTypeOptions.find((item) => item.value === value)?.label || value || '-'
}

function statusTagType(value) {
  const map = {
    won: 'success',
    lost: 'error',
    negotiation: 'warning',
    quotation: 'warning',
    solution: 'info',
    qualified: 'info',
  }
  return map[value] || 'default'
}

function priorityTagType(value) {
  const map = {
    urgent: 'error',
    high: 'warning',
    medium: 'info',
    low: 'default',
  }
  return map[value] || 'default'
}

function moneyText(value, currency = 'USD') {
  const amount = Number(value || 0)
  if (!amount) return '-'
  return `${currency || 'USD'} ${amount.toLocaleString()}`
}

function requirementSpec(row) {
  return [
    row.bandwidth,
    row.a_end && row.z_end ? `${row.a_end} -> ${row.z_end}` : '',
    row.ip_count ? `${row.ip_count} IP` : '',
    row.cabinet_count ? `${row.cabinet_count} 柜` : '',
    row.server_count ? `${row.server_count} 台` : '',
  ]
    .filter(Boolean)
    .join(' / ')
}

onMounted(async () => {
  await Promise.all([loadOptions(), loadRows()])
})
</script>

<template>
  <CommonPage show-footer title="需求管理">
    <template #action>
      <NSpace align="center">
        <NSelect v-model:value="activeView" size="small" :options="viewOptions" style="width: 120px" />
        <NButton type="primary" round @click="openAdd">
          <TheIcon icon="material-symbols:add" :size="18" class="mr-5" />
          新增需求
        </NButton>
      </NSpace>
    </template>

    <div class="requirement-page">
      <div class="requirement-toolbar">
        <NInput v-model:value="query.keyword" clearable placeholder="搜索客户、需求、机房、带宽、下一步" @keyup.enter="loadRows" />
        <NSelect
          v-model:value="query.customer_id"
          clearable
          filterable
          placeholder="客户 / 签约主体"
          :options="customerOptions"
          :filter="pinyinOptionFilter"
          :render-label="renderCustomerOptionLabel"
        />
        <NSelect v-model:value="query.status" clearable placeholder="销售阶段" :options="statusOptions" />
        <NSelect v-model:value="query.service_type" clearable placeholder="服务类型" :options="serviceTypeOptions" />
        <NCascader
          v-model:value="query.region"
          clearable
          filterable
          placeholder="POP区域"
          :options="regionOptions"
        />
        <NSelect v-model:value="query.owner" clearable filterable placeholder="负责人" :options="userOptions" />
        <NButton type="primary" secondary @click="loadRows">查询</NButton>
      </div>

      <div class="summary-strip">
        <div class="summary-item">
          <span>需求总数</span>
          <strong>{{ summary.total }}</strong>
        </div>
        <div class="summary-item">
          <span>跟进中</span>
          <strong>{{ summary.open }}</strong>
        </div>
        <div class="summary-item">
          <NTooltip trigger="hover">
            <template #trigger>
              <span class="metric-help">预计MRR</span>
            </template>
            当前筛选范围内所有需求的预计月经常性收入合计，不考虑成交概率。
          </NTooltip>
          <strong>{{ moneyText(summary.expectedMrr, 'USD') }}</strong>
        </div>
        <div class="summary-item">
          <NTooltip trigger="hover">
            <template #trigger>
              <span class="metric-help">加权MRR</span>
            </template>
            预计MRR按每条需求的成交概率加权后的金额，用于估算销售管道的可实现月收入。
          </NTooltip>
          <strong>{{ moneyText(summary.weightedMrr, 'USD') }}</strong>
        </div>
      </div>

      <div v-if="activeView === 'board'" class="requirement-board" :class="{ loading }">
        <section v-for="column in boardRows" :key="column.value" class="board-column">
          <header>
            <span class="column-title">
              <TheIcon :icon="column.icon" :size="17" />
              {{ column.label }}
            </span>
            <NTag size="small" round>{{ column.rows.length }}</NTag>
          </header>
          <div class="column-body">
            <button
              v-for="item in column.rows"
              :key="item.id"
              class="requirement-card"
              type="button"
              @click="openEdit(item)"
            >
              <div class="card-head">
                <strong>{{ item.title }}</strong>
                <NTag size="small" :type="priorityTagType(item.priority)">{{ priorityLabel(item.priority) }}</NTag>
              </div>
              <div class="card-meta">
                <span>{{ item.customer_legal_name || item.customer_name || '未关联客户' }}</span>
                <span>{{ serviceTypeLabel(item.requirement_type) }} · {{ item.region || '未定区域' }}</span>
                <span>{{ item.a_end && item.z_end ? `${item.a_end} -> ${item.z_end}` : item.datacenter || '未定端点/机房' }}</span>
              </div>
              <div class="card-spec">{{ requirementSpec(item) || '暂无容量规格' }}</div>
              <div class="card-foot">
                <span>{{ item.owner || '未分配销售' }}</span>
                <span>{{ moneyText(item.expected_mrr, item.budget_currency) }} · {{ item.probability || 0 }}%</span>
              </div>
              <div class="card-next">{{ item.next_action || '未设置下一步' }}</div>
              <div class="status-actions" @click.stop>
                <NSelect
                  :value="item.status"
                  size="tiny"
                  :options="statusOptions"
                  @update:value="(value) => changeStatus(item, value)"
                />
              </div>
            </button>
          </div>
        </section>
      </div>

      <NDataTable
        v-else
        class="requirement-table"
        size="small"
        striped
        :loading="loading"
        :columns="columns"
        :data="rows"
        :pagination="{ pageSize: 20, showSizePicker: true, pageSizes: [10, 20, 50, 100] }"
        :scroll-x="1500"
      />
    </div>

    <NModal
      v-model:show="modalVisible"
      preset="card"
      :title="modalAction === 'add' ? '新增需求' : '编辑需求'"
      class="requirement-modal"
      style="width: min(1120px, calc(100vw - 40px))"
      :bordered="false"
    >
      <NForm class="requirement-form" label-placement="top" :model="form">
        <section class="requirement-form-section primary">
          <div class="section-heading">
            <strong>需求概览</strong>
            <span>先记录销售能识别的客户诉求和归属关系</span>
          </div>
          <NGrid :cols="3" :x-gap="14" :y-gap="4" responsive="screen">
            <NGridItem :span="modalAction === 'edit' ? 2 : 3">
              <NFormItem label="客户需求" required>
                <NInput v-model:value="form.title" placeholder="例如：香港 10G 带宽 + /24 IPv4 资源" />
              </NFormItem>
            </NGridItem>
            <NGridItem v-if="modalAction === 'edit'">
              <NFormItem label="需求编号">
                <NInput v-model:value="form.code" disabled placeholder="保存后自动生成" />
              </NFormItem>
            </NGridItem>
            <NGridItem>
              <NFormItem label="客户">
                <NSelect
                  v-model:value="form.customer_id"
                  clearable
                  filterable
                  placeholder="客户 / 签约主体"
                  :options="customerOptions"
                  :filter="pinyinOptionFilter"
                  :render-label="renderCustomerOptionLabel"
                />
              </NFormItem>
            </NGridItem>
            <NGridItem>
              <NFormItem label="关联项目">
                <NSelect v-model:value="form.project_id" clearable filterable placeholder="选择关联项目" :options="filteredProjectOptions" />
              </NFormItem>
            </NGridItem>
            <NGridItem>
              <NFormItem label="客户联系人">
                <NInput v-model:value="form.requester" placeholder="客户侧联系人" />
              </NFormItem>
            </NGridItem>
          </NGrid>
        </section>

        <section class="requirement-form-section">
          <div class="section-heading">
            <strong>销售跟进</strong>
            <span>阶段、来源和负责人决定看板流转</span>
          </div>
          <NGrid :cols="4" :x-gap="14" :y-gap="4" responsive="screen">
            <NGridItem>
              <NFormItem label="销售">
                <NSelect v-model:value="form.owner" clearable filterable tag placeholder="负责人" :options="userOptions" />
              </NFormItem>
            </NGridItem>
            <NGridItem>
              <NFormItem label="销售阶段">
                <NSelect v-model:value="form.status" :options="statusOptions" />
              </NFormItem>
            </NGridItem>
            <NGridItem>
              <NFormItem label="优先级">
                <NSelect v-model:value="form.priority" :options="priorityOptions" />
              </NFormItem>
            </NGridItem>
            <NGridItem>
              <NFormItem label="来源">
                <NSelect v-model:value="form.source" :options="sourceOptions" />
              </NFormItem>
            </NGridItem>
          </NGrid>
        </section>

        <section class="requirement-form-section">
          <div class="section-heading">
            <strong>资源规格</strong>
            <span>按服务类型展示相关 IDC 字段</span>
          </div>
          <NGrid :cols="3" :x-gap="14" :y-gap="4" responsive="screen">
            <NGridItem>
              <NFormItem label="服务类型">
                <NSelect v-model:value="form.requirement_type" :options="serviceTypeOptions" />
              </NFormItem>
            </NGridItem>
            <NGridItem v-if="specFieldVisibility.location">
              <NFormItem label="区域 / POP">
                <NCascader
                  v-model:value="form.region"
                  clearable
                  filterable
                  placeholder="国家 / 城市 / POP点"
                  :options="regionOptions"
                />
              </NFormItem>
            </NGridItem>
            <NGridItem v-if="specFieldVisibility.datacenter">
              <NFormItem label="机房/POP">
                <NInput v-model:value="form.datacenter" placeholder="例如 HK2 / SG1 / LA" />
              </NFormItem>
            </NGridItem>
            <NGridItem v-if="specFieldVisibility.circuit">
              <NFormItem label="A端">
                <NInput v-model:value="form.a_end" placeholder="例如 Equinix HK2" />
              </NFormItem>
            </NGridItem>
            <NGridItem v-if="specFieldVisibility.circuit">
              <NFormItem label="Z端">
                <NInput v-model:value="form.z_end" placeholder="例如 Global Switch AMS" />
              </NFormItem>
            </NGridItem>
            <NGridItem v-if="specFieldVisibility.bandwidth">
              <NFormItem label="带宽">
                <NInput v-model:value="form.bandwidth" placeholder="例如 10G commit / 95th" />
              </NFormItem>
            </NGridItem>
            <NGridItem v-if="specFieldVisibility.ip">
              <NFormItem label="IP数量">
                <NInputNumber v-model:value="form.ip_count" :min="0" />
              </NFormItem>
            </NGridItem>
            <NGridItem v-if="specFieldVisibility.cabinet">
              <NFormItem label="机柜数">
                <NInputNumber v-model:value="form.cabinet_count" :min="0" />
              </NFormItem>
            </NGridItem>
            <NGridItem v-if="specFieldVisibility.server">
              <NFormItem label="服务器数">
                <NInputNumber v-model:value="form.server_count" :min="0" />
              </NFormItem>
            </NGridItem>
          </NGrid>
        </section>

        <section class="requirement-form-section">
          <div class="section-heading">
            <strong>商务测算</strong>
            <span>用于销售预测、报价和后续成交复盘</span>
          </div>
          <NGrid :cols="4" :x-gap="14" :y-gap="4" responsive="screen">
            <NGridItem>
              <NFormItem label="币种">
                <NSelect v-model:value="form.budget_currency" filterable tag :options="currencyOptions" />
              </NFormItem>
            </NGridItem>
            <NGridItem>
              <NFormItem label="预算">
                <NInputNumber v-model:value="form.budget_amount" :min="0" />
              </NFormItem>
            </NGridItem>
            <NGridItem>
              <NFormItem label="目标价">
                <NInputNumber v-model:value="targetPriceValue" :min="0" clearable placeholder="请输入目标价格">
                  <template #prefix>{{ form.budget_currency || 'USD' }}</template>
                </NInputNumber>
              </NFormItem>
            </NGridItem>
            <NGridItem>
              <NFormItem label="合同周期">
                <NInput v-model:value="form.contract_term" placeholder="例如 12个月" />
              </NFormItem>
            </NGridItem>
            <NGridItem>
              <NFormItem label="预计MRR">
                <NInputNumber v-model:value="form.expected_mrr" :min="0" />
              </NFormItem>
            </NGridItem>
            <NGridItem>
              <NFormItem label="预计NRC">
                <NInputNumber v-model:value="form.nrc_amount" :min="0" />
              </NFormItem>
            </NGridItem>
            <NGridItem>
              <NFormItem label="成交概率">
                <NInputNumber v-model:value="form.probability" :min="0" :max="100" />
              </NFormItem>
            </NGridItem>
            <NGridItem>
              <NFormItem label="期望交付">
                <NDatePicker v-model:formatted-value="form.expected_at" clearable type="date" value-format="yyyy-MM-dd" />
              </NFormItem>
            </NGridItem>
            <NGridItem :span="2">
              <NFormItem label="竞争对手">
                <NInput v-model:value="form.competitor" placeholder="例如 Equinix / Zenlayer / Cogent" />
              </NFormItem>
            </NGridItem>
            <NGridItem :span="2">
              <NFormItem label="下一步">
                <NInput v-model:value="form.next_action" placeholder="例如：本周五前给客户 HK 10G 方案和报价" />
              </NFormItem>
            </NGridItem>
          </NGrid>
        </section>

        <section class="requirement-form-section muted">
          <NCollapse class="requirement-extra" arrow-placement="right">
            <NCollapseItem title="更多信息" name="extra">
            <NFormItem label="来源说明">
              <NInput v-model:value="form.source_detail" placeholder="例如：飞书表格、客户会议、WhatsApp、工单编号" />
            </NFormItem>
            <NFormItem label="标签">
              <NSelect v-model:value="form.tags" multiple filterable tag placeholder="客户等级、区域、资源类型、竞品等" :options="[]" />
            </NFormItem>
            <NFormItem label="相关链接">
              <NSelect v-model:value="form.related_links" multiple filterable tag placeholder="飞书文档、报价单、工单或客户沟通记录" :options="[]" />
            </NFormItem>
            <NFormItem label="需求描述">
              <NInput v-model:value="form.description" type="textarea" :autosize="{ minRows: 3, maxRows: 6 }" />
            </NFormItem>
            <NFormItem label="交付/验收">
              <NInput v-model:value="form.acceptance_criteria" type="textarea" :autosize="{ minRows: 2, maxRows: 5 }" />
            </NFormItem>
            <NFormItem label="方案备注">
              <NInput v-model:value="form.solution" type="textarea" :autosize="{ minRows: 2, maxRows: 5 }" />
            </NFormItem>
            </NCollapseItem>
          </NCollapse>
        </section>
      </NForm>

      <template #footer>
        <NSpace justify="space-between" align="center">
          <span class="modal-hint">
            {{ sourceLabel(form.source) }} / {{ serviceTypeLabel(form.requirement_type) }} / {{ statusLabel(form.status) }}
          </span>
          <NSpace>
            <NButton @click="modalVisible = false">取消</NButton>
            <NButton type="primary" :loading="saving" @click="saveRow">保存</NButton>
          </NSpace>
        </NSpace>
      </template>
    </NModal>

  </CommonPage>
</template>

<style scoped>
.requirement-page {
  padding: 16px;
  background: #fff;
  border: 1px solid #e7ebf2;
  border-radius: 8px;
}

.requirement-toolbar {
  display: grid;
  grid-template-columns: minmax(220px, 2fr) repeat(5, minmax(130px, 1fr)) auto;
  gap: 10px;
  align-items: center;
}

.summary-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(150px, 1fr));
  gap: 10px;
  margin: 14px 0;
}

.summary-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 56px;
  padding: 10px 14px;
  border: 1px solid #e4eaf3;
  border-radius: 8px;
  background: #f8fafc;
}

.summary-item span {
  color: #64748b;
}

.summary-item .metric-help {
  cursor: help;
  border-bottom: 1px dashed #94a3b8;
}

.summary-item strong {
  font-size: 21px;
  color: #0f172a;
}

.requirement-extra {
  padding: 0 2px;
}

.requirement-form {
  display: grid;
  gap: 12px;
}

.requirement-form-section {
  padding: 14px 14px 4px;
  border: 1px solid #e6edf6;
  border-radius: 8px;
  background: #fbfcfe;
}

.requirement-form-section.primary {
  background: #f8fbff;
  border-color: #dce9fb;
}

.requirement-form-section.muted {
  padding-bottom: 10px;
  background: #fff;
}

.section-heading {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 12px;
}

.section-heading strong {
  color: #0f172a;
  font-size: 14px;
}

.section-heading span {
  color: #64748b;
  font-size: 12px;
}

.requirement-form :deep(.n-input-number),
.requirement-form :deep(.n-date-picker),
.requirement-form :deep(.n-cascader) {
  width: 100%;
}

.requirement-modal :deep(.n-card-header) {
  padding-bottom: 8px;
}

.requirement-modal :deep(.n-card__content) {
  max-height: min(76vh, 760px);
  overflow-y: auto;
}

.requirement-board {
  display: grid;
  grid-template-columns: repeat(4, minmax(280px, 1fr));
  gap: 12px;
  overflow-x: auto;
  padding-bottom: 4px;
}

.board-column {
  min-width: 280px;
  border: 1px solid #dfe7f1;
  border-radius: 8px;
  background: #f8fafc;
}

.board-column header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 48px;
  padding: 0 12px;
  border-bottom: 1px solid #e5eaf2;
}

.column-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-weight: 700;
  color: #1f2937;
}

.column-body {
  display: grid;
  gap: 10px;
  min-height: 180px;
  padding: 10px;
}

.requirement-card {
  width: 100%;
  min-height: 188px;
  padding: 12px;
  text-align: left;
  border: 1px solid #dce5ef;
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
}

.requirement-card:hover {
  border-color: #8bb8ff;
  box-shadow: 0 8px 18px rgba(37, 99, 235, 0.08);
}

.card-head,
.card-foot {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.card-head strong {
  line-height: 1.35;
  color: #0f172a;
}

.card-meta {
  display: grid;
  gap: 2px;
  margin-top: 8px;
  color: #64748b;
  font-size: 12px;
}

.card-spec {
  min-height: 24px;
  margin-top: 10px;
  color: #334155;
  font-size: 13px;
}

.card-foot {
  margin-top: 8px;
  color: #334155;
  font-size: 12px;
}

.card-next {
  min-height: 28px;
  margin-top: 8px;
  color: #475569;
  line-height: 1.35;
}

.status-actions {
  margin-top: 10px;
}

.requirement-table {
  margin-top: 8px;
}

.requirement-title-cell {
  display: grid;
  gap: 2px;
}

.title-button {
  padding: 0;
  text-align: left;
  font-weight: 700;
  color: #0f172a;
  background: transparent;
  border: 0;
  cursor: pointer;
}

.title-button:hover {
  color: #2563eb;
}

.muted-text,
.modal-hint {
  color: #64748b;
  font-size: 12px;
}

.sync-result {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.sync-result span {
  padding: 4px 10px;
  color: #334155;
  background: #f1f5f9;
  border: 1px solid #dbe4ee;
  border-radius: 8px;
}

@media (max-width: 1200px) {
  .requirement-toolbar {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .summary-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .requirement-page {
    padding: 12px;
  }

  .requirement-toolbar,
  .summary-strip {
    grid-template-columns: 1fr;
  }

  .requirement-board {
    grid-template-columns: minmax(280px, 1fr);
  }
}
</style>
