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
  const grouped = new Map()
  regions.value.forEach((region) => {
    const country = String(region.country || '未分组').trim() || '未分组'
    if (!grouped.has(country)) {
      grouped.set(country, { label: country, value: `country:${country}`, children: [] })
    }
    grouped.get(country).children.push({
      label: regionOptionLabel(region),
      value: region.id,
      country: region.country || '',
      city: region.city || '',
      name: region.name || '',
      code: region.code || '',
    })
  })
  return Array.from(grouped.values())
})

const columns = [
  {
    title: '模板信息',
    key: 'template',
    minWidth: 260,
    fixed: 'left',
    render: (row) =>
      h('div', { class: 'template-cell' }, [
        h('div', { class: 'template-name' }, row.name || '-'),
        h('div', { class: 'template-meta' }, [
          h('span', { class: 'spec-pill' }, row.product_code || '未设置规格'),
          row.remark ? h('span', { class: 'meta-text' }, row.remark) : null,
        ]),
      ]),
  },
  {
    title: '服务 / 区域',
    key: 'service',
    minWidth: 230,
    render: (row) =>
      h('div', { class: 'service-cell' }, [
        h(NTag, { type: serviceTagType(row.service_type), bordered: false, round: true }, { default: () => row.service_type || '-' }),
        h('span', { class: 'region-text' }, displayRegionLabel(row)),
      ]),
  },
  {
    title: '计费',
    key: 'billing',
    minWidth: 220,
    align: 'right',
    render: (row) =>
      h('div', { class: 'billing-cell' }, [
        h('div', { class: 'price-line' }, [
          h('span', { class: 'price' }, formatNumber(row.unit_price)),
          h('span', { class: 'currency' }, row.currency || ''),
        ]),
        h('div', { class: 'billing-sub' }, `${billingRuleText(row.billing_rule)} · ${row.unit || '-'}`),
      ]),
  },
  {
    title: '默认合同',
    key: 'contract',
    width: 120,
    align: 'center',
    render: (row) => h('span', { class: 'contract-pill' }, `${row.default_contract_months || 12}个月`),
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
    region_id: source.region_id || null,
    service_type: source.service_type || '',
    billing_rule: source.billing_rule || 'monthly',
    unit_price: Number(source.unit_price || 0),
    currency: source.currency || 'USD',
    unit: source.unit || '',
    default_contract_months: Number(source.default_contract_months || 12),
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
  const values = baseValues.map((item) => {
    if (!unit || !unit.includes('95th') || !/^\d/.test(item) || item.includes('95th')) return item
    return `${item} 95th`
  })
  if (currentValue && !values.includes(currentValue)) {
    values.unshift(currentValue)
  }
  return values.map((item) => ({ label: item, value: item }))
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
    return
  }
  form.service_type = option.serviceType || ''
  syncUnitOptions(option)
  if (!unitOptions.value.some((item) => item.value === form.unit)) {
    form.unit = option.unit || ''
  }
  if (!productCodeOptions.value.some((item) => item.value === form.product_code)) {
    form.product_code = ''
  }
}

function serviceTypeFilter(pattern, option, path = []) {
  const text = [option.label, option.serviceType, option.unit, ...path.map((item) => item.label)]
    .filter(Boolean)
    .join(' ')
    .toLowerCase()
  return text.includes(String(pattern || '').toLowerCase())
}

function regionFilter(pattern, option, path = []) {
  const text = [
    option.label,
    option.country,
    option.city,
    option.name,
    option.code,
    ...path.map((item) => item.label),
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase()
  return text.includes(String(pattern || '').trim().toLowerCase())
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
}

function openAdd() {
  Object.assign(form, createForm())
  syncUnitOptions()
  modalVisible.value = true
}

function openEdit(row) {
  Object.assign(form, createForm(row))
  syncUnitOptions()
  modalVisible.value = true
}

async function saveRow() {
  if (!form.name) return window.$message?.warning?.('请填写模板名')
  modalLoading.value = true
  try {
    await api.saveBillingTemplate({ ...form })
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

function regionOptionLabel(region = {}) {
  const city = region.region_city || region.city || region.name || ''
  const code = region.region_code || region.code || ''
  return code ? `${city || '-'} (${code})` : city || '-'
}

function displayRegionLabel(region = {}) {
  const raw = region.region_name || regionOptionLabel(region)
  const main = String(raw || '-').split('/').map((item) => item.trim()).filter(Boolean).pop() || '-'
  return main
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
        size="small"
        striped
        :loading="loading"
        :columns="columns"
        :data="rows"
        :pagination="{ pageSize: 20, showSizePicker: true, pageSizes: [10, 20, 50] }"
        :scroll-x="1040"
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
            <NFormItem label="模板名" required>
              <NInput v-model:value="form.name" placeholder="SG1-DIA-10G" />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="参数规格">
              <NSelect
                v-model:value="form.product_code"
                clearable
                filterable
                placeholder="根据服务类型选择参数规格"
                :options="productCodeOptions"
              />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="区域">
              <NCascader
                v-model:value="form.region_id"
                clearable
                filterable
                check-strategy="child"
                :show-path="false"
                placeholder="从 POP 区域选择"
                :options="regionOptions"
                :filter="regionFilter"
              />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="服务类型">
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
            <NFormItem label="计费规则">
              <NSelect v-model:value="form.billing_rule" filterable tag :options="billingRuleOptions" />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="单价">
              <NInputNumber v-model:value="form.unit_price" :min="0" :precision="2" />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="币种">
              <NSelect v-model:value="form.currency" filterable tag :options="currencyOptions" />
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
              />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="默认合同">
              <NInputNumber v-model:value="form.default_contract_months" :min="1" />
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
  min-height: calc(100vh - 176px);
  padding: 16px;
  overflow: hidden;
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
  margin-top: 14px;
}

:deep(.n-data-table .n-data-table-th) {
  height: 44px;
  color: #334155;
  font-weight: 600;
  background: #f8fafc;
}

:deep(.n-data-table .n-data-table-td) {
  height: 58px;
  vertical-align: middle;
}

.template-cell {
  display: flex;
  flex-direction: column;
  gap: 7px;
  min-width: 0;
}

.template-name {
  overflow: hidden;
  color: #0f172a;
  font-size: 14px;
  font-weight: 650;
  line-height: 1.25;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.template-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.spec-pill,
.contract-pill {
  display: inline-flex;
  align-items: center;
  max-width: 126px;
  height: 24px;
  padding: 0 10px;
  overflow: hidden;
  color: #31557a;
  font-size: 12px;
  line-height: 24px;
  text-overflow: ellipsis;
  white-space: nowrap;
  background: #eef5fb;
  border-radius: 999px;
}

.contract-pill {
  color: #5f6470;
  background: #f2f4f7;
}

.meta-text,
.region-text,
.billing-sub {
  overflow: hidden;
  color: #64748b;
  font-size: 12px;
  line-height: 1.4;
  text-overflow: ellipsis;
  white-space: nowrap;
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
  align-items: baseline;
  gap: 6px;
  color: #0f172a;
}

.currency {
  color: #64748b;
  font-size: 12px;
  font-weight: 600;
}

.price {
  font-size: 15px;
  font-weight: 700;
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
