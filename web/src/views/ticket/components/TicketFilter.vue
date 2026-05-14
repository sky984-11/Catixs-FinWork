<template>
  <div class="ticket-filter">
    <div class="filter-row">
      <div class="filter-item">
        <span class="filter-label">工单标题：</span>
        <n-input v-model:value="localFilters.title" placeholder="请输入工单标题" style="width: 180px" />
      </div>
      <div class="filter-item">
        <span class="filter-label">工单状态：</span>
        <n-select v-model:value="localFilters.status" :options="statusOptions" placeholder="请选择状态" style="width: 130px" />
      </div>
      <div class="filter-item">
        <span class="filter-label">工单类型：</span>
        <n-select v-model:value="localFilters.type" :options="visibleTypeOptions" placeholder="请选择类型" style="width: 150px" />
      </div>
      <div v-show="isAdminOrNoc" class="filter-item">
        <span class="filter-label">用户：</span>
        <n-select v-model:value="localFilters.customerId" :options="customerOptions" placeholder="请选择用户" style="width: 150px" />
      </div>
      <n-button secondary type="primary" style="border-radius: 12px" @click="$emit('search')">查询</n-button>
      <n-button secondary style="border-radius: 12px" @click="$emit('reset')">重置</n-button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

defineEmits(['search', 'reset'])

const props = defineProps({
  filters: {
    type: Object,
    required: true
  },
  isAdminOrNoc: {
    type: Boolean,
    default: false
  },
  statusOptions: {
    type: Array,
    default: () => []
  },
  typeOptions: {
    type: Array,
    default: () => []
  },
  customerOptions: {
    type: Array,
    default: () => []
  }
})

const localFilters = computed({
  get: () => props.filters,
  set: (val) => {
    Object.assign(props.filters, val)
  }
})

const visibleTypeOptions = computed(() => {
  return [{ label: '全部类型', value: null }, ...props.typeOptions]
})
</script>

<style scoped>
.ticket-filter {
  padding: 16px;
}

.filter-row {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.filter-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.filter-label {
  font-size: 14px;
  color: var(--n-text-color);
}
</style>
