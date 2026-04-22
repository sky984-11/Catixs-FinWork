<template>
  <div class="vendor-page">
    <div class="vendor-container">
      <aside class="sidebar bg-white dark:bg-dark transition-background-color duration-300 ease-in-out">
        <SupplierTree @select="onSelectSupplier" />
      </aside>

      <main class="main bg-white dark:bg-dark transition-background-color duration-300 ease-in-out">
        <FilterBar @search="onSearch" />

        <div class="toolbar">
          <div class="left info">
            <div class="supplier-name">{{ supplierLabel }}</div>
            <div class="supplier-count">共 {{ billCount }} 条账单</div>
          </div>

          <div class="right actions">
            <n-space>
              <n-button type="primary" @click="onNew">+ 新增账单</n-button>
              <n-button @click="onExport">导出</n-button>
            </n-space>
          </div>
        </div>

        <BillsTable
          :bills="bills"
          :loading="loading"
          :page.sync="page"
          :pageSize.sync="pageSize"
          :total="total"
          @page-change="handlePageChange"
        />
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import SupplierTree from './components/SupplierTree.vue'
import FilterBar from './components/FilterBar.vue'
import BillsTable from './components/BillsTable.vue'

const bills = ref([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)
const selectedSupplier = ref(null)

function mockLoad() {
  loading.value = true
  setTimeout(() => {
    const rows = []
      const currencies = ['CNY', 'USD', 'EUR']
      for (let i = 0; i < 10; i++) {
      const id = (page.value - 1) * pageSize.value + i + 1
      // assign a mock supplier key for demo filtering
      const suppliers = ['telecom', 'unicom', 'cmcc', 'huawei', 'h3c', 'zte', 'dell', 'lenovo', 'cisco', 'juniper']
      const supplierKey = suppliers[id % suppliers.length]

      const currencyKey = currencies[id % currencies.length]

      rows.push({
        id,
        billNo: `BILL-202405-${String(1000 + id).slice(-4)}`,
        type: ['带票费用', 'IP资源费用', '机柜租用费'][id % 3],
        billDate: '2024-05-25',
        dueDate: '2024-06-24',
        amount: (Math.random() * 100000).toFixed(2),
        paid: (Math.random() * 50000).toFixed(2),
        unpaid: (Math.random() * 50000).toFixed(2),
        status: ['已付款', '部分付款', '未付款'][id % 3],
        owner: ['张三', '李四', '王五'][id % 3],
        supplier: supplierKey,
        currency: currencyKey
      })
    }
    // apply supplier filter if selected
    if (selectedSupplier.value) {
      bills.value = rows.filter(r => r.supplier === selectedSupplier.value.key)
    } else {
      bills.value = rows
    }
    total.value = 118
    loading.value = false
  }, 300)
}

onMounted(() => {
  mockLoad()
})

function onSearch(filters) {
  // apply filters and reload
  page.value = 1
  mockLoad()
}

function onSelectSupplier(supplier) {
  selectedSupplier.value = supplier
  page.value = 1
  mockLoad()
}

function onNew() {
  if (!selectedSupplier.value) {
    // Use global $message injected by AppProvider
    $message.error('请选择供应商')
    return
  }
  // proceed to create new bill for selected supplier
  console.log('新建账单 for', selectedSupplier.value)
}
function onImport() {
  console.log('导入账单')
}
function onExport() {
  console.log('导出')
}

function handlePageChange(p) {
  page.value = p
  mockLoad()
}

const supplierLabel = computed(() => {
  return selectedSupplier.value && selectedSupplier.value.label ? selectedSupplier.value.label : '全部供应商'
})

const billCount = computed(() => bills.value ? bills.value.length : 0)
</script>

<style scoped>
.vendor-container {
  display: flex;
  gap: 20px;
  padding: 18px;
}
.sidebar {
  width: 260px;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  height: calc(100vh - 48px);
  overflow: auto;
}
.main {
  flex: 1;
  min-width: 700px;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin: 12px 0;
}
.toolbar .info { display:flex; flex-direction:column }
.supplier-name { font-weight: 600; font-size: 16px }
.supplier-count { color: var(--text-2); font-size: 12px }
.toolbar .actions { display:flex; align-items:center }
</style>
