<template>
  <AppPage>
    <div class="edit-ticket-page">
      <div v-if="loading" class="loading-container">
        <n-spin size="large" />
      </div>

      <n-card v-else-if="ticketLoaded" :bordered="false" class="edit-ticket-card" content-style="padding: 0">
        <div class="edit-ticket-header">
          <div class="header-title">
            <n-icon size="28">
              <Icon icon="mdi:file-document-edit-outline" />
            </n-icon>
            <span>编辑工单</span>
          </div>
          <n-button secondary class="back-btn" @click="handleCancel">
            <template #icon>
              <n-icon><Icon icon="mdi:chevron-left" /></n-icon>
            </template>
            返回
          </n-button>
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
            <n-input v-model:value="form.title" placeholder="请输入工单标题" />
          </n-form-item>

          <n-form-item label="工单状态">
            <n-select
              v-model:value="form.status"
              :options="statusOptions"
              disabled
              placeholder="工单状态"
            />
          </n-form-item>

          <n-form-item label="工单描述" path="description" required>
            <n-input
              v-model:value="form.description"
              type="textarea"
              placeholder="请输入工单描述"
              :rows="6"
            />
          </n-form-item>

          <template v-if="showLocationField">
            <n-form-item label="地点" path="location">
              <n-input v-model:value="form.location" placeholder="请输入地点" />
            </n-form-item>
          </template>

          <template v-if="showSingleTime">
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

          <template v-if="showRangeTime">
            <n-form-item :label="timeFieldLabel" path="timeRange">
              <n-date-picker
                v-model:value="form.timeRange"
                type="datetimerange"
                format="yyyy-MM-dd HH:mm"
                :time-picker-props="{ format: 'HH:mm' }"
                clearable
                :placeholder="`请选择${timeFieldLabel}`"
                style="width: 100%"
              />
            </n-form-item>
          </template>

          <n-form-item label="附件图片">
            <n-upload
              v-model:file-list="uploadedFiles"
              multiple
              directory-dnd
              :max="5"
              accept="image/*"
              list-type="image-card"
              @change="handleUploadChange"
            />
          </n-form-item>

          <div class="form-actions">
            <CButton
              show-cancel
              show-save
              :save-loading="submitting"
              @cancel="handleCancel"
              @save="handleSubmit"
            />
          </div>
        </n-form>
      </n-card>

      <n-result v-else status="404" title="工单不存在" description="请返回工单列表后重新选择。">
        <template #footer>
          <n-button type="primary" @click="handleCancel">返回列表</n-button>
        </template>
      </n-result>
    </div>
  </AppPage>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import api from '@/api'
import CButton from '@/components/public/CButton.vue'
import { fileToBase64Payload } from '../utils/fileBase64'

defineOptions({ name: 'EditTicket' })

const route = useRoute()
const router = useRouter()

const formRef = ref(null)
const loading = ref(false)
const submitting = ref(false)
const ticketLoaded = ref(false)
const uploadedFiles = ref([])

const form = reactive({
  id: null,
  ticketNo: '',
  title: '',
  type: null,
  status: null,
  description: '',
  location: '',
  planTime: null,
  timeRange: null
})

const statusOptions = [
  { label: '已完成', value: 0 },
  { label: '进行中', value: 1 },
  { label: '未开始', value: 2 },
  { label: '已关闭', value: 3 }
]

const isMaintenanceType = computed(() => form.type === 2 || form.type === 3)
const showLocationField = computed(() => form.type === 0 || isMaintenanceType.value)
const showSingleTime = computed(() => form.type === 0)
const showRangeTime = computed(() => isMaintenanceType.value)
const timeFieldLabel = computed(() => {
  if (form.type === 0) return '故障时间'
  if (isMaintenanceType.value) return '维护时间'
  return '计划时间'
})

const rules = {
  title: { required: true, message: '请输入工单标题', trigger: ['input', 'blur'] },
  description: { required: true, message: '请输入工单描述', trigger: ['input', 'blur'] }
}

watch(() => form.type, (type, oldType) => {
  if (oldType === undefined || oldType === null) return
  if (type !== 0 && type !== 2 && type !== 3) {
    form.location = ''
  }
  form.planTime = type === 0 ? form.planTime : null
  form.timeRange = type === 2 || type === 3 ? form.timeRange : null
})

async function loadTicket() {
  const ticketId = route.query.ticket_id
  if (!ticketId) {
    ticketLoaded.value = false
    return
  }

  loading.value = true
  try {
    const result = await api.ticketApi.get({ ticket_id: ticketId })
    if (result.code === 200 && result.data) {
      fillForm(result.data)
      ticketLoaded.value = true
    } else {
      ticketLoaded.value = false
      window.$message?.error(result.msg || '工单加载失败')
    }
  } catch (error) {
    ticketLoaded.value = false
    window.$message?.error('工单加载失败')
  } finally {
    loading.value = false
  }
}

function fillForm(ticket) {
  form.id = ticket.id
  form.ticketNo = ticket.ticket_no || ''
  form.title = ticket.title || ''
  form.type = Number(ticket.type ?? 0)
  form.status = Number(ticket.status ?? 2)
  form.description = ticket.desc || ''
  form.location = ticket.location || ''
  const planTime = ticket.start_time ? new Date(ticket.start_time).getTime() : null
  const endTime = ticket.end_time ? new Date(ticket.end_time).getTime() : null
  form.planTime = form.type === 0 && !Number.isNaN(planTime) ? planTime : null
  form.timeRange = (form.type === 2 || form.type === 3) && !Number.isNaN(planTime) && !Number.isNaN(endTime)
    ? [planTime, endTime]
    : null
  uploadedFiles.value = parseAttachmentUrls(ticket).map((url, index) => ({
    id: `existing-${index}`,
    name: getFileName(url, index),
    status: 'finished',
    url
  }))
  formRef.value?.restoreValidation()
}

function handleUploadChange(options) {
  uploadedFiles.value = options.fileList
}

function parseAttachmentUrls(ticket) {
  if (Array.isArray(ticket.attachment_urls)) return ticket.attachment_urls.filter(Boolean)
  if (!ticket.attachment_url) return []
  try {
    const parsed = JSON.parse(ticket.attachment_url)
    if (Array.isArray(parsed)) return parsed.filter(Boolean)
  } catch (error) {
    return [ticket.attachment_url]
  }
  return [ticket.attachment_url]
}

function getFileName(url, index) {
  const name = String(url || '').split('/').filter(Boolean).pop()
  return name || `附件${index + 1}`
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
    const attachmentUrls = await resolveAttachmentUrls()
    const result = await api.ticketApi.update({
      id: form.id,
      ticket_no: form.ticketNo,
      title: form.title,
      desc: form.description,
      location: showLocationField.value ? form.location || undefined : undefined,
      start_time: getSubmitStartTime(),
      end_time: getSubmitEndTime(),
      attachment_url: JSON.stringify(attachmentUrls)
    })

    if (result.code === 200) {
      window.$message?.success('编辑成功')
      router.push({ path: '/ticket/detail', query: { ticket_id: form.id } })
    } else {
      window.$message?.error(result.msg || '编辑失败')
    }
  } catch (error) {
    window.$message?.error(error?.message || '编辑失败')
  } finally {
    submitting.value = false
  }
}

function getSubmitStartTime() {
  if (showSingleTime.value && form.planTime) return formatTimeToMinute(form.planTime)
  if (showRangeTime.value && form.timeRange?.[0]) return formatTimeToMinute(form.timeRange[0])
  return undefined
}

function getSubmitEndTime() {
  if (showRangeTime.value && form.timeRange?.[1]) return formatTimeToMinute(form.timeRange[1])
  return undefined
}

async function resolveAttachmentUrls() {
  const urls = []
  for (const item of uploadedFiles.value) {
    if (item.url) {
      urls.push(item.url)
      continue
    }
    if (!item.file) continue
    const uploadRes = await api.ticketApi.upload(await fileToBase64Payload(item.file), { ticket_id: form.id })
    if (uploadRes.code !== 200) {
      throw new Error(uploadRes.msg || '附件上传失败')
    }
    if (uploadRes.data?.url) {
      urls.push(uploadRes.data.url)
    }
  }
  return urls
}

onMounted(loadTicket)
</script>

<style scoped>
.edit-ticket-page {
  min-height: calc(100vh - 92px);
  padding: 24px;
  background: #eef3fb;
}

.loading-container {
  display: flex;
  justify-content: center;
  padding: 80px 0;
}

.edit-ticket-card {
  max-width: 920px;
  margin: 0 auto;
  overflow: hidden;
  border-radius: 8px;
  box-shadow: 0 14px 40px rgb(31 41 55 / 10%);
}

.edit-ticket-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-height: 90px;
  padding: 0 36px;
  color: #fff;
  background: linear-gradient(135deg, #5f7fee 0%, #7a4dae 100%);
}

.header-title {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 26px;
  font-weight: 700;
}

.back-btn {
  color: #fff;
  border-color: rgb(255 255 255 / 35%);
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

.form-actions {
  display: flex;
  justify-content: flex-end;
  padding-top: 4px;
}

@media (max-width: 768px) {
  .edit-ticket-page {
    padding: 12px;
  }

  .edit-ticket-header {
    align-items: flex-start;
    flex-direction: column;
    padding: 22px;
  }

  .header-title {
    font-size: 22px;
  }

  .back-btn {
    width: 100%;
  }

  .ticket-form {
    padding: 20px;
  }
}

html.dark .edit-ticket-page {
  background: #101827;
}

html.dark .ticket-form {
  background: #18181c;
}

html.dark .ticket-form :deep(.n-form-item-label) {
  color: #e5e7eb;
}
</style>
