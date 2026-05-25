<script setup>
import { computed, h, nextTick, onMounted, reactive, ref } from 'vue'
import {
  NButton,
  NDatePicker,
  NForm,
  NFormItem,
  NGrid,
  NFormItemGi,
  NInput,
  NInputNumber,
  NModal,
  NPopconfirm,
  NSelect,
  NSpace,
  NTag,
  NTooltip,
  NUpload,
} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudModal from '@/components/table/CrudModal.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import api from '@/api'
import { renderIcon } from '@/utils'

defineOptions({ name: '账单管理' })

const $table = ref(null)
const modalFormRef = ref(null)
const modalVisible = ref(false)
const detailVisible = ref(false)
const modalLoading = ref(false)
const modalAction = ref('add')
const pendingVoucherFile = ref(null)
const detailBill = ref(null)
const invoicePrintRef = ref(null)
const companyList = ref([])
const issuerCompanyList = ref([])
const issuerBankAccounts = ref({})
const tableRows = ref([])

const queryItems = ref({
  company_id: null,
  bill_month: null,
})

const modalForm = reactive(createEmptyForm())

const modalTitle = computed(() => (modalAction.value === 'add' ? '新增账单' : '编辑账单'))
const companyOptions = computed(() =>
  companyList.value.map((item) => ({
    label: `${item.name || item.legal_name || '-'}${item.legal_name ? ` - ${item.legal_name}` : ''}${item.role === 2 ? ' (供应商)' : ' (客户)'}`,
    value: item.id,
    role: item.role,
    name: item.name,
    legal_name: item.legal_name,
    address: item.address,
  }))
)

const billTypeOptions = [
  { label: '客户账单', value: 1 },
  { label: '供应商账单', value: 2 },
]

const currencyOptions = ['CNY', 'USD', 'HKD', 'EUR', 'GBP', 'JPY', 'SGD'].map((item) => ({
  label: item,
  value: item,
}))

const owners = [
  { name: '林凯恩', id: 'KYRA' },
  { name: '朱俊琳', id: '77' },
  { name: '常康玮', id: 'CHALI' },
]
const ownerOptions = owners.map((item) => ({ label: item.name, value: item.id }))

const rules = {
  company_id: [{ required: true, type: 'number', message: '请选择客户或供应商', trigger: 'change' }],
  bill_month: [{ required: true, message: '请选择月份', trigger: 'change' }],
  owner: [{ required: true, message: '请选择负责人', trigger: 'change' }],
}

const columns = [
  {
    title: '客户名',
    key: 'customer_name',
    width: 190,
    fixed: 'left',
    ellipsis: { tooltip: true },
    render(row) {
      return h('div', { class: 'bill-customer-cell' }, [
        h('strong', row.customer_name || '-'),
        h('span', getCompanyLegalName(row.company_id, row.customer_name) || '-'),
      ])
    },
  },
  {
    title: '月份',
    key: 'bill_month',
    width: 92,
    align: 'center',
    render: (row) => h('span', { class: 'date-pill' }, formatMonth(row.bill_month)),
  },
  {
    title: '是否结清',
    key: 'is_settled',
    width: 92,
    align: 'center',
    render(row) {
      return h(
        NTag,
        { type: row.is_settled ? 'success' : 'warning', bordered: false, round: true },
        { default: () => (row.is_settled ? '已结清' : '未结清') }
      )
    },
  },
  {
    title: '账单编号',
    key: 'invoice_no',
    width: 220,
    ellipsis: { tooltip: true },
    render: (row) => h('span', { class: 'invoice-no-cell' }, row.invoice_no || '-'),
  },
  { title: '账单日期', key: 'invoice_date', width: 112, align: 'center', render: (row) => renderDateCell(row.invoice_date) },
  { title: '截止日期', key: 'due_date', width: 112, align: 'center', render: (row) => renderDateCell(row.due_date) },
  { title: '计费开始', key: 'billing_start_date', width: 112, align: 'center', render: (row) => renderDateCell(row.billing_start_date) },
  { title: '计费结束', key: 'billing_end_date', width: 112, align: 'center', render: (row) => renderDateCell(row.billing_end_date) },
  {
    title: '币种',
    key: 'currency',
    width: 80,
    align: 'center',
    render(row) {
      return row.currency
        ? h(NTag, { type: 'info', round: true, bordered: false }, { default: () => row.currency })
        : '-'
    },
  },
  {
    title: '账单金额',
    key: 'total_amount',
    width: 116,
    align: 'right',
    render: (row) => renderMoneyCell(row.total_amount, row.currency),
  },
  {
    title: '已付金额',
    key: 'paid_amount',
    width: 116,
    align: 'right',
    render: (row) => renderMoneyCell(row.paid_amount, row.currency),
  },
  {
    title: '欠费金额',
    key: 'unpaid_amount',
    width: 116,
    align: 'right',
    render: (row) => renderMoneyCell(row.unpaid_amount, row.currency, Number(row.unpaid_amount || 0) > 0 ? 'danger' : 'muted'),
  },
  {
    title: '付款凭证',
    key: 'payment_voucher_url',
    width: 84,
    align: 'center',
    render(row) {
      return row.payment_voucher_url
        ? renderIconButton('查看凭证', 'mdi:paperclip', { onClick: () => openFile(row.payment_voucher_url) })
        : h('span', { class: 'muted' }, '-')
    },
  },
  {
    title: '负责人',
    key: 'owner',
    width: 110,
    ellipsis: { tooltip: true },
    render: (row) => h(NTag, { size: 'small', bordered: false, round: true }, { default: () => getOwnerName(row.owner) }),
  },
  {
    title: '备注',
    key: 'remark',
    width: 150,
    ellipsis: { tooltip: true },
    render: (row) => h('span', { class: row.remark ? 'remark-cell' : 'muted' }, row.remark || '-'),
  },
  {
    title: '操作',
    key: 'actions',
    width: 116,
    fixed: 'right',
    align: 'center',
    render(row) {
      return h(NSpace, { class: 'row-actions', justify: 'center', size: 8, wrap: false }, () => [
        renderIconButton('详情', 'mdi:receipt-text-outline', { onClick: () => openDetail(row) }),
        renderIconButton('编辑', 'material-symbols:edit', { type: 'primary', onClick: () => openEdit(row) }),
        h(
          NPopconfirm,
          { onPositiveClick: () => handleDelete(row) },
          {
            trigger: () =>
              renderIconButton('删除', 'material-symbols:delete-outline', { type: 'error' }),
            default: () => '确定删除该账单吗？',
          }
        ),
      ])
    },
  },
]

const summary = computed(() => {
  const rows = tableRows.value || []
  return {
    total: rows.reduce((sum, row) => sum + Number(row.total_amount || 0), 0),
    paid: rows.reduce((sum, row) => sum + Number(row.paid_amount || 0), 0),
    unpaid: rows.reduce((sum, row) => sum + Number(row.unpaid_amount || 0), 0),
  }
})

function createEmptyForm() {
  return {
    id: null,
    company_id: null,
    invoice_no: '',
    customer_name: '',
    bill_month: null,
    invoice_date: null,
    due_date: null,
    billing_start_date: null,
    billing_end_date: null,
    currency: 'USD',
    net_amount: 0,
    vat_amount: 0,
    total_amount: 0,
    paid_amount: 0,
    unpaid_amount: 0,
    is_settled: false,
    payment_voucher_url: '',
    owner: '',
    remark: '',
    bill_type: 1,
    items: [],
  }
}

function resetForm() {
  Object.assign(modalForm, createEmptyForm())
  pendingVoucherFile.value = null
}

async function loadCompanies() {
  const res = await api.getCompanyList({ page: 1, page_size: 9999, business_only: true, status: true })
  companyList.value = res?.data || []
}

async function loadIssuerCompanies() {
  const res = await api.getCompanyList({ page: 1, page_size: 9999, role: 0, status: true })
  issuerCompanyList.value = res?.data || []
}

async function loadIssuerBankAccounts(issuerId) {
  if (!issuerId || issuerBankAccounts.value[issuerId]) return
  const res = await api.getBankAccountList({ page: 1, page_size: 9999, company_id: issuerId })
  issuerBankAccounts.value = {
    ...issuerBankAccounts.value,
    [issuerId]: res?.data || [],
  }
}

function openAdd() {
  modalAction.value = 'add'
  resetForm()
  modalForm.bill_month = getPreviousMonthFirstDay()
  modalForm.invoice_date = getToday()
  syncInvoiceNo()
  addItem()
  modalVisible.value = true
}

async function openEdit(row) {
  modalAction.value = 'edit'
  resetForm()
  const res = await api.getBillById({ bill_id: row.id })
  Object.assign(modalForm, normalizeBill(res?.data || row))
  modalVisible.value = true
}

async function openDetail(row) {
  const res = await api.getBillById({ bill_id: row.id })
  const bill = normalizeBill(res?.data || row)
  detailBill.value = bill
  await loadIssuerBankAccounts(getIssuerCompanyId(bill))
  detailVisible.value = true
}

async function printBill() {
  if (!invoicePrintRef.value) return
  await nextTick()
  const iframe = document.createElement('iframe')
  iframe.setAttribute('aria-hidden', 'true')
  iframe.style.position = 'fixed'
  iframe.style.right = '0'
  iframe.style.bottom = '0'
  iframe.style.width = '0'
  iframe.style.height = '0'
  iframe.style.border = '0'
  document.body.appendChild(iframe)

  const printWindow = iframe.contentWindow
  const printDocument = iframe.contentDocument || printWindow?.document
  if (!printWindow || !printDocument) {
    iframe.remove()
    return
  }

  printDocument.open()
  printDocument.write(buildInvoicePrintDocument(invoicePrintRef.value.outerHTML))
  printDocument.close()
  await waitForPrintAssets(printDocument)

  const cleanup = () => iframe.remove()
  printWindow.addEventListener('afterprint', cleanup, { once: true })
  window.setTimeout(() => {
    printWindow.focus()
    printWindow.print()
    window.setTimeout(cleanup, 1200)
  }, 250)
}

function waitForPrintAssets(printDocument) {
  const images = Array.from(printDocument.images || [])
  if (!images.length) return Promise.resolve()
  return Promise.all(
    images.map((img) => {
      if (img.complete) return Promise.resolve()
      return new Promise((resolve) => {
        img.onload = resolve
        img.onerror = resolve
      })
    })
  )
}

function buildInvoicePrintDocument(invoiceHtml) {
  return `<!doctype html>
<html>
<head>
  <base href="${window.location.origin}/">
  <meta charset="utf-8">
  <title>${detailBill.value?.invoice_no || 'Invoice'}</title>
  <style>
    @page { size: A4; margin: 0; }
    * { box-sizing: border-box; }
    html, body { margin: 0; padding: 0; background: #fff; color: #1f2937; font-family: Arial, "Microsoft YaHei", sans-serif; }
    .invoice-preview { width: 210mm; min-height: 297mm; margin: 0; background: #fff; box-shadow: none; color: #1f2937; font-size: 14px; padding: 18mm 16mm 20mm; }
    .invoice-header { display: flex; min-height: 104px; align-items: stretch; justify-content: space-between; margin-bottom: 34px; }
    .brand { display: flex; width: 470px; min-height: 104px; align-items: center; color: #050505; font-size: 52px; font-weight: 700; letter-spacing: 0; line-height: 1; }
    .issuer-logo { display: block; max-width: 150px; max-height: 104px; object-fit: contain; }
    .issuer { display: flex; flex-direction: column; gap: 3px; justify-content: center; color: #000; font-weight: 600; text-align: right; }
    .invoice-top { display: grid; grid-template-columns: minmax(0, 1fr) 120px 250px; gap: 10px; }
    .customer-block, .meta-labels, .meta-values { display: flex; flex-direction: column; gap: 5px; border-radius: 6px; background: #f8fafc; padding: 10px 12px; }
    .meta-values { text-align: right; }
    .invoice-summary { display: grid; width: 360px; grid-template-columns: 1fr 120px; gap: 6px; margin-top: 16px; }
    .summary-title { color: #111827; font-weight: 700; }
    .summary-amount { text-align: right; }
    .summary-label { text-align: left; }
    .invoice-table { margin-top: 64px; }
    .invoice-table h2 { margin: 0; border: 1px solid #d8dde6; border-bottom: 0; background: #f3f4f6; font-size: 22px; line-height: 42px; text-align: center; }
    .invoice-table table { width: 100%; border-collapse: collapse; }
    .invoice-table th, .invoice-table td { border: 1px solid #d8dde6; padding: 8px 9px; text-align: center; }
    .invoice-table th { background: #f8fafc; font-weight: 500; }
    .amount-row td:first-child { text-align: right; }
    .amount-row td:last-child { text-align: left; }
    .issuer-accounts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin-top: 28px; }
    .account-card { display: flex; min-height: 132px; flex-direction: column; gap: 7px; border-radius: 6px; background: #f8fafc; padding: 14px 16px; color: #111827; }
    .account-card strong { font-size: 15px; }
    .account-card span { line-height: 1.45; }
  </style>
</head>
<body>${invoiceHtml}</body>
</html>`
}

function normalizeBill(row) {
  return {
    ...createEmptyForm(),
    ...row,
    owner: normalizeOwner(row.owner),
    bill_type: Number(row.bill_type || 1),
    net_amount: Number(row.net_amount ?? (Number(row.total_amount || 0) - Number(row.vat_amount || 0))),
    vat_amount: Number(row.vat_amount || 0),
    total_amount: Number(row.total_amount || 0),
    paid_amount: Number(row.paid_amount || 0),
    unpaid_amount: Number(row.unpaid_amount || 0),
    items: (row.items || []).map((item) => ({
      ...item,
      nrc_amount: Number(item.nrc_amount || 0),
      mrc_amount: Number(item.mrc_amount ?? item.amount ?? 0),
      amount: Number(item.amount || 0),
    })),
  }
}

async function handleSave() {
  try {
    modalLoading.value = true
    await modalFormRef.value?.validate()
    const items = modalForm.items.filter(hasItemValue)
    syncTotalAmount()
    if (!validateBillAmounts(items)) return
    syncInvoiceNo()
    const payload = { ...modalForm, items }
    const res =
      modalAction.value === 'add' ? await api.createBill(payload) : await api.updateBill(payload)
    const billId = res?.data?.id || modalForm.id
    if (pendingVoucherFile.value && billId) {
      await api.uploadBillVoucher({ bill_id: billId }, pendingVoucherFile.value)
    }
    window.$message?.success?.('保存成功')
    modalVisible.value = false
    await $table.value?.handleSearch()
  } finally {
    modalLoading.value = false
  }
}

async function handleDelete(row) {
  await api.deleteBill({ bill_id: row.id })
  window.$message?.success?.('删除成功')
  await $table.value?.handleSearch()
}

function handleCompanyChange(companyId) {
  const company = companyList.value.find((item) => item.id === companyId)
  if (!company) return
  modalForm.customer_name = company.name || ''
  modalForm.bill_type = Number(company.role) === 2 ? 2 : 1
  syncInvoiceNo()
}

function handleBillMonthChange(value) {
  modalForm.bill_month = value
  syncInvoiceNo()
}

function handleOwnerChange(value) {
  modalForm.owner = value
  syncInvoiceNo()
}

function syncInvoiceNo() {
  const customerName = String(modalForm.customer_name || '').trim()
  const ownerId = String(modalForm.owner || '').trim()
  const month = formatInvoiceMonth(modalForm.bill_month)
  if (!customerName || !ownerId || !month) {
    modalForm.invoice_no = ''
    return
  }
  modalForm.invoice_no = `${customerName}_INV${ownerId}_${month}`
}

function getItemsAmountTotal(items = modalForm.items) {
  return items.reduce(
    (sum, item) => sum + Number(item.nrc_amount || 0) + Number(item.mrc_amount || 0),
    0
  )
}

function isSameAmount(left, right) {
  return Math.abs(Number(left || 0) - Number(right || 0)) < 0.01
}

function syncAmounts() {
  const itemTotal = getItemsAmountTotal()
  modalForm.total_amount = itemTotal
  modalForm.net_amount = Math.max(itemTotal - Number(modalForm.vat_amount || 0), 0)
  syncDueAmount()
}

function syncTotalAmount() {
  modalForm.total_amount = Number(modalForm.net_amount || 0) + Number(modalForm.vat_amount || 0)
  syncDueAmount()
}

function syncDueAmount() {
  modalForm.unpaid_amount = Math.max(
    Number(modalForm.total_amount || 0) - Number(modalForm.paid_amount || 0),
    0
  )
  syncSettled()
}

function syncSettled() {
  modalForm.is_settled = Number(modalForm.unpaid_amount || 0) <= 0
}

function validateBillAmounts(items) {
  const itemTotal = getItemsAmountTotal(items)
  if (!isSameAmount(itemTotal, modalForm.total_amount)) {
    window.$message?.error?.('Total Amount 必须等于 Invoice Summary 的 NRC + MRC 合计')
    return false
  }
  return true
}

function addItem() {
  modalForm.items.push({
    service: '',
    item: '',
    location: '',
    start_date: null,
    end_date: null,
    nrc_amount: 0,
    mrc_amount: 0,
  })
}

function removeItem(index) {
  modalForm.items.splice(index, 1)
}

function hasItemValue(item) {
  return ['service', 'item', 'location', 'start_date', 'end_date'].some((key) => item[key])
    || Number(item.nrc_amount || 0)
    || Number(item.mrc_amount || 0)
}

function handleVoucherChange({ file }) {
  if (!file?.file) {
    pendingVoucherFile.value = null
    return
  }
  if (!String(file.file.type || '').startsWith('image/')) {
    window.$message?.warning?.('请上传图片凭证')
    pendingVoucherFile.value = null
    return
  }
  pendingVoucherFile.value = file.file
}

function openFile(url) {
  window.open(url, '_blank')
}

function formatMonth(value) {
  return value ? String(value).slice(0, 7) : '-'
}

function formatShortDate(value) {
  return value ? String(value).slice(5, 10).replace('-', '/') : '-'
}

function formatInvoiceMonth(value) {
  if (!value) return ''
  const text = String(value)
  const match = text.match(/^(\d{4})-(\d{2})/)
  if (!match) return ''
  return `${match[1].slice(2)}.${match[2]}`
}

function getOwnerName(ownerId) {
  return owners.find((item) => item.id === ownerId)?.name || ownerId || '-'
}

function normalizeOwner(value) {
  const text = String(value || '')
  return owners.find((item) => item.id === text || item.name === text)?.id || text
}

function formatDateValue(date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function getToday() {
  return formatDateValue(new Date())
}

function getPreviousMonthFirstDay() {
  const now = new Date()
  return formatDateValue(new Date(now.getFullYear(), now.getMonth() - 1, 1))
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString('zh-CN', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  })
}

function formatMoney(value, currency = 'USD') {
  return `${currency || ''} ${formatNumber(value)}`.trim()
}

function renderDateCell(value) {
  return h('span', { class: value ? 'date-cell' : 'muted' }, formatShortDate(value))
}

function renderMoneyCell(value, currency = 'USD', tone = '') {
  return h('div', { class: ['money-cell', tone] }, [
    h('strong', formatNumber(value)),
    h('span', currency || ''),
  ])
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

function getBillNrcTotal(bill = detailBill.value) {
  return (bill?.items || []).reduce((sum, item) => sum + Number(item.nrc_amount || 0), 0)
}

function getBillMrcTotal(bill = detailBill.value) {
  return (bill?.items || []).reduce((sum, item) => sum + Number(item.mrc_amount || 0), 0)
}

function getCompanyAddress(companyId) {
  return getCompany(companyId)?.address || ''
}

function getCompany(companyId) {
  return companyList.value.find((item) => item.id === companyId) || null
}

function getIssuerCompanyId(bill = detailBill.value) {
  const billCompany = getCompany(bill?.company_id)
  return billCompany?.contract_company_id || issuerCompanyList.value.find((item) => item.name === 'Catixs Ltd')?.id
}

function getIssuerCompany(bill = detailBill.value) {
  const issuerId = getIssuerCompanyId(bill)
  return issuerCompanyList.value.find((item) => item.id === issuerId) || null
}

function getIssuerLogo(bill = detailBill.value) {
  return getIssuerCompany(bill)?.logo_url || ''
}

function getIssuerName(bill = detailBill.value) {
  const issuer = getIssuerCompany(bill)
  return issuer?.legal_name || issuer?.name || 'Catixs Ltd'
}

function getIssuerAddress(bill = detailBill.value) {
  return String(getIssuerCompany(bill)?.address || '').trim()
}

function getIssuerBankAccounts(bill = detailBill.value) {
  const issuerId = getIssuerCompanyId(bill)
  return issuerBankAccounts.value[issuerId] || []
}

function getAccountTitle(account, bill = detailBill.value) {
  const issuer = getIssuerCompany(bill)
  return `${issuer?.name || getIssuerName(bill)} ${account.currency || ''} Account`.trim()
}

function getAccountLines(account) {
  return [
    ['Account holder', account.account_name],
    ['Sort code', account.sort_code],
    ['Bank code', account.bank_code],
    ['Branch code', account.branch_code],
    ['Account number', account.account_number],
    ['SWIFT/BIC', account.swift_code],
    ['IBAN', account.iban],
    ['Bank name', account.bank_name],
  ].filter((line) => line[1])
}

function getCompanyLegalName(companyId, fallback = '') {
  const company = getCompany(companyId)
  return company?.legal_name || fallback || company?.name || ''
}

function getCompanyFinanceContact(companyId) {
  return getCompany(companyId)?.contact_person || ''
}

function getCompanyBillEmail(companyId) {
  const company = getCompany(companyId)
  return company?.bill_email || company?.company_email || ''
}

onMounted(async () => {
  await Promise.all([loadCompanies(), loadIssuerCompanies()])
  await $table.value?.handleSearch()
})
</script>

<template>
  <CommonPage show-footer title="账单管理">
    <template #action>
      <NButton type="primary" round @click="openAdd">
        <TheIcon icon="material-symbols:add" :size="18" class="mr-5" />
        新增账单
      </NButton>
    </template>

    <div class="summary-strip">
      <span>账单金额 {{ formatMoney(summary.total) }}</span>
      <span>已付金额 {{ formatMoney(summary.paid) }}</span>
      <span>欠费金额 {{ formatMoney(summary.unpaid) }}</span>
    </div>

    <CrudTable
      ref="$table"
      v-model:query-items="queryItems"
      :columns="columns"
      :get-data="api.getBillList"
      :scroll-x="1900"
      @on-data-change="(rows) => (tableRows = rows)"
    >
      <template #queryBar>
        <QueryBarItem label="客户" :label-width="50">
          <NSelect
            v-model:value="queryItems.company_id"
            clearable
            filterable
            :options="companyOptions"
          />
        </QueryBarItem>
        <QueryBarItem label="月份" :label-width="50">
          <NDatePicker
            v-model:formatted-value="queryItems.bill_month"
            type="month"
            value-format="yyyy-MM-dd"
            clearable
          />
        </QueryBarItem>
      </template>
    </CrudTable>

    <CrudModal
      v-model:visible="modalVisible"
      width="980px"
      :title="modalTitle"
      :loading="modalLoading"
      @save="handleSave"
    >
      <NForm
        ref="modalFormRef"
        label-placement="left"
        label-align="left"
        :label-width="96"
        :model="modalForm"
        :rules="rules"
      >
        <NGrid :cols="3" :x-gap="16">
          <NFormItemGi label="客户/供应商" path="company_id">
            <NSelect
              v-model:value="modalForm.company_id"
              filterable
              :options="companyOptions"
              @update:value="handleCompanyChange"
            />
          </NFormItemGi>
          <NFormItemGi label="账单类型">
            <NSelect v-model:value="modalForm.bill_type" :options="billTypeOptions" />
          </NFormItemGi>
          <NFormItemGi label="月份" path="bill_month">
            <NDatePicker
              v-model:formatted-value="modalForm.bill_month"
              type="month"
              value-format="yyyy-MM-dd"
              clearable
              @update:formatted-value="handleBillMonthChange"
            />
          </NFormItemGi>
          <NFormItemGi label="账单日期">
            <NDatePicker v-model:formatted-value="modalForm.invoice_date" type="date" value-format="yyyy-MM-dd" clearable />
          </NFormItemGi>
          <NFormItemGi label="截止日期">
            <NDatePicker v-model:formatted-value="modalForm.due_date" type="date" value-format="yyyy-MM-dd" clearable />
          </NFormItemGi>
          <NFormItemGi label="计费开始">
            <NDatePicker v-model:formatted-value="modalForm.billing_start_date" type="date" value-format="yyyy-MM-dd" clearable />
          </NFormItemGi>
          <NFormItemGi label="计费结束">
            <NDatePicker v-model:formatted-value="modalForm.billing_end_date" type="date" value-format="yyyy-MM-dd" clearable />
          </NFormItemGi>
          <NFormItemGi label="币种">
            <NSelect v-model:value="modalForm.currency" filterable tag :options="currencyOptions" />
          </NFormItemGi>
          <NFormItemGi label="Net Amount">
            <NInputNumber v-model:value="modalForm.net_amount" :min="0" :precision="2" @update:value="syncTotalAmount" />
          </NFormItemGi>
          <NFormItemGi label="VAT Amount">
            <NInputNumber v-model:value="modalForm.vat_amount" :min="0" :precision="2" @update:value="syncAmounts" />
          </NFormItemGi>
          <NFormItemGi label="Total Amount">
            <NInputNumber v-model:value="modalForm.total_amount" :min="0" :precision="2" disabled />
          </NFormItemGi>
          <NFormItemGi label="已付金额">
            <NInputNumber v-model:value="modalForm.paid_amount" :min="0" :precision="2" @update:value="syncTotalAmount" />
          </NFormItemGi>
          <NFormItemGi label="负责人" path="owner">
            <NSelect
              v-model:value="modalForm.owner"
              clearable
              :options="ownerOptions"
              @update:value="handleOwnerChange"
            />
          </NFormItemGi>
          <NFormItemGi :span="3" label="备注">
            <NInput v-model:value="modalForm.remark" type="textarea" :autosize="{ minRows: 2, maxRows: 4 }" />
          </NFormItemGi>
          <NFormItemGi :span="3" label="付款凭证">
            <NUpload
              :default-upload="false"
              list-type="image-card"
              accept="image/*"
              :max="1"
              @change="handleVoucherChange"
            />
            <NButton
              v-if="modalForm.payment_voucher_url"
              text
              round
              type="primary"
              @click="openFile(modalForm.payment_voucher_url)"
            >
              查看当前凭证
            </NButton>
          </NFormItemGi>
        </NGrid>
      </NForm>

      <div class="items-editor">
        <div class="items-editor-head">
          <strong>Invoice Summary</strong>
          <NButton size="small" secondary round @click="addItem">添加明细</NButton>
        </div>
        <div class="item-row item-header">
          <span>Service ID</span>
          <span>Service</span>
          <span>Item</span>
          <span>Location</span>
          <span>Start Date</span>
          <span>End Date</span>
          <span>NRC {{ modalForm.currency || '' }}</span>
          <span>MRC {{ modalForm.currency || '' }}</span>
          <span></span>
        </div>
        <div v-for="(item, index) in modalForm.items" :key="index" class="item-row">
          <span class="service-seq">{{ index + 1 }}</span>
          <NInput v-model:value="item.service" size="small" />
          <NInput v-model:value="item.item" size="small" />
          <NInput v-model:value="item.location" size="small" />
          <NDatePicker v-model:formatted-value="item.start_date" size="small" type="date" value-format="yyyy-MM-dd" clearable />
          <NDatePicker v-model:formatted-value="item.end_date" size="small" type="date" value-format="yyyy-MM-dd" clearable />
          <NInputNumber v-model:value="item.nrc_amount" size="small" :min="0" :precision="2" @update:value="syncAmounts" />
          <NInputNumber v-model:value="item.mrc_amount" size="small" :min="0" :precision="2" @update:value="syncAmounts" />
          <NButton size="small" secondary circle round @click="removeItem(index)">
            <template #icon><TheIcon icon="mdi:minus" :size="16" /></template>
          </NButton>
        </div>
      </div>
    </CrudModal>

    <NModal v-model:show="detailVisible" preset="card" class="invoice-modal" :title="detailBill?.invoice_no || '账单详情'">
      <template #header-extra>
        <NButton v-if="detailBill" type="primary" secondary round @click="printBill">
          <template #icon><TheIcon icon="mdi:printer-outline" :size="18" /></template>
          打印
        </NButton>
      </template>

      <div v-if="detailBill" class="pdf-preview-shell">
        <div ref="invoicePrintRef" class="invoice-preview invoice-print-area">
          <header class="invoice-header">
            <div class="brand">
              <img v-if="getIssuerLogo(detailBill)" :src="getIssuerLogo(detailBill)" :alt="getIssuerName(detailBill)" class="issuer-logo" />
              <span v-else>{{ getIssuerName(detailBill) }}</span>
            </div>
            <div class="issuer">
              <strong>{{ getIssuerName(detailBill) }}</strong>
              <span v-if="getIssuerAddress(detailBill)">{{ getIssuerAddress(detailBill) }}</span>
            </div>
          </header>

          <section class="invoice-top">
            <div class="customer-block">
              <strong>{{ getCompanyLegalName(detailBill.company_id, detailBill.customer_name) || '-' }}</strong>
              <span v-if="getCompanyFinanceContact(detailBill.company_id)">{{ getCompanyFinanceContact(detailBill.company_id) }}</span>
              <span v-if="getCompanyBillEmail(detailBill.company_id)">{{ getCompanyBillEmail(detailBill.company_id) }}</span>
              <span v-for="line in getCompanyAddress(detailBill.company_id).split(',')" :key="line">{{ line }}</span>
            </div>
            <div class="meta-labels">
              <span>Invoice#</span>
              <span>Invoice Date</span>
              <span>Due Date</span>
              <span>Currency</span>
            </div>
            <div class="meta-values">
              <span>{{ detailBill.invoice_no || '-' }}</span>
              <span>{{ detailBill.invoice_date || '-' }}</span>
              <span>{{ detailBill.due_date || '-' }}</span>
              <span>{{ detailBill.currency || '-' }}</span>
            </div>
          </section>

          <section class="invoice-summary">
            <div class="summary-title">Summary</div>
            <span class="summary-amount">{{ detailBill.currency || '-' }}</span>
            <label>Recurring</label>
            <span class="summary-amount">{{ formatNumber(getBillMrcTotal(detailBill)) }}</span>
            <label>Non-Recurring</label>
            <span class="summary-amount">{{ formatNumber(getBillNrcTotal(detailBill)) }}</span>
            <label>Total Charges</label>
            <b class="summary-amount">{{ formatNumber(detailBill.total_amount) }}</b>
            <strong class="summary-label">Total Due</strong>
            <strong class="summary-amount">{{ formatNumber(detailBill.unpaid_amount ?? detailBill.total_amount) }}</strong>
          </section>

          <section class="invoice-table">
            <h2>Invoice Summary</h2>
            <table>
              <thead>
                <tr>
                  <th>Service ID</th>
                  <th>Service</th>
                  <th>Item</th>
                  <th>Location</th>
                  <th>Start Date</th>
                  <th>End Date</th>
                  <th>NRC {{ detailBill.currency || '' }}</th>
                  <th>MRC {{ detailBill.currency || '' }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in detailBill.items" :key="item.id || `${item.service_id}-${item.item}`">
                  <td>{{ item.service_id || '-' }}</td>
                  <td>{{ item.service || '-' }}</td>
                  <td>{{ item.item || '-' }}</td>
                  <td>{{ item.location || '-' }}</td>
                  <td>{{ item.start_date || '-' }}</td>
                  <td>{{ item.end_date || '-' }}</td>
                  <td>{{ formatNumber(item.nrc_amount) }}</td>
                  <td>{{ formatNumber(item.mrc_amount) }}</td>
                </tr>
                <tr class="amount-row">
                  <td colspan="7">Net Amount</td>
                  <td>{{ formatNumber(detailBill.net_amount) }}</td>
                </tr>
                <tr class="amount-row">
                  <td colspan="7">VAT Amount</td>
                  <td>{{ formatNumber(detailBill.vat_amount) }}</td>
                </tr>
                <tr class="amount-row">
                  <td colspan="7">Total Amount</td>
                  <td>{{ formatNumber(detailBill.total_amount) }}</td>
                </tr>
              </tbody>
            </table>
          </section>

          <section v-if="getIssuerBankAccounts(detailBill).length" class="issuer-accounts">
            <div v-for="account in getIssuerBankAccounts(detailBill)" :key="account.id" class="account-card">
              <strong>{{ getAccountTitle(account, detailBill) }}</strong>
              <span v-for="line in getAccountLines(account)" :key="`${account.id}-${line[0]}`">
                {{ line[0] }}: {{ line[1] }}
              </span>
            </div>
          </section>
        </div>
      </div>
    </NModal>
  </CommonPage>
</template>

<style scoped>
.summary-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  margin-bottom: 14px;
  color: #475569;
  font-size: 13px;
}

:deep(.muted) {
  color: #94a3b8;
}

:deep(.bill-customer-cell) {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 3px;
  line-height: 1.25;
}

:deep(.bill-customer-cell strong) {
  overflow: hidden;
  color: #0f172a;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

:deep(.bill-customer-cell span) {
  overflow: hidden;
  color: #64748b;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

:deep(.date-pill),
:deep(.date-cell) {
  color: #475569;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
}

:deep(.date-pill) {
  display: inline-flex;
  min-width: 64px;
  justify-content: center;
  border-radius: 999px;
  background: #f1f5f9;
  padding: 2px 8px;
}

:deep(.invoice-no-cell) {
  color: #334155;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
}

:deep(.money-cell) {
  display: flex;
  min-width: 0;
  align-items: baseline;
  justify-content: flex-end;
  gap: 5px;
}

:deep(.money-cell strong) {
  color: #0f172a;
  font-variant-numeric: tabular-nums;
  font-weight: 600;
}

:deep(.money-cell span) {
  color: #94a3b8;
  font-size: 11px;
}

:deep(.money-cell.danger strong) {
  color: #dc2626;
}

:deep(.money-cell.muted strong) {
  color: #64748b;
}

:deep(.remark-cell) {
  color: #64748b;
}

.items-editor {
  margin-top: 12px;
}

.items-editor-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.item-row {
  display: grid;
  grid-template-columns: 64px 0.8fr 1.4fr 0.9fr 122px 122px 105px 105px 34px;
  gap: 6px;
  margin-bottom: 6px;
}

.service-seq {
  display: inline-flex;
  min-height: 34px;
  align-items: center;
  justify-content: center;
  border: 1px solid #dcdfe6;
  border-radius: 3px;
  background: #f8fafc;
  color: #475569;
  font-size: 13px;
}

.item-header {
  color: #64748b;
  font-size: 12px;
  font-weight: 600;
}

.invoice-modal {
  width: min(1040px, 96vw);
}

:deep(.invoice-modal .n-card__content) {
  padding: 0;
}

.pdf-preview-shell {
  max-height: calc(100vh - 150px);
  overflow: auto;
  background: #e5e7eb;
  padding: 24px;
}

.invoice-preview {
  width: 210mm;
  min-height: 297mm;
  margin: 0 auto;
  background: #fff;
  box-shadow: 0 12px 34px rgb(15 23 42 / 16%);
  color: #1f2937;
  font-size: 14px;
  padding: 18mm 16mm 20mm;
}

.invoice-header {
  display: flex;
  min-height: 104px;
  align-items: stretch;
  justify-content: space-between;
  margin-bottom: 34px;
}

.brand {
  display: flex;
  width: 470px;
  min-height: 104px;
  align-items: center;
  color: #050505;
  font-size: 52px;
  font-weight: 700;
  letter-spacing: 0;
  line-height: 1;
}

.issuer-logo {
  display: block;
  max-width: 150px;
  max-height: 104px;
  object-fit: contain;
}

.issuer {
  display: flex;
  flex-direction: column;
  gap: 3px;
  justify-content: center;
  color: #000;
  font-weight: 600;
  text-align: right;
}

.invoice-top {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 120px 250px;
  gap: 10px;
}

.customer-block,
.meta-labels,
.meta-values {
  display: flex;
  flex-direction: column;
  gap: 5px;
  border-radius: 6px;
  background: #f8fafc;
  padding: 10px 12px;
}

.meta-values {
  text-align: right;
}

.invoice-summary {
  display: grid;
  width: 360px;
  grid-template-columns: 1fr 120px;
  gap: 6px;
  margin-top: 16px;
}

.summary-title {
  color: #111827;
  font-weight: 700;
}

.summary-amount {
  text-align: right;
}

.summary-label {
  text-align: left;
}

.invoice-table {
  margin-top: 64px;
}

.invoice-table h2 {
  margin: 0;
  border: 1px solid #d8dde6;
  border-bottom: 0;
  background: #f3f4f6;
  font-size: 22px;
  line-height: 42px;
  text-align: center;
}

.invoice-table table {
  width: 100%;
  border-collapse: collapse;
}

.invoice-table th,
.invoice-table td {
  border: 1px solid #d8dde6;
  padding: 8px 9px;
  text-align: center;
}

.invoice-table th {
  background: #f8fafc;
  font-weight: 500;
}

.amount-row td:first-child {
  text-align: right;
}

.amount-row td:last-child {
  text-align: left;
}

.issuer-accounts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 28px;
}

.account-card {
  display: flex;
  min-height: 132px;
  flex-direction: column;
  gap: 7px;
  border-radius: 6px;
  background: #f8fafc;
  padding: 14px 16px;
  color: #111827;
}

.account-card strong {
  font-size: 15px;
}

.account-card span {
  line-height: 1.45;
}

:deep(.row-actions .n-button) {
  width: 30px;
  padding: 0;
}

@media (max-width: 960px) {
  .item-row,
  .invoice-top {
    grid-template-columns: 1fr;
  }

  .invoice-header,
  .issuer {
    text-align: left;
  }

  .invoice-header,
  .issuer-accounts {
    grid-template-columns: 1fr;
  }

  .invoice-header {
    display: grid;
    gap: 16px;
  }

  .invoice-summary {
    width: 100%;
  }
}

</style>
