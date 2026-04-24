<template>
    <n-card title="账单列表">
        <n-space vertical>
            <n-button type="primary">上传 PDF</n-button>

            <n-data-table :columns="columns" :data="data" />

            <PdfPreview v-if="pdfUrl" :url="pdfUrl" />
        </n-space>
    </n-card>
</template>

<script setup>
import { ref, h } from 'vue'
import PdfPreview from './PdfPreview.vue'

const pdfUrl = ref('')

const viewPdf = (row) => {
    pdfUrl.value = row.pdf
}

const columns = [
    { title: '发票编号', key: 'invoice' },
    { title: '发票日期', key: 'date' },
    { title: '金额', key: 'amount' },
    {
        title: '操作',
        key: 'action',
        render(row) {
            return h(
                'span',
                {
                    style: 'color:#3b82f6;cursor:pointer',
                    onClick: () => viewPdf(row)
                },
                '查看'
            )
        }
    }
]

const data = ref([
    {
        invoice: '267711',
        date: '2026-03-01',
        amount: '98.23 USD',
        pdf: '/mock.pdf'
    }
])
</script>