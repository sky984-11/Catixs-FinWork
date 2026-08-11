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
const query = reactive({ keyword: '', status: null })
const form = reactive(createForm())

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

const filteredRows = computed(() => {
  const keyword = query.keyword.trim().toLowerCase()
  if (!keyword) return rows.value
  return rows.value.filter((row) =>
    [row.name, row.product_code, row.service_type, row.billing_rule, row.unit, row.remark]
      .some((value) => String(value || '').toLowerCase().includes(keyword))
  )
})

const columns = [
  { title: '模板名', key: 'name', width: 190, fixed: 'left', ellipsis: { tooltip: true } },
  { title: '产品Code', key: 'product_code', width: 120 },
  { title: '服务类型', key: 'service_type', width: 130 },
  { title: '计费规则', key: 'billing_rule', width: 100, render: (row) => billingRuleText(row.billing_rule) },
  {
    title: '单价',
    key: 'unit_price',
    width: 130,
    align: 'right',
    render: (row) => `${row.currency || ''} ${formatNumber(row.unit_price)}`,
  },
  { title: '计量单位', key: 'unit', width: 120 },
  {
    title: '默认合同',
    key: 'default_contract_months',
    width: 110,
    render: (row) => `${row.default_contract_months || 12}个月`,
  },
  { title: '备注', key: 'remark', minWidth: 220, ellipsis: { tooltip: true } },
  {
    title: '状态',
    key: 'status',
    width: 90,
    align: 'center',
    render: (row) =>
      h(NTag, { type: row.status ? 'success' : 'default', bordered: false, round: true }, {
        default: () => (row.status ? '启用' : '停用'),
      }),
  },
  {
    title: '操作',
    key: 'actions',
    width: 110,
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

async function loadRows() {
  loading.value = true
  try {
    const params = {}
    if (query.status !== null && query.status !== undefined) params.status = query.status
    const res = await api.getBillingTemplates(params)
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

onMounted(loadRows)
</script>

<template>
  <CommonPage show-footer title="产品模板">
    <template #action>
      <NButton type="primary" round @click="openAdd">
        <TheIcon icon="material-symbols:add" :size="18" class="mr-5" />
        新增模板
      </NButton>
    </template>

    <div class="template-toolbar">
      <QueryBarItem label="关键词" :label-width="62">
        <NInput v-model:value="query.keyword" clearable placeholder="模板名 / 产品Code / 服务类型" />
      </QueryBarItem>
      <QueryBarItem label="状态" :label-width="50">
        <NSelect v-model:value="query.status" clearable :options="statusOptions" />
      </QueryBarItem>
      <NButton type="primary" secondary @click="loadRows">查询</NButton>
    </div>

    <NDataTable
      size="small"
      :loading="loading"
      :columns="columns"
      :data="filteredRows"
      :pagination="{ pageSize: 20 }"
      :scroll-x="1320"
    />

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
            <NFormItem label="产品Code">
              <NInput v-model:value="form.product_code" placeholder="10G" />
            </NFormItem>
          </NGridItem>
          <NGridItem>
            <NFormItem label="服务类型">
              <NInput v-model:value="form.service_type" placeholder="DIA / Cloud VM" />
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
              <NInput v-model:value="form.unit" placeholder="Gbps/月 / VM/月" />
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
.template-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}
</style>
