<template>
  <n-card title="账单列表">
    <n-space vertical>
      <n-button type="primary" disabled>上传 PDF</n-button>

      <n-data-table :columns="columns" :data="data" :bordered="false" />

      <PdfPreview v-if="pdfUrl" :url="pdfUrl" />
    </n-space>
  </n-card>
</template>

<script setup>
import { h, ref, watch } from 'vue'
import PdfPreview from './PdfPreview.vue'
import api from '@/api'

const props = defineProps({
  companyId: {
    type: [Number, String],
    default: null,
  },
})

const pdfUrl = ref('')

const viewPdf = (row) => {
  pdfUrl.value = row.invoice_url || ''
}

const data = ref([])

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
      return h(
        'span',
        {
          style: 'color:#3b82f6;cursor:pointer',
          onClick: () => viewPdf(row),
        },
        '查看'
      )
    },
  },
]
</script>
