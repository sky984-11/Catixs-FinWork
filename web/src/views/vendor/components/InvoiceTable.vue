<template>
  <n-card title="账单列表">
    <n-space vertical>
      <n-space justify="space-between" align="center">
        <n-button type="primary" @click="openAdd">
          上传 PDF
        </n-button>
      </n-space>

      <n-data-table :columns="columns" :data="data" :bordered="false" />

      <PdfPreview v-if="pdfUrl" :url="pdfUrl" />
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
        <NFormItem label="发票编号" path="invoice_no">
          <NInput v-model:value="modalForm.invoice_no" clearable placeholder="请输入发票编号" />
        </NFormItem>
        <NFormItem label="发票日期" path="invoice_date">
          <NDatePicker
            v-model:value="invoiceDateValue"
            type="date"
            clearable
            placeholder="请选择发票日期"
            style="width: 100%"
            :is-date-invalid="!modalForm.invoice_date"
            @update:value="handleDateChange"
          />
        </NFormItem>
        <NFormItem label="金额" path="total_amount">
          <NInputNumber v-model:value="modalForm.total_amount" clearable placeholder="请输入金额" style="width: 100%" />
        </NFormItem>
        <NFormItem label="币种" path="currency">
          <NSelect
            v-model:value="modalForm.currency"
            :options="currencyOptions"
            clearable
            placeholder="请选择币种"
          />
        </NFormItem>
        <NFormItem label="PDF文件" path="pdf_file">
          <div class="upload-row">
            <n-button @click="triggerFileSelect">
              选择文件
            </n-button>
            <span v-if="selectedFileName" class="file-name">{{ selectedFileName }}</span>
            <input
              ref="fileInput"
              type="file"
              accept="application/pdf"
              style="display: none"
              @change="handleFileChange"
            />
          </div>
        </NFormItem>
      </NForm>
    </CrudModal>
  </n-card>
</template>

<script setup>
import { computed, h, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { NButton, NSelect, NInput, NInputNumber, NDatePicker } from 'naive-ui'
import PdfPreview from './PdfPreview.vue'
import CrudModal from '@/components/table/CrudModal.vue'
import CButton from '@/components/public/CButton.vue'
import api from '@/api'

const props = defineProps({
  companyId: {
    type: [Number, String],
    default: null,
  },
})

// 处理日期选择器的值转换
const invoiceDateValue = computed({
  get() {
    if (!modalForm.invoice_date) return null
    const date = new Date(modalForm.invoice_date)
    return isNaN(date.getTime()) ? null : date.getTime()
  },
  set(val) {
    modalForm.invoice_date = val
  }
})

function handleDateChange(value) {
  modalForm.invoice_date = value
}

const pdfUrl = ref('')
const fileInput = ref(null)
const selectedFileName = ref('')
const selectedFile = ref(null)

// 币种选项
const currencyOptions = [
  { label: 'USD', value: 'USD' },
  { label: 'HKD', value: 'HKD' },
  { label: 'GBP', value: 'GBP' },
  { label: 'CNY', value: 'CNY' },
  { label: 'EUR', value: 'EUR' },
]

const data = ref([])

const modalVisible = ref(false)
const modalLoading = ref(false)
const modalAction = ref('add')
const modalTitle = ref('上传账单')
const modalFormRef = ref(null)
const modalForm = reactive({
  id: null,
  invoice_no: '',
  invoice_date: null,
  total_amount: null,
  currency: 'USD',
})

const modalRules = {
  invoice_no: [{ required: true, message: '请输入发票编号', trigger: 'blur' }],
  invoice_date: [{ required: true, message: '请选择发票日期'}],
  total_amount: [{ required: true, type: 'number', message: '请输入金额', trigger: 'blur' }],
  currency: [{ required: true, message: '请选择币种', trigger: 'change' }],
}

async function fetchList() {
  if (!props.companyId) {
    data.value = []
    return
  }
  const res = await api.getBillList({
    company_id: Number(props.companyId),
    bill_type: 2,
    page: 1,
    page_size: 9999,
  })
  data.value = res?.data || []
}

watch(
  () => props.companyId,
  async () => {
    pdfUrl.value = ''
    try {
      await fetchList()
    } catch (e) {
      window.$message?.error?.('获取账单失败')
    }
  },
  { immediate: true }
)

function resetModalForm() {
  modalForm.id = null
  modalForm.invoice_no = ''
  modalForm.invoice_date = null
  modalForm.total_amount = null
  modalForm.currency = 'USD'
  selectedFileName.value = ''
  selectedFile.value = null
}

function openAdd() {
  if (!props.companyId) return
  modalAction.value = 'add'
  modalTitle.value = '上传账单'
  resetModalForm()
  modalVisible.value = true
}

function triggerFileSelect() {
  fileInput.value?.click()
}

function handleFileChange(event) {
  const file = event.target.files?.[0]
  if (!file) return
  
  if (!file.name.toLowerCase().endsWith('.pdf')) {
    window.$message?.error?.('请选择 PDF 文件')
    return
  }
  
  selectedFileName.value = file.name
  selectedFile.value = file
}

async function handleSave() {
  try {
    modalLoading.value = true
    await modalFormRef.value?.validate?.()
    
    // 如果有选中的文件，先上传
    if (selectedFile.value) {
      // 先创建账单记录，获取ID
      const billData = {
        company_id: Number(props.companyId),
        bill_type: 2,
        invoice_no: modalForm.invoice_no,
        invoice_date: modalForm.invoice_date ? new Date(modalForm.invoice_date).toISOString().split('T')[0] : null,
        total_amount: modalForm.total_amount,
        currency: modalForm.currency,
      }
      
      let billId
      if (modalAction.value === 'add') {
        const res = await api.createBill(billData)
        billId = res?.data?.id
      } else {
        await api.updateBill({ id: modalForm.id, ...billData })
        billId = modalForm.id
      }
      
      // 上传PDF
      await api.uploadBillPdf({ bill_id: billId }, selectedFile.value)
      window.$message?.success?.('上传成功')
    } else {
      // 只更新账单信息，不上传文件
      const billData = {
        company_id: Number(props.companyId),
        bill_type: 2,
        invoice_no: modalForm.invoice_no,
        invoice_date: modalForm.invoice_date ? new Date(modalForm.invoice_date).toISOString().split('T')[0] : null,
        total_amount: modalForm.total_amount,
        currency: modalForm.currency,
      }
      
      if (modalAction.value === 'add') {
        await api.createBill(billData)
        window.$message?.success?.('创建成功')
      } else {
        await api.updateBill({ id: modalForm.id, ...billData })
        window.$message?.success?.('更新成功')
      }
    }
    
    modalVisible.value = false
    await fetchList()
  } catch (e) {
    console.error(e)
    window.$message?.error?.(e.message || '操作失败')
  } finally {
    modalLoading.value = false
  }
}

const pdfLoading = ref(false)
const deleteLoadingId = ref(null)

const viewPdf = (row) => {
  pdfUrl.value = row.invoice_url || ''
}

function openEdit(row) {
  if (!row?.id) return
  modalAction.value = 'edit'
  modalTitle.value = '编辑账单'
  modalForm.id = row.id
  modalForm.invoice_no = row.invoice_no || ''
  // 处理发票日期，确保是有效的日期时间戳
  if (row.invoice_date) {
    const date = new Date(row.invoice_date)
    modalForm.invoice_date = isNaN(date.getTime()) ? null : date.getTime()
  } else {
    modalForm.invoice_date = null
  }
  modalForm.total_amount = row.total_amount ?? null
  modalForm.currency = row.currency || 'USD'
  selectedFileName.value = ''
  selectedFile.value = null
  modalVisible.value = true
}

async function handleDelete(row) {
  if (!row?.id) return
  window.$dialog?.confirm?.({
    title: '删除账单',
    content: `确定删除发票「${row.invoice_no || ''}」吗？`,
    confirm: async () => {
      try {
        deleteLoadingId.value = row.id
        await api.deleteBill({ bill_id: row.id })
        window.$message?.success?.('删除成功')
        await fetchList()
      } catch (e) {
        window.$message?.error?.('删除失败')
      } finally {
        deleteLoadingId.value = null
      }
    },
  })
}

const columns = [
  { title: '发票编号', key: 'invoice_no' },
  { title: '发票日期', key: 'invoice_date' },
  {
    title: '金额',
    key: 'total_amount',
    render(row) {
      const amount = row.total_amount ?? ''
      const currency = row.currency || ''
      return `${amount} ${currency}`.trim()
    },
  },
  {
    title: '操作',
    key: 'action',
    render(row) {
      return h(CButton, {
        showEdit: true,
        showDelete: true,
        editLoading: false,
        deleteLoading: deleteLoadingId.value === row.id,
        onEdit: () => openEdit(row),
        onDelete: () => handleDelete(row),
      })
    },
  },
]
</script>

<style scoped>
.upload-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.file-name {
  color: #666;
  font-size: 12px;
}
</style>
