<template>
  <div class="filter-bar">
    <div class="row">
      <n-input v-model="filters.billNo" placeholder="请输入账单编号" style="width: 220px" />
      <n-select v-model="filters.supplier" :options="supplierOptions" placeholder="请选择供应商" style="width: 200px"/>
      <n-select v-model="filters.status" :options="statusOptions" placeholder="状态" style="width: 140px"/>
      <n-date-picker v-model="filters.dateRange" type="daterange" placeholder="账单日期" style="width: 260px"/>
      <n-button type="primary" @click="onSearch">查询</n-button>
      <n-button @click="onReset">重置</n-button>
    </div>
  </div>
</template>

<script setup>
import { reactive } from 'vue'

const emit = defineEmits(['search'])

const filters = reactive({
  billNo: '',
  supplier: null,
  status: null,
  dateRange: []
})

const supplierOptions = [
  { label: '全部供应商', value: null },
  { label: '中国电信股份有限公司', value: 'telecom' }
]
const statusOptions = [
  { label: '全部', value: null },
  { label: '已付款', value: 'paid' },
  { label: '未付款', value: 'unpaid' }
]

function onSearch() {
  emit('search', { ...filters })
}
function onReset() {
  filters.billNo = ''
  filters.supplier = null
  filters.status = null
  filters.dateRange = []
  emit('search', { ...filters })
}
</script>

<style scoped>
.filter-bar { padding: 8px 0 }
.row { display: flex; gap: 12px; align-items: center }
</style>
