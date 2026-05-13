<template>
  <n-modal :show="visible" preset="card" title="编辑工单" style="width: 600px" @update:show="$emit('update:visible', $event)">
    <n-form ref="formRef" :model="form" :rules="rules" label-placement="top" :show-feedback="false">
      <n-form-item label="工单标题" path="title" required>
        <n-input v-model:value="form.title" placeholder="请输入工单标题" />
      </n-form-item>
      <n-form-item label="工单类型" path="type" required>
        <n-select v-model:value="form.type" :options="typeOptions" placeholder="请选择工单类型" />
      </n-form-item>
      <n-form-item label="工单描述" path="description" required>
        <n-input v-model:value="form.description" type="textarea" placeholder="请输入工单描述" :rows="4" />
      </n-form-item>
      <n-form-item label="地点">
        <n-input v-model:value="form.location" placeholder="请输入地点" />
      </n-form-item>
      <n-form-item label="计划时间">
        <n-date-picker
          v-model:value="form.planTime"
          type="datetime"
          format="yyyy-MM-dd HH:mm"
          :time-picker-props="{ format: 'HH:mm' }"
          placeholder="请选择计划时间"
          style="width: 100%"
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
import { reactive, ref, watch } from 'vue'

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

const formRef = ref(null)
const rules = {
  title: { required: true, message: '', trigger: ['input', 'blur'] },
  type: {
    required: true,
    type: 'number',
    message: '',
    trigger: ['change', 'blur']
  },
  description: { required: true, message: '', trigger: ['input', 'blur'] }
}

watch(() => props.ticket, (newTicket) => {
  if (newTicket) {
    form.id = newTicket.id
    form.title = newTicket.title || ''
    form.type = newTicket.type
    form.description = newTicket.description || ''
    form.location = newTicket.location || ''
    const planTime = newTicket.planTime ? new Date(newTicket.planTime).getTime() : null
    form.planTime = Number.isNaN(planTime) ? null : planTime
    formRef.value?.restoreValidation()
  }
}, { immediate: true })

function handleSubmit() {
  formRef.value?.validate((errors) => {
    if (errors) return
    emit('submit', {
      id: form.id,
      title: form.title,
      type: form.type,
      description: form.description,
      location: form.location || undefined,
      planTime: form.planTime || undefined
    })
  })
}
</script>
