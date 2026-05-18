<template>
  <n-modal
    :show="visible"
    preset="card"
    title="创建工单"
    style="width: 600px"
    @update:show="$emit('update:visible', $event)"
  >
    <n-form
      ref="formRef"
      class="ticket-form"
      :model="form"
      :rules="rules"
      label-placement="top"
      :show-feedback="false"
    >
      <n-form-item label="工单标题" path="title" required>
        <n-input v-model:value="form.title" placeholder="请输入工单标题" />
      </n-form-item>
      <n-form-item class="type-form-item" path="type" required>
        <template #label>
          <span class="type-label">
            工单类型
            <n-tooltip trigger="hover" placement="right">
              <template #trigger>
                <span class="type-help" @click.stop>?</span>
              </template>
              <div class="type-help-content">
                <p>故障工单：链路、服务器、网络异常</p>
                <p>服务请求：带宽、资源、权限类需求</p>
                <p>维护工单：巡检、升级、割接与资产维护</p>
              </div>
            </n-tooltip>
          </span>
        </template>
        <n-select v-model:value="form.type" :options="typeOptions" placeholder="请选择工单类型" />
      </n-form-item>
      <template v-if="showLocationTime">
        <n-form-item label="地点" path="location">
          <n-input v-model:value="form.location" placeholder="请输入地点" />
        </n-form-item>
        <n-form-item :label="timeFieldLabel" path="planTime">
          <n-date-picker
            v-model:value="form.planTime"
            type="datetime"
            format="yyyy-MM-dd HH:mm"
            :time-picker-props="{ format: 'HH:mm' }"
            :placeholder="`请选择${timeFieldLabel}`"
            style="width: 100%"
          />
        </n-form-item>
      </template>
      <n-form-item label="工单描述" path="description" required>
        <TicketDescriptionInput v-model:value="form.description" :type="form.type" />
      </n-form-item>
      <n-form-item label="附件图片">
        <n-upload
          v-model:file-list="uploadedFiles"
          multiple
          directory-dnd
          :max="5"
          accept="image/*"
          @change="handleUploadChange"
        >
          <n-upload-dragger>
            <div class="upload-icon">
              <n-icon size="48" :depth="3">
                <Icon icon="mdi:archive-arrow-up-outline" />
              </n-icon>
            </div>
            <n-text class="upload-title"> 点击或者拖动图片到该区域上传 </n-text>
            <n-p depth="3" class="upload-tip"> 支持上传问题截图，请不要上传敏感数据。 </n-p>
          </n-upload-dragger>
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
import { Icon } from '@iconify/vue'
import TicketDescriptionInput from './TicketDescriptionInput.vue'
import { cleanupTicketDescriptionForSubmit } from '../utils/ticketDescriptionTemplates'

const emit = defineEmits(['update:visible', 'submit'])

const props = defineProps({
  visible: {
    type: Boolean,
    default: false,
  },
  typeOptions: {
    type: Array,
    default: () => [],
  },
})

const form = reactive({
  title: '',
  type: null,
  description: '',
  location: '',
  planTime: null,
})

const formRef = ref(null)
const uploadedFiles = ref([])
const showLocationTime = computed(() => form.type === 0 || form.type === 2 || form.type === 3)
const timeFieldLabel = computed(() => {
  if (form.type === 0) return '故障时间'
  if (form.type === 2 || form.type === 3) return '维护时间'
  return '计划时间'
})
const rules = {
  title: { required: true, message: '', trigger: ['input', 'blur'] },
  type: {
    required: true,
    type: 'number',
    message: '',
    trigger: ['change', 'blur'],
  },
  description: { required: true, message: '', trigger: ['input', 'blur'] },
}

watch(
  () => props.visible,
  (visible) => {
    if (visible) {
      resetForm()
    }
  }
)

watch(
  () => form.type,
  (type) => {
    form.location = ''
    form.planTime = type === 0 ? Date.now() : null
  }
)

function resetForm() {
  form.title = ''
  form.type = null
  form.description = ''
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
    const files = uploadedFiles.value.filter((f) => f.file).map((f) => f.file)
    emit('submit', {
      ...form,
      description: cleanupTicketDescriptionForSubmit(form.description),
      location: showLocationTime.value ? form.location : '',
      planTime: showLocationTime.value ? form.planTime : null,
      attachments: files,
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

.type-form-item :deep(.n-form-item-label__asterisk) {
  order: 2;
}

.type-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  order: 1;
}

.type-label :deep(.n-tooltip) {
  order: 3;
}

.type-help {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #e5e7eb;
  color: #6b7280;
  font-size: 12px;
  font-weight: 700;
  line-height: 1;
  cursor: help;
  user-select: none;
}

.type-help-content {
  max-width: 460px;
  line-height: 1.6;
}

.type-help-content p {
  margin: 6px 0 0;
}

.upload-icon {
  margin-bottom: 12px;
}

.upload-title {
  font-size: 16px;
}

.upload-tip {
  margin: 8px 0 0;
}
</style>
