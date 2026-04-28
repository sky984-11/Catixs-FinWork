<template>
  <n-card title="供应商列表" :bordered="false">
        <template #header-extra>
                <n-button type="primary" size="small" quaternary @click="triggerImport">
            <template #icon>
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                <polyline points="17 8 12 3 7 8"/>
                <line x1="12" y1="3" x2="12" y2="15"/>
              </svg>
            </template>
            导入
          </n-button>
          <n-button type="info" size="small" quaternary @click="handleExport">
            <template #icon>
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                <polyline points="7 10 12 15 17 10"/>
                <line x1="12" y1="15" x2="12" y2="3"/>
              </svg>
            </template>
            导出
          </n-button>
    </template>
    <n-space vertical size="medium">
      <n-space justify="space-between" align="center">
        <n-input v-model:value="keyword" clearable placeholder="搜索供应商名称"  />
        <n-space size="small">

          <input
            ref="importInput"
            type="file"
            accept=".csv"
            style="display: none"
            @change="handleImport"
          />
        </n-space>
      </n-space>

      <div class="list">
        <div
          v-for="item in filteredList"
          :key="item.id"
          class="item"
          :class="{ active: activeId === item.id }"
          @click="selectItem(item)"
        >
          <div class="avatar">{{ item.name.slice(0, 2) }}</div>

          <div class="info">
            <div class="name">{{ item.name }}</div>
            <div class="sub">{{ item.country }}</div>
          </div>

          <n-tag round  :type="item.status ? 'success' : 'error'" size="small">
            {{ item.status ? '启用' : '禁用' }}
          </n-tag>
        </div>
      </div>

      <n-button type="primary" block round @click="emit('add')"> + 新增供应商 </n-button>
    </n-space>
  </n-card>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import api from '@/api'

const props = defineProps({
  vendorList: {
    type: Array,
    default: () => [],
  },
  activeId: {
    type: [Number, String],
    default: null,
  },
})

const innerActiveId = ref(null)
const keyword = ref('')
const importInput = ref(null)

const emit = defineEmits(['select', 'add', 'update:activeId', 'refresh'])

const activeId = computed(() => props.activeId ?? innerActiveId.value)

const filteredList = computed(() => {
  const k = keyword.value.trim()
  if (!k) return props.vendorList
  return props.vendorList.filter((v) => String(v?.name || '').includes(k))
})

// ✅ 默认选中第一个
watch(
  () => props.vendorList,
  (list) => {
    if (list.length && !activeId.value) {
      innerActiveId.value = list[0].id
      emit('update:activeId', list[0].id)
      emit('select', list[0]) // 顺便通知父组件
    }
  },
  { immediate: true }
)

const selectItem = (item) => {
  innerActiveId.value = item.id
  emit('update:activeId', item.id)
  emit('select', item)
}

// 导出
async function handleExport() {
  try {
    const response = await api.exportVendor()
    // 获取响应数据
    const res = response.data
    // 创建下载链接
    const blob = new Blob([res], { type: 'text/csv;charset=utf-8;' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `供应商_${new Date().toISOString().slice(0, 10)}.csv`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  } catch (e) {
    window.$message?.error?.('导出失败')
  }
}

// 触发导入
function triggerImport() {
  importInput.value?.click()
}

// 导入
async function handleImport(event) {
  const file = event.target.files?.[0]
  if (!file) return
  
  if (!file.name.toLowerCase().endsWith('.csv')) {
    window.$message?.error?.('请选择 CSV 文件')
    return
  }
  
  try {
    const res = await api.importVendor(file)
    if (res?.code === 0 || res?.code === 200) {
      window.$message?.success?.(res?.msg || '导入成功')
      emit('refresh')
    } else {
      window.$message?.error?.(res?.msg || '导入失败')
    }
  } catch (e) {
    window.$message?.error?.('导入失败')
  }
  
  // 清空input
  event.target.value = ''
}
</script>

<style scoped>
.item {
  display: flex;
  align-items: center;
  padding: 12px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
}

/* ⭐ 选中态 */
.item.active {
  box-shadow: 0 2px 10px rgba(59, 130, 246, 0.15);
}

/* 左侧高亮条（增强选中感） */
.item.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 8px;
  bottom: 8px;
  width: 4px;
  background: #3b82f6;
  border-radius: 4px;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #3b82f6;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 10px;
}

.info {
  flex: 1;
}

.name {
  font-weight: 600;
}

.sub {
  font-size: 12px;
  color: #999;
}
</style>
