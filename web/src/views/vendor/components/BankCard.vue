<template>
  <n-card title="银行账户" class="bank-card">
    <n-space vertical>
      <n-space justify="space-between" align="center">
        <div class="hint">{{ companyName || '-' }}</div>
        <n-button type="primary" size="small" @click="openAdd">新增账户</n-button>
      </n-space>

      <n-data-table :columns="columns" :data="data" :bordered="false" />
    </n-space>

    <CrudModal
      v-model:visible="modalVisible"
      :title="modalTitle"
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
        <NFormItem label="银行名称" path="bank_name">
          <NInput v-model:value="modalForm.bank_name" clearable placeholder="请输入银行名称" />
        </NFormItem>
        <NFormItem label="账号" path="account_number">
          <NInput v-model:value="modalForm.account_number" clearable placeholder="请输入账号" />
        </NFormItem>
        <NFormItem label="账户名" path="account_name">
          <NInput v-model:value="modalForm.account_name" clearable placeholder="请输入账户名" />
        </NFormItem>
        <NFormItem label="SWIFT" path="swift_code">
          <NInput v-model:value="modalForm.swift_code" clearable placeholder="请输入 SWIFT" />
        </NFormItem>
        <NFormItem label="币种" path="currency">
          <NInput v-model:value="modalForm.currency" clearable placeholder="如：USD/HKD/GBP" />
        </NFormItem>
        <NFormItem label="税号" path="tax_no">
          <NInput v-model:value="modalForm.tax_no" clearable placeholder="请输入税号" />
        </NFormItem>
        <NFormItem label="联系邮箱" path="contact_email">
          <NInput v-model:value="modalForm.contact_email" clearable placeholder="请输入邮箱" />
        </NFormItem>
        <NFormItem label="联系电话" path="contact_phone">
          <NInput v-model:value="modalForm.contact_phone" clearable placeholder="请输入电话" />
        </NFormItem>
      </NForm>
    </CrudModal>
  </n-card>
</template>

<script setup>
import { h, onMounted, reactive, ref, watch } from 'vue'
import { NButton } from 'naive-ui'
import CrudModal from '@/components/table/CrudModal.vue'
import api from '@/api'

const props = defineProps({
  companyId: {
    type: [Number, String],
    default: null,
  },
  companyName: {
    type: String,
    default: '',
  },
})

const data = ref([])

const modalVisible = ref(false)
const modalLoading = ref(false)
const modalAction = ref('add') // add | edit
const modalTitle = ref('新增银行账户')
const modalFormRef = ref(null)
const modalForm = reactive({
  id: null,
  company_id: null,
  bank_name: '',
  account_number: '',
  account_name: '',
  swift_code: '',
  currency: '',
  tax_no: '',
  contact_email: '',
  contact_phone: '',
})

const modalRules = {
  bank_name: [{ required: true, message: '请输入银行名称', trigger: ['blur', 'input'] }],
  account_number: [{ required: true, message: '请输入账号', trigger: ['blur', 'input'] }],
}

async function fetchList() {
  if (!props.companyId) {
    data.value = []
    return
  }
  const res = await api.getBankAccountList({
    company_id: Number(props.companyId),
    page: 1,
    page_size: 9999,
  })
  data.value = res?.data || []
}

watch(
  () => props.companyId,
  async () => {
    try {
      await fetchList()
    } catch (e) {
      window.$message?.error?.('获取银行账户失败')
    }
  },
  { immediate: true }
)

onMounted(fetchList)

function resetModalForm() {
  modalForm.id = null
  modalForm.company_id = props.companyId ? Number(props.companyId) : null
  modalForm.bank_name = ''
  modalForm.account_number = ''
  modalForm.account_name = ''
  modalForm.swift_code = ''
  modalForm.currency = ''
  modalForm.tax_no = ''
  modalForm.contact_email = ''
  modalForm.contact_phone = ''
}

function openAdd() {
  if (!props.companyId) return
  modalAction.value = 'add'
  modalTitle.value = '新增银行账户'
  resetModalForm()
  modalVisible.value = true
}

function openEdit(row) {
  modalAction.value = 'edit'
  modalTitle.value = '编辑银行账户'
  modalForm.id = row.id
  modalForm.company_id = row.company_id
  modalForm.bank_name = row.bank_name || ''
  modalForm.account_number = row.account_number || ''
  modalForm.account_name = row.account_name || ''
  modalForm.swift_code = row.swift_code || ''
  modalForm.currency = row.currency || ''
  modalForm.tax_no = row.tax_no || ''
  modalForm.contact_email = row.contact_email || ''
  modalForm.contact_phone = row.contact_phone || ''
  modalVisible.value = true
}

async function handleSave() {
  try {
    modalLoading.value = true
    await modalFormRef.value?.validate?.()
    if (modalAction.value === 'add') {
      const payload = { ...modalForm }
      delete payload.id
      await api.createBankAccount(payload)
      window.$message?.success?.('新增成功')
    } else {
      await api.updateBankAccount({ ...modalForm })
      window.$message?.success?.('更新成功')
    }
    modalVisible.value = false
    await fetchList()
  } finally {
    modalLoading.value = false
  }
}

function handleDelete(row) {
  window.$dialog?.confirm?.({
    title: '删除银行账户',
    content: `确定删除该账户吗？`,
    confirm: async () => {
      await api.deleteBankAccount({ bank_account_id: row.id })
      window.$message?.success?.('删除成功')
      await fetchList()
    },
  })
}

const columns = [
  { title: '银行', key: 'bank_name' },
  { title: '账号', key: 'account_number' },
  { title: '币种', key: 'currency' },
  { title: 'SWIFT', key: 'swift_code' },
  {
    title: '操作',
    key: 'action',
    render(row) {
      return h('div', { style: 'display:flex;gap:8px;' }, [
        h(
          NButton,
          { size: 'small', type: 'info', secondary: true, onClick: () => openEdit(row) },
          { default: () => '编辑' }
        ),
        h(
          NButton,
          { size: 'small', type: 'error', secondary: true, onClick: () => handleDelete(row) },
          { default: () => '删除' }
        ),
      ])
    },
  },
]
</script>

<style scoped>
.hint {
  color: #666;
  font-size: 12px;
}
</style>
