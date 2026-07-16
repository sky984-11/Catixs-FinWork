<script setup>
import { computed, h, onMounted, reactive, ref } from 'vue'
import {
  NButton,
  NCheckbox,
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
const fieldOptions = ref({
  regions: [],
  service_resources: [],
  service_names: [],
  currencies: [],
})
const checkedQuoteIds = ref([])
const summary = ref({ count: 0, active: 0, by_type: [] })
const DEFAULT_QUOTE_TYPE = 'ipt'

const query = reactive({
  keyword: '',
  quote_type: DEFAULT_QUOTE_TYPE,
  region: null,
  status: null,
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  itemCount: 0,
})

const sorterState = reactive({
  columnKey: '',
  order: '',
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

const defaultResourceOptions = [
  { label: 'Onnet', value: 'Onnet' },
  { label: 'Offnet', value: 'Offnet' },
]

const defaultServiceNameOptions = [
  { label: 'IP Transit', value: 'IP Transit' },
  { label: 'DIA', value: 'DIA' },
]

const pageSizeOptions = computed(() => {
  const sizes = [10, 20, 50, 100]
  if (pagination.itemCount > 100) sizes.push(pagination.itemCount)
  return Array.from(new Set(sizes)).filter(Boolean)
})

const modalTitle = computed(() => (quoteModal.form.id ? '编辑报价' : '新增报价'))
const activeFormType = computed(() => quoteModal.form.quote_type || 'server')

const activeTypeLabel = computed(() => {
  if (!query.quote_type) return '全部报价'
  return quoteTypeOptions.find((item) => item.value === query.quote_type)?.label || '报价'
})
const regionFilterPlaceholder = computed(() => (['ipt', 'dia'].includes(query.quote_type) ? '机房' : '地区'))
const mergedSiteOptions = computed(() => {
  const values = new Set(siteOptions.value.map((item) => item.value).filter(Boolean))
  ;[query.region, quoteModal.form.site_a].forEach((value) => {
    if (value) values.add(value)
  })
  return Array.from(values)
    .sort()
    .map((value) => ({ label: value, value }))
})

const mergedRegionOptions = computed(() =>
  makeTagOptions(
    [
      ...(fieldOptions.value.regions || []),
      ...siteOptions.value,
      { label: quoteModal.form.region, value: quoteModal.form.region },
      { label: query.region, value: query.region },
    ],
    [quoteModal.form.region, query.region]
  )
)

const mergedResourceOptions = computed(() =>
  makeTagOptions(
    [
      ...defaultResourceOptions,
      ...(fieldOptions.value.service_resources || []),
      { label: quoteModal.form.service_resource, value: quoteModal.form.service_resource },
    ],
    [quoteModal.form.service_resource]
  )
)

const mergedServiceNameOptions = computed(() =>
  makeTagOptions(
    [
      ...defaultServiceNameOptions,
      ...(fieldOptions.value.service_names || []),
      { label: quoteModal.form.service_name, value: quoteModal.form.service_name },
    ],
    [quoteModal.form.service_name]
  )
)

const mergedCurrencyOptions = computed(() => {
  return makeTagOptions(
    [
      ...currencyOptions,
      ...(fieldOptions.value.currencies || []),
      { label: quoteModal.form.currency, value: quoteModal.form.currency },
    ],
    [quoteModal.form.currency],
    (value) => String(value).trim().toUpperCase()
  )
})

const checkedRows = computed(() => {
  const selected = new Set(checkedQuoteIds.value)
  return rows.value.filter((row) => selected.has(row.id))
})

const isCurrentPageChecked = computed(() => rows.value.length > 0 && rows.value.every((row) => checkedQuoteIds.value.includes(row.id)))

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
      ipt: '机房',
      dia: '机房',
    },
    placeholder: {
      ipt: '选择POP点机房',
      dia: '选择POP点机房',
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

const columns = computed(() =>
  [
    {
      type: 'selection',
      fixed: 'left',
      width: 46,
    },
    ...columnDefinitions,
  ]
    .filter((column) => !column.show || column.show())
    .map((column) =>
      column.sorter
        ? {
            ...column,
            resizable: column.key !== 'actions',
            sortOrder: sorterState.columnKey === column.key ? sorterState.order : false,
          }
        : {
            ...column,
            resizable: column.type !== 'selection' && column.key !== 'actions',
          }
    )
)
const tableScrollX = computed(() =>
  columns.value.reduce((total, column) => total + Number(column.width || column.minWidth || 130), 0)
)
const isNetworkTable = computed(() => ['ipt', 'dia'].includes(query.quote_type))

function sortableColumn(key) {
  return {
    sorter: true,
  }
}

function makeTagOptions(options = [], extras = [], normalize = (value) => String(value).trim()) {
  const values = new Map()
  ;[...options, ...extras].forEach((item) => {
    const rawValue = typeof item === 'object' ? item?.value : item
    const value = normalize(rawValue ?? '')
    if (!value) return
    values.set(value, { label: value, value })
  })
  return Array.from(values.values()).sort((a, b) => a.label.localeCompare(b.label))
}

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
  { title: '地区', key: 'region', width: 110, fixed: 'left', ellipsis: { tooltip: true }, show: () => !isNetworkTable.value, ...sortableColumn('region') },
  { title: '资源类型', key: 'service_resource', width: 126, ellipsis: { tooltip: true }, show: () => isNetworkTable.value, ...sortableColumn('service_resource') },
  {
    title: () => (query.quote_type && query.quote_type !== 'server' ? typeFieldLabel('service_name', query.quote_type) : 'CPU型号'),
    key: 'cpu_model',
    minWidth: 150,
    ellipsis: { tooltip: true },
    show: () => !query.quote_type || query.quote_type === 'server',
    render: (row) => row.cpu_model || row.service_name || '-',
    ...sortableColumn('cpu_model'),
  },
  { title: '供应商', key: 'provider', minWidth: 150, ellipsis: { tooltip: true }, show: () => isNetworkTable.value, ...sortableColumn('provider') },
  { title: '逻辑核心数', key: 'cpu_cores', width: 110, ellipsis: { tooltip: true }, show: () => !query.quote_type || query.quote_type === 'server', ...sortableColumn('cpu_cores') },
  { title: '内存', key: 'memory', width: 100, ellipsis: { tooltip: true }, show: () => !query.quote_type || query.quote_type === 'server', ...sortableColumn('memory') },
  { title: '硬盘', key: 'disk', minWidth: 160, ellipsis: { tooltip: true }, show: () => !query.quote_type || query.quote_type === 'server', ...sortableColumn('disk') },
  { title: () => typeFieldLabel('bandwidth', query.quote_type || 'server'), key: 'bandwidth', width: 112, ellipsis: { tooltip: true }, ...sortableColumn('bandwidth') },
  { title: '突发带宽', key: 'burst', width: 110, ellipsis: { tooltip: true }, show: () => isNetworkTable.value, ...sortableColumn('burst') },
  { title: '机房', key: 'site_a', minWidth: 150, ellipsis: { tooltip: true }, show: () => isNetworkTable.value, ...sortableColumn('site_a') },
  { title: '币种', key: 'currency', width: 78, ellipsis: { tooltip: true }, show: () => isNetworkTable.value, ...sortableColumn('currency') },
  { title: '一次性费用', key: 'nrc', width: 116, align: 'right', render: (row) => renderPriceCell(formatNumber(row.nrc)), show: () => isNetworkTable.value, ...sortableColumn('nrc') },
  { title: '月费', key: 'mrc', width: 106, align: 'right', render: (row) => renderPriceCell(formatNumber(row.mrc), true), show: () => isNetworkTable.value, ...sortableColumn('mrc') },
  { title: '每Mbps一次性费用', key: 'usd_per_mbps_nrc', width: 152, align: 'right', ellipsis: { tooltip: true }, render: (row) => renderPriceCell(row.usd_per_mbps_nrc || '-'), show: () => isNetworkTable.value, ...sortableColumn('usd_per_mbps_nrc') },
  { title: '每Mbps月费', key: 'usd_per_mbps_mrc', width: 132, align: 'right', render: (row) => renderPriceCell(formatRate(row.usd_per_mbps_mrc), true), show: () => isNetworkTable.value, ...sortableColumn('usd_per_mbps_mrc') },
  { title: '成本价', key: 'cost_price', width: 116, align: 'right', render: (row) => renderPriceCell(formatMoney(row.cost_price, row.currency)), show: () => !isNetworkTable.value, ...sortableColumn('cost_price') },
  { title: '目标价', key: 'target_price', width: 116, align: 'right', render: (row) => renderPriceCell(formatMoney(row.target_price, row.currency)), show: () => !isNetworkTable.value, ...sortableColumn('target_price') },
  { title: '报价', key: 'sale_price', width: 116, align: 'right', render: (row) => renderPriceCell(formatMoney(row.sale_price, row.currency), true), show: () => !isNetworkTable.value, ...sortableColumn('sale_price') },
  { title: '毛利', key: 'profit', width: 110, align: 'right', render: renderProfit, show: () => !isNetworkTable.value },
  { title: () => typeFieldLabel('provider', query.quote_type || 'server'), key: 'provider', minWidth: 120, ellipsis: { tooltip: true }, show: () => query.quote_type && query.quote_type !== 'server' && !isNetworkTable.value, ...sortableColumn('provider') },
  { title: '保护方式', key: 'protection', width: 110, ellipsis: { tooltip: true }, show: () => isNetworkTable.value, ...sortableColumn('protection') },
  { title: '交叉/布线', key: 'xc_cabling', width: 115, ellipsis: { tooltip: true }, show: () => isNetworkTable.value, ...sortableColumn('xc_cabling') },
  { title: '合同周期', key: 'contract_terms', width: 135, ellipsis: { tooltip: true }, show: () => isNetworkTable.value, ...sortableColumn('contract_terms') },
  { title: '备注', key: 'remark', minWidth: 220, ellipsis: { tooltip: true }, render: (row) => row.remark || row.note || '-' },
  {
    title: '状态',
    key: 'status',
    width: 86,
    align: 'center',
    ...sortableColumn('status'),
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
    region: null,
    service_name: '',
    cpu_model: '',
    cpu_cores: '',
    memory: '',
    disk: '',
    bandwidth: '',
    burst: '',
    traffic: '',
    site_a: null,
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
    syncCheckedRows()
  } finally {
    loading.value = false
  }
}

function syncCheckedRows() {
  const currentIds = new Set(rows.value.map((row) => row.id))
  checkedQuoteIds.value = checkedQuoteIds.value.filter((id) => currentIds.has(id))
}

async function loadSiteOptions(type = query.quote_type) {
  if (!['ipt', 'dia'].includes(type)) {
    siteOptions.value = []
    return
  }
  const [regionRes, locationRes] = await Promise.all([
    api.assetApi.regions({ page_size: 1000 }),
    api.assetApi.locations({ page_size: 1000, type: 1 }),
  ])
  const regionMap = new Map((regionRes.data || []).map((region) => [region.id, region]))
  siteOptions.value = (locationRes.data || [])
    .filter((location) => Number(location.type) === 1)
    .map((location) => {
      const region = regionMap.get(location.region_id)
      const place = [region?.country, region?.city].filter(Boolean).join(' / ') || region?.name || ''
      const label = [place, location.name].filter(Boolean).join(' / ')
      return {
        label: label || location.name,
        value: label || location.name,
      }
    })
}

async function loadFieldOptions(type = query.quote_type) {
  const res = await api.financeQuoteApi.fieldOptions({
    quote_type: type || undefined,
  })
  fieldOptions.value = {
    regions: res.data?.regions || [],
    service_resources: res.data?.service_resources || [],
    service_names: res.data?.service_names || [],
    currencies: res.data?.currencies || [],
  }
}

function handleSearch() {
  pagination.page = 1
  loadQuotes()
}

function handleTypeChange(value) {
  query.quote_type = value || DEFAULT_QUOTE_TYPE
  query.region = null
  pagination.page = 1
  loadSiteOptions()
  loadFieldOptions()
  loadQuotes()
}

function handleFormTypeChange(value) {
  quoteModal.form.quote_type = value || 'server'
  loadSiteOptions(quoteModal.form.quote_type)
  loadFieldOptions(quoteModal.form.quote_type)
}

function resetQuery() {
  query.keyword = ''
  query.quote_type = DEFAULT_QUOTE_TYPE
  query.region = null
  query.status = null
  loadSiteOptions()
  loadFieldOptions()
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
        region: row.region || null,
        site_a: row.site_a || null,
        usd_per_mbps_mrc: parseRateNumber(row.usd_per_mbps_mrc),
        remark: row.remark || row.note || '',
        status: Number(row.status ?? 1),
      }
    : createQuoteForm()
  loadSiteOptions(quoteModal.form.quote_type)
  loadFieldOptions(quoteModal.form.quote_type)
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
      service_resource: quoteModal.form.service_resource || '',
      service_name: quoteModal.form.service_name || '',
      site_a: quoteModal.form.site_a || '',
      currency: quoteModal.form.currency ? String(quoteModal.form.currency).trim().toUpperCase() : 'USD',
      usd_per_mbps_mrc: parseRateNumber(quoteModal.form.usd_per_mbps_mrc),
      note: quoteModal.form.remark || '',
      status: Number(quoteModal.form.status),
    })
    window.$message?.success?.('保存成功')
    quoteModal.show = false
    await loadFieldOptions(query.quote_type)
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

function handleCheckedRowKeys(keys) {
  checkedQuoteIds.value = keys
}

function toggleCurrentPageChecked(checked) {
  checkedQuoteIds.value = checked ? rows.value.map((row) => row.id) : []
}

function onSorterChange(sorter) {
  const activeSorter = Array.isArray(sorter) ? sorter.find((item) => item.order) : sorter
  if (!activeSorter?.order) {
    sorterState.columnKey = ''
    sorterState.order = ''
    return loadQuotes()
  }
  sorterState.columnKey = activeSorter.columnKey
  sorterState.order = activeSorter.order
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
      syncCheckedRows()
    })
}

function quoteExportColumns() {
  if (isNetworkTable.value) {
    return [
      ['quote_type', '类型', (row) => quoteTypeLabel(row.quote_type)],
      ['service_resource', '资源类型'],
      ['provider', '供应商'],
      ['bandwidth', '带宽'],
      ['burst', '突发带宽'],
      ['site_a', '机房'],
      ['currency', '币种'],
      ['nrc', '一次性费用'],
      ['mrc', '月费'],
      ['usd_per_mbps_nrc', '每Mbps一次性费用'],
      ['usd_per_mbps_mrc', '每Mbps月费', (row) => formatRate(row.usd_per_mbps_mrc)],
      ['protection', '保护方式'],
      ['xc_cabling', '交叉/布线'],
      ['contract_terms', '合同周期'],
      ['remark', '备注', (row) => row.remark || row.note || ''],
      ['status', '状态', (row) => (Number(row.status) === 1 ? '上架' : '下架')],
    ]
  }
  return [
    ['quote_type', '类型', (row) => quoteTypeLabel(row.quote_type)],
    ['region', '地区'],
    ['cpu_model', 'CPU型号', (row) => row.cpu_model || row.service_name || ''],
    ['cpu_cores', '逻辑核心数'],
    ['memory', '内存'],
    ['disk', '硬盘'],
    ['bandwidth', '带宽'],
    ['provider', '供应商'],
    ['cost_price', '成本价', (row) => formatMoney(row.cost_price, row.currency)],
    ['target_price', '目标价', (row) => formatMoney(row.target_price, row.currency)],
    ['sale_price', '报价', (row) => formatMoney(row.sale_price, row.currency)],
    ['profit', '毛利', (row) => formatMoney(Number(row.sale_price || 0) - Number(row.cost_price || 0), row.currency)],
    ['remark', '备注', (row) => row.remark || row.note || ''],
    ['status', '状态', (row) => (Number(row.status) === 1 ? '上架' : '下架')],
  ]
}

function escapeExcelCell(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function exportSelectedQuotes() {
  if (!checkedRows.value.length) {
    window.$message?.warning?.('请先选择要导出的报价')
    return
  }

  const exportColumns = quoteExportColumns()
  const header = exportColumns.map(([, title]) => `<th>${escapeExcelCell(title)}</th>`).join('')
  const body = checkedRows.value
    .map((row) => {
      const cells = exportColumns
        .map(([key, , formatter]) => {
          const value = formatter ? formatter(row) : row[key]
          return `<td>${escapeExcelCell(value)}</td>`
        })
        .join('')
      return `<tr>${cells}</tr>`
    })
    .join('')
  const html = `
    <html>
      <head>
        <meta charset="UTF-8" />
        <style>
          table { border-collapse: collapse; }
          th, td { border: 1px solid #999; padding: 6px 8px; white-space: nowrap; }
          th { background: #eaf2ff; font-weight: 700; }
        </style>
      </head>
      <body><table><thead><tr>${header}</tr></thead><tbody>${body}</tbody></table></body>
    </html>
  `
  const blob = new Blob([html], { type: 'application/vnd.ms-excel;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `报价系统_${new Date().toISOString().slice(0, 10)}.xls`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
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

function renderPriceCell(value, strong = false) {
  return h('span', { class: ['price-cell', strong ? 'is-strong' : ''] }, value)
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
  return h('span', { class: ['price-cell', cls] }, formatMoney(profit, row.currency))
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
  loadFieldOptions()
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
            :options="mergedRegionOptions"
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
          :row-key="(row) => row.id"
          :checked-row-keys="checkedQuoteIds"
          :row-class-name="rowClassName"
          :scroll-x="tableScrollX"
          flex-height
          :bordered="false"
          size="small"
          @update:checked-row-keys="handleCheckedRowKeys"
          @update:sorter="onSorterChange"
        />

        <div class="quote-pagination">
          <div class="quote-selection-actions">
            <NCheckbox :checked="isCurrentPageChecked" :disabled="!rows.length" @update:checked="toggleCurrentPageChecked">
              全选当前页
            </NCheckbox>
            <span class="selection-count">已选 {{ checkedQuoteIds.length }} 条</span>
            <NButton size="small" secondary :disabled="!checkedQuoteIds.length" @click="exportSelectedQuotes">
              <TheIcon icon="mdi:file-excel-outline" :size="16" class="mr-5" />
              导出Excel
            </NButton>
          </div>
          <div class="quote-page-actions">
            <span class="pagination-total">共 {{ pagination.itemCount }} 条</span>
            <NPagination
              v-model:page="pagination.page"
              v-model:page-size="pagination.pageSize"
              show-size-picker
              :page-sizes="pageSizeOptions"
              :item-count="pagination.itemCount"
              @update:page="onPageChange"
              @update:page-size="onPageSizeChange"
            />
          </div>
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
              <NSelect
                v-model:value="quoteModal.form.region"
                clearable
                filterable
                tag
                :options="mergedRegionOptions"
                placeholder="硅谷 / 洛杉矶 / 凤凰城"
              />
            </NFormItem>
          </NGridItem>
          <NGridItem v-if="isQuoteFieldVisible('service_name')">
            <NFormItem :label="typeFieldLabel('service_name')">
              <NSelect
                v-model:value="quoteModal.form.service_name"
                clearable
                filterable
                tag
                :options="mergedServiceNameOptions"
                :placeholder="typeFieldPlaceholder('service_name')"
              />
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
              <NSelect
                v-model:value="quoteModal.form.service_resource"
                clearable
                filterable
                tag
                :options="mergedResourceOptions"
                :placeholder="typeFieldPlaceholder('service_resource')"
              />
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
              <NSelect
                v-model:value="quoteModal.form.currency"
                filterable
                tag
                :options="mergedCurrencyOptions"
                placeholder="USD / CNY / HKD"
              />
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
  border: 1px solid #d9e2ef;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 8px 22px rgba(15, 23, 42, 0.04);
}

.quote-table {
  min-height: 0;
  flex: 1;
}

.quote-table :deep(.n-data-table-base-table) {
  min-height: 0;
}

.quote-table :deep(.n-data-table-wrapper) {
  background: linear-gradient(180deg, #fff 0%, #fbfdff 100%);
}

.quote-table :deep(.n-data-table-resize-button) {
  width: 3px;
  border-radius: 999px;
  background: #cbd5e1;
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
  height: 42px;
  border-color: #dbe3ee;
  background: #f6f8fb;
  color: #334155;
  font-size: 12px;
  font-weight: 700;
}

.quote-table :deep(.n-data-table-th__title) {
  white-space: nowrap;
}

.quote-table :deep(.n-data-table-td) {
  height: 42px;
  border-color: #edf1f7;
  color: #172033;
  font-size: 13px;
}

.quote-table :deep(.n-data-table-tr:hover .n-data-table-td) {
  background: #f8fbff;
}

.quote-table :deep(.n-data-table-th--fixed-left),
.quote-table :deep(.n-data-table-td--fixed-left),
.quote-table :deep(.n-data-table-th--fixed-right),
.quote-table :deep(.n-data-table-td--fixed-right) {
  box-shadow: 1px 0 0 #e5eaf2;
}

.price-cell {
  display: inline-flex;
  min-width: 74px;
  justify-content: flex-end;
  color: #0f172a;
  font-variant-numeric: tabular-nums;
  font-weight: 600;
}

.price-cell.is-strong {
  color: #0f3f77;
  font-weight: 800;
}

.quote-table :deep(.quote-row-warning td) {
  background: #fff8df;
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
  justify-content: space-between;
  gap: 12px;
  border-top: 1px solid #e5e7eb;
  background: #fff;
  padding: 9px 12px;
}

.quote-selection-actions,
.quote-page-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.selection-count {
  color: #475569;
  font-size: 13px;
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

  .quote-pagination {
    align-items: flex-start;
    flex-direction: column;
  }

  .quote-selection-actions,
  .quote-page-actions {
    flex-wrap: wrap;
  }
}
</style>
