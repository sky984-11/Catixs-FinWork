<template>
  <AppPage>
    <div class="create-ticket-page">
      <n-card :bordered="false" class="create-ticket-card" content-style="padding: 0">
        <div class="create-ticket-header">
          <n-icon size="28">
            <Icon icon="mdi:file-document-plus-outline" />
          </n-icon>
          <span>提交新工单</span>
        </div>

        <n-form
          ref="formRef"
          class="ticket-form"
          :model="form"
          :rules="rules"
          label-placement="top"
          :show-feedback="false"
        >
          <n-form-item label="工单标题" path="title" required>
            <n-input v-model:value="form.title" placeholder="请简要描述您遇到的问题" />
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
                    <p>故障工单：处理突发异常。如：网络中断、设备故障、服务不可用等。</p>
                    <p>服务请求：申请日常业务。如：开通专线、申请IP、带宽/端口扩容等。</p>
                    <p>变更工单：执行网络/系统变更。如：网络割接、设备升级、配置调整等。</p>
                    <p>维护工单：记录现场运维作业。如：机房施工、硬件维护等。</p>
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
            <n-input
              v-model:value="form.description"
              type="textarea"
              placeholder="请详细描述您遇到的问题或需要的帮助，支持粘贴图片"
              :rows="6"
            />
          </n-form-item>

          <n-form-item label="上传图片">
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
                  <n-icon size="52" :depth="3">
                    <Icon icon="mdi:cloud-upload-outline" />
                  </n-icon>
                </div>
                <n-text class="upload-title">点击或拖拽图片到此处上传</n-text>
                <n-p depth="3" class="upload-tip">支持 JPG、PNG、WebP 和 GIF 格式，单张图片最大 5MB。</n-p>
              </n-upload-dragger>
            </n-upload>
          </n-form-item>

          <div class="form-actions">
            <CButton
              show-cancel
              show-save
              save-text="提交"
              :save-loading="submitting"
              @cancel="handleCancel"
              @save="handleSubmit"
            />
          </div>
        </n-form>
      </n-card>
    </div>
  </AppPage>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { useUserStore } from '@/store'
import api from '@/api'
import CButton from '@/components/public/CButton.vue'

defineOptions({ name: 'CreateTicket' })

const router = useRouter()
const userStore = useUserStore()

const typeOptions = [
  { label: '故障工单', value: 0 },
  { label: '服务请求工单', value: 1 },
  { label: '变更工单', value: 2 },
  { label: '维护工单', value: 3 }
]

const formRef = ref(null)
const uploadedFiles = ref([])
const submitting = ref(false)

const form = reactive({
  title: '',
  type: null,
  description: '',
  location: '',
  planTime: null
})

const showLocationTime = computed(() => form.type === 0 || form.type === 3)
const timeFieldLabel = computed(() => {
  if (form.type === 0) return '故障时间'
  if (form.type === 3) return '维护时间'
  return '计划时间'
})

const rules = {
  title: { required: true, message: '请输入工单标题', trigger: ['input', 'blur'] },
  type: {
    required: true,
    type: 'number',
    message: '请选择工单类型',
    trigger: ['change', 'blur']
  },
  description: { required: true, message: '请输入工单描述', trigger: ['input', 'blur'] }
}

watch(() => form.type, (type) => {
  form.location = ''
  form.planTime = type === 0 ? Date.now() : null
})

function handleUploadChange(options) {
  uploadedFiles.value = options.fileList
}

function formatTimeToMinute(dateStr) {
  const date = new Date(dateStr)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  return `${year}-${month}-${day} ${hours}:${minutes}`
}

function handleCancel() {
  router.push('/ticket')
}

function handleSubmit() {
  formRef.value?.validate(async (errors) => {
    if (errors) return
    await submitTicket()
  })
}

async function submitTicket() {
  if (submitting.value) return
  submitting.value = true

  try {
    let attachmentUrl = undefined
    const files = uploadedFiles.value.filter(f => f.file).map(f => f.file)

    if (files.length > 0) {
      const uploadFormData = new FormData()
      uploadFormData.append('file', files[0])
      const uploadRes = await api.ticketApi.upload(uploadFormData)
      if (uploadRes.code === 200) {
        attachmentUrl = uploadRes.data.url
      } else {
        window.$message?.warning(uploadRes.msg || '附件上传失败')
        return
      }
    }

    const result = await api.ticketApi.create({
      title: form.title,
      type: form.type,
      user_id: userStore.userId,
      desc: form.description,
      location: showLocationTime.value ? form.location || undefined : undefined,
      start_time: showLocationTime.value && form.planTime ? formatTimeToMinute(form.planTime) : undefined,
      attachment_url: attachmentUrl
    })

    if (result.code === 200) {
      window.$message?.success('创建成功')
      router.push('/ticket')
    } else {
      window.$message?.error(result.msg || '创建失败')
    }
  } catch (error) {
    window.$message?.error('创建失败')
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.create-ticket-page {
  min-height: calc(100vh - 92px);
  padding: 24px;
  background: #eef3fb;
}

.create-ticket-card {
  max-width: 920px;
  margin: 0 auto;
  overflow: hidden;
  border-radius: 8px;
  box-shadow: 0 14px 40px rgb(31 41 55 / 10%);
}

.create-ticket-header {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  min-height: 90px;
  color: #fff;
  font-size: 26px;
  font-weight: 700;
  background: linear-gradient(135deg, #5f7fee 0%, #7a4dae 100%);
}

.ticket-form {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 36px;
  background: #fff;
}

.ticket-form :deep(.n-form-item) {
  margin-bottom: 0;
}

.ticket-form :deep(.n-form-item-label) {
  padding-bottom: 8px;
  color: #1f2937;
  font-weight: 700;
}

.ticket-form :deep(.n-input),
.ticket-form :deep(.n-base-selection) {
  --n-border-radius: 12px;
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
  margin-bottom: 14px;
  color: #5f7fee;
}

.upload-title {
  font-size: 16px;
  font-weight: 700;
}

.upload-tip {
  margin: 8px 0 0;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  padding-top: 4px;
}

@media (max-width: 768px) {
  .create-ticket-page {
    padding: 12px;
  }

  .create-ticket-header {
    min-height: 76px;
    font-size: 22px;
  }

  .ticket-form {
    padding: 20px;
  }
}

html.dark .create-ticket-page {
  background: #101827;
}

html.dark .ticket-form {
  background: #18181c;
}

html.dark .ticket-form :deep(.n-form-item-label) {
  color: #e5e7eb;
}
</style>
