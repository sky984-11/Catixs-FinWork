<script setup>
import { computed, h, onMounted, reactive, ref } from 'vue'
import {
  NButton,
  NDataTable,
  NDatePicker,
  NEmpty,
  NForm,
  NFormItem,
  NGrid,
  NGridItem,
  NInput,
  NInputNumber,
  NModal,
  NPagination,
  NPopconfirm,
  NSelect,
  NSpace,
  NSpin,
  NTag,
  NTooltip,
} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import api from '@/api'
import { renderIcon } from '@/utils'

const loading = ref(false)
const inventories = ref([])
const categories = ref([])
const locations = ref([])
const sales = ref([])
const flows = ref([])
const saleQuantities = reactive({})

const query = reactive({
  keyword: '',
  location_id: null,
  type: null,
  subtype: null,
  only_low_stock: false,
})

const pagination = reactive({
  page: 1,
  pageSize: 12,
  itemCount: 0,
})

const saleModal = reactive({
  show: false,
  submitting: false,
  inventory: null,
  form: createSaleForm(),
})

const saleRecordsModal = reactive({
  show: false,
  loading: false,
  page: 1,
  pageSize: 10,
  itemCount: 0,
})

const flowModal = reactive({
  show: false,
  loading: false,
  page: 1,
  pageSize: 10,
  itemCount: 0,
})

const typeOptions = computed(() =>
  categories.value.map((item) => ({
    label: item.name,
    value: item.name,
  }))
)

const locationOptions = computed(() =>
  locations.value.map((item) => ({
    label: item.region_name ? `${item.name}（${item.region_name}）` : item.name,
    value: item.id,
  }))
)

const subtypeOptions = computed(() => {
  const type = categories.value.find((item) => item.name === query.type)
  return (type?.children || []).map((item) => ({
    label: item.name,
    value: item.name,
  }))
})

const currentInventoryTitle = computed(() => {
  const row = saleModal.inventory
  if (!row) return ''
  return `${row.type || '-'} / ${row.subtype || '-'}`
})

const saleAmount = computed(() =>
  ((Number(saleModal.form.quantity) || 0) * (Number(saleModal.form.unit_price) || 0)).toFixed(2)
)

const saleColumns = [
  { title: '销售单号', key: 'sale_no', minWidth: 180, ellipsis: { tooltip: true } },
  { title: '销售日期', key: 'sale_date', width: 120, align: 'center', render: (row) => formatDate(row.sale_date) },
  {
    title: '金额',
    key: 'total_amount',
    width: 120,
    align: 'right',
    render: (row) => h('span', { class: 'amount-cell' }, formatMoney(row.total_amount)),
  },
  {
    title: '状态',
    key: 'status',
    width: 96,
    align: 'center',
    render(row) {
      const cancelled = Number(row.status) === 2
      return h(
        NTag,
        { type: cancelled ? 'default' : 'success', round: true, bordered: false },
        { default: () => (cancelled ? '已取消' : '已完成') }
      )
    },
  },
  {
    title: '明细',
    key: 'items',
    minWidth: 220,
    ellipsis: { tooltip: true },
    render: (row) =>
      (row.items || [])
        .map((item) => `${item.type || '-'} / ${item.subtype || '-'} x ${item.quantity}`)
        .join('；') || '-',
  },
  {
    title: '操作',
    key: 'actions',
    width: 82,
    align: 'center',
    render(row) {
      if (Number(row.status) === 2) return h('span', { class: 'muted' }, '-')
      return h(
        NPopconfirm,
        { onPositiveClick: () => cancelSale(row) },
        {
          trigger: () => renderIconButton('取消销售单', 'mdi:undo-variant', { type: 'warning' }),
          default: () => '取消后会回滚库存，确定继续吗？',
        }
      )
    },
  },
]

const flowColumns = [
  { title: '时间', key: 'created_at', width: 170, render: (row) => formatDateTime(row.created_at) },
  { title: '类型', key: 'flow_type', width: 96, align: 'center', render: (row) => flowTypeLabel(row.flow_type) },
  { title: '库存', key: 'inventory', minWidth: 180, ellipsis: { tooltip: true }, render: flowInventoryLabel },
  { title: '变动', key: 'quantity_change', width: 90, align: 'right', render: (row) => renderDelta(row.quantity_change) },
  { title: '变动前', key: 'quantity_before', width: 90, align: 'right' },
  { title: '变动后', key: 'quantity_after', width: 90, align: 'right' },
  { title: '关联单号', key: 'reference_no', minWidth: 150, ellipsis: { tooltip: true } },
  { title: '备注', key: 'remark', minWidth: 180, ellipsis: { tooltip: true } },
]

function createSaleForm() {
  return {
    sale_date: getToday(),
    quantity: 1,
    unit_price: 0,
    remark: '',
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

async function loadCategories() {
  const res = await api.assetApi.inventoryCategories()
  categories.value = res.data || []
}

async function loadLocations() {
  const res = await api.assetApi.locations({ page_size: 1000, type: 0 })
  locations.value = res.data || []
}

async function loadInventories() {
  loading.value = true
  try {
    const res = await api.assetApi.inventory({
      page: pagination.page,
      page_size: pagination.pageSize,
      keyword: query.keyword || undefined,
      location_id: query.location_id || undefined,
      type: query.type || undefined,
      subtype: query.subtype || undefined,
      only_low_stock: query.only_low_stock || undefined,
      only_available: true,
    })
    inventories.value = res.data || []
    syncSaleQuantities(inventories.value)
    pagination.itemCount = res.total || 0
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  pagination.page = 1
  loadInventories()
}

function resetQuery() {
  query.keyword = ''
  query.location_id = null
  query.type = null
  query.subtype = null
  query.only_low_stock = false
  handleSearch()
}

function handleTypeChange() {
  query.subtype = null
  handleSearch()
}

function syncSaleQuantities(rows) {
  rows.forEach((row) => {
    const max = Math.max(Number(row.quantity || 0), 1)
    const current = Number(saleQuantities[row.id] || 0)
    saleQuantities[row.id] = current > 0 ? Math.min(current, max) : 1
  })
}

function getSaleQuantity(row) {
  return Math.min(Math.max(Number(saleQuantities[row.id] || 1), 1), Math.max(Number(row.quantity || 0), 1))
}

function openSale(row) {
  if (Number(row.quantity || 0) <= 0) {
    window.$message?.warning?.('当前库存不足，无法售卖')
    return
  }
  saleModal.inventory = row
  saleModal.form = createSaleForm()
  saleModal.form.quantity = getSaleQuantity(row)
  saleModal.form.unit_price = Number(row.sale_price || 0)
  saleModal.show = true
}

async function submitSale() {
  if (!saleModal.inventory) return
  if (Number(saleModal.form.quantity || 0) <= 0) {
    window.$message?.warning?.('请输入销售数量')
    return
  }
  if (Number(saleModal.form.quantity || 0) > Number(saleModal.inventory.quantity || 0)) {
    window.$message?.warning?.('销售数量不能大于当前库存')
    return
  }

  saleModal.submitting = true
  try {
    await api.assetApi.createInventorySale({
      customer_name: '',
      customer_contact: '',
      sale_date: saleModal.form.sale_date,
      remark: saleModal.form.remark,
      items: [
        {
          inventory_id: saleModal.inventory.id,
          quantity: saleModal.form.quantity,
          unit_price: saleModal.form.unit_price,
          remark: saleModal.form.remark,
        },
      ],
    })
    window.$message?.success?.('售卖成功，库存已扣减')
    saleModal.show = false
    await Promise.all([loadInventories(), saleRecordsModal.show ? loadSales() : Promise.resolve()])
  } finally {
    saleModal.submitting = false
  }
}

async function openSales() {
  saleRecordsModal.page = 1
  saleRecordsModal.show = true
  await loadSales()
}

async function loadSales() {
  saleRecordsModal.loading = true
  try {
    const res = await api.assetApi.inventorySales({
      page: saleRecordsModal.page,
      page_size: saleRecordsModal.pageSize,
    })
    sales.value = res.data || []
    saleRecordsModal.itemCount = res.total || 0
  } finally {
    saleRecordsModal.loading = false
  }
}

async function cancelSale(row) {
  await api.assetApi.cancelInventorySale({ id: row.id, reason: '财务库存售卖页面取消销售单' })
  window.$message?.success?.('销售单已取消，库存已回滚')
  await Promise.all([loadSales(), loadInventories()])
}

async function openFlows() {
  flowModal.page = 1
  flowModal.show = true
  await loadFlows()
}

async function loadFlows() {
  flowModal.loading = true
  try {
    const res = await api.assetApi.inventoryFlows({
      page: flowModal.page,
      page_size: flowModal.pageSize,
    })
    flows.value = res.data || []
    flowModal.itemCount = res.total || 0
  } finally {
    flowModal.loading = false
  }
}

function onPageChange(page) {
  pagination.page = page
  loadInventories()
}

function onPageSizeChange(pageSize) {
  pagination.pageSize = pageSize
  pagination.page = 1
  loadInventories()
}

function isLowStock(row) {
  const quantity = Number(row.quantity || 0)
  const threshold = Number(row.threshold || 0)
  return quantity <= 0 || (threshold > 0 && quantity < threshold)
}

function stockTagType(row) {
  if (Number(row.quantity || 0) <= 0) return 'error'
  if (isLowStock(row)) return 'warning'
  return 'success'
}

function getCardMeta(row) {
  const parts = [row.location_name, row.cabinet_name].filter(Boolean)
  return parts.length ? parts.join(' / ') : '未绑定位置'
}

function getAttributeTags(row) {
  const attrs = row.attributes && typeof row.attributes === 'object' ? row.attributes : {}
  return Object.entries(attrs)
    .filter(([, value]) => value !== null && value !== undefined && String(value).trim() !== '')
    .map(([key, value]) => ({
      key,
      label: `${key}: ${value}`,
    }))
}

function flowInventoryLabel(row) {
  const parts = [row.inventory_type, row.inventory_subtype].filter(Boolean)
  return parts.length ? parts.join(' / ') : row.inventory_id || '-'
}

function renderDelta(value) {
  const number = Number(value || 0)
  return h('span', { class: number < 0 ? 'delta-negative' : 'delta-positive' }, number > 0 ? `+${number}` : String(number))
}

function flowTypeLabel(type) {
  const labels = { sale: '销售', sale_cancel: '取消', adjust: '调整', import: '导入' }
  return labels[type] || type || '-'
}

function formatMoney(value) {
  return Number(value || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function formatDate(value) {
  return value ? String(value).slice(0, 10) : '-'
}

function formatDateTime(value) {
  return value ? String(value).replace('T', ' ').slice(0, 19) : '-'
}

function getToday() {
  const now = new Date()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${now.getFullYear()}-${month}-${day}`
}

onMounted(async () => {
  await Promise.all([loadCategories(), loadLocations(), loadInventories()])
})
</script>

<template>
  <CommonPage show-footer title="库存售卖">
    <template #action>
      <NSpace>
        <NButton secondary round @click="openSales">
          <TheIcon icon="mdi:receipt-text-outline" :size="18" class="mr-5" />
          销售记录
        </NButton>
        <NButton secondary round @click="openFlows">
          <TheIcon icon="mdi:swap-horizontal" :size="18" class="mr-5" />
          库存流水
        </NButton>
        <NButton type="primary" round :loading="loading" @click="loadInventories">
          <TheIcon icon="mdi:refresh" :size="18" class="mr-5" />
          刷新
        </NButton>
      </NSpace>
    </template>

    <div class="sale-page">
      <div class="filter-bar">
        <NInput v-model:value="query.keyword" clearable placeholder="搜索库存名称、型号、位置" @keypress.enter="handleSearch">
          <template #prefix>
            <TheIcon icon="mdi:magnify" :size="18" />
          </template>
        </NInput>
        <NSelect
          v-model:value="query.location_id"
          clearable
          filterable
          :options="locationOptions"
          placeholder="全部仓库"
          @update:value="handleSearch"
        />
        <NSelect v-model:value="query.type" clearable :options="typeOptions" placeholder="全部类型" @update:value="handleTypeChange" />
        <NSelect
          v-model:value="query.subtype"
          clearable
          :disabled="!query.type"
          :options="subtypeOptions"
          placeholder="全部子类型"
          @update:value="handleSearch"
        />
        <NButton :type="query.only_low_stock ? 'warning' : 'default'" secondary round @click="query.only_low_stock = !query.only_low_stock; handleSearch()">
          <TheIcon icon="mdi:alert-circle-outline" :size="18" class="mr-5" />
          低库存
        </NButton>
        <NButton type="primary" round @click="handleSearch">
          <TheIcon icon="mdi:magnify" :size="18" class="mr-5" />
          查询
        </NButton>
        <NButton secondary round @click="resetQuery">重置</NButton>
      </div>

      <NSpin :show="loading">
        <NEmpty v-if="!inventories.length" class="empty-state" description="暂无可售库存" />
        <NGrid v-else responsive="screen" cols="1 s:2 m:3 l:4 xl:4 2xl:5" :x-gap="16" :y-gap="16">
          <NGridItem v-for="item in inventories" :key="item.id">
            <div class="inventory-card" :class="{ warning: isLowStock(item) }">
              <div class="card-head">
                <div class="title-group">
                  <strong>{{ item.type || '-' }}</strong>
                  <span>{{ item.subtype || '未分类' }}</span>
                </div>
                <NTag :type="stockTagType(item)" round bordered>{{ isLowStock(item) ? '低库存' : '库存正常' }}</NTag>
              </div>
              <div class="stock-number">
                <strong>{{ item.quantity || 0 }}</strong>
                <span>可售库存</span>
              </div>
              <div class="card-meta">
                <span>{{ getCardMeta(item) }}</span>
                <span>阈值 {{ item.threshold || 0 }}</span>
              </div>
              <div class="price-line">
                <span>成本 {{ formatMoney(item.cost_price) }}</span>
                <strong>售价 {{ formatMoney(item.sale_price) }}</strong>
              </div>
              <div class="attr-line">
                <NTag v-if="item.brand" size="small" round>{{ item.brand }}</NTag>
                <NTag v-if="item.model" size="small" round>{{ item.model }}</NTag>
                <NTag v-if="item.unit" size="small" round>{{ item.unit }}</NTag>
                <NTooltip v-for="attr in getAttributeTags(item)" :key="attr.key" trigger="hover" placement="top">
                  <template #trigger>
                    <NTag size="small" round class="attr-tag">{{ attr.label }}</NTag>
                  </template>
                  {{ attr.label }}
                </NTooltip>
              </div>
              <div class="sale-quantity-row">
                <span>售卖数量</span>
                <NInputNumber
                  v-model:value="saleQuantities[item.id]"
                  size="small"
                  button-placement="both"
                  :min="1"
                  :max="Number(item.quantity || 1)"
                />
              </div>
              <div class="card-actions">
                <NButton type="primary" round block :disabled="Number(item.quantity || 0) <= 0" @click="openSale(item)">
                  <TheIcon icon="mdi:cart-outline" :size="18" class="mr-5" />
                  售卖
                </NButton>
              </div>
            </div>
          </NGridItem>
        </NGrid>
      </NSpin>

      <div class="pagination-wrap">
        <NPagination
          v-model:page="pagination.page"
          v-model:page-size="pagination.pageSize"
          show-size-picker
          :page-sizes="[12, 24, 48, 96]"
          :item-count="pagination.itemCount"
          @update:page="onPageChange"
          @update:page-size="onPageSizeChange"
        />
      </div>
    </div>

    <NModal v-model:show="saleModal.show" preset="card" title="库存售卖" class="sale-modal">
      <NForm label-placement="top">
        <NGrid :cols="2" :x-gap="16">
          <NFormItem label="库存">
            <NInput :value="currentInventoryTitle" readonly />
          </NFormItem>
          <NFormItem label="当前库存">
            <NInput :value="String(saleModal.inventory?.quantity || 0)" readonly />
          </NFormItem>
          <NFormItem label="销售日期">
            <NDatePicker v-model:formatted-value="saleModal.form.sale_date" value-format="yyyy-MM-dd" type="date" clearable />
          </NFormItem>
          <NFormItem label="销售数量">
            <NInputNumber v-model:value="saleModal.form.quantity" :min="1" :max="Number(saleModal.inventory?.quantity || 1)" />
          </NFormItem>
          <NFormItem label="单价">
            <NInputNumber v-model:value="saleModal.form.unit_price" :min="0" />
          </NFormItem>
          <NFormItem label="销售金额">
            <NInput :value="saleAmount" readonly />
          </NFormItem>
        </NGrid>
        <NFormItem label="备注">
          <NInput v-model:value="saleModal.form.remark" type="textarea" placeholder="销售备注" />
        </NFormItem>
      </NForm>
      <template #footer>
        <div class="modal-footer">
          <NButton round @click="saleModal.show = false">取消</NButton>
          <NButton type="primary" round :loading="saleModal.submitting" @click="submitSale">确认售卖</NButton>
        </div>
      </template>
    </NModal>

    <NModal v-model:show="saleRecordsModal.show" preset="card" title="销售记录" class="table-modal">
      <NDataTable
        remote
        :loading="saleRecordsModal.loading"
        :columns="saleColumns"
        :data="sales"
        :pagination="{
          page: saleRecordsModal.page,
          pageSize: saleRecordsModal.pageSize,
          itemCount: saleRecordsModal.itemCount,
          showSizePicker: true,
          pageSizes: [10, 20, 50],
        }"
        :scroll-x="1180"
        @update:page="(page) => { saleRecordsModal.page = page; loadSales() }"
        @update:page-size="(size) => { saleRecordsModal.pageSize = size; saleRecordsModal.page = 1; loadSales() }"
      />
    </NModal>

    <NModal v-model:show="flowModal.show" preset="card" title="库存流水" class="table-modal">
      <NDataTable
        remote
        :loading="flowModal.loading"
        :columns="flowColumns"
        :data="flows"
        :pagination="{
          page: flowModal.page,
          pageSize: flowModal.pageSize,
          itemCount: flowModal.itemCount,
          showSizePicker: true,
          pageSizes: [10, 20, 50],
        }"
        :scroll-x="1080"
        @update:page="(page) => { flowModal.page = page; loadFlows() }"
        @update:page-size="(size) => { flowModal.pageSize = size; flowModal.page = 1; loadFlows() }"
      />
    </NModal>
  </CommonPage>
</template>

<style scoped>
.sale-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.filter-bar {
  display: grid;
  grid-template-columns:
    minmax(220px, 1.4fr)
    minmax(150px, 0.9fr)
    minmax(130px, 0.7fr)
    minmax(130px, 0.7fr)
    auto auto auto;
  gap: 12px;
  align-items: center;
}

.inventory-card {
  display: flex;
  min-height: 238px;
  padding: 16px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--card-color);
  flex-direction: column;
  gap: 14px;
}

.inventory-card.warning {
  border-color: rgba(240, 160, 32, 0.55);
}

.card-head,
.card-meta,
.card-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.title-group {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 3px;
}

.title-group strong {
  overflow: hidden;
  font-size: 16px;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.title-group span,
.card-meta,
.stock-number span,
.muted {
  color: var(--text-color-3);
}

.stock-number {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.stock-number strong {
  font-size: 34px;
  line-height: 1;
}

.card-meta {
  font-size: 13px;
}

.card-meta span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.attr-line {
  display: flex;
  min-height: 24px;
  flex-wrap: wrap;
  gap: 6px;
}

.price-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: var(--text-color-2);
  font-size: 13px;
}

.price-line strong {
  color: var(--text-color-1);
  font-weight: 650;
}

.attr-tag {
  max-width: 100%;
}

.attr-tag :deep(.n-tag__content) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sale-quantity-row {
  display: grid;
  grid-template-columns: auto minmax(120px, 1fr);
  gap: 10px;
  align-items: center;
  color: var(--text-color-2);
  font-size: 13px;
}

.card-actions {
  margin-top: auto;
}

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
}

.empty-state {
  padding: 72px 0;
}

.sale-modal {
  width: min(720px, 92vw);
}

.table-modal {
  width: min(1180px, 94vw);
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.amount-cell {
  font-weight: 650;
}

.delta-negative {
  color: #d03050;
}

.delta-positive {
  color: #18a058;
}

:deep(.icon-only-btn) {
  width: 30px;
  height: 30px;
}

@media (max-width: 900px) {
  .filter-bar {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 560px) {
  .filter-bar {
    grid-template-columns: 1fr;
  }
}
</style>
