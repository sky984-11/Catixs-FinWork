<template>
  <section class="vendor-panel">
    <div class="panel-head">
      <div>
        <span class="eyebrow">VENDOR CENTER</span>
        <h2>供应商管理</h2>
      </div>
      <NSpace>
        <NButton secondary :loading="loading" @click="emit('refresh')">刷新</NButton>
        <NButton secondary :loading="exporting" @click="exportVendors">导出</NButton>
        <NButton secondary :loading="importing" @click="fileInput.click()">导入 CSV</NButton>
        <input ref="fileInput" type="file" accept=".csv" hidden @change="importVendors" />
        <NButton type="primary" @click="emit('add')">新增供应商</NButton>
      </NSpace>
    </div>
    <div class="filters">
      <NInput v-model:value="keyword" clearable placeholder="搜索供应商编号、名称" />
      <NSelect
        v-model:value="entityId"
        clearable
        filterable
        :options="entityOptions"
        placeholder="签约主体"
      />
      <NSelect
        v-model:value="status"
        clearable
        :options="[
          { label: '启用', value: 1 },
          { label: '禁用', value: 0 },
        ]"
        placeholder="状态"
      />
      <NButton @click="reset">重置</NButton>
    </div>
    <NAlert v-if="error" type="error">{{ error }}</NAlert>
    <NDataTable
      remote
      striped
      flex-height
      class="vendor-table"
      :loading="loading"
      :columns="columns"
      :data="vendors"
      :pagination="false"
      :row-key="(row) => row.id"
      :scroll-x="scrollX"
      :scrollbar-props="{ trigger: 'none' }"
    >
      <template #empty><NEmpty description="暂无供应商" /></template>
    </NDataTable>
    <div class="vendor-pagination">
      <span>共 {{ pagination.itemCount }} 条</span>
      <NPagination
        :page="pagination.page"
        :page-size="pagination.pageSize"
        :item-count="pagination.itemCount"
        :page-sizes="pagination.pageSizes"
        :disabled="loading"
        show-size-picker
        @update:page="emit('page-change', $event)"
        @update:page-size="emit('page-size-change', $event)"
      />
    </div>
  </section>
</template>

<script setup>
import { computed, h, ref, watch } from 'vue'
import { NButton, NPagination, NSpace, NTag } from 'naive-ui'
import TheIcon from '@/components/icon/TheIcon.vue'
import api from '@/api'

const props = defineProps({
  vendors: { type: Array, default: () => [] },
  companies: { type: Array, default: () => [] },
  loading: Boolean,
  error: { type: String, default: '' },
  pagination: { type: Object, required: true },
})
const emit = defineEmits(['select', 'add', 'edit', 'delete', 'refresh', 'query-change', 'page-change', 'page-size-change'])
const keyword = ref('')
const entityId = ref(null)
const status = ref(null)
const exporting = ref(false)
const importing = ref(false)
const fileInput = ref(null)
const entityOptions = computed(() => props.companies.map((c) => ({ label: c.name, value: c.id })))
watch([keyword, entityId, status], () => {
  emit('query-change', { keyword: keyword.value.trim(), signing_entity_id: entityId.value, status: status.value })
})
function reset() {
  keyword.value = ''
  entityId.value = null
  status.value = null
}
function entity(row) {
  const name =
    row.signing_entity_name ||
    props.companies.find((c) => c.id === row.signing_entity_id)?.name ||
    '-'
  const type = name.includes('科特思') ? 'success' : name.includes('77') ? 'warning' : 'info'
  return h(NTag, { type, size: 'small', round: true }, () => name)
}
function action(row, title, icon, type, event) {
  return h(
    NButton,
    { title, type, circle: true, secondary: true, size: 'small', onClick: () => emit(event, row) },
    { icon: () => h(TheIcon, { icon, size: 15 }) }
  )
}
const columns = [
  { title: '供应商编号', key: 'code', width: 130 },
  { title: '签约主体', key: 'signing_entity_id', width: 170, render: entity },
  { title: '供应商名称', key: 'name', width: 260 },
  {
    title: '状态',
    key: 'status',
    width: 90,
    render: (row) =>
      h(NTag, { size: 'small', type: row.status ? 'success' : 'error' }, () =>
        row.status ? '启用' : '禁用'
      ),
  },
  {
    title: '操作',
    key: 'actions',
    width: 126,
    fixed: 'right',
    render: (row) =>
      h(NSpace, { size: 6, wrap: false }, () => [
        action(row, '详情', 'mdi:eye-outline', 'default', 'select'),
        action(row, '编辑', 'mdi:pencil', 'info', 'edit'),
        action(row, '删除', 'mdi:trash-can-outline', 'error', 'delete'),
      ]),
  },
].map((column) =>
  column.key === 'actions' ? column : { ...column, resizable: true, minWidth: 80 }
)
const scrollX = columns.reduce((sum, column) => sum + column.width, 0)
async function exportVendors() {
  exporting.value = true
  try {
    const response = await api.exportVendor()
    const url = URL.createObjectURL(
      new Blob(['\ufeff', response.data], { type: 'text/csv;charset=utf-8' })
    )
    const link = document.createElement('a')
    link.href = url
    link.download = '供应商.csv'
    link.click()
    URL.revokeObjectURL(url)
  } catch {
    window.$message?.error('导出失败，请重试')
  } finally {
    exporting.value = false
  }
}
async function importVendors(event) {
  const file = event.target.files?.[0]
  if (!file) return
  importing.value = true
  try {
    const response = await api.importVendor(file)
    window.$message?.info(response.msg || '导入完成')
    emit('refresh')
  } catch {
    window.$message?.error('导入失败，请重试')
  } finally {
    importing.value = false
    event.target.value = ''
  }
}
</script>

<style scoped>
.vendor-panel {
  padding: 24px;
  border-radius: 16px;
  background: var(--n-color, #fff);
}
.vendor-table {
  height: clamp(320px, calc(100vh - 340px), 720px);
}
.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}
.eyebrow {
  font-size: 11px;
  letter-spacing: 2px;
  color: #718096;
}
h2 {
  margin: 4px 0 0;
  font-size: 22px;
}
.filters {
  display: grid;
  grid-template-columns: minmax(200px, 2fr) minmax(160px, 1fr) 120px auto;
  gap: 12px;
  margin-bottom: 20px;
}
.vendor-pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 16px;
  color: #718096;
}
.vendor-pagination :deep(.n-pagination) {
  flex-wrap: wrap;
}
@media (max-width: 760px) {
  .vendor-panel {
    padding: 12px;
  }
  .filters {
    grid-template-columns: 1fr;
  }
}
</style>
