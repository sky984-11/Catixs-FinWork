<script setup>
import { computed, h, onMounted, reactive, ref } from 'vue'
import {
  NButton,
  NDataTable,
  NForm,
  NFormItem,
  NGrid,
  NGridItem,
  NInput,
  NInputNumber,
  NModal,
  NPagination,
  NPopconfirm,
  NSelect,
  NSpace,
  NSwitch,
  NTag,
  NTooltip,
} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import api from '@/api'
import { renderIcon } from '@/utils'

const loading = ref(false)
const rows = ref([])
const siteOptions = ref([])
const summary = ref({ count: 0, active: 0, by_type: [] })
const DEFAULT_QUOTE_TYPE = 'ipt'

const query = reactive({
  keyword: '',
  quote_type: DEFAULT_QUOTE_TYPE,
  region: '',
  status: null,
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  itemCount: 0,
})

const quoteModal = reactive({
  show: false,
  submitting: false,
  form: createQuoteForm(),
})

const quoteTypeOptions = [
  { label: '服务器', value: 'server' },
  { label: 'IPT', value: 'ipt' },
  { label: 'DIA', value: 'dia' },
  { label: '传输', value: 'transport' },
]

const statusOptions = [
  { label: '上架', value: 1 },
  { label: '下架', value: 0 },
]

const currencyOptions = [
  { label: 'USD', value: 'USD' },
  { label: 'CNY', value: 'CNY' },
  { label: 'HKD', value: 'HKD' },
  { label: 'SGD', value: 'SGD' },
  { label: 'GBP', value: 'GBP' },
  { label: 'EUR', value: 'EUR' },
]

const modalTitle = computed(() => (quoteModal.form.id ? '编辑报价' : '新增报价'))
const activeFormType = computed(() => quoteModal.form.quote_type || 'server')

const activeTypeLabel = computed(() => {
  if (!query.quote_type) return '全部报价'
  return quoteTypeOptions.find((item) => item.value === query.quote_type)?.label || '报价'
})
const regionFilterPlaceholder = computed(() => (['ipt', 'dia'].includes(query.quote_type) ? '站点A' : '地区'))
const mergedSiteOptions = computed(() => {
  const values = new Set(siteOptions.value.map((item) => item.value).filter(Boolean))
  ;[query.region, quoteModal.form.site_a].forEach((value) => {
    if (value) values.add(value)
  })
  return Array.from(values)
    .sort()
    .map((value) => ({ label: value, value }))
})

const quoteTypeFields = {
  server: ['cpu_model', 'cpu_cores', 'memory', 'disk', 'bandwidth'],
  ipt: [
    'service_resource',
    'service_name',
    'provider',
    'bandwidth',
    'burst',
    'site_a',
    'protection',
    'xc_cabling',
    'contract_terms',
    'nrc',
    'mrc',
    'usd_per_mbps_nrc',
    'usd_per_mbps_mrc',
    'note',
  ],
  dia: [
    'service_resource',
    'service_name',
    'provider',
    'bandwidth',
    'burst',
    'site_a',
    'protection',
    'xc_cabling',
    'contract_terms',
    'nrc',
    'mrc',
    'usd_per_mbps_nrc',
    'usd_per_mbps_mrc',
    'note',
  ],
  transport: ['service_name', 'bandwidth', 'provider'],
}

const fieldMeta = {
  service_resource: {
    label: {
      ipt: '资源类型',
      dia: '资源类型',
    },
    placeholder: {
      ipt: 'Onnet / Offnet',
      dia: 'Onnet / Offnet',
    },
  },
  service_name: {
    label: {
      server: '产品/服务名称',
      ipt: '服务类型',
      dia: '服务类型',
      transport: '传输线路',
    },
    placeholder: {
      server: '可选',
      ipt: 'IP Transit',
      dia: 'DIA',
      transport: 'HK-LA / CN-HK 传输',
    },
  },
  bandwidth: {
    label: {
      server: '带宽',
      ipt: '带宽',
      dia: '带宽',
      transport: '传输容量',
    },
    placeholder: {
      server: '2G / 10G',
      ipt: '10G / 100G',
      dia: '100M / 1G',
      transport: '10G / 100G',
    },
  },
  burst: {
    label: {
      ipt: '突发带宽',
      dia: '突发带宽',
    },
    placeholder: {
      ipt: 'N/A / 100G / 200G',
      dia: 'N/A',
    },
  },
  site_a: {
    label: {
      ipt: '站点A',
      dia: '站点A',
    },
    placeholder: {
      ipt: 'Equinix HK1 / SG1 / LD8',
      dia: 'Equinix HK2',
    },
  },
  protection: {
    label: {
      ipt: '保护方式',
      dia: '保护方式',
    },
    placeholder: {
      ipt: 'NA',
      dia: 'NA',
    },
  },
  xc_cabling: {
    label: {
      ipt: '交叉/布线',
      dia: '交叉/布线',
    },
    placeholder: {
      ipt: 'No / Yes',
      dia: 'No / Yes',
    },
  },
  contract_terms: {
    label: {
      ipt: '合同周期',
      dia: '合同周期',
    },
    placeholder: {
      ipt: '12 Months',
      dia: '12 Months',
    },
  },
  nrc: {
    label: {
      ipt: '一次性费用',
      dia: '一次性费用',
    },
  },
  mrc: {
    label: {
      ipt: '月费',
      dia: '月费',
    },
  },
  usd_per_mbps_nrc: {
    label: {
      ipt: '每Mbps一次性费用',
      dia: '每Mbps一次性费用',
    },
    placeholder: {
      ipt: '0 / 0.16 USD/Mbps',
      dia: '0',
    },
  },
  usd_per_mbps_mrc: {
    label: {
      ipt: '每Mbps月费',
      dia: '每Mbps月费',
    },
    placeholder: {
      ipt: '0.3 / 0.075 / 1.5 USD/Mbps',
      dia: '',
    },
  },
  provider: {
    label: {
      server: '供应商',
      ipt: '供应商',
      dia: '供应商',
      transport: '线路供应商',
    },
    placeholder: {
      server: '供应商/上游',
      ipt: 'Cogent / RETN / NTT Communications',
      dia: 'HK EIE',
      transport: '传输供应商',
    },
  },
  note: {
    label: {
      ipt: '备注',
      dia: '备注',
    },
    placeholder: {
      ipt: 'Cct# / USD 0.3/M, Port 100G',
      dia: '备注',
    },
  },
}

const columns = computed(() => columnDefinitions.filter((column) => !column.show || column.show()))
const tableScrollX = computed(() =>
  columns.value.reduce((total, column) => total + Number(column.width || column.minWidth || 130), 0)
)
const isNetworkTable = computed(() => ['ipt', 'dia'].includes(query.quote_type))

const columnDefinitions = [
  {
    title: () =>
      h('div', { class: 'quote-type-head' }, [
        h('span', '类型'),
        h(NSelect, {
          value: query.quote_type,
          options: quoteTypeOptions,
          size: 'tiny',
          consistentMenuWidth: false,
          class: 'quote-type-select',
          onUpdateValue: handleTypeChange,
        }),
      ]),
    key: 'quote_type',
    width: 138,
    fixed: 'left',
    render(row) {
      return h(NTag, { type: quoteTypeTag(row.quote_type), round: true, bordered: false }, { default: () => quoteTypeLabel(row.quote_type) })
    },
  },
  { title: '地区', key: 'region', width: 110, fixed: 'left', ellipsis: { tooltip: true }, show: () => !isNetworkTable.value },
  { title: '资源类型', key: 'service_resource', width: 130, ellipsis: { tooltip: true }, show: () => isNetworkTable.value },
  {
    title: () => (query.quote_type && query.quote_type !== 'server' ? typeFieldLabel('service_name', query.quote_type) : 'CPU型号'),
    key: 'cpu_model',
    minWidth: 150,
    ellipsis: { tooltip: true },
    show: () => !query.quote_type || query.quote_type === 'server',
    render: (row) => row.cpu_model || row.service_name || '-',
  },
  { title: '供应商', key: 'provider', minWidth: 150, ellipsis: { tooltip: true }, show: () => isNetworkTable.value },
  { title: '逻辑核心数', key: 'cpu_cores', width: 110, ellipsis: { tooltip: true }, show: () => !query.quote_type || query.quote_type === 'server' },
  { title: '内存', key: 'memory', width: 100, ellipsis: { tooltip: true }, show: () => !query.quote_type || query.quote_type === 'server' },
  { title: '硬盘', key: 'disk', minWidth: 160, ellipsis: { tooltip: true }, show: () => !query.quote_type || query.quote_type === 'server' },
  { title: () => typeFieldLabel('bandwidth', query.quote_type || 'server'), key: 'bandwidth', width: 120, ellipsis: { tooltip: true } },
  { title: '突发带宽', key: 'burst', width: 110, ellipsis: { tooltip: true }, show: () => isNetworkTable.value },
  { title: '站点A', key: 'site_a', minWidth: 150, ellipsis: { tooltip: true }, show: () => isNetworkTable.value },
  { title: '币种', key: 'currency', width: 95, ellipsis: { tooltip: true }, show: () => isNetworkTable.value },
  { title: '一次性费用', key: 'nrc', width: 110, align: 'right', sorter: true, render: (row) => formatNumber(row.nrc), show: () => isNetworkTable.value },
  { title: '月费', key: 'mrc', width: 96, align: 'right', sorter: true, render: (row) => formatNumber(row.mrc), show: () => isNetworkTable.value },
  { title: '每Mbps一次性费用', key: 'usd_per_mbps_nrc', width: 150, align: 'right', ellipsis: { tooltip: true }, show: () => isNetworkTable.value },
  { title: '每Mbps月费', key: 'usd_per_mbps_mrc', width: 130, align: 'right', render: (row) => formatRate(row.usd_per_mbps_mrc), show: () => isNetworkTable.value },
  { title: '成本价', key: 'cost_price', width: 110, align: 'right', sorter: true, render: (row) => formatMoney(row.cost_price, row.currency), show: () => !isNetworkTable.value },
  { title: '目标价', key: 'target_price', width: 110, align: 'right', sorter: true, render: (row) => formatMoney(row.target_price, row.currency), show: () => !isNetworkTable.value },
  { title: '报价', key: 'sale_price', width: 110, align: 'right', sorter: true, render: (row) => h('strong', formatMoney(row.sale_price, row.currency)), show: () => !isNetworkTable.value },
  { title: '毛利', key: 'profit', width: 110, align: 'right', render: renderProfit, show: () => !isNetworkTable.value },
  { title: () => typeFieldLabel('provider', query.quote_type || 'server'), key: 'provider', minWidth: 120, ellipsis: { tooltip: true }, show: () => query.quote_type && query.quote_type !== 'server' && !isNetworkTable.value },
  { title: '保护方式', key: 'protection', width: 110, ellipsis: { tooltip: true }, show: () => isNetworkTable.value },
  { title: '交叉/布线', key: 'xc_cabling', width: 115, ellipsis: { tooltip: true }, show: () => isNetworkTable.value },
  { title: '合同周期', key: 'contract_terms', width: 135, ellipsis: { tooltip: true }, show: () => isNetworkTable.value },
  { title: '备注', key: 'remark', minWidth: 220, ellipsis: { tooltip: true }, render: (row) => row.remark || row.note || '-' },
  {
    title: '状态',
    key: 'status',
    width: 86,
    align: 'center',
    render(row) {
      const active = Number(row.status) === 1
      return h(NTag, { type: active ? 'success' : 'default', round: true, bordered: false }, { default: () => (active ? '上架' : '下架') })
    },
  },
  {
    title: '操作',
    key: 'actions',
    width: 108,
    fixed: 'right',
    align: 'center',
    render(row) {
      return h(NSpace, { justify: 'center', size: 6 }, () => [
        renderIconButton('编辑', 'mdi:pencil-outline', { onClick: () => openQuote(row) }),
        h(
          NPopconfirm,
          { onPositiveClick: () => deleteQuote(row) },
          {
            trigger: () => renderIconButton('删除', 'mdi:trash-can-outline', { type: 'error' }),
            default: () => '确定删除这条报价吗？',
          }
        ),
      ])
    },
  },
]

function createQuoteForm() {
  return {
    id: null,
    quote_type: 'server',
    service_resource: '',
    region: '',
    service_name: '',
    cpu_model: '',
    cpu_cores: '',
    memory: '',
    disk: '',
    bandwidth: '',
    burst: '',
    traffic: '',
    site_a: '',
    protection: 'NA',
    xc_cabling: 'No',
    contract_terms: '12 Months',
    delivery_time: '立即',
    ip_count: '',
    provider: '',
    currency: 'USD',
    nrc: 0,
    mrc: 0,
    usd_per_mbps_nrc: '',
    usd_per_mbps_mrc: 0,
    cost_price: 0,
    target_price: 0,
    sale_price: 0,
    status: 1,
    sort: 0,
    note: '',
    remark: '',
  }
}

function renderIconButton(label, icon, props = {}) {
  const { type, ...buttonProps } = props
  return h(
    NTooltip,
    { trigger: 'hover', placement: 'top' },
    {
      trigger: () =>
        h(
          NButton,
          {
            size: 'small',
            type,
            secondary: true,
            circle: true,
            class: 'icon-only-btn',
            ...buttonProps,
          },
          { icon: renderIcon(icon, { size: 16 }) }
        ),
      default: () => label,
    }
  )
}

async function loadQuotes() {
  loading.value = true
  try {
    const res = await api.financeQuoteApi.list({
      page: pagination.page,
      page_size: pagination.pageSize,
      keyword: query.keyword || undefined,
      quote_type: query.quote_type || undefined,
      region: query.region || undefined,
      status: query.status ?? undefined,
    })
    rows.value = res.data || []
    pagination.itemCount = res.total || 0
    summary.value = res.summary || { count: 0, active: 0, by_type: [] }
  } finally {
    loading.value = false
  }
}

async function loadSiteOptions(type = query.quote_type) {
  const res = await api.financeQuoteApi.siteOptions({
    quote_type: ['ipt', 'dia'].includes(type) ? type : undefined,
  })
  siteOptions.value = res.data || []
}

function handleSearch() {
  pagination.page = 1
  loadQuotes()
}

function handleTypeChange(value) {
  query.quote_type = value || DEFAULT_QUOTE_TYPE
  query.region = ''
  pagination.page = 1
  loadSiteOptions()
  loadQuotes()
}

function handleFormTypeChange(value) {
  quoteModal.form.quote_type = value || 'server'
  loadSiteOptions(quoteModal.form.quote_type)
}

function resetQuery() {
  query.keyword = ''
  query.quote_type = DEFAULT_QUOTE_TYPE
  query.region = ''
  query.status = null
  handleSearch()
}

function isQuoteFieldVisible(field, type = activeFormType.value) {
  return (quoteTypeFields[type] || quoteTypeFields.server).includes(field)
}

function typeFieldLabel(field, type = activeFormType.value) {
  return fieldMeta[field]?.label?.[type] || fieldMeta[field]?.label?.server || ''
}

function typeFieldPlaceholder(field, type = activeFormType.value) {
  return fieldMeta[field]?.placeholder?.[type] || fieldMeta[field]?.placeholder?.server || ''
}

function openQuote(row = null) {
  quoteModal.form = row
    ? {
        ...createQuoteForm(),
        ...row,
        usd_per_mbps_mrc: parseRateNumber(row.usd_per_mbps_mrc),
        remark: row.remark || row.note || '',
        status: Number(row.status ?? 1),
      }
    : createQuoteForm()
  loadSiteOptions(quoteModal.form.quote_type)
  quoteModal.show = true
}

async function submitQuote() {
  if (!quoteModal.form.region && !quoteModal.form.service_name && !quoteModal.form.cpu_model) {
    window.$message?.warning?.('请至少填写地区或产品信息')
    return
  }
  quoteModal.submitting = true
  try {
    const submit = quoteModal.form.id ? api.financeQuoteApi.update : api.financeQuoteApi.create
    const isNetworkQuote = ['ipt', 'dia'].includes(quoteModal.form.quote_type)
    await submit({
      ...quoteModal.form,
      region: isNetworkQuote ? quoteModal.form.site_a || quoteModal.form.region || '' : quoteModal.form.region || '',
      usd_per_mbps_mrc: parseRateNumber(quoteModal.form.usd_per_mbps_mrc),
      note: quoteModal.form.remark || '',
      status: Number(quoteModal.form.status),
    })
    window.$message?.success?.('保存成功')
    quoteModal.show = false
    await loadQuotes()
  } finally {
    quoteModal.submitting = false
  }
}

async function deleteQuote(row) {
  await api.financeQuoteApi.delete({ quote_id: row.id })
  window.$message?.success?.('删除成功')
  await loadQuotes()
}

function onPageChange(page) {
  pagination.page = page
  loadQuotes()
}

function onPageSizeChange(pageSize) {
  pagination.pageSize = pageSize
  pagination.page = 1
  loadQuotes()
}

function onSorterChange(sorter) {
  const activeSorter = Array.isArray(sorter) ? sorter.find((item) => item.order) : sorter
  if (!activeSorter?.order) return loadQuotes()
  api.financeQuoteApi
    .list({
      page: pagination.page,
      page_size: pagination.pageSize,
      keyword: query.keyword || undefined,
      quote_type: query.quote_type || undefined,
      region: query.region || undefined,
      status: query.status ?? undefined,
      sort_field: activeSorter.columnKey,
      sort_order: activeSorter.order,
    })
    .then((res) => {
      rows.value = res.data || []
      pagination.itemCount = res.total || 0
      summary.value = res.summary || summary.value
    })
}

function quoteTypeLabel(value) {
  return quoteTypeOptions.find((item) => item.value === value)?.label || value || '-'
}

function quoteTypeTag(value) {
  const map = { server: 'success', ipt: 'info', dia: 'warning', transport: 'default' }
  return map[value] || 'default'
}

function formatMoney(value, currency = 'CNY') {
  const amount = Number(value || 0).toLocaleString('zh-CN', { maximumFractionDigits: 2 })
  return `${currency || 'CNY'} ${amount}`
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString('zh-CN', { maximumFractionDigits: 2 })
}

function formatRate(value) {
  return Number(value || 0).toLocaleString('zh-CN', { maximumFractionDigits: 6 })
}

function parseRateNumber(value) {
  if (typeof value === 'number') return Number.isFinite(value) ? value : 0
  const text = String(value || '').replace(/,/g, '')
  const decimal = text.match(/\d+\.\d+/)
  if (decimal) return Number(decimal[0])
  const integer = text.match(/\d+/)
  return integer ? Number(integer[0]) : 0
}

function renderProfit(row) {
  const profit = Number(row.sale_price || 0) - Number(row.cost_price || 0)
  const cls = profit >= 0 ? 'profit-positive' : 'profit-negative'
  return h('span', { class: cls }, formatMoney(profit, row.currency))
}

function rowClassName(row) {
  if (Number(row.status) !== 1) return 'quote-row-disabled'
  if (Number(row.sale_price || 0) < Number(row.target_price || 0)) return 'quote-row-warning'
  return ''
}

function typeCount(type) {
  return summary.value.by_type?.find((item) => item.quote_type === type)?.count || 0
}

onMounted(() => {
  loadSiteOptions()
  loadQuotes()
})
</script>

<template>
  <CommonPage class="quote-common-page" title="报价系统">
    <template #action>
      <NSpace>
        <NButton secondary round :loading="loading" @click="loadQuotes">
          <TheIcon icon="mdi:refresh" :size="18" class="mr-5" />
          刷新
        </NButton>
        <NButton type="primary" round @click="openQuote()">
          <TheIcon icon="mdi:plus" :size="18" class="mr-5" />
          新增报价
        </NButton>
      </NSpace>
    </template>

    <div class="quote-page">
      <section class="quote-toolbar">
        <div class="quote-filter">
          <NInput v-model:value="query.keyword" clearable placeholder="搜索地区、型号、带宽、供应商、备注" @keypress.enter="handleSearch">
            <template #prefix>
              <TheIcon icon="mdi:magnify" :size="18" />
            </template>
          </NInput>
          <NSelect
            v-model:value="query.region"
            clearable
            filterable
            tag
            :options="mergedSiteOptions"
            :placeholder="regionFilterPlaceholder"
            @update:value="handleSearch"
          />
          <NSelect v-model:value="query.status" clearable :options="statusOptions" placeholder="全部状态" @update:value="handleSearch" />
          <NButton type="primary" :loading="loading" @click="handleSearch">查询</NButton>
          <NButton secondary @click="resetQuery">重置</NButton>
        </div>
        <div class="quote-summary">
          <div class="summary-main">
            <span>{{ activeTypeLabel }}</span>
            <strong>{{ summary.count || 0 }}</strong>
            <small>上架 {{ summary.active || 0 }}</small>
          </div>
          <div class="summary-types">
            <span v-for="item in quoteTypeOptions" :key="item.value">{{ item.label }} {{ typeCount(item.value) }}</span>
          </div>
        </div>
      </section>

      <section class="quote-table-card">
        <NDataTable
          remote
          class="quote-table"
          :columns="columns"
          :data="rows"
          :loading="loading"
          :pagination="false"
          :row-class-name="rowClassName"
          :scroll-x="tableScrollX"
          flex-height
          :bordered="false"
          size="small"
          @update:sorter="onSorterChange"
        />

        <div class="quote-pagination">
          <span class="pagination-total">共 {{ pagination.itemCount }} 条</span>
          <NPagination
            v-model:page="pagination.page"
            v-model:page-size="pagination.pageSize"
            show-size-picker
            :page-sizes="[10, 20, 50, 100]"
            :item-count="pagination.itemCount"
            @update:page="onPageChange"
            @update:page-size="onPageSizeChange"
          />
        </div>
      </section>
    </div>

    <NModal
      v-model:show="quoteModal.show"
      preset="card"
      :title="modalTitle"
      class="quote-modal"
      :bordered="false"
      segmented
    >
      <NForm label-placement="top" :model="quoteModal.form">
        <NGrid :cols="4" :x-gap="12" :y-gap="4" responsive="screen">
          <NGridItem>
            <NFormItem label="报价类型">
              <NSelect v-model:value="quoteModal.form.quote_type" :options="quoteTypeOptions" @update:value="handleFormTypeChange" />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="地区">
              <NInput v-model:value="quoteModal.form.region" placeholder="硅谷 / 洛杉矶 / 凤凰城" />
            </NFormItem>
          </NGridItem>
          <NGridItem v-if="isQuoteFieldVisible('service_name')">
            <NFormItem :label="typeFieldLabel('service_name')">
              <NInput v-model:value="quoteModal.form.service_name" :placeholder="typeFieldPlaceholder('service_name')" />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="状态">
              <NSwitch
                v-model:value="quoteModal.form.status"
                :checked-value="1"
                :unchecked-value="0"
              >
                <template #checked>上架</template>
                <template #unchecked>下架</template>
              </NSwitch>
            </NFormItem>
          </NGridItem>

          <NGridItem v-if="isQuoteFieldVisible('service_resource')">
            <NFormItem :label="typeFieldLabel('service_resource')">
              <NInput v-model:value="quoteModal.form.service_resource" :placeholder="typeFieldPlaceholder('service_resource')" />
            </NFormItem>
          </NGridItem>
          <NGridItem v-if="isQuoteFieldVisible('provider')">
            <NFormItem :label="typeFieldLabel('provider')">
              <NInput v-model:value="quoteModal.form.provider" :placeholder="typeFieldPlaceholder('provider')" />
            </NFormItem>
          </NGridItem>

          <NGridItem v-if="isQuoteFieldVisible('cpu_model')">
            <NFormItem label="CPU型号">
              <NInput v-model:value="quoteModal.form.cpu_model" placeholder="银牌4116 / EPYC 7B13" />
            </NFormItem>
          </NGridItem>
          <NGridItem v-if="isQuoteFieldVisible('cpu_cores')">
            <NFormItem label="逻辑核心数">
              <NInput v-model:value="quoteModal.form.cpu_cores" placeholder="24核心 / 128核心" />
            </NFormItem>
          </NGridItem>
          <NGridItem v-if="isQuoteFieldVisible('memory')">
            <NFormItem label="内存">
              <NInput v-model:value="quoteModal.form.memory" placeholder="96G / 256G" />
            </NFormItem>
          </NGridItem>
          <NGridItem v-if="isQuoteFieldVisible('disk')">
            <NFormItem label="硬盘">
              <NInput v-model:value="quoteModal.form.disk" placeholder="2*1.92T SSD" />
            </NFormItem>
          </NGridItem>

          <NGridItem v-if="isQuoteFieldVisible('bandwidth')">
            <NFormItem :label="typeFieldLabel('bandwidth')">
              <NInput v-model:value="quoteModal.form.bandwidth" :placeholder="typeFieldPlaceholder('bandwidth')" />
            </NFormItem>
          </NGridItem>
          <NGridItem v-if="isQuoteFieldVisible('burst')">
            <NFormItem :label="typeFieldLabel('burst')">
              <NInput v-model:value="quoteModal.form.burst" :placeholder="typeFieldPlaceholder('burst')" />
            </NFormItem>
          </NGridItem>
          <NGridItem v-if="isQuoteFieldVisible('site_a')">
            <NFormItem :label="typeFieldLabel('site_a')">
              <NSelect
                v-model:value="quoteModal.form.site_a"
                clearable
                filterable
                tag
                :options="mergedSiteOptions"
                :placeholder="typeFieldPlaceholder('site_a')"
              />
            </NFormItem>
          </NGridItem>
          <NGridItem v-if="isQuoteFieldVisible('protection')">
            <NFormItem :label="typeFieldLabel('protection')">
              <NInput v-model:value="quoteModal.form.protection" :placeholder="typeFieldPlaceholder('protection')" />
            </NFormItem>
          </NGridItem>
          <NGridItem v-if="isQuoteFieldVisible('xc_cabling')">
            <NFormItem :label="typeFieldLabel('xc_cabling')">
              <NInput v-model:value="quoteModal.form.xc_cabling" :placeholder="typeFieldPlaceholder('xc_cabling')" />
            </NFormItem>
          </NGridItem>
          <NGridItem v-if="isQuoteFieldVisible('contract_terms')">
            <NFormItem :label="typeFieldLabel('contract_terms')">
              <NInput v-model:value="quoteModal.form.contract_terms" :placeholder="typeFieldPlaceholder('contract_terms')" />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="币种">
              <NSelect v-model:value="quoteModal.form.currency" :options="currencyOptions" />
            </NFormItem>
          </NGridItem>
          <NGridItem v-if="isQuoteFieldVisible('nrc')">
            <NFormItem :label="typeFieldLabel('nrc')">
              <NInputNumber v-model:value="quoteModal.form.nrc" :min="0" :precision="2" class="full-input" />
            </NFormItem>
          </NGridItem>
          <NGridItem v-if="isQuoteFieldVisible('mrc')">
            <NFormItem :label="typeFieldLabel('mrc')">
              <NInputNumber v-model:value="quoteModal.form.mrc" :min="0" :precision="2" class="full-input" />
            </NFormItem>
          </NGridItem>
          <NGridItem v-if="isQuoteFieldVisible('usd_per_mbps_nrc')">
            <NFormItem :label="typeFieldLabel('usd_per_mbps_nrc')">
              <NInput v-model:value="quoteModal.form.usd_per_mbps_nrc" :placeholder="typeFieldPlaceholder('usd_per_mbps_nrc')" />
            </NFormItem>
          </NGridItem>
          <NGridItem v-if="isQuoteFieldVisible('usd_per_mbps_mrc')">
            <NFormItem :label="typeFieldLabel('usd_per_mbps_mrc')">
              <NInputNumber v-model:value="quoteModal.form.usd_per_mbps_mrc" :min="0" :precision="6" class="full-input" />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="成本价">
              <NInputNumber v-model:value="quoteModal.form.cost_price" :min="0" :precision="2" class="full-input" />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="目标价">
              <NInputNumber v-model:value="quoteModal.form.target_price" :min="0" :precision="2" class="full-input" />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="报价">
              <NInputNumber v-model:value="quoteModal.form.sale_price" :min="0" :precision="2" class="full-input" />
            </NFormItem>
          </NGridItem>

          <NGridItem>
            <NFormItem label="排序">
              <NInputNumber v-model:value="quoteModal.form.sort" class="full-input" />
            </NFormItem>
          </NGridItem>
          <NGridItem :span="2">
            <NFormItem label="备注">
              <NInput v-model:value="quoteModal.form.remark" placeholder="仅记上行流量 / 可加更多内存硬盘" />
            </NFormItem>
          </NGridItem>
        </NGrid>
      </NForm>
      <template #footer>
        <NSpace justify="end">
          <NButton @click="quoteModal.show = false">取消</NButton>
          <NButton type="primary" :loading="quoteModal.submitting" @click="submitQuote">保存</NButton>
        </NSpace>
      </template>
    </NModal>
  </CommonPage>
</template>

<style scoped>
.quote-common-page {
  height: 100%;
  min-height: 0;
}

.quote-common-page :deep(.n-card) {
  min-height: 0;
  overflow: hidden;
}

.quote-common-page :deep(.n-card > .n-card__content) {
  display: flex;
  height: 100%;
  min-height: 0;
  flex-direction: column;
}

.quote-page {
  display: flex;
  height: 100%;
  min-height: 0;
  flex-direction: column;
  gap: 12px;
  overflow: hidden;
}

.quote-toolbar {
  flex: 0 0 auto;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: 12px;
  align-items: stretch;
}

.quote-filter {
  display: grid;
  grid-template-columns: minmax(260px, 1fr) 150px 130px auto auto;
  gap: 10px;
  align-items: center;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  padding: 12px;
}

.quote-summary {
  display: grid;
  grid-template-columns: 120px 1fr;
  gap: 10px;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #eff6ff;
  padding: 10px;
}

.summary-main {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 2px;
}

.summary-main span,
.summary-main small,
.summary-types span {
  color: #64748b;
  font-size: 12px;
}

.summary-main strong {
  color: #0f172a;
  font-size: 28px;
  line-height: 1;
}

.summary-types {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px;
  align-content: center;
}

.summary-types span {
  border: 1px solid rgba(96, 165, 250, 0.32);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.76);
  padding: 5px 7px;
}

.quote-table-card {
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
}

.quote-table {
  min-height: 0;
  flex: 1;
}

.quote-table :deep(.n-data-table-base-table) {
  min-height: 0;
}

.quote-type-head {
  display: grid;
  width: 116px;
  grid-template-columns: 30px minmax(0, 1fr);
  gap: 6px;
  align-items: center;
}

.quote-type-select {
  min-width: 76px;
}

.quote-table :deep(.n-data-table-th) {
  background: #f8fafc;
  font-weight: 700;
}

.quote-table :deep(.quote-row-warning td) {
  background: #fef3c7;
}

.quote-table :deep(.quote-row-disabled td) {
  color: #94a3b8;
  background: #f8fafc;
}

.profit-positive {
  color: #047857;
}

.profit-negative {
  color: #dc2626;
}

.quote-pagination {
  display: flex;
  min-height: 52px;
  align-items: center;
  justify-content: flex-end;
  gap: 14px;
  border-top: 1px solid #e5e7eb;
  background: #fff;
  padding: 9px 12px;
}

.pagination-total {
  color: #64748b;
  font-size: 13px;
}

.quote-modal {
  width: min(980px, 94vw);
}

.full-input {
  width: 100%;
}

@media (max-width: 1180px) {
  .quote-toolbar {
    grid-template-columns: 1fr;
  }

  .quote-filter {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .quote-filter,
  .quote-summary {
    grid-template-columns: 1fr;
  }
}
</style>
