<template>
  <AppPage>
    <div class="ticket-detail-page">
      <div v-if="loading" class="loading-container">
        <n-spin size="large" />
      </div>

      <template v-else-if="ticket">
        <section class="detail-hero">
          <div class="hero-title-row">
            <n-icon size="28">
              <Icon icon="mdi:file-document-outline" />
            </n-icon>
            <h1>工单详情</h1>
            <n-button secondary class="back-btn" @click="handleBack">
              <template #icon>
                <n-icon><Icon icon="mdi:chevron-left" /></n-icon>
              </template>
              返回
            </n-button>
          </div>
          <div class="hero-meta">
            <span>工单编号: {{ ticket.ticketNo }}</span>
            <span class="status-pill" :class="'status-' + ticket.status">{{ getStatusName(ticket.status) }}</span>
          </div>
        </section>

        <n-card :bordered="false" class="detail-card">
          <div class="section-title">{{ ticket.title }}</div>
          <div class="detail-grid">
            <div v-for="field in visibleDetailFields" :key="field.key" class="detail-item">
              <span class="detail-label">{{ field.label }}</span>
              <span
                v-if="field.tagClass"
                :class="field.tagClass"
              >
                {{ field.value }}
              </span>
              <span v-else class="detail-value">{{ field.value }}</span>
            </div>
          </div>
        </n-card>

        <n-card v-if="ticket.description" :bordered="false" class="detail-card">
          <div class="section-heading">
            <n-icon size="22">
              <Icon icon="mdi:file-document-edit-outline" />
            </n-icon>
            <span>问题描述</span>
          </div>
          <div class="description-box">
            {{ ticket.description }}
          </div>
        </n-card>

        <n-card v-if="ticket.status === 0 && ticket.completionNote" :bordered="false" class="detail-card">
          <div class="section-heading">
            <n-icon size="22">
              <Icon icon="mdi:reply-outline" />
            </n-icon>
            <span>完成回复/备注</span>
          </div>
          <div class="description-box completion-box">
            {{ ticket.completionNote }}
          </div>
        </n-card>

        <n-card v-if="ticket.attachments.length" :bordered="false" class="detail-card">
          <div class="section-heading">
            <n-icon size="22">
              <Icon icon="mdi:paperclip" />
            </n-icon>
            <span>附件图片</span>
          </div>
          <n-image-group>
            <n-space>
              <n-image
                v-for="(img, index) in ticket.attachments"
                :key="index"
                width="140"
                :src="getImageUrl(img)"
                @error="handleAttachmentError"
              />
            </n-space>
          </n-image-group>
        </n-card>
      </template>

      <n-result v-else status="404" title="工单不存在" description="请返回工单列表后重新选择。">
        <template #footer>
          <n-button type="primary" @click="handleBack">返回列表</n-button>
        </template>
      </n-result>
    </div>
  </AppPage>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import api from '@/api'
import { useUserStore } from '@/store'

defineOptions({ name: 'TicketDetail' })

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const loading = ref(false)
const ticket = ref(null)

const visibleDetailFields = computed(() => {
  if (!ticket.value) return []
  const fields = [
    { key: 'ticket_no', label: '工单编号', value: ticket.value.ticketNo },
    { key: 'title', label: '工单标题', value: ticket.value.title },
    { key: 'status', label: '工单状态', value: getStatusName(ticket.value.status), tagClass: `status-pill status-${ticket.value.status}` },
    { key: 'type', label: '工单类型', value: getTypeName(ticket.value.type), tagClass: `type-pill type-${ticket.value.type}` },
    { key: 'creator_name', label: '创建人', value: ticket.value.creatorName || ticket.value.customerName },
    { key: 'assignee_name', label: '处理人', value: ticket.value.assigneeName || ticket.value.operatorName },
    { key: 'location', label: '地点', value: ticket.value.location },
    { key: 'start_time', label: getStartTimeLabel(ticket.value.type), value: ticket.value.startTime },
    { key: 'end_time', label: getEndTimeLabel(ticket.value.type), value: ticket.value.completeTime },
    { key: 'created_at', label: '创建时间', value: ticket.value.createTime },
    { key: 'updated_at', label: '更新时间', value: ticket.value.updateTime },
  ]
  return fields.filter((field) => hasValue(field.value))
})

function formatTicket(data) {
  return {
    id: data.id,
    ticketNo: data.ticket_no,
    title: data.title || '未命名工单',
    type: Number(data.type ?? 0),
    status: Number(data.status ?? 2),
    customerId: data.user_id,
    creatorName: data.creator_name,
    assigneeName: data.assignee_name,
    assigneeId: data.assignee_id,
    customerName: data.creator_name || userStore.name,
    operatorName: data.assignee_id ? `处理人${data.assignee_id}` : null,
    description: data.desc,
    createTime: formatTimeToMinute(data.created_at),
    startTime: formatTimeToMinute(data.start_time),
    completeTime: formatTimeToMinute(data.end_time),
    updateTime: shouldShowUpdatedAt(data.updated_at, data.created_at) ? formatTimeToMinute(data.updated_at) : null,
    location: data.location,
    completionNote: data.completion_note || '',
    attachmentUrl: data.attachment_url,
    attachments: parseAttachmentUrls(data),
    attachmentUrlDisplay: parseAttachmentUrls(data).join('\n')
  }
}

function parseAttachmentUrls(data) {
  if (Array.isArray(data.attachment_urls)) return data.attachment_urls.filter(Boolean)
  if (!data.attachment_url) return []
  try {
    const parsed = JSON.parse(data.attachment_url)
    if (Array.isArray(parsed)) return parsed.filter(Boolean)
  } catch (error) {
    return [data.attachment_url]
  }
  return [data.attachment_url]
}

function hasValue(value) {
  if (value === null || value === undefined) return false
  if (typeof value === 'string') return value.trim() !== ''
  if (Array.isArray(value)) return value.length > 0
  return true
}

function formatTimeToMinute(value) {
  if (!hasValue(value)) return value
  return String(value).slice(0, 16)
}

function shouldShowUpdatedAt(updatedAt, createdAt) {
  if (!hasValue(updatedAt)) return false
  if (!hasValue(createdAt)) return true
  if (updatedAt === createdAt) return false

  const updatedTime = new Date(updatedAt).getTime()
  const createdTime = new Date(createdAt).getTime()
  if (Number.isNaN(updatedTime) || Number.isNaN(createdTime)) return true

  return updatedTime !== createdTime
}

async function loadTicket() {
  const ticketId = route.query.ticket_id
  if (!ticketId) {
    ticket.value = null
    return
  }

  loading.value = true
  try {
    const result = await api.ticketApi.get({ ticket_id: ticketId })
    if (result.code === 200 && result.data) {
      ticket.value = formatTicket(result.data)
    } else {
      ticket.value = null
      window.$message?.error(result.msg || '工单加载失败')
    }
  } catch (error) {
    ticket.value = null
    window.$message?.error('工单加载失败')
  } finally {
    loading.value = false
  }
}

function handleBack() {
  router.push('/ticket')
}

function getStatusName(status) {
  const map = { 0: '已完成', 1: '进行中', 2: '未开始', 3: '已关闭' }
  return map[status] || '未知'
}

function getTypeName(type) {
  const map = { 0: '故障工单', 1: '服务请求工单', 2: '维护工单', 3: '维护工单' }
  return map[type] || '未知'
}

function getStartTimeLabel(type) {
  const map = { 0: '故障时间', 2: '维护开始时间', 3: '维护开始时间' }
  return map[type] || '计划开始时间'
}

function getEndTimeLabel(type) {
  const map = { 2: '维护结束时间', 3: '维护结束时间' }
  return map[type] || '完成时间'
}

function getImageUrl(img) {
  if (!img) return ''
  if (img.startsWith('http://') || img.startsWith('https://') || img.startsWith('/') || img.startsWith('data:')) return img
  return ''
}

function handleAttachmentError() {
  window.$message?.warning('附件图片不存在或已失效')
}

onMounted(loadTicket)
</script>

<style scoped>
.ticket-detail-page {
  min-height: calc(100vh - 92px);
  padding: 24px;
  background: #eef3fb;
}

.loading-container {
  display: flex;
  justify-content: center;
  padding: 80px 0;
}

.detail-hero,
.detail-card {
  max-width: 1040px;
  margin: 0 auto;
}

.detail-hero {
  padding: 34px;
  color: #fff;
  border-radius: 8px;
  background: linear-gradient(135deg, #5f7fee 0%, #7a4dae 100%);
  box-shadow: 0 14px 34px rgb(31 41 55 / 14%);
}

.hero-title-row {
  display: flex;
  align-items: center;
  gap: 14px;
}

.hero-title-row h1 {
  margin: 0;
  font-size: 30px;
  font-weight: 700;
  letter-spacing: 0;
}

.back-btn {
  margin-left: auto;
  color: #fff;
  border-color: rgb(255 255 255 / 35%);
}

.hero-meta {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 24px;
  font-size: 16px;
  font-weight: 700;
}

.hero-meta > span:first-child {
  padding: 8px 14px;
  border-radius: 8px;
  background: rgb(255 255 255 / 18%);
}

.detail-card {
  margin-top: 24px;
  border-radius: 8px;
  box-shadow: 0 10px 28px rgb(31 41 55 / 8%);
}

.section-title {
  padding-bottom: 16px;
  margin-bottom: 22px;
  color: #5f7fee;
  font-size: 24px;
  font-weight: 700;
  border-bottom: 2px solid #6e85f3;
}

.section-heading {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-bottom: 16px;
  margin-bottom: 20px;
  color: #5f7fee;
  font-size: 22px;
  font-weight: 700;
  border-bottom: 2px solid #6e85f3;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 24px 48px;
}

.detail-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.detail-label {
  color: #6b7280;
  font-size: 14px;
  font-weight: 700;
}

.detail-value {
  color: #1f2937;
  font-size: 16px;
  font-weight: 700;
  word-break: break-word;
}

.description-box {
  min-height: 180px;
  padding: 22px;
  color: #374151;
  font-size: 15px;
  line-height: 1.8;
  white-space: pre-wrap;
  border-left: 4px solid #667df0;
  background: #f8fafc;
  border-radius: 8px;
}

.status-pill,
.type-pill {
  display: inline-flex;
  width: fit-content;
  align-items: center;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 700;
}

.status-0 {
  color: #237804;
  background: #f6ffed;
}

.status-1 {
  color: #ad4e00;
  background: #fff7e6;
}

.status-2 {
  color: #595959;
  background: #f5f5f5;
}

.status-3 {
  color: #a8071a;
  background: #fff1f0;
}

.type-0 {
  color: #a8071a;
  background: #fff1f0;
}

.type-1 {
  color: #0958d9;
  background: #e6f4ff;
}

.type-2 {
  color: #237804;
  background: #f6ffed;
}

.type-3 {
  color: #237804;
  background: #f6ffed;
}

@media (max-width: 900px) {
  .detail-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .ticket-detail-page {
    padding: 12px;
  }

  .detail-hero {
    padding: 24px;
  }

  .hero-title-row h1 {
    font-size: 24px;
  }

  .hero-meta,
  .hero-title-row {
    flex-wrap: wrap;
  }

  .back-btn {
    width: 100%;
    margin-left: 0;
  }

  .detail-grid {
    grid-template-columns: 1fr;
  }
}

html.dark .ticket-detail-page {
  background: #101827;
}

html.dark .description-box {
  color: #d1d5db;
  background: #111827;
}
</style>
