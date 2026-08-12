<script setup>
import { computed, h, onMounted, reactive, ref } from 'vue'
import {
  NButton,
  NCascader,
  NDataTable,
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
  NSwitch,
  NTag,
  NTooltip,
} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import api from '@/api'
import { renderIcon } from '@/utils'
import { translateCity, translateCountry, translateLocationPath } from '@/utils/location-i18n'

defineOptions({ name: '产品模板' })

const loading = ref(false)
const modalVisible = ref(false)
const modalLoading = ref(false)
const rows = ref([])
const regions = ref([])
const query = reactive({ region_id: null, service_type: null, status: null })
const form = reactive(createForm())
const unitOptions = ref([])
const productCodeOptions = computed(() => buildProductCodeOptions(form.service_type, form.unit, form.product_code))
const isIeplTemplate = computed(() => form.service_type === 'IEPL')
const bandwidthUnitLabel = computed(() => bandwidthUnitFromBillingUnit(form.unit))

const statusOptions = [
  { label: '启用', value: true },
  { label: '停用', value: false },
]

const currencyOptions = ['CNY', 'USD', 'HKD', 'EUR', 'GBP', 'JPY', 'SGD'].map((item) => ({
  label: item,
  value: item,
}))

const billingRuleOptions = [
  { label: '月付', value: 'monthly' },
  { label: '年付', value: 'yearly' },
  { label: '一次性', value: 'one_time' },
]

const priceModelOptions = [
  { label: '固定月费', value: 'fixed' },
  { label: '按数量计费', value: 'quantity' },
  { label: '带宽 Commit/Burst', value: 'commit_burst' },
  { label: '95th 带宽', value: 'p95' },
  { label: 'IP 数量计费', value: 'ip_quantity' },
  { label: '一次性服务', value: 'one_time' },
  { label: '服务抵扣 / 调账', value: 'credit' },
]

const serviceTypeCodeMap = {
  机柜: 'RACK',
  机位: 'U',
  kW: 'POWER-KW',
  kWh: 'POWER-KWH',
  A: 'POWER-A',
  物理服务器: 'SERVER',
  云主机: 'VM',
  'IPv4 段': 'IPV4',
  'IPv4 个': 'IPV4',
  IPv6: 'IPV6',
  ASN: 'ASN',
  Prefix: 'PREFIX',
  'Cross Connect': 'CROSS-CONNECT',
  IX: 'IX',
  Peering: 'PEERING',
  'Cloud Connect': 'CLOUD-CONNECT',
  'IP Transit': 'IPT',
  DIA: 'DIA',
  CN2: 'CN2',
  IEPL: 'IEPL',
  EPL: 'EPL',
  'Remote Hands': 'REMOTE-HANDS',
}

const serviceTypeOptions = [
  {
    label: '机房资源',
    value: 'category:机房资源',
    children: [
      {
        label: '机柜',
        value: 'group:机房资源/机柜',
        children: [
          serviceTypeOption('机柜', 'U / Rack / 月'),
          serviceTypeOption('机位', 'U / 月'),
        ],
      },
      {
        label: '电力',
        value: 'group:机房资源/电力',
        children: [
          serviceTypeOption('kW', 'kW / 月'),
          serviceTypeOption('kWh', 'kWh'),
          serviceTypeOption('A', 'A / 月'),
        ],
      },
    ],
  },
  {
    label: '计算资源',
    value: 'category:计算资源',
    children: [
      serviceTypeOption('物理服务器', '台 / 月'),
      serviceTypeOption('云主机', '台 / 月'),
    ],
  },
  {
    label: '互联网资源',
    value: 'category:互联网资源',
    children: [
      {
        label: 'IPv4',
        value: 'group:互联网资源/IPv4',
        children: [
          serviceTypeOption('IPv4 段', '段 / 月'),
          serviceTypeOption('IPv4 个', '个 / 月'),
        ],
      },
      serviceTypeOption('IPv6', 'Prefix / 月'),
      serviceTypeOption('ASN', 'ASN / 月'),
      serviceTypeOption('Prefix', 'Prefix / 月'),
    ],
  },
  {
    label: '网络互联',
    value: 'category:网络互联',
    children: [
      serviceTypeOption('Cross Connect', ''),
      serviceTypeOption('IX', ''),
      serviceTypeOption('Peering', ''),
      serviceTypeOption('Cloud Connect', ''),
    ],
  },
  {
    label: '网络传输服务',
    value: 'category:网络传输服务',
    children: [
      serviceTypeOption('IP Transit', ['Mbps / 月', 'Gbps / 月', 'Mbps(95th) / 月']),
      serviceTypeOption('DIA', ['Mbps / 月', 'Gbps / 月', 'Mbps(95th) / 月']),
      serviceTypeOption('CN2', ['Mbps / 月', 'Gbps / 月', 'Mbps(95th) / 月']),
      serviceTypeOption('IEPL', ['Mbps / 月', 'Gbps / 月', 'Mbps(95th) / 月']),
      serviceTypeOption('EPL', ['Mbps / 月', 'Gbps / 月', 'Mbps(95th) / 月']),
    ],
  },
  {
    label: '增值服务',
    value: 'category:增值服务',
    children: [serviceTypeOption('Remote Hands', '')],
  },
]

const regionOptions = computed(() => {
  const roots = []
  regions.value.forEach((region) => ensureRegionPath(roots, popRegionPathParts(region), region))
  return sortCascaderTree(roots)
})

const columns = [
  {
    title: '模板名称',
    key: 'name',
    minWidth: 300,
    fixed: 'left',
    render: (row) =>
      h(NTooltip, { trigger: 'hover', placement: 'top' }, {
        trigger: () => h('div', { class: 'template-name-cell' }, [
          h('div', { class: 'template-code-text' }, row.name || '-'),
        ]),
        default: () => row.name || '-',
      }),
  },
  {
    title: '参数规格',
    key: 'spec',
    minWidth: 280,
    render: (row) =>
      h('div', { class: 'template-spec-cell' }, [
        h(NTooltip, { trigger: 'hover', placement: 'top' }, {
          trigger: () => h('div', { class: 'template-spec-text' }, templateSpecSummary(row)),
          default: () => templateSpecSummary(row),
        }),
        row.remark ? h('div', { class: 'template-remark' }, row.remark) : null,
      ]),
  },
  {
    title: '服务 / 区域',
    key: 'service',
    minWidth: 240,
    render: (row) =>
      h('div', { class: 'service-cell' }, [
        h(NTag, { type: serviceTagType(row.service_type), bordered: false, round: true }, { default: () => row.service_type || '-' }),
        h('span', { class: 'region-text' }, displayRouteRegionLabel(row)),
      ]),
  },
  {
    title: '标准价格',
    key: 'billing',
    minWidth: 260,
    align: 'right',
    render: (row) =>
      h('div', { class: 'billing-cell' }, [
        h('div', { class: 'price-line' }, formatPriceParts(row)),
        h('div', { class: 'billing-sub' }, [
          priceModelText(row.price_model),
          billingRuleText(row.billing_rule),
          row.unit || '-',
        ].filter(Boolean).join(' · ')),
        priceExtraSummary(row) ? h('div', { class: 'billing-extra' }, priceExtraSummary(row)) : null,
      ]),
  },
  {
    title: '状态',
    key: 'status',
    width: 100,
    align: 'center',
    render: (row) =>
      h(NTag, { type: row.status ? 'success' : 'default', bordered: false, round: true }, {
        default: () => (row.status ? '启用' : '停用'),
      }),
  },
  {
    title: '操作',
    key: 'actions',
    width: 112,
    fixed: 'right',
    align: 'center',
    render: (row) =>
      h(NSpace, { size: 8, justify: 'center' }, () => [
        iconButton('编辑', 'material-symbols:edit', { type: 'primary', onClick: () => openEdit(row) }),
        h(
          NPopconfirm,
          { onPositiveClick: () => deleteRow(row) },
          {
            trigger: () => iconButton('删除', 'material-symbols:delete-outline', { type: 'error' }),
            default: () => `确定删除模板「${row.name || ''}」吗？`,
          }
        ),
      ]),
  },
]

function createForm(source = {}) {
  return {
    id: source.id || null,
    name: source.name || '',
    product_code: source.product_code || '',
    guaranteed: parseIeplSpec(source.product_code).guaranteed,
    burst: parseIeplSpec(source.product_code).burst,
    region_id: source.region_id || null,
    target_region_id: source.target_region_id || null,
    service_type: source.service_type || '',
    billing_rule: source.billing_rule || 'monthly',
    price_model: source.price_model || inferPriceModel(source.service_type, source.unit),
    nrc_price: Number(source.nrc_price || 0),
    mrc_price: Number(source.mrc_price ?? source.unit_price ?? 0),
    unit_price: Number(source.mrc_price ?? source.unit_price ?? 0),
    currency: source.currency || 'USD',
    unit: source.unit || '',
    default_quantity: Number(source.default_quantity || 1),
    included_ip_quantity: Number(source.included_ip_quantity || 0),
    ip_unit_price: Number(source.ip_unit_price || 0),
    default_tax_rate: Number(source.default_tax_rate || 0),
    status: source.status ?? true,
    remark: source.remark || '',
  }
}

function serviceTypeOption(serviceType, units) {
  const unitList = Array.isArray(units) ? units : units ? [units] : []
  return {
    label: serviceType,
    value: serviceType,
    serviceType,
    unit: unitList[0] || '',
    units: unitList,
  }
}

const productCodePresetMap = {
  机柜: ['整柜', '半柜', '1/4柜', '42U Rack', '47U Rack', '52U Rack'],
  机位: ['1U', '2U', '4U', '5U', '10U', '20U'],
  kW: ['1kW', '2kW', '3kW', '5kW', '10kW', '20kW'],
  kWh: ['按实际用量', '保底电量', '超额电量'],
  A: ['10A', '16A', '20A', '32A', '40A', '63A'],
  物理服务器: ['1C2G', '2C4G', '4C8G', '8C16G', '16C32G', '32C64G', 'GPU服务器'],
  云主机: ['1C2G', '2C4G', '4C8G', '8C16G', '16C32G', '32C64G'],
  'IPv4 段': ['/30', '/29', '/28', '/27', '/26', '/25', '/24'],
  'IPv4 个': ['1 IP', '2 IP', '4 IP', '8 IP', '16 IP', '32 IP'],
  IPv6: ['/64', '/56', '/48', '/32'],
  ASN: ['1 ASN'],
  Prefix: ['/24', '/23', '/22', '/21', '/20', '/19', '/18'],
  'Cross Connect': ['1G SMF', '1G MMF', '10G LR', '10G SR', '40G LR4', '100G LR4'],
  IX: ['1G Port', '10G Port', '100G Port'],
  Peering: ['1G Peering', '10G Peering', '100G Peering'],
  'Cloud Connect': ['50M', '100M', '200M', '500M', '1G', '10G'],
  'IP Transit': ['10M', '20M', '50M', '100M', '200M', '500M', '1G', '2G', '5G', '10G', '100G'],
  DIA: ['10M', '20M', '50M', '100M', '200M', '500M', '1G', '2G', '5G', '10G'],
  CN2: ['10M', '20M', '50M', '100M', '200M', '500M', '1G', '2G', '5G', '10G'],
  IEPL: ['10M', '20M', '50M', '100M', '200M', '500M', '1G', '2G', '5G', '10G'],
  EPL: ['10M', '20M', '50M', '100M', '200M', '500M', '1G', '2G', '5G', '10G'],
  'Remote Hands': ['30分钟', '1小时', '2小时', '半天', '全天'],
}

function buildProductCodeOptions(serviceType, unit, currentValue) {
  const baseValues = productCodePresetMap[serviceType] || []
  const expandedValues = ['DIA', 'IEPL'].includes(serviceType)
    ? [...baseValues, ...buildCommitBurstPresets(baseValues)]
    : baseValues
  const values = expandedValues.map((item) => {
    if (!unit || !unit.includes('95th') || !/^\d/.test(item) || item.includes('95th')) return item
    return `${item} 95th`
  })
  if (currentValue && !values.includes(currentValue)) {
    values.unshift(currentValue)
  }
  return values.map((item) => ({ label: item, value: item }))
}

function buildCommitBurstPresets(values = []) {
  const pairs = [
    ['10M', '100M'],
    ['20M', '200M'],
    ['50M', '500M'],
    ['100M', '1G'],
    ['200M', '1G'],
    ['500M', '2G'],
    ['1G', '10G'],
    ['2G', '10G'],
    ['5G', '10G'],
  ]
  const available = new Set(values)
  return pairs
    .filter(([commit, burst]) => available.has(commit) && available.has(burst))
    .map(([commit, burst]) => `${commit} Commit / ${burst} Burst`)
}

function getServiceTypeValue() {
  if (!form.service_type) return null
  const option = findServiceTypeOptionByType(form.service_type)
  return option?.value || form.service_type
}

function handleServiceTypeChange(value, option) {
  if (!option) {
    form.service_type = ''
    form.unit = ''
    unitOptions.value = []
    syncTemplateName()
    return
  }
  form.service_type = option.serviceType || ''
  if (form.service_type === 'IEPL') {
    const parsed = parseIeplSpec(form.product_code)
    form.guaranteed = parsed.guaranteed || form.guaranteed || ''
    form.burst = parsed.burst || form.burst || ''
  } else {
    form.target_region_id = null
    form.guaranteed = ''
    form.burst = ''
  }
  syncUnitOptions(option)
  if (!unitOptions.value.some((item) => item.value === form.unit)) {
    form.unit = option.unit || ''
  }
  form.price_model = inferPriceModel(form.service_type, form.unit)
  if (!productCodeOptions.value.some((item) => item.value === form.product_code)) {
    form.product_code = ''
  }
  syncTemplateName()
}

function handleRegionChange(value) {
  form.region_id = value
  syncTemplateName()
}

function handleTargetRegionChange(value) {
  form.target_region_id = value
  syncTemplateName()
}

function handleProductCodeChange(value) {
  form.product_code = value || ''
  syncTemplateName()
}

function handleIeplSpecChange() {
  form.product_code = buildIeplProductCode()
  syncTemplateName()
}

function handleUnitChange(value) {
  form.unit = value || ''
  form.price_model = inferPriceModel(form.service_type, form.unit)
  if (form.service_type === 'IEPL') form.product_code = buildIeplProductCode()
  syncTemplateName()
}

function serviceTypeFilter(pattern, option, path = []) {
  const text = [option.label, option.serviceType, option.unit, ...path.map((item) => item.label)]
    .filter(Boolean)
    .join(' ')
    .toLowerCase()
  return text.includes(String(pattern || '').toLowerCase())
}

function regionFilter(pattern, option, path = []) {
  const options = Array.isArray(path) && path.length ? path : [option]
  const text = options
    .flatMap((item) => [item?.label, item?.value, item?.region, item?.searchText])
    .filter(Boolean)
    .join(' ')
  return normalizeSearchText(text).includes(normalizeSearchText(pattern))
}

function findServiceTypeOptionByType(serviceType, options = serviceTypeOptions) {
  for (const option of options) {
    if (option.serviceType === serviceType) return option
    const match = option.children ? findServiceTypeOptionByType(serviceType, option.children) : null
    if (match) return match
  }
  return null
}

function syncUnitOptions(option = findServiceTypeOptionByType(form.service_type)) {
  const units = option?.units?.length ? option.units : form.unit ? [form.unit] : []
  unitOptions.value = units.map((item) => ({ label: item, value: item }))
}

async function loadRows() {
  loading.value = true
  try {
    const params = {}
    if (query.status !== null && query.status !== undefined) params.status = query.status
    if (query.region_id) params.region_id = query.region_id
    if (query.service_type) params.service_type = query.service_type
    const res = await api.getBillingTemplates(params)
    rows.value = res?.data || []
  } finally {
    loading.value = false
  }
}

async function loadRegions() {
  const res = await api.assetApi.regions({ page: 1, page_size: 1000, status: true })
  regions.value = res?.data || []
  syncTemplateName()
}

function openAdd() {
  Object.assign(form, createForm())
  syncUnitOptions()
  syncTemplateName()
  modalVisible.value = true
}

function openEdit(row) {
  Object.assign(form, createForm(row))
  syncUnitOptions()
  syncTemplateName()
  modalVisible.value = true
}

async function saveRow() {
  if (form.service_type !== 'IEPL') form.target_region_id = null
  else form.product_code = buildIeplProductCode()
  syncTemplateName()
  if (!form.service_type) return window.$message?.warning?.('请选择服务类型')
  if (!form.region_id) return window.$message?.warning?.('请选择区域')
  if (form.service_type === 'IEPL') {
    if (!form.unit) return window.$message?.warning?.('请选择计量单位')
    if (!form.guaranteed) return window.$message?.warning?.('请填写 Guaranteed')
    if (!form.burst) return window.$message?.warning?.('请填写 Burst')
  } else if (!form.product_code) return window.$message?.warning?.('请选择参数规格')
  if (form.service_type === 'IEPL' && form.target_region_id && form.target_region_id === form.region_id) {
    return window.$message?.warning?.('IEPL 目标区域不能和源区域相同')
  }
  if (!form.name) return window.$message?.warning?.('模板名称生成失败，请检查服务类型、区域和参数规格')
  form.mrc_price = Number(form.mrc_price || 0)
  form.nrc_price = Number(form.nrc_price || 0)
  form.unit_price = form.mrc_price
  modalLoading.value = true
  try {
    const { guaranteed, burst, ...payload } = form
    await api.saveBillingTemplate(payload)
    window.$message?.success?.('保存成功')
    modalVisible.value = false
    await loadRows()
  } finally {
    modalLoading.value = false
  }
}

async function deleteRow(row) {
  await api.deleteBillingTemplate(row.id)
  window.$message?.success?.('删除成功')
  await loadRows()
}

function billingRuleText(value) {
  return billingRuleOptions.find((item) => item.value === value)?.label || value || '-'
}

function priceModelText(value) {
  return priceModelOptions.find((item) => item.value === value)?.label || value || '固定月费'
}

function inferPriceModel(serviceType, unit) {
  if (serviceType === 'IEPL') return 'commit_burst'
  if (String(unit || '').toLowerCase().includes('95th')) return 'p95'
  if (['IPv4 段', 'IPv4 个', 'IPv6'].includes(serviceType)) return 'ip_quantity'
  if (['Remote Hands', 'Cross Connect'].includes(serviceType)) return 'one_time'
  if (['机位', 'kW', 'kWh', 'A', '物理服务器', '云主机'].includes(serviceType)) return 'quantity'
  return 'fixed'
}

function formatPriceParts(row = {}) {
  const currency = row.currency || ''
  const nrc = Number(row.nrc_price || 0)
  const mrc = Number(row.mrc_price ?? row.unit_price ?? 0)
  const parts = []
  if (nrc) parts.push(h('span', { class: 'price-chip nrc' }, `NRC ${formatNumber(nrc)}${currency}`))
  parts.push(h('span', { class: 'price-chip mrc' }, `MRC ${formatNumber(mrc)}${currency}`))
  return parts
}

function priceExtraSummary(row = {}) {
  const parts = []
  const quantity = Number(row.default_quantity || 1)
  const includedIp = Number(row.included_ip_quantity || 0)
  const ipPrice = Number(row.ip_unit_price || 0)
  const taxRate = Number(row.default_tax_rate || 0)
  if (quantity !== 1) parts.push(`默认数量 ${formatNumber(quantity)}`)
  if (includedIp) parts.push(`含 IP ${formatNumber(includedIp)}`)
  if (ipPrice) parts.push(`IP ${formatNumber(ipPrice)}${row.currency || ''}/个`)
  if (taxRate) parts.push(`税率 ${formatNumber(taxRate * 100)}%`)
  return parts.join(' · ')
}

function serviceTagType(serviceType = '') {
  if (['DIA', 'CN2', 'IEPL', 'EPL', 'IP Transit'].includes(serviceType)) return 'info'
  if (['云主机', '物理服务器'].includes(serviceType)) return 'success'
  if (['机柜', '机位', 'kW', 'kWh', 'A'].includes(serviceType)) return 'warning'
  if (['IPv4 段', 'IPv4 个', 'IPv6', 'ASN', 'Prefix'].includes(serviceType)) return 'error'
  return 'default'
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString('zh-CN', { maximumFractionDigits: 4 })
}

function templateSpecSummary(row = {}) {
  if (row.service_type === 'IEPL') {
    const parsed = parseIeplSpec(row.product_code)
    const parts = [
      parsed.guaranteed ? `Guaranteed ${parsed.guaranteed}` : '',
      parsed.burst ? `Burst ${parsed.burst}` : '',
    ].filter(Boolean)
    if (parts.length) return parts.join(' / ')
  }
  return row.product_code || '未设置规格'
}

function syncTemplateName() {
  form.name = buildTemplateName()
}

function buildTemplateName() {
  return [
    templateRegionCode(),
    serviceTypeCode(form.service_type),
    specCode(form.product_code, form.unit),
  ].filter(Boolean).join('-')
}

function templateRegionCode() {
  const source = regionCode(form.region_id)
  const target = form.service_type === 'IEPL' ? regionCode(form.target_region_id) : ''
  return [source, target].filter(Boolean).join('-')
}

function regionCode(regionId) {
  const region = regions.value.find((item) => item.id === regionId)
  return regionCodeFromRegion(region)
}

function regionCodeFromRegion(region) {
  if (!region) return ''
  const code = fieldText(region.region_code || region.code)
  if (code) return normalizeTemplateCode(code)
  return normalizeTemplateCode(translateCity(region.region_city || region.city) || region.name || region.region_name)
}

function serviceTypeCode(serviceType) {
  return serviceTypeCodeMap[serviceType] || normalizeTemplateCode(serviceType)
}

function specCode(value, unit) {
  const base = normalizeTemplateCode(value)
  if (!base) return ''
  if (String(unit || '').toLowerCase().includes('95th') && !base.includes('95TH')) return `${base}-95TH`
  return base
}

function buildIeplProductCode() {
  const guaranteed = bandwidthValueWithUnit(form.guaranteed, form.unit)
  const burst = bandwidthValueWithUnit(form.burst, form.unit)
  return [guaranteed ? `Guaranteed ${guaranteed}` : '', burst ? `Burst ${burst}` : '']
    .filter(Boolean)
    .join(' / ')
}

function parseIeplSpec(value) {
  const text = String(value || '').trim()
  if (!text) return { guaranteed: '', burst: '' }
  const guaranteedMatch = text.match(/(?:guaranteed|commit)\s*[:：-]?\s*([^/]+?)(?=\s*(?:\/|burst|$))/i)
  const burstMatch = text.match(/burst\s*[:：-]?\s*([^/]+)$/i)
  const legacyParts = text
    .split('/')
    .map((item) => item.trim())
    .filter(Boolean)
  return {
    guaranteed: cleanBandwidthValue(guaranteedMatch?.[1] || legacyParts[0]?.replace(/commit|guaranteed/ig, '') || ''),
    burst: cleanBandwidthValue(burstMatch?.[1] || legacyParts[1]?.replace(/burst/ig, '') || ''),
  }
}

function cleanBandwidthValue(value) {
  return String(value || '')
    .replace(/\b(commit|guaranteed|burst)\b/ig, '')
    .trim()
}

function bandwidthValueWithUnit(value, unit) {
  const text = cleanBandwidthValue(value)
  if (!text) return ''
  if (/[a-zA-Z]/.test(text)) return text.replace(/\s+/g, '')
  const unitLabel = bandwidthUnitFromBillingUnit(unit)
  return unitLabel ? `${text}${unitLabel}` : text
}

function bandwidthUnitFromBillingUnit(unit) {
  const text = String(unit || '').split('/')[0].trim()
  if (!text) return ''
  return text.replace(/\s+/g, '')
}

function normalizeTemplateCode(value) {
  return String(value || '')
    .trim()
    .replace(/\s+\/\s+/g, '-')
    .replace(/\s+／\s+/g, '-')
    .replace(/分钟/g, 'MIN')
    .replace(/小时/g, 'H')
    .replace(/半天/g, 'HALF-DAY')
    .replace(/全天/g, 'FULL-DAY')
    .replace(/按实际用量/g, 'USAGE')
    .replace(/保底电量/g, 'COMMIT')
    .replace(/超额电量/g, 'OVERAGE')
    .replace(/整柜/g, 'FULL-RACK')
    .replace(/半柜/g, 'HALF-RACK')
    .replace(/柜/g, 'RACK')
    .replace(/台/g, 'SERVER')
    .replace(/\s+/g, '-')
    .replace(/[^a-zA-Z0-9/.-]+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '')
    .toUpperCase()
}

function popRegionPathParts(item = {}) {
  const country = translateCountry(fieldText(item.country) || fieldText(item.country_name))
  const city = translateCity(fieldText(item.city) || fieldText(item.city_name))
  const regionParts = regionPathParts(fieldText(item.name) || fieldText(item.region_name))
  const values = [country, city]
  if (!city) {
    regionParts.forEach((part) => {
      const label = translateRegionAlias(part) || fieldText(part)
      if (!label) return
      const key = normalizeRegion(label)
      if (!key || values.some((value) => normalizeRegion(value) === key)) return
      values.push(label)
    })
  }
  const parts = []
  values.forEach((value) => {
    const label = translateRegionAlias(value) || fieldText(value)
    if (!label) return
    const key = normalizeRegion(label)
    if (!key || parts.some((part) => normalizeRegion(part) === key)) return
    parts.push(label)
  })
  return parts
}

function ensureRegionPath(roots, parts, region = {}) {
  let children = roots
  let current = null
  const path = []
  parts.forEach((part, index) => {
    const label = translateRegionAlias(part) || part
    const key = normalizeRegion(label)
    if (!key) return
    path.push(label)
    const isLeaf = index === parts.length - 1
    const value = isLeaf ? region.id : `region:${path.join('/')}`
    let node = children.find((item) => normalizeRegion(item.label) === key)
    if (!node) {
      node = {
        label,
        value,
        region: label,
        searchText: uniqueValues([path.join(' '), label, region.name, region.code]).join(' '),
        children: [],
      }
      children.push(node)
    } else {
      node.searchText = uniqueValues([node.searchText, path.join(' '), label, region.name, region.code]).join(' ')
      if (isLeaf && !regions.value.some((item) => item.id === node.value)) node.value = value
    }
    current = node
    children = node.children
  })
  return current
}

function sortCascaderTree(nodes) {
  return nodes
    .sort((left, right) => String(left.label || '').localeCompare(String(right.label || ''), 'zh-Hans-CN'))
    .map((node) => ({
      ...node,
      children: node.children?.length ? sortCascaderTree(node.children) : undefined,
    }))
}

function regionPathParts(value) {
  const parts = displayRegionText(value)
    .split(/[\/／\\]+/)
    .map((item) => translateRegionAlias(item.trim()) || item.trim())
    .filter(Boolean)
  return parts.length ? parts : [canonicalRegion(value)].filter(Boolean)
}

function displayRegionText(value) {
  const text = fieldText(value)
  if (!text) return ''
  return translateLocationPath(text) || translateCountry(text) || translateCity(text) || text
}

function translateRegionAlias(value) {
  const text = fieldText(value)
  if (!text) return ''
  return translateCity(text) || translateCountry(text) || text
}

function canonicalRegion(value) {
  const text = displayRegionText(value)
  if (!text) return ''
  return text
    .split(/[\/／\\]+/)
    .map((item) => item.trim())
    .filter(Boolean)
    .pop() || text
}

function normalizeRegion(value) {
  return String(value || '')
    .toLowerCase()
    .replace(/[\s　]+/g, '')
    .replace(/[，、|]+/g, ',')
    .replace(/[／\\]+/g, '/')
    .replace(/\/+/g, '/')
    .trim()
}

function normalizeSearchText(value) {
  return String(value || '')
    .toLowerCase()
    .replace(/[\s　]+/g, '')
    .trim()
}

function fieldText(value) {
  return String(value ?? '').trim()
}

function uniqueValues(values) {
  return [...new Set(values.map((value) => String(value || '').trim()).filter(Boolean))]
}

function displayRegionLabel(region = {}) {
  const raw = region.region_name || translateCity(region.region_city || region.city) || region.name || ''
  const main = String(raw || '-').split('/').map((item) => item.trim()).filter(Boolean).pop() || '-'
  return main
}

function displayTargetRegionLabel(region = {}) {
  const raw = region.target_region_name || translateCity(region.target_region_city) || ''
  return String(raw || '').split('/').map((item) => item.trim()).filter(Boolean).pop() || ''
}

function displayRouteRegionLabel(row = {}) {
  const source = displayRegionLabel(row)
  const target = displayTargetRegionLabel(row)
  return target ? `${source} -> ${target}` : source
}

function iconButton(label, icon, props = {}) {
  const { type, ...buttonProps } = props
  return h(
    NTooltip,
    { trigger: 'hover' },
    {
      trigger: () => h(NButton, { size: 'small', secondary: true, circle: true, type, ...buttonProps }, { icon: renderIcon(icon, { size: 16 }) }),
      default: () => label,
    }
  )
}

onMounted(async () => {
  await Promise.all([loadRows(), loadRegions()])
})
</script>

<template>
  <CommonPage show-footer title="产品模板">
    <template #action>
      <NButton type="primary" round @click="openAdd">
        <TheIcon icon="material-symbols:add" :size="18" class="mr-5" />
        新增模板
      </NButton>
    </template>

    <div class="template-panel">
      <div class="template-toolbar">
        <QueryBarItem label="区域" :label-width="50">
          <NCascader
            v-model:value="query.region_id"
            clearable
            filterable
            check-strategy="child"
            :show-path="false"
            placeholder="从 POP 区域选择"
            :options="regionOptions"
            :filter="regionFilter"
          />
        </QueryBarItem>
        <QueryBarItem label="服务类型" :label-width="72">
          <NCascader
            v-model:value="query.service_type"
            clearable
            filterable
            check-strategy="child"
            placeholder="请选择服务类型"
            :options="serviceTypeOptions"
            :filter="serviceTypeFilter"
          />
        </QueryBarItem>
        <QueryBarItem label="状态" :label-width="50">
          <NSelect v-model:value="query.status" clearable :options="statusOptions" />
        </QueryBarItem>
        <NButton type="primary" secondary @click="loadRows">查询</NButton>
      </div>

      <NDataTable
        class="template-table"
        size="small"
        flex-height
        striped
        :loading="loading"
        :columns="columns"
        :data="rows"
        :pagination="{ pageSize: 20, showSizePicker: true, pageSizes: [10, 20, 50] }"
        :scroll-x="1420"
      />
    </div>

    <NModal
      v-model:show="modalVisible"
      preset="card"
      :title="form.id ? '编辑模板' : '新增模板'"
      style="width: min(980px, calc(100vw - 40px))"
      :bordered="false"
    >
      <NForm label-placement="left" label-width="86" :model="form">
        <NGrid :cols="3" :x-gap="14">
          <NGridItem>
            <NFormItem label="服务类型" required>
              <NCascader
                :value="getServiceTypeValue()"
                clearable
                filterable
                check-strategy="child"
                placeholder="请选择服务类型"
                :options="serviceTypeOptions"
                :filter="serviceTypeFilter"
                @update:value="handleServiceTypeChange"
              />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="区域" required>
              <NCascader
                v-model:value="form.region_id"
                clearable
                filterable
                check-strategy="child"
                :show-path="false"
                placeholder="从 POP 区域选择"
                :options="regionOptions"
                :filter="regionFilter"
                @update:value="handleRegionChange"
              />
            </NFormItem>
          </NGridItem>
          <NGridItem v-if="isIeplTemplate">
            <NFormItem label="目标区域">
              <NCascader
                v-model:value="form.target_region_id"
                clearable
                filterable
                check-strategy="child"
                :show-path="false"
                placeholder="选择目标 POP 区域"
                :options="regionOptions"
                :filter="regionFilter"
                @update:value="handleTargetRegionChange"
              />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="计量单位">
              <NSelect
                v-model:value="form.unit"
                clearable
                filterable
                tag
                placeholder="请选择计量单位"
                :options="unitOptions"
                @update:value="handleUnitChange"
              />
            </NFormItem>
          </NGridItem>
          <NGridItem v-if="isIeplTemplate">
            <NFormItem label="Guaranteed" required>
              <NInput
                v-model:value="form.guaranteed"
                clearable
                placeholder="如 100 或 100M"
                @update:value="handleIeplSpecChange"
              >
                <template v-if="bandwidthUnitLabel" #suffix>{{ bandwidthUnitLabel }}</template>
              </NInput>
            </NFormItem>
          </NGridItem>
          <NGridItem v-if="isIeplTemplate">
            <NFormItem label="Burst" required>
              <NInput
                v-model:value="form.burst"
                clearable
                placeholder="如 500 或 1G"
                @update:value="handleIeplSpecChange"
              >
                <template v-if="bandwidthUnitLabel" #suffix>{{ bandwidthUnitLabel }}</template>
              </NInput>
            </NFormItem>
          </NGridItem>
          <NGridItem v-else>
            <NFormItem label="参数规格" required>
              <NSelect
                v-model:value="form.product_code"
                clearable
                filterable
                tag
                placeholder="根据服务类型选择参数规格"
                :options="productCodeOptions"
                :disabled="!form.service_type"
                @update:value="handleProductCodeChange"
              />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="计费规则">
              <NSelect v-model:value="form.billing_rule" filterable tag :options="billingRuleOptions" />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="计价模型">
              <NSelect v-model:value="form.price_model" filterable tag :options="priceModelOptions" />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="NRC">
              <NInputNumber v-model:value="form.nrc_price" :precision="2" placeholder="一次性费用" />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="MRC">
              <NInputNumber v-model:value="form.mrc_price" :precision="2" placeholder="月度循环费用" />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="币种">
              <NSelect v-model:value="form.currency" filterable tag :options="currencyOptions" />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="默认数量">
              <NInputNumber v-model:value="form.default_quantity" :min="0" :precision="4" />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="包含 IP">
              <NInputNumber v-model:value="form.included_ip_quantity" :min="0" :precision="0" />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="IP 单价">
              <NInputNumber v-model:value="form.ip_unit_price" :min="0" :precision="2" />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="默认税率">
              <NInputNumber v-model:value="form.default_tax_rate" :min="0" :max="1" :precision="4" placeholder="如 0.2" />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="启用">
              <NSwitch v-model:value="form.status" />
            </NFormItem>
          </NGridItem>
        </NGrid>
        <NFormItem label="备注">
          <NInput v-model:value="form.remark" type="textarea" :autosize="{ minRows: 2, maxRows: 4 }" />
        </NFormItem>
      </NForm>
      <template #footer>
        <NSpace justify="end">
          <NButton @click="modalVisible = false">取消</NButton>
          <NButton type="primary" :loading="modalLoading" @click="saveRow">保存</NButton>
        </NSpace>
      </template>
    </NModal>
  </CommonPage>
</template>

<style scoped>
.template-panel {
  display: flex;
  height: calc(100vh - 204px);
  max-height: calc(100vh - 204px);
  min-height: 420px;
  padding: 16px;
  overflow: hidden;
  flex-direction: column;
  background: #fff;
  border: 1px solid #e9edf3;
  border-radius: 8px;
  box-shadow: 0 8px 24px rgb(15 23 42 / 3%);
}

.template-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  padding: 2px 0 16px;
  margin-bottom: 4px;
  border-bottom: 1px solid #edf0f5;
}

.template-toolbar :deep(.query-bar-item) {
  margin-bottom: 0;
}

.template-toolbar :deep(.n-cascader),
.template-toolbar :deep(.n-select) {
  width: 220px;
}

:deep(.n-data-table) {
  min-height: 0;
  margin-top: 14px;
}

.template-table {
  flex: 1;
  min-height: 0;
}

:deep(.n-data-table .n-data-table-th) {
  height: 44px;
  color: #334155;
  font-weight: 600;
  background: #f8fafc;
}

:deep(.n-data-table .n-data-table-td) {
  height: 82px;
  vertical-align: middle;
}

.template-name-cell,
.template-spec-cell {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.template-spec-text {
  min-width: 0;
  overflow: hidden;
  color: #0f172a;
  font-size: 15px;
  font-weight: 700;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.template-code-text {
  min-width: 0;
  overflow: hidden;
  color: #0f172a;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
  font-size: 13px;
  font-weight: 650;
  line-height: 1.4;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.meta-text,
.template-remark,
.region-text,
.billing-sub,
.billing-extra {
  overflow: hidden;
  color: #64748b;
  font-size: 12px;
  line-height: 1.4;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.template-remark {
  max-width: 520px;
  color: #94a3b8;
}

.service-cell {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
  min-width: 0;
}

.billing-cell {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 5px;
}

.price-line {
  display: inline-flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  align-items: center;
  gap: 6px;
  color: #0f172a;
}

.price-chip {
  display: inline-flex;
  align-items: center;
  height: 24px;
  padding: 0 8px;
  font-size: 12px;
  font-weight: 600;
  line-height: 24px;
  border-radius: 999px;
}

.price-chip.mrc {
  color: #0f4f9f;
  background: #eaf3ff;
}

.price-chip.nrc {
  color: #9a4b00;
  background: #fff3df;
}

.billing-extra {
  max-width: 260px;
  color: #8a95a6;
}

@media (max-width: 900px) {
  .template-panel {
    padding: 12px;
  }

  .template-toolbar {
    align-items: stretch;
  }

  .template-toolbar :deep(.query-bar-item),
  .template-toolbar :deep(.n-cascader),
  .template-toolbar :deep(.n-select) {
    width: 100%;
  }
}
</style>
