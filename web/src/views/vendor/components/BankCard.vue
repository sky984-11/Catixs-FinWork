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
        <NFormItem :label="region === 'CN' ? '开户行' : '银行'" path="bank_id">
          <div class="bank-row">
            <NSelect
              v-model:value="modalForm.bank_id"
              filterable
              clearable
              :options="bankOptions"
              placeholder="请选择银行"
            />
            <n-button size="small" secondary @click="openAddBank">新增银行</n-button>
          </div>
        </NFormItem>

        <NFormItem v-if="region === 'HK'" label="Bank Name">
          <NInput :value="selectedBankName" disabled placeholder="请选择银行" />
        </NFormItem>

        <NFormItem label="币种" path="currency">
          <NInput v-model:value="modalForm.currency" clearable placeholder="如：USD/HKD/GBP/CNY" />
        </NFormItem>

        <!-- UK -->
        <template v-if="region === 'GB'">
          <NFormItem label="Sort Code" path="sort_code">
            <NInput v-model:value="modalForm.sort_code" clearable placeholder="请输入 Sort Code" />
          </NFormItem>
          <NFormItem label="Account Number" path="account_number">
            <NInput v-model:value="modalForm.account_number" clearable placeholder="请输入 Account Number" />
          </NFormItem>
          <NFormItem label="SWIFT" path="swift_code">
            <NInput v-model:value="modalForm.swift_code" clearable placeholder="请输入 SWIFT" />
          </NFormItem>
          <NFormItem label="IBAN" path="iban">
            <NInput v-model:value="modalForm.iban" clearable placeholder="请输入 IBAN" />
          </NFormItem>
        </template>

        <!-- HK -->
        <template v-else-if="region === 'HK'">
          <NFormItem label="Bank Code" path="bank_code">
            <NInput v-model:value="modalForm.bank_code" clearable placeholder="请输入 Bank Code" />
          </NFormItem>
          <NFormItem label="Branch Code" path="branch_code">
            <NInput v-model:value="modalForm.branch_code" clearable placeholder="请输入 Branch Code" />
          </NFormItem>
          <NFormItem label="Account Number" path="account_number">
            <NInput v-model:value="modalForm.account_number" clearable placeholder="请输入 Account Number" />
          </NFormItem>
          <NFormItem label="SWIFT" path="swift_code">
            <NInput v-model:value="modalForm.swift_code" clearable placeholder="请输入 SWIFT" />
          </NFormItem>
        </template>

        <!-- CN -->
        <template v-else-if="region === 'CN'">
          <NFormItem label="账户号" path="account_number">
            <NInput v-model:value="modalForm.account_number" clearable placeholder="请输入账户号" />
          </NFormItem>
        </template>

        <!-- Fallback -->
        <template v-else>
          <NFormItem label="账号" path="account_number">
            <NInput v-model:value="modalForm.account_number" clearable placeholder="请输入账号" />
          </NFormItem>
          <NFormItem label="SWIFT" path="swift_code">
            <NInput v-model:value="modalForm.swift_code" clearable placeholder="请输入 SWIFT" />
          </NFormItem>
          <NFormItem label="IBAN" path="iban">
            <NInput v-model:value="modalForm.iban" clearable placeholder="请输入 IBAN" />
          </NFormItem>
          <NFormItem label="SORT CODE" path="sort_code">
            <NInput v-model:value="modalForm.sort_code" clearable placeholder="请输入 SORT CODE" />
          </NFormItem>
          <NFormItem label="Bank Code" path="bank_code">
            <NInput v-model:value="modalForm.bank_code" clearable placeholder="请输入 Bank Code" />
          </NFormItem>
	          <NFormItem label="Branch Code" path="branch_code">
	            <NInput v-model:value="modalForm.branch_code" clearable placeholder="请输入 Branch Code" />
	          </NFormItem>
	        </template>
	      </NForm>
	    </CrudModal>

    <CrudModal
      v-model:visible="bankModalVisible"
      title="新增银行"
      :loading="bankModalLoading"
      @save="handleSaveBank"
    >
      <NForm
        ref="bankFormRef"
        label-placement="left"
        label-align="left"
        :label-width="90"
        :model="bankForm"
        :rules="bankRules"
      >
        <NFormItem label="银行名称" path="name">
          <NInput v-model:value="bankForm.name" clearable placeholder="请输入银行名称" />
        </NFormItem>
        <NFormItem label="国家" path="country">
          <NInput v-model:value="bankForm.country" clearable placeholder="如：中国/香港/台湾" />
        </NFormItem>
        <NFormItem label="SWIFT" path="swift_code">
          <NInput v-model:value="bankForm.swift_code" clearable placeholder="请输入 SWIFT" />
        </NFormItem>
        <NFormItem label="地址" path="bank_address">
          <NInput
            v-model:value="bankForm.bank_address"
            type="textarea"
            :autosize="{ minRows: 2, maxRows: 4 }"
          />
        </NFormItem>
      </NForm>
    </CrudModal>
  </n-card>
</template>

<script setup>
import { computed, h, onMounted, reactive, ref, watch } from 'vue'
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

const bankList = ref([])
const bankOptions = computed(() => (bankList.value || []).map((b) => ({ label: b.name, value: b.id })))
const selectedBank = computed(() => (bankList.value || []).find((b) => b.id === modalForm.bank_id) || null)
const selectedBankName = computed(() => selectedBank.value?.name || '')

function normalizeText(v) {
  return String(v || '').trim().toLowerCase()
}

const region = computed(() => {
  const cur = String(modalForm.currency || '').trim().toUpperCase()
  const c = normalizeText(selectedBank.value?.country)

  if (c.includes('hong kong') || c.includes('hk') || c.includes('香港')) return 'HK'
  if (c.includes('united kingdom') || c === 'uk' || c === 'gb' || c.includes('英国')) return 'GB'
  if (c.includes('china') || c === 'cn' || c.includes('中国')) return 'CN'

  if (cur === 'GBP') return 'GB'
  if (cur === 'HKD') return 'HK'
  if (cur === 'CNY' || cur === 'RMB') return 'CN'
  // USD 只在银行国家判断为香港时才按香港逻辑处理
  if (cur === 'USD' && (c.includes('hong kong') || c.includes('hk') || c.includes('香港'))) return 'HK'
  return 'GEN'
})

const modalVisible = ref(false)
const modalLoading = ref(false)
const modalAction = ref('add') // add | edit
const modalTitle = ref('新增银行账户')
const modalFormRef = ref(null)
const modalForm = reactive({
  id: null,
  company_id: null,
  bank_id: null,
  account_number: '',
  bank_code: '',
  branch_code: '',
  swift_code: '',
  iban: '',
  sort_code: '',
  currency: '',
})

function requireIf(conditionFn, message) {
  return {
    trigger: ['blur', 'input'],
    validator: (rule, value, callback) => {
      if (!conditionFn()) return callback()
      const v = String(value || '').trim()
      if (!v) return callback(message)
      return callback()
    },
  }
}

const modalRules = {
  bank_id: [{ required: true, message: '请选择银行', trigger: ['blur', 'change'] }],
  account_number: [{ required: true, message: '请输入账号', trigger: ['blur', 'input'] }],
  sort_code: [requireIf(() => region.value === 'GB', '请输入 Sort Code')],
  bank_code: [requireIf(() => region.value === 'HK', '请输入 Bank Code')],
  branch_code: [requireIf(() => region.value === 'HK', '请输入 Branch Code')],
}

const bankModalVisible = ref(false)
const bankModalLoading = ref(false)
const bankFormRef = ref(null)
const bankForm = reactive({
  name: '',
  country: '',
  swift_code: '',
  bank_address: '',
})
const bankRules = {
  name: [{ required: true, message: '请输入银行名称', trigger: ['blur', 'input'] }],
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

watch(
  () => modalForm.bank_id,
  () => {
    // 新增时自动带出银行 SWIFT（可手改）
    if (modalAction.value !== 'add') return
    if (modalForm.swift_code) return
    const swift = selectedBank.value?.swift_code
    if (swift) modalForm.swift_code = swift
  }
)

async function fetchBanks() {
  const res = await api.getBankList({ page: 1, page_size: 9999 })
  bankList.value = res?.data || []
}

onMounted(async () => {
  try {
    await fetchBanks()
  } catch (e) {
    window.$message?.error?.('获取银行列表失败')
  }
})

function resetModalForm() {
  modalForm.id = null
  modalForm.company_id = props.companyId ? Number(props.companyId) : null
  modalForm.bank_id = null
  modalForm.account_number = ''
  modalForm.bank_code = ''
  modalForm.branch_code = ''
  modalForm.swift_code = ''
  modalForm.iban = ''
  modalForm.sort_code = ''
  modalForm.currency = ''
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
  modalForm.bank_id = row.bank_id ?? null
  modalForm.account_number = row.account_number || ''
  modalForm.bank_code = row.bank_code || ''
  modalForm.branch_code = row.branch_code || ''
  modalForm.swift_code = row.swift_code || ''
  modalForm.iban = row.iban || ''
  modalForm.sort_code = row.sort_code || ''
  modalForm.currency = row.currency || ''
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

function resetBankForm() {
  bankForm.name = ''
  bankForm.country = ''
  bankForm.swift_code = ''
  bankForm.bank_address = ''
}

function openAddBank() {
  resetBankForm()
  bankModalVisible.value = true
}

async function handleSaveBank() {
  try {
    bankModalLoading.value = true
    await bankFormRef.value?.validate?.()
    const res = await api.createBank({ ...bankForm })
    window.$message?.success?.('新增银行成功')
    bankModalVisible.value = false
    await fetchBanks()
    if (res?.data?.id) modalForm.bank_id = res.data.id
  } finally {
    bankModalLoading.value = false
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

.bank-row {
  width: 100%;
  display: flex;
  gap: 8px;
  align-items: center;
}

.bank-row :deep(.n-select) {
  flex: 1;
}
</style>
