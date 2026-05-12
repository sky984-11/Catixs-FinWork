<template>
  <n-modal :show="visible" preset="card" title="创建工单" style="width: 600px" @update:show="$emit('update:visible', $event)">
    <n-form ref="formRef" class="ticket-form" :model="form" :rules="rules" label-placement="top" :show-feedback="false">
      <n-form-item label="工单标题" path="title" required>
        <n-input v-model:value="form.title" placeholder="请输入工单标题" />
      </n-form-item>
      <n-form-item label="工单类型" path="type" required>
        <n-select v-model:value="form.type" :options="typeOptions" placeholder="请选择工单类型" />
      </n-form-item>
      <template v-if="showLocationTime">
        <n-form-item label="地点" path="location">
          <n-input v-model:value="form.location" placeholder="请输入地点" />
        </n-form-item>
        <n-form-item label="计划时间" path="planTime">
          <n-date-picker
            v-model:value="form.planTime"
            type="datetime"
            format="yyyy-MM-dd HH:mm"
            :time-picker-props="{ format: 'HH:mm' }"
            placeholder="请选择计划时间"
            style="width: 100%"
          />
        </n-form-item>
      </template>
      <n-form-item label="工单描述" path="description" required>
        <n-input v-model:value="form.description" type="textarea" placeholder="请输入工单描述" :rows="4" />
      </n-form-item>
      <n-form-item v-show="isAdminOrNoc" label="用户">
        <n-select v-model:value="form.customerId" :options="customerOptions" placeholder="请选择用户" />
      </n-form-item>
      <n-form-item label="附件图片">
        <n-upload
          v-model:file-list="uploadedFiles"
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
import { computed, reactive, ref, watch } from 'vue'

const emit = defineEmits(['update:visible', 'submit'])

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
  customerId: null,
  location: '',
  planTime: null
})

const formRef = ref(null)
const uploadedFiles = ref([])
const showLocationTime = computed(() => form.type === 0 || form.type === 3)

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

watch(() => props.visible, (visible) => {
  if (visible) {
    resetForm()
  }
})

watch(() => form.type, () => {
  form.location = ''
  form.planTime = null
})

function resetForm() {
  form.title = ''
  form.type = null
  form.description = ''
  form.customerId = null
  form.location = ''
  form.planTime = null
  uploadedFiles.value = []
  formRef.value?.restoreValidation()
}

function handleUploadChange(options) {
  uploadedFiles.value = options.fileList
}

function handleSubmit() {
  formRef.value?.validate((errors) => {
    if (errors) return
    // 传递 File 对象，供父组件上传到服务器
    const files = uploadedFiles.value.filter(f => f.file).map(f => f.file)
    emit('submit', {
      ...form,
      location: showLocationTime.value ? form.location : '',
      planTime: showLocationTime.value ? form.planTime : null,
      attachments: files
    })
  })
}
</script>

<style scoped>
.ticket-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.ticket-form :deep(.n-form-item) {
  margin-bottom: 0;
}

.ticket-form :deep(.n-form-item-label) {
  padding-bottom: 8px;
}
</style>
