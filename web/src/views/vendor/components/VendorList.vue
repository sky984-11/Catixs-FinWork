<template>
  <n-card title="供应商列表" :bordered="false">
    <n-space vertical size="medium">
      <n-input v-model:value="keyword" clearable placeholder="搜索供应商名称" />

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

const emit = defineEmits(['select', 'add', 'update:activeId'])

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
