<script setup>
import { computed, h, onMounted, reactive, ref, watch } from 'vue'
import {
  NButton,
  NDataTable,
  NForm,
  NGrid,
  NFormItemGi,
  NInput,
  NPagination,
  NPopconfirm,
  NSelect,
  NSpace,
  NSwitch,
  NTag,
  NTooltip,
} from 'naive-ui'

import AppPage from '@/components/page/AppPage.vue'
import CrudModal from '@/components/table/CrudModal.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import api from '@/api'
import { renderIcon } from '@/utils'

defineOptions({ name: '客户供应商管理' })

const modalFormRef = ref(null)
const modalVisible = ref(false)
const modalLoading = ref(false)
const modalAction = ref('add')
const contractCompanyOptions = ref([])
const tableLoading = ref(false)
const companyRows = ref([])
const statsRows = ref([])
const total = ref(0)

const pagination = reactive({
  page: 1,
  pageSize: 20,
  pageSizes: [10, 20, 50, 100],
})

const queryItems = ref({
  business_only: true,
  role: null,
  contract_company_id: null,
  name: '',
  status: null,
})

const roleOptions = [
  { label: '客户', value: 1 },
  { label: '供应商', value: 2 },
]

const statusOptions = [
  { label: '启用', value: true },
  { label: '停用', value: false },
]

const modalForm = reactive(createEmptyForm())

const modalRules = {
  name: [{ required: true, message: '请输入公司简称', trigger: ['input', 'blur'] }],
  role_values: [{ required: true, type: 'array', message: '请选择类型', trigger: 'change' }],
  company_email: [{ trigger: 'blur', validator: validateOptionalEmail }],
  bill_email: [{ trigger: 'blur', validator: validateOptionalEmail }],
  noc_email: [{ trigger: 'blur', validator: validateOptionalEmail }],
}

const columns = [
  {
    title: '公司名称',
    key: 'name',
    minWidth: 220,
    ellipsis: { tooltip: true },
    render(row) {
      return h('div', { class: 'company-name-cell' }, [
        h('strong', row.name || '-'),
        h('span', row.legal_name || '未设置公司全称'),
      ])
    },
  },
  {
    title: '类型',
    key: 'role',
    width: 140,
    align: 'center',
    render(row) {
      return h(NSpace, { justify: 'center', size: 4 }, () =>
        getRoleTags(row.role).map((item) =>
          h(NTag, { type: item.type, bordered: false }, { default: () => item.label })
        )
      )
    },
  },
  {
    title: '签约主体',
    key: 'contract_company_id',
    minWidth: 140,
    ellipsis: { tooltip: true },
    render(row) {
      return row.contract_company_name || getContractCompanyName(row.contract_company_id) || '-'
    },
  },
  {
    title: '国家/地区',
    key: 'country',
    width: 110,
    ellipsis: { tooltip: true },
  },
  {
    title: '联系信息',
    key: 'company_email',
    minWidth: 240,
    render(row) {
      return h('div', { class: 'contact-cell' }, [
        h('span', row.bill_email || row.company_email || row.noc_email || '-'),
        h('span', row.company_phone || row.noc_phone || '-'),
        h('span', row.contact_person || '-'),
      ])
    },
  },
  {
    title: '税号/注册号',
    key: 'tax_no',
    minWidth: 180,
    render(row) {
      return h('div', { class: 'contact-cell' }, [
        h('span', row.tax_no || '-'),
        h('span', row.registration_no || '-'),
      ])
    },
  },
  {
    title: '状态',
    key: 'status',
    width: 80,
    align: 'center',
    render(row) {
      return h(
        NTag,
        { type: row.status ? 'success' : 'default', bordered: false },
        { default: () => (row.status ? '启用' : '停用') }
      )
    },
  },
  {
    title: '操作',
    key: 'actions',
    width: 92,
    align: 'center',
    fixed: 'right',
    render(row) {
      return h(NSpace, { class: 'row-actions', justify: 'center', size: 8, wrap: false }, () => [
        renderIconButton('编辑', 'material-symbols:edit', { type: 'primary', onClick: () => openEdit(row) }),
        h(
          NPopconfirm,
          { onPositiveClick: () => handleDelete(row) },
          {
            trigger: () =>
              renderIconButton('删除', 'material-symbols:delete-outline', { type: 'error' }),
            default: () => `确定删除 ${row.name || '该记录'} 吗？`,
          }
        ),
      ])
    },
  },
]

const customerCount = computed(() =>
  statsRows.value.filter((item) => [1, 3].includes(Number(item.role))).length
)
const vendorCount = computed(() =>
  statsRows.value.filter((item) => [2, 3].includes(Number(item.role))).length
)
const activeCount = computed(() => statsRows.value.filter((item) => item.status !== false).length)

function createEmptyForm() {
  return {
    id: null,
    role: 1,
    role_values: [1],
    name: '',
    legal_name: '',
    country: '',
    address: '',
    company_email: '',
    bill_email: '',
    contact_person: '',
    company_phone: '',
    noc_email: '',
    noc_phone: '',
    registration_no: '',
    tax_no: '',
    contract_company_id: null,
    remark: '',
    status: true,
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

function resetForm() {
  Object.assign(modalForm, createEmptyForm())
}

async function loadContractCompanies() {
  const res = await api.getCompanyList({ page: 1, page_size: 9999, role: 0, status: true })
  contractCompanyOptions.value = (res?.data || []).map((item) => ({
    label: item.name,
    value: item.id,
  }))
}

async function loadRows() {
  tableLoading.value = true
  try {
    const [res, statsRes] = await Promise.all([
      api.getCompanyList({
        ...queryItems.value,
        page: pagination.page,
        page_size: pagination.pageSize,
      }),
      api.getCompanyList({
        ...queryItems.value,
        page: 1,
        page_size: 9999,
      }),
    ])
    companyRows.value = res?.data || []
    statsRows.value = statsRes?.data || []
    total.value = Number(res?.total || 0)
  } finally {
    tableLoading.value = false
  }
}

async function handleSearch() {
  pagination.page = 1
  await loadRows()
}

async function handleRefresh() {
  await loadRows()
}

async function handlePageChange(page) {
  pagination.page = page
  await loadRows()
}

async function handlePageSizeChange(pageSize) {
  pagination.pageSize = pageSize
  pagination.page = 1
  await loadRows()
}

function openAdd(role = 1) {
  modalAction.value = 'add'
  resetForm()
  modalForm.role = role
  modalForm.role_values = getRoleValues(role)
  modalVisible.value = true
}

function openEdit(row) {
  modalAction.value = 'edit'
  resetForm()
  Object.assign(modalForm, {
    ...row,
    role: Number(row.role || 1),
    role_values: getRoleValues(row.role),
    status: row.status !== false,
    contract_company_id: row.contract_company_id ?? null,
  })
  modalVisible.value = true
}

async function handleSave() {
  try {
    modalLoading.value = true
    await modalFormRef.value?.validate()
    const payload = { ...modalForm, role: getRoleValue(modalForm.role_values) }
    delete payload.role_values
    Object.keys(payload).forEach((key) => {
      if (payload[key] === null && key !== 'id' && key !== 'contract_company_id') {
        payload[key] = ''
      }
    })
    if (modalAction.value === 'add') {
      delete payload.id
      await api.createCompany(payload)
      window.$message?.success?.('新增成功')
    } else {
      await api.updateCompany(payload)
      window.$message?.success?.('保存成功')
    }
    modalVisible.value = false
    await loadRows()
  } finally {
    modalLoading.value = false
  }
}

async function handleDelete(row) {
  await api.deleteCompany({ company_id: row.id })
  window.$message?.success?.('删除成功')
  await loadRows()
}

function validateOptionalEmail(rule, value, callback) {
  const email = String(value || '').trim()
  if (!email) return callback()
  const re = /^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+)+$/
  if (!re.test(email)) return callback('邮箱格式错误')
  return callback()
}

function getRoleTags(role) {
  const value = Number(role || 0)
  if (value === 3) {
    return [
      { label: '客户', type: 'info' },
      { label: '供应商', type: 'warning' },
    ]
  }
  if (value === 2) return [{ label: '供应商', type: 'warning' }]
  if (value === 1) return [{ label: '客户', type: 'info' }]
  return [{ label: '内部', type: 'default' }]
}

function getRoleValues(role) {
  const value = Number(role || 0)
  if (value === 3) return [1, 2]
  if (value === 2) return [2]
  if (value === 1) return [1]
  return []
}

function getRoleValue(values) {
  const selected = Array.from(new Set(values || [])).map(Number)
  const hasCustomer = selected.includes(1)
  const hasVendor = selected.includes(2)
  if (hasCustomer && hasVendor) return 3
  if (hasVendor) return 2
  if (hasCustomer) return 1
  return 0
}

function getContractCompanyName(id) {
  return contractCompanyOptions.value.find((item) => item.value === id)?.label
}

watch(
  () => queryItems.value.name,
  (value, oldValue) => {
    if (!value && oldValue) handleSearch()
  }
)

onMounted(async () => {
  await loadContractCompanies()
  await loadRows()
})
</script>

<template>
  <AppPage :show-footer="false">
    <div class="company-page">
      <section class="company-summary">
        <article>
          <span class="summary-icon blue"><TheIcon icon="mdi:domain" :size="22" /></span>
          <div>
            <small>客户/供应商</small>
            <strong>{{ total }}</strong>
          </div>
        </article>
        <article>
          <span class="summary-icon green"><TheIcon icon="mdi:account-group-outline" :size="22" /></span>
          <div>
            <small>客户</small>
            <strong>{{ customerCount }}</strong>
          </div>
        </article>
        <article>
          <span class="summary-icon orange"><TheIcon icon="mdi:truck-outline" :size="22" /></span>
          <div>
            <small>供应商</small>
            <strong>{{ vendorCount }}</strong>
          </div>
        </article>
      </section>

      <section class="company-panel">
        <div class="table-toolbar">
          <div class="filter-row">
            <NSelect
              v-model:value="queryItems.role"
              clearable
              :options="roleOptions"
              placeholder="全部类型"
              @update:value="handleSearch"
            />
            <NSelect
              v-model:value="queryItems.contract_company_id"
              clearable
              filterable
              :options="contractCompanyOptions"
              placeholder="全部签约主体"
              @update:value="handleSearch"
            />
            <NInput
              v-model:value="queryItems.name"
              clearable
              placeholder="搜索简称 / 公司全称"
              @keypress.enter="handleSearch"
            >
              <template #prefix><TheIcon icon="mdi:magnify" :size="17" /></template>
            </NInput>
            <NSelect
              v-model:value="queryItems.status"
              clearable
              :options="statusOptions"
              placeholder="全部状态"
              @update:value="handleSearch"
            />
          </div>

          <NSpace :wrap="false">
            <NTooltip trigger="hover">
              <template #trigger>
                <NButton secondary circle :loading="tableLoading" @click="handleRefresh">
                  <template #icon><TheIcon icon="mdi:refresh" :size="18" /></template>
                </NButton>
              </template>
              刷新
            </NTooltip>
            <NButton type="primary" @click="openAdd(1)">
              <template #icon><TheIcon icon="material-symbols:add" :size="18" /></template>
              新增客户
            </NButton>
            <NButton secondary type="primary" @click="openAdd(2)">
              <template #icon><TheIcon icon="material-symbols:add-business-outline" :size="18" /></template>
              新增供应商
            </NButton>
          </NSpace>
        </div>

        <div class="company-table-wrap">
          <NDataTable
            remote
            flex-height
            striped
            :loading="tableLoading"
            :columns="columns"
            :data="companyRows"
            :pagination="false"
            :scroll-x="1180"
            :row-key="(row) => row.id"
          />
        </div>

        <div class="company-list-footer">
          <div class="status-summary">
            <NTag type="success" :bordered="false">启用 {{ activeCount }}</NTag>
            <NTag type="default" :bordered="false">停用 {{ total - activeCount }}</NTag>
          </div>
          <NPagination
            v-model:page="pagination.page"
            v-model:page-size="pagination.pageSize"
            show-size-picker
            :page-sizes="pagination.pageSizes"
            :item-count="total"
            @update:page="handlePageChange"
            @update:page-size="handlePageSizeChange"
          />
        </div>
      </section>

      <CrudModal
        v-model:visible="modalVisible"
        width="820px"
        :title="modalAction === 'add' ? '新增客户/供应商' : '编辑客户/供应商'"
        :loading="modalLoading"
        @save="handleSave"
      >
        <NForm
          ref="modalFormRef"
          label-placement="left"
          label-align="left"
          :label-width="90"
          :model="modalForm"
          :rules="modalRules"
        >
          <NGrid :cols="2" :x-gap="16">
            <NFormItemGi label="类型" path="role_values">
              <NSelect
                v-model:value="modalForm.role_values"
                multiple
                :options="roleOptions"
                placeholder="请选择类型"
              />
            </NFormItemGi>
            <NFormItemGi label="签约主体" path="contract_company_id">
              <NSelect
                v-model:value="modalForm.contract_company_id"
                clearable
                filterable
                :options="contractCompanyOptions"
                placeholder="请选择签约主体"
              />
            </NFormItemGi>
            <NFormItemGi label="公司简称" path="name">
              <NInput v-model:value="modalForm.name" clearable placeholder="例如：163" />
            </NFormItemGi>
            <NFormItemGi label="公司全称" path="legal_name">
              <NInput v-model:value="modalForm.legal_name" clearable placeholder="例如：163 Global Communications Limited" />
            </NFormItemGi>
            <NFormItemGi label="国家/地区" path="country">
              <NInput v-model:value="modalForm.country" clearable />
            </NFormItemGi>
            <NFormItemGi label="启用" path="status">
              <NSwitch
                v-model:value="modalForm.status"
                :checked-value="true"
                :unchecked-value="false"
              />
            </NFormItemGi>
            <NFormItemGi label="公司邮箱" path="company_email">
              <NInput v-model:value="modalForm.company_email" clearable />
            </NFormItemGi>
            <NFormItemGi label="财务邮箱" path="bill_email">
              <NInput v-model:value="modalForm.bill_email" clearable />
            </NFormItemGi>
            <NFormItemGi label="财务联系人" path="contact_person">
              <NInput v-model:value="modalForm.contact_person" clearable />
            </NFormItemGi>
            <NFormItemGi label="公司电话" path="company_phone">
              <NInput v-model:value="modalForm.company_phone" clearable />
            </NFormItemGi>
            <NFormItemGi label="NOC邮箱" path="noc_email">
              <NInput v-model:value="modalForm.noc_email" clearable />
            </NFormItemGi>
            <NFormItemGi label="NOC电话" path="noc_phone">
              <NInput v-model:value="modalForm.noc_phone" clearable />
            </NFormItemGi>
            <NFormItemGi label="税号" path="tax_no">
              <NInput v-model:value="modalForm.tax_no" clearable />
            </NFormItemGi>
            <NFormItemGi label="注册号" path="registration_no">
              <NInput v-model:value="modalForm.registration_no" clearable />
            </NFormItemGi>
            <NFormItemGi :span="2" label="地址" path="address">
              <NInput
                v-model:value="modalForm.address"
                type="textarea"
                :autosize="{ minRows: 2, maxRows: 4 }"
              />
            </NFormItemGi>
            <NFormItemGi :span="2" label="备注" path="remark">
              <NInput
                v-model:value="modalForm.remark"
                type="textarea"
                :autosize="{ minRows: 2, maxRows: 4 }"
              />
            </NFormItemGi>
          </NGrid>
        </NForm>
      </CrudModal>
    </div>
  </AppPage>
</template>

<style scoped>
.company-page {
  display: flex;
  height: 100%;
  min-height: 0;
  flex-direction: column;
  gap: 10px;
  background: #f5f7fb;
  padding: 10px;
}

.company-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.company-summary article {
  display: flex;
  align-items: center;
  gap: 10px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 8px;
  background: #fff;
  padding: 12px 14px;
}

.summary-icon {
  display: grid;
  width: 38px;
  height: 38px;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 8px;
}

.summary-icon.blue {
  background: #e0f2fe;
  color: #0369a1;
}

.summary-icon.green {
  background: #dcfce7;
  color: #15803d;
}

.summary-icon.orange {
  background: #ffedd5;
  color: #c2410c;
}

.company-summary small {
  display: block;
  color: #64748b;
  font-size: 12px;
}

.company-summary strong {
  color: #0f172a;
  font-size: 22px;
  line-height: 1.1;
}

.company-panel {
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 8px;
  background: #fff;
  padding: 10px;
}

.company-panel :deep(.n-data-table) {
  min-height: 0;
  flex: 1;
}

.company-panel :deep(.n-data-table .n-data-table-base-table) {
  min-height: 0;
}

.table-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.filter-row {
  display: grid;
  width: min(780px, 100%);
  grid-template-columns: 140px 220px minmax(180px, 1fr) 120px;
  gap: 8px;
}

.company-table-wrap {
  display: flex;
  min-height: 0;
  flex: 1;
  overflow: hidden;
}

.company-table-wrap :deep(.n-data-table) {
  width: 100%;
  height: 100%;
}

.company-list-footer {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-top: 12px;
}

.status-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

:deep(.company-name-cell),
:deep(.contact-cell) {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
}

:deep(.company-name-cell strong) {
  overflow: hidden;
  color: #0f172a;
  text-overflow: ellipsis;
  white-space: nowrap;
}

:deep(.company-name-cell span),
:deep(.contact-cell span) {
  overflow: hidden;
  color: #64748b;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

:deep(.row-actions .n-button) {
  width: 30px;
  padding: 0;
}

@media (max-width: 980px) {
  .filter-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .table-toolbar {
    align-items: stretch;
    flex-direction: column;
  }
}

@media (max-width: 760px) {
  .company-summary,
  .filter-row {
    grid-template-columns: 1fr;
  }

  .company-list-footer {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
