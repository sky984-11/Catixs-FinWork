<script setup>
import { h, onMounted, reactive, ref } from 'vue'
import {
  NButton,
  NForm,
  NFormItem,
  NGrid,
  NFormItemGi,
  NInput,
  NPopconfirm,
  NSelect,
  NSpace,
  NSwitch,
  NTag,
  NTooltip,
} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudModal from '@/components/table/CrudModal.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import api from '@/api'
import { renderIcon } from '@/utils'

defineOptions({ name: '客户供应商管理' })

const $table = ref(null)
const modalFormRef = ref(null)
const modalVisible = ref(false)
const modalLoading = ref(false)
const modalAction = ref('add')
const contractCompanyOptions = ref([])
const queryItems = ref({
  business_only: true,
  role: null,
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
  role: [{ required: true, type: 'number', message: '请选择类型', trigger: 'change' }],
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
    width: 90,
    align: 'center',
    render(row) {
      return h(
        NTag,
        { type: Number(row.role) === 2 ? 'warning' : 'info', bordered: false },
        { default: () => getRoleName(row.role) }
      )
    },
  },
  {
    title: '签约主体',
    key: 'contract_company_id',
    minWidth: 140,
    ellipsis: { tooltip: true },
    render(row) {
      return getContractCompanyName(row.contract_company_id) || '-'
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
    width: 86,
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

function createEmptyForm() {
  return {
    id: null,
    role: 1,
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
            round: true,
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

function openAdd(role = 1) {
  modalAction.value = 'add'
  resetForm()
  modalForm.role = role
  modalVisible.value = true
}

function openEdit(row) {
  modalAction.value = 'edit'
  resetForm()
  Object.assign(modalForm, {
    ...row,
    role: Number(row.role || 1),
    status: row.status !== false,
    contract_company_id: row.contract_company_id ?? null,
  })
  modalVisible.value = true
}

async function handleSave() {
  try {
    modalLoading.value = true
    await modalFormRef.value?.validate()
    const payload = { ...modalForm }
    if (modalAction.value === 'add') {
      delete payload.id
      await api.createCompany(payload)
      window.$message?.success?.('新增成功')
    } else {
      await api.updateCompany(payload)
      window.$message?.success?.('保存成功')
    }
    modalVisible.value = false
    await $table.value?.handleSearch()
  } finally {
    modalLoading.value = false
  }
}

async function handleDelete(row) {
  await api.deleteCompany({ company_id: row.id })
  window.$message?.success?.('删除成功')
  await $table.value?.handleSearch()
}

function validateOptionalEmail(rule, value, callback) {
  const email = String(value || '').trim()
  if (!email) return callback()
  const re = /^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+)+$/
  if (!re.test(email)) return callback('邮箱格式错误')
  return callback()
}

function getRoleName(role) {
  return Number(role) === 2 ? '供应商' : '客户'
}

function getContractCompanyName(id) {
  return contractCompanyOptions.value.find((item) => item.value === id)?.label
}

onMounted(async () => {
  await loadContractCompanies()
  await $table.value?.handleSearch()
})
</script>

<template>
  <CommonPage show-footer title="客户/供应商">
    <template #action>
      <NSpace>
        <NButton type="primary" round @click="openAdd(1)">
          <TheIcon icon="material-symbols:add" :size="18" class="mr-5" />
          新增客户
        </NButton>
        <NButton secondary type="primary" round @click="openAdd(2)">
          <TheIcon icon="material-symbols:add-business-outline" :size="18" class="mr-5" />
          新增供应商
        </NButton>
      </NSpace>
    </template>

    <CrudTable
      ref="$table"
      v-model:query-items="queryItems"
      :columns="columns"
      :get-data="api.getCompanyList"
      :scroll-x="1180"
    >
      <template #queryBar>
        <QueryBarItem label="类型" :label-width="50">
          <NSelect v-model:value="queryItems.role" clearable :options="roleOptions" placeholder="全部" />
        </QueryBarItem>
        <QueryBarItem label="名称" :label-width="50">
          <NInput
            v-model:value="queryItems.name"
            clearable
            placeholder="简称/公司全称"
            @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="状态" :label-width="50">
          <NSelect
            v-model:value="queryItems.status"
            clearable
            :options="statusOptions"
            placeholder="全部"
          />
        </QueryBarItem>
      </template>
    </CrudTable>

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
          <NFormItemGi label="类型" path="role">
            <NSelect v-model:value="modalForm.role" :options="roleOptions" />
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
            <NInput v-model:value="modalForm.name" clearable placeholder="例如：263" />
          </NFormItemGi>
          <NFormItemGi label="公司全称" path="legal_name">
            <NInput v-model:value="modalForm.legal_name" clearable placeholder="例如：263 Global Communications Limited" />
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
  </CommonPage>
</template>

<style scoped>
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
</style>
