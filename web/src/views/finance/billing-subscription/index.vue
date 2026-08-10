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

defineOptions({ name: '产品订阅' })

const loading = ref(false)
const modalVisible = ref(false)
const modalLoading = ref(false)
const templateModalVisible = ref(false)
const templateLoading = ref(false)
const rows = ref([])
const companies = ref([])
const templates = ref([])
const query = reactive({ company_id: null, is_active: null })
const form = reactive(createForm())
const templateForm = reactive(createTemplateForm())

const activeOptions = [
  { label: '激活', value: true },
  { label: '停用', value: false },
]

const currencyOptions = ['CNY', 'USD', 'HKD', 'EUR', 'GBP', 'JPY', 'SGD'].map((item) => ({
  label: item,
  value: item,
}))

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
    .map((item) => ({ label: item.name, value: item.id, template: item }))
)

const columns = [
  { title: '客户', key: 'company_name', width: 180, fixed: 'left', ellipsis: { tooltip: true } },
  { title: '产品Code', key: 'product_code', width: 120 },
  { title: '服务类型', key: 'service_type', width: 110 },
  { title: '服务名称', key: 'service_name', width: 180, ellipsis: { tooltip: true } },
  { title: '服务位置', key: 'service_location', width: 160, ellipsis: { tooltip: true } },
  { title: '计费周期', key: 'billing_start_date', width: 210, render: (row) => `${row.billing_start_date || '-'} ~ ${row.billing_end_date || '长期'}` },
  { title: '单价', key: 'unit_price', width: 130, align: 'right', render: (row) => `${row.currency || ''} ${formatNumber(row.unit_price)}` },
  { title: '数量', key: 'quantity', width: 90, align: 'right' },
  { title: '计量单位', key: 'unit', width: 100 },
  { title: 'VAT', key: 'vat_rate', width: 90, align: 'right', render: (row) => `${formatNumber(Number(row.vat_rate || 0) * 100)}%` },
  { title: '最后计费', key: 'last_billed_month', width: 120, render: (row) => row.last_billed_month ? String(row.last_billed_month).slice(0, 7) : '-' },
  {
    title: '状态',
    key: 'is_active',
    width: 90,
    align: 'center',
    render: (row) => h(NTag, { type: row.is_active ? 'success' : 'default', bordered: false, round: true }, { default: () => (row.is_active ? '激活' : '停用') }),
  },
  {
    title: '操作',
    key: 'actions',
    width: 110,
    fixed: 'right',
    align: 'center',
    render: (row) => h(NSpace, { size: 8, justify: 'center' }, () => [
      iconButton('编辑', 'material-symbols:edit', { type: 'primary', onClick: () => openEdit(row) }),
      h(
        NPopconfirm,
        { onPositiveClick: () => deleteRow(row) },
        {
          trigger: () => iconButton('删除', 'material-symbols:delete-outline', { type: 'error' }),
          default: () => `确定删除订阅「${row.product_code || row.service_name || ''}」吗？`,
        }
      ),
    ]),
  },
]

const templateColumns = [
  { title: '模板名', key: 'name', width: 180, fixed: 'left', ellipsis: { tooltip: true } },
  { title: '产品Code', key: 'product_code', width: 120 },
  { title: '服务类型', key: 'service_type', width: 120 },
  { title: '计费规则', key: 'billing_rule', width: 100 },
  { title: '单价', key: 'unit_price', width: 130, align: 'right', render: (row) => `${row.currency || ''} ${formatNumber(row.unit_price)}` },
  { title: '计量单位', key: 'unit', width: 110 },
  { title: '默认合同', key: 'default_contract_months', width: 100, render: (row) => `${row.default_contract_months || 12}个月` },
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
      iconButton('编辑模板', 'material-symbols:edit', { type: 'primary', onClick: () => openTemplateEdit(row) }),
      h(
        NPopconfirm,
        { onPositiveClick: () => deleteTemplate(row) },
        {
          trigger: () => iconButton('删除模板', 'material-symbols:delete-outline', { type: 'error' }),
          default: () => `确定删除模板「${row.name || ''}」吗？`,
        }
      ),
    ]),
  },
]

function createForm(source = {}) {
  return {
    id: source.id || null,
    company_id: source.company_id || null,
    template_id: source.template_id || null,
    product_code: source.product_code || '',
    service_type: source.service_type || '',
    service_name: source.service_name || '',
    service_location: source.service_location || '',
    billing_start_date: source.billing_start_date || getMonthFirstDay(),
    billing_end_date: source.billing_end_date || null,
    contract_months: Number(source.contract_months || 12),
    unit_price: Number(source.unit_price || 0),
    quantity: Number(source.quantity || 1),
    currency: source.currency || 'USD',
    unit: source.unit || '',
    vat_rate: Number(source.vat_rate || 0),
    is_active: source.is_active ?? true,
    last_billed_month: source.last_billed_month || null,
    remark: source.remark || '',
  }
}

function createTemplateForm(source = {}) {
  return {
    id: source.id || null,
    name: source.name || '',
    product_code: source.product_code || '',
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

async function loadBaseData() {
  const [companyRes, templateRes] = await Promise.all([
    api.getCompanyList({ page: 1, page_size: 9999, business_only: true, status: true }),
    api.getBillingTemplates({}),
  ])
  companies.value = companyRes?.data || []
  templates.value = templateRes?.data || []
}

async function loadTemplates() {
  const res = await api.getBillingTemplates({})
  templates.value = res?.data || []
}

async function loadRows() {
  loading.value = true
  try {
    const res = await api.getBillingSubscriptions({ ...query })
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
  form.product_code = template.product_code || form.product_code
  form.service_type = template.service_type || form.service_type
  form.service_name = template.name || form.service_name
  form.unit_price = Number(template.unit_price || 0)
  form.currency = template.currency || 'USD'
  form.unit = template.unit || ''
  form.contract_months = Number(template.default_contract_months || 12)
}

async function saveRow() {
  if (!form.company_id) return window.$message?.warning?.('请选择客户')
  if (!form.product_code) return window.$message?.warning?.('请填写产品Code')
  modalLoading.value = true
  try {
    await api.saveBillingSubscription({ ...form })
    window.$message?.success?.('保存成功')
    modalVisible.value = false
    await loadRows()
  } finally {
    modalLoading.value = false
  }
}

async function deleteRow(row) {
  await api.deleteBillingSubscription(row.id)
  window.$message?.success?.('删除成功')
  await loadRows()
}

function openTemplateManager() {
  Object.assign(templateForm, createTemplateForm())
  templateModalVisible.value = true
  loadTemplates()
}

function openTemplateEdit(row) {
  Object.assign(templateForm, createTemplateForm(row))
}

async function saveTemplate() {
  if (!templateForm.name) return window.$message?.warning?.('请填写模板名')
  templateLoading.value = true
  try {
    await api.saveBillingTemplate({ ...templateForm })
    window.$message?.success?.('模板已保存')
    Object.assign(templateForm, createTemplateForm())
    await loadTemplates()
  } finally {
    templateLoading.value = false
  }
}

async function deleteTemplate(row) {
  await api.deleteBillingTemplate(row.id)
  window.$message?.success?.('模板已删除')
  await loadTemplates()
}

function formatDateValue(date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function getMonthFirstDay() {
  const now = new Date()
  return formatDateValue(new Date(now.getFullYear(), now.getMonth(), 1))
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString('zh-CN', { maximumFractionDigits: 4 })
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
  await loadBaseData()
  await loadRows()
})
</script>

<template>
  <CommonPage show-footer title="产品订阅">
    <template #action>
      <NButton secondary round @click="openTemplateManager">
        <TheIcon icon="mdi:shape-outline" :size="18" class="mr-5" />
        模板管理
      </NButton>
      <NButton type="primary" round @click="openAdd">
        <TheIcon icon="material-symbols:add" :size="18" class="mr-5" />
        新增订阅
      </NButton>
    </template>

    <div class="subscription-toolbar">
      <QueryBarItem label="客户" :label-width="50">
        <NSelect v-model:value="query.company_id" clearable filterable :options="companyOptions" />
      </QueryBarItem>
      <QueryBarItem label="状态" :label-width="50">
        <NSelect v-model:value="query.is_active" clearable :options="activeOptions" />
      </QueryBarItem>
      <NButton type="primary" secondary @click="loadRows">查询</NButton>
    </div>

    <NDataTable
      :loading="loading"
      :columns="columns"
      :data="rows"
      :pagination="{ pageSize: 20 }"
      :scroll-x="1690"
      size="small"
    />

    <NModal
      v-model:show="modalVisible"
      preset="card"
      :title="form.id ? '编辑产品订阅' : '新增产品订阅'"
      style="width: min(980px, calc(100vw - 40px))"
      :bordered="false"
    >
      <NForm label-placement="left" label-width="86" :model="form">
        <NGrid :cols="3" :x-gap="14">
          <NGridItem>
            <NFormItem label="客户" required>
              <NSelect v-model:value="form.company_id" filterable :options="companyOptions" />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="模板">
              <NSelect v-model:value="form.template_id" clearable filterable :options="templateOptions" @update:value="handleTemplateChange" />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="产品Code" required>
              <NInput v-model:value="form.product_code" placeholder="如 10G / 16*VM" />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="服务类型">
              <NInput v-model:value="form.service_type" placeholder="DIA / Cloud VM" />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="服务名称">
              <NInput v-model:value="form.service_name" placeholder="SG1-DIA-10G" />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="服务位置">
              <NInput v-model:value="form.service_location" placeholder="Equinix SG1" />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="开始日期">
              <NDatePicker v-model:formatted-value="form.billing_start_date" type="date" value-format="yyyy-MM-dd" clearable />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="结束日期">
              <NDatePicker v-model:formatted-value="form.billing_end_date" type="date" value-format="yyyy-MM-dd" clearable />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="合同月数">
              <NInputNumber v-model:value="form.contract_months" :min="1" />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="单价">
              <NInputNumber v-model:value="form.unit_price" :min="0" :precision="2" />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="数量">
              <NInputNumber v-model:value="form.quantity" :min="0" :precision="2" />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="币种">
              <NSelect v-model:value="form.currency" filterable tag :options="currencyOptions" />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="计量单位">
              <NInput v-model:value="form.unit" placeholder="Gbps·月 / VM·月" />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="VAT">
              <NInputNumber v-model:value="form.vat_rate" :min="0" :max="1" :precision="4" />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="启用">
              <NSwitch v-model:value="form.is_active" />
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

    <NModal
      v-model:show="templateModalVisible"
      preset="card"
      title="模板管理"
      style="width: min(1040px, calc(100vw - 40px))"
      :bordered="false"
    >
      <NForm label-placement="left" label-width="86" :model="templateForm">
        <NGrid :cols="4" :x-gap="12">
          <NGridItem>
            <NFormItem label="模板名" required>
              <NInput v-model:value="templateForm.name" placeholder="SG1-DIA-10G" />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="产品Code">
              <NInput v-model:value="templateForm.product_code" placeholder="10G" />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="服务类型">
              <NInput v-model:value="templateForm.service_type" placeholder="DIA / Cloud VM" />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="计费规则">
              <NInput v-model:value="templateForm.billing_rule" placeholder="monthly" />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="单价">
              <NInputNumber v-model:value="templateForm.unit_price" :min="0" :precision="2" />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="币种">
              <NSelect v-model:value="templateForm.currency" filterable tag :options="currencyOptions" />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="计量单位">
              <NInput v-model:value="templateForm.unit" placeholder="Gbps·月 / VM·月" />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="默认合同">
              <NInputNumber v-model:value="templateForm.default_contract_months" :min="1" />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="启用">
              <NSwitch v-model:value="templateForm.status" />
            </NFormItem>
          </NGridItem>
        </NGrid>
        <NFormItem label="备注">
          <NInput v-model:value="templateForm.remark" type="textarea" :autosize="{ minRows: 2, maxRows: 4 }" />
        </NFormItem>
        <NSpace justify="end">
          <NButton secondary @click="Object.assign(templateForm, createTemplateForm())">清空</NButton>
          <NButton type="primary" :loading="templateLoading" @click="saveTemplate">保存模板</NButton>
        </NSpace>
      </NForm>

      <NDataTable
        class="template-table"
        size="small"
        :columns="templateColumns"
        :data="templates"
        :pagination="{ pageSize: 8 }"
        :scroll-x="1060"
      />
    </NModal>
  </CommonPage>
</template>

<style scoped>
.subscription-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}

.template-table {
  margin-top: 16px;
}
</style>
