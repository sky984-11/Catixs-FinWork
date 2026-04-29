<template>
  <n-modal :show="visible" preset="card" title="创建工单" style="width: 600px" @update:show="$emit('update:visible', $event)">
    <n-form :model="form" label-placement="top">
      <n-form-item label="工单标题" required>
        <n-input v-model:value="form.title" placeholder="请输入工单标题" />
      </n-form-item>
      <n-form-item label="工单类型" required>
        <n-select v-model:value="form.type" :options="typeOptions" placeholder="请选择工单类型" @update:value="handleTypeChange" />
      </n-form-item>
      <n-form-item label="工单描述" required>
        <n-input v-model:value="form.description" type="textarea" placeholder="请输入工单描述" :rows="4" />
      </n-form-item>
      <n-form-item v-show="isAdminOrNoc" label="用户">
        <n-select v-model:value="form.customerId" :options="customerOptions" placeholder="请选择用户" />
      </n-form-item>
      <n-form-item label="附件图片">
        <n-upload
          :max="3"
          accept="image/*"
          list-type="image-card"
          @change="handleUploadChange"
        >
          <n-button size="small">上传图片</n-button>
        </n-upload>
      </n-form-item>
    </n-form>
    <template #footer>
      <n-space justify="end">
        <n-button @click="$emit('update:visible', false)">取消</n-button>
        <n-button type="primary" @click="handleSubmit">提交</n-button>
      </n-space>
    </template>
  </n-modal>
</template>

<script setup>
import { reactive } from 'vue'

const emit = defineEmits(['update:visible', 'submit', 'typeChange'])

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  isAdminOrNoc: {
    type: Boolean,
    default: false
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

const form = reactive({
  title: '',
  type: null,
  description: '',
  customerId: null
})

const uploadedFiles = []

function handleTypeChange(type) {
  if (type !== null) {
    emit('typeChange', type)
  }
}

function handleUploadChange(options) {
  uploadedFiles.length = 0
  uploadedFiles.push(...options.fileList)
}

function handleSubmit() {
  if (!form.title || !form.type || !form.description) {
    window.$message?.warning('请填写必填项')
    return
  }
  emit('submit', { ...form, attachments: uploadedFiles.map(file => file.name) })
}
</script>

<style scoped>
/* Dark theme styles */
[data-theme='dark'] .n-form-item-label {
  color: var(--n-text-color);
}

[data-theme='dark'] .n-input,
[data-theme='dark'] .n-select,
[data-theme='dark'] .n-date-picker {
  background-color: var(--n-input-color);
  border-color: var(--n-border-color);
  color: var(--n-text-color);
}
</style>