<script setup>
import { computed, h, onMounted, reactive, ref } from 'vue'
import {
  NButton,
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
  NSwitch,
  NTag,
  NTooltip,
} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import api from '@/api'
import { renderIcon } from '@/utils'

defineOptions({ name: '客户价格微调' })

const loading = ref(false)
const modalVisible = ref(false)
const modalLoading = ref(false)
const rows = ref([])
const companies = ref([])
const templates = ref([])
const query = reactive({ company_id: null, service_type: null, status: null })
const form = reactive(createForm())

const statusOptions = [
  { label: '启用', value: true },
  { label: '停用', value: false },
]

const currencyOptions = ['CNY', 'USD', 'HKD', 'EUR', 'GBP', 'JPY', 'SGD'].map((item) => ({ label: item, value: item }))

const adjustmentTypeOptions = [
  { label: '固定价格', value: 'fixed_price' },
  { label: '折扣比例', value: 'discount' },
  { label: '加价比例', value: 'markup' },
  { label: '固定加减', value: 'amount_delta' },
  { label: '费用减免', value: 'waive' },
  { label: '服务抵扣', value: 'credit' },
]

const targetFieldOptions = [
  { label: 'MRC', value: 'mrc' },
  { label: 'NRC', value: 'nrc' },
  { label: 'IP 单价', value: 'ip' },
  { label: '账单总额', value: 'total' },
]

const serviceTypeOptions = computed(() => {
  const values = new Set(templates.value.map((item) => item.service_type).filter(Boolean))
  return [...values].map((item) => ({ label: item, value: item }))
})

const companyOptions = computed(() =>
  companies.value.map((item) => ({
    label: [item.name || item.legal_name || `公司 ${item.id}`, item.legal_name && item.legal_name !== item.name ? item.legal_name : '']
      .filter(Boolean)
      .join(' / '),
    value: item.id,
  }))
)

const templateOptions = computed(() =>
  templates.value
    .filter((item) => item.status)
    .map((item) => ({ label: `${item.name} · ${item.currency || 'USD'} ${formatNumber(item.mrc_price ?? item.unit_price ?? 0)}`, value: item.id, template: item }))
)

const columns = [
  {
    title: '客户 / 规则',
    key: 'company',
    minWidth: 240,
    fixed: 'left',
    render: (row) =>
      h('div', { class: 'rule-main' }, [
        h('strong', row.company_name || '-'),
        h('span', row.remark || adjustmentTypeText(row.adjustment_type)),
      ]),
  },
  {
    title: '适用范围',
    key: 'scope',
    minWidth: 260,
    render: (row) =>
      h('div', { class: 'scope-cell' }, [
        row.template_name ? h(NTag, { type: 'info', bordered: false, round: true }, { default: () => row.template_name }) : null,
        row.service_type ? h(NTag, { type: 'success', bordered: false, round: true }, { default: () => row.service_type }) : null,
        h('span', row.region_name || '全部区域'),
      ]),
  },
  {
    title: '调整方式',
    key: 'adjustment',
    minWidth: 220,
    render: (row) =>
      h('div', { class: 'adjust-cell' }, [
        h('strong', formatAdjustmentValue(row)),
        h('span', `${targetFieldText(row.target_field)} · ${adjustmentTypeText(row.adjustment_type)}`),
      ]),
  },
  {
    title: '生效期',
    key: 'date',
    width: 190,
    render: (row) => `${row.effective_date || '立即'} ~ ${row.expiry_date || '长期'}`,
  },
  { title: '优先级', key: 'priority', width: 90, align: 'center' },
  {
    title: '状态',
    key: 'status',
    width: 90,
    align: 'center',
    render: (row) => h(NTag, { type: row.status ? 'success' : 'default', bordered: false, round: true }, { default: () => (row.status ? '启用' : '停用') }),
  },
  {
    title: '操作',
    key: 'actions',
    width: 110,
    fixed: 'right',
    align: 'center',
    render: (row) => h(NSpace, { size: 8, justify: 'center' }, () => [
      iconButton('编辑', 'material-symbols:edit', { type: 'primary', onClick: () => openEdit(row) }),
      h(NPopconfirm, { onPositiveClick: () => deleteRow(row) }, {
        trigger: () => iconButton('删除', 'material-symbols:delete-outline', { type: 'error' }),
        default: () => `确定删除「${row.company_name || ''}」的价格规则吗？`,
      }),
    ]),
  },
]

function createForm(source = {}) {
  return {
    id: source.id || null,
    company_id: source.company_id || null,
    template_id: source.template_id || null,
    service_type: source.service_type || '',
    region_id: source.region_id || null,
    adjustment_type: source.adjustment_type || 'fixed_price',
    target_field: source.target_field || 'mrc',
    adjustment_value: Number(source.adjustment_value || 0),
    currency: source.currency || 'USD',
    priority: Number(source.priority || 100),
    effective_date: source.effective_date || null,
    expiry_date: source.expiry_date || null,
    status: source.status ?? true,
    remark: source.remark || '',
  }
}

async function loadBaseData() {
  const [companyRes, templateRes] = await Promise.all([
    api.getCompanyList({ page: 1, page_size: 9999, business_only: true, status: true }),
    api.getBillingTemplates({}),
  ])
  companies.value = companyRes?.data || []
  templates.value = templateRes?.data || []
}

async function loadRows() {
  loading.value = true
  try {
    const params = {}
    if (query.company_id) params.company_id = query.company_id
    if (query.service_type) params.service_type = query.service_type
    if (query.status !== null && query.status !== undefined) params.status = query.status
    const res = await api.getBillingPriceAdjustments(params)
    rows.value = res?.data || []
  } finally {
    loading.value = false
  }
}

function openAdd() {
  Object.assign(form, createForm())
  modalVisible.value = true
}

function openEdit(row) {
  Object.assign(form, createForm(row))
  modalVisible.value = true
}

function handleTemplateChange(templateId) {
  const template = templates.value.find((item) => item.id === templateId)
  if (!template) return
  form.service_type = template.service_type || form.service_type
  form.currency = template.currency || form.currency || 'USD'
}

async function saveRow() {
  if (!form.company_id) return window.$message?.warning?.('请选择客户')
  if (!form.template_id && !form.service_type) return window.$message?.warning?.('请选择模板或服务类型')
  modalLoading.value = true
  try {
    await api.saveBillingPriceAdjustment({ ...form })
    window.$message?.success?.('保存成功')
    modalVisible.value = false
    await loadRows()
  } finally {
    modalLoading.value = false
  }
}

async function deleteRow(row) {
  await api.deleteBillingPriceAdjustment(row.id)
  window.$message?.success?.('删除成功')
  await loadRows()
}

function adjustmentTypeText(value) {
  return adjustmentTypeOptions.find((item) => item.value === value)?.label || value || '-'
}

function targetFieldText(value) {
  return targetFieldOptions.find((item) => item.value === value)?.label || value || '-'
}

function formatAdjustmentValue(row) {
  const value = Number(row.adjustment_value || 0)
  if (['discount', 'markup'].includes(row.adjustment_type)) return `${formatNumber(value * 100)}%`
  if (row.adjustment_type === 'waive') return '减免'
  return `${row.currency || ''} ${formatNumber(value)}`.trim()
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString('zh-CN', { maximumFractionDigits: 4 })
}

function iconButton(label, icon, props = {}) {
  const { type, ...buttonProps } = props
  return h(NTooltip, { trigger: 'hover' }, {
    trigger: () => h(NButton, { size: 'small', secondary: true, circle: true, type, ...buttonProps }, { icon: renderIcon(icon, { size: 16 }) }),
    default: () => label,
  })
}

onMounted(async () => {
  await loadBaseData()
  await loadRows()
})
</script>

<template>
  <CommonPage show-footer title="客户价格微调">
    <template #action>
      <NButton type="primary" round @click="openAdd">
        <TheIcon icon="material-symbols:add" :size="18" class="mr-5" />
        新增规则
      </NButton>
    </template>

    <div class="price-rule-panel">
      <div class="rule-toolbar">
        <QueryBarItem label="客户" :label-width="50">
          <NSelect v-model:value="query.company_id" clearable filterable :options="companyOptions" />
        </QueryBarItem>
        <QueryBarItem label="服务类型" :label-width="70">
          <NSelect v-model:value="query.service_type" clearable filterable :options="serviceTypeOptions" />
        </QueryBarItem>
        <QueryBarItem label="状态" :label-width="50">
          <NSelect v-model:value="query.status" clearable :options="statusOptions" />
        </QueryBarItem>
        <NButton type="primary" secondary @click="loadRows">查询</NButton>
      </div>

      <NDataTable
        class="rule-table"
        size="small"
        striped
        :loading="loading"
        :columns="columns"
        :data="rows"
        :pagination="{ pageSize: 20, showSizePicker: true, pageSizes: [10, 20, 50] }"
        :scroll-x="1200"
      />
    </div>

    <NModal v-model:show="modalVisible" preset="card" :title="form.id ? '编辑价格微调' : '新增价格微调'" style="width: min(980px, calc(100vw - 40px))" :bordered="false">
      <NForm label-placement="left" label-width="90" :model="form">
        <NGrid :cols="3" :x-gap="14">
          <NGridItem>
            <NFormItem label="客户" required>
              <NSelect v-model:value="form.company_id" filterable :options="companyOptions" />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="产品模板">
              <NSelect v-model:value="form.template_id" clearable filterable :options="templateOptions" @update:value="handleTemplateChange" />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="服务类型">
              <NSelect v-model:value="form.service_type" clearable filterable tag :options="serviceTypeOptions" />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="作用范围">
              <NSelect v-model:value="form.target_field" :options="targetFieldOptions" />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="调整方式">
              <NSelect v-model:value="form.adjustment_type" :options="adjustmentTypeOptions" />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="调整值">
              <NInputNumber v-model:value="form.adjustment_value" :precision="4" placeholder="折扣填 0.9，固定价填金额" />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="币种">
              <NSelect v-model:value="form.currency" filterable tag :options="currencyOptions" />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="生效日期">
              <NDatePicker v-model:formatted-value="form.effective_date" type="date" value-format="yyyy-MM-dd" clearable />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="失效日期">
              <NDatePicker v-model:formatted-value="form.expiry_date" type="date" value-format="yyyy-MM-dd" clearable />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="优先级">
              <NInputNumber v-model:value="form.priority" :precision="0" />
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
.price-rule-panel {
  padding: 16px;
  background: #fff;
  border: 1px solid #e9edf3;
  border-radius: 8px;
}

.rule-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  padding-bottom: 14px;
  margin-bottom: 12px;
  border-bottom: 1px solid #edf0f5;
}

.rule-toolbar :deep(.n-select) {
  width: 240px;
}

.rule-main,
.adjust-cell {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 5px;
}

.rule-main strong,
.adjust-cell strong {
  overflow: hidden;
  color: #0f172a;
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rule-main span,
.adjust-cell span,
.scope-cell span {
  overflow: hidden;
  color: #64748b;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.scope-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

@media (max-width: 900px) {
  .rule-toolbar,
  .rule-toolbar :deep(.n-select) {
    width: 100%;
  }
}
</style>
