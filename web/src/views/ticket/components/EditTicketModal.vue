<template>
  <n-modal :show="visible" preset="card" title="编辑工单" style="width: 600px" @update:show="$emit('update:visible', $event)">
    <n-form :model="form" label-placement="top">
      <n-form-item label="工单标题" required>
        <n-input v-model:value="form.title" placeholder="请输入工单标题" />
      </n-form-item>
      <n-form-item label="工单类型" required>
        <n-select v-model:value="form.type" :options="typeOptions" placeholder="请选择工单类型" />
      </n-form-item>
      <n-form-item label="工单描述" required>
        <n-input v-model:value="form.description" type="textarea" placeholder="请输入工单描述" :rows="4" />
      </n-form-item>
      <n-form-item label="地点">
        <n-input v-model:value="form.location" placeholder="请输入地点" />
      </n-form-item>
      <n-form-item label="计划时间">
        <n-date-picker
          v-model:value="form.planTime"
          type="datetime"
          placeholder="请选择计划时间"
        />
      </n-form-item>
    </n-form>
    <template #footer>
      <n-space justify="end">
        <n-button @click="$emit('update:visible', false)">取消</n-button>
        <n-button type="primary" @click="handleSubmit">保存</n-button>
      </n-space>
    </template>
  </n-modal>
</template>

<script setup>
import { reactive, watch } from 'vue'

const emit = defineEmits(['update:visible', 'submit'])

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  ticket: {
    type: Object,
    default: null
  },
  typeOptions: {
    type: Array,
    default: () => []
  }
})

const form = reactive({
  id: null,
  title: '',
  type: null,
  description: '',
  location: '',
  planTime: null
})

watch(() => props.ticket, (newTicket) => {
  if (newTicket) {
    form.id = newTicket.id
    form.title = newTicket.title || ''
    form.type = newTicket.type
    form.description = newTicket.description || ''
    form.location = newTicket.location || ''
    form.planTime = newTicket.planTime ? new Date(newTicket.planTime) : null
  }
}, { immediate: true })

function handleSubmit() {
  if (!form.title || form.type === null || !form.description) {
    window.$message?.warning('请填写必填项')
    return
  }
  emit('submit', {
    id: form.id,
    title: form.title,
    type: form.type,
    description: form.description,
    location: form.location || undefined,
    planTime: form.planTime ? form.planTime.toISOString() : undefined
  })
}
</script>
