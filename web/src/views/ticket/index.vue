<template>
  <AppPage>
    <div class="ticket-page">
      
      <n-card :bordered="false" class="filter-card" rounded-10>
        <TicketFilter
          :filters="filters"
          :is-admin-or-noc="isAdminOrNoc"
          :status-options="statusOptions"
          :type-options="typeOptions"
          :customer-options="customerOptions"
          @search="handleSearch"
          @reset="handleReset"
        />
      </n-card>

      
      <n-card title=" " class="ticket-list-container" :segmented="true" rounded-10>
        <template #header-extra>
          <n-button secondary type="primary" style="border-radius: 12px" @click="handleCreate">新增工单</n-button>
        </template>

        <div v-if="loading" class="loading-container">
          <n-spin size="large" />
        </div>

        <n-infinite-scroll
          v-else
          class="scroll-container"
          :distance="100"
          @load="handleInfiniteLoad"
        >
          <div class="cards-wrapper">
            <TicketCard
              v-for="ticket in ticketList"
              :key="ticket.id"
              :ticket="ticket"
              :is-admin-or-noc="isAdminOrNoc"
              @detail="handleView"
              @edit="handleEdit"
              @send="handleSend"
              @status-change="handleStatusChange"
              @delete="handleDelete"
            />
          </div>
          <div v-if="loadingMore" class="loading-more">
            <n-spin size="small" />
            <span>加载中...</span>
          </div>
          <div v-if="noMore && ticketList.length > 0" class="no-more">
            已加载全部
          </div>
        </n-infinite-scroll>
      </n-card>

      <n-modal v-model:show="sendModalVisible" preset="card" title="发送通知" style="width: 600px">
        <n-transfer
          v-model:value="sendSelectedUsers"
          :options="userOptions"
          :titles="['可选用户', '已选用户']"
          filterable
          search-placeholder="搜索用户"
        />
        <template #footer>
          <div class="send-modal-footer">
            <CButton
              show-cancel
              show-send
              :send-loading="sendSubmitting"
              @cancel="handleCancelSend"
              @send="handleConfirmSend"
            />
          </div>
        </template>
      </n-modal>

      <n-modal v-model:show="completionModalVisible" preset="card" title="完成工单" style="width: 560px">
        <n-input
          v-model:value="completionNote"
          type="textarea"
          placeholder="请输入处理回复或备注原因"
          :autosize="{ minRows: 4, maxRows: 8 }"
        />
        <template #footer>
          <div class="completion-modal-footer">
            <n-button @click="handleCancelCompletion">取消</n-button>
            <n-button type="primary" :loading="completionSubmitting" @click="handleConfirmCompletion">
              确认完成
            </n-button>
          </div>
        </template>
      </n-modal>
    </div>
  </AppPage>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/store'
import api from '@/api'
import TicketFilter from './components/TicketFilter.vue'
import TicketCard from './components/TicketCard.vue'
import CButton from '@/components/public/CButton.vue'

defineOptions({ name: 'MyTickets' })

const userStore = useUserStore()
const router = useRouter()

const loading = ref(false)
const sendModalVisible = ref(false)
const sendTicket = ref(null)
const sendSubmitting = ref(false)
const completionModalVisible = ref(false)
const completionSubmitting = ref(false)
const completionNote = ref('')
const pendingCompletionTicket = ref(null)

const sendSelectedUsers = ref([])
const userOptions = ref([])
const customerOptions = ref([{ label: '全部用户', value: null }])

const isAdminOrNoc = computed(() => {
  if (userStore.isSuperUser) return true
  const accountNames = [
    userStore.name,
    userStore.userInfo?.alias,
    String(userStore.email || '').split('@')[0],
  ].map(value => String(value || '').trim().toLowerCase())
  if (accountNames.includes('noc')) return true
  const roles = userStore.role || []
  const result = roles.some(role => {
    const roleName = String(typeof role === 'string' ? role : role?.name || '').trim().toLowerCase()
    return ['admin', 'noc', '管理员'].includes(roleName)
  })
  return result
})

const filters = reactive({
  title: '',
  status: null,
  type: null,
  customerId: null,
  dateRange: null
})

const statusOptions = [
  { label: '全部状态', value: null },
  { label: '已完成', value: 0 },
  { label: '进行中', value: 1 },
  { label: '未开始', value: 2 }
]

const typeOptions = [
  { label: '故障工单', value: 0 },
  { label: '服务请求工单', value: 1 },
  { label: '维护工单', value: 2 }
]

const ticketList = ref([])
const loadingMore = ref(false)
const noMore = ref(false)

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0
})

async function loadData(reset = false) {
  if (reset) {
    loading.value = true
    pagination.page = 1
    noMore.value = false
    ticketList.value = []
  } else {
    loadingMore.value = true
    pagination.page++
  }

  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      title: filters.title || undefined,
      status: filters.status !== null ? filters.status : undefined,
      type: filters.type !== null ? filters.type : undefined,
      user_id: filters.customerId !== null && isAdminOrNoc.value ? filters.customerId : undefined
    }

    const result = await api.ticketApi.list(params)
    
    if (result.code === 200) {
      pagination.total = result.total
      
      const formatTickets = result.data.map(ticket => ({
        id: ticket.id,
        ticketNo: ticket.ticket_no,
        title: ticket.title,
        type: ticket.type,
        status: ticket.status,
        customerId: ticket.user_id,
        creatorName: ticket.creator_name,
        assigneeName: ticket.assignee_name,
        assigneeId: ticket.assignee_id,
        customerName: ticket.user_id ? customerOptions.value.find(c => c.value === ticket.user_id)?.label || '未知用户' : userStore.name,
        operatorName: ticket.assignee_id ? `处理人${ticket.assignee_id}` : null,
        description: ticket.desc,
        createTime: formatTimeToMinute(ticket.created_at),
        startTime: formatTimeToMinute(ticket.start_time),
        completeTime: formatTimeToMinute(ticket.end_time),
        updateTime: formatTimeToMinute(ticket.updated_at),
        location: ticket.location,
        planTime: formatTimeToMinute(ticket.start_time),
        completionNote: ticket.completion_note || '',
        attachments: parseAttachmentUrls(ticket)
      }))

      if (reset) {
        ticketList.value = formatTickets
        loading.value = false
      } else {
        ticketList.value = [...ticketList.value, ...formatTickets]
        loadingMore.value = false
      }

      if (pagination.page * pagination.pageSize >= pagination.total) {
        noMore.value = true
      }
    } else {
      window.$message?.error(result.msg || '加载失败')
      if (reset) loading.value = false
      else loadingMore.value = false
    }
  } catch (error) {
    window.$message?.error('加载失败')
    if (reset) loading.value = false
    else loadingMore.value = false
  }
}

function formatTimeToMinute(value) {
  if (value === null || value === undefined || value === '') return value
  return String(value).slice(0, 16)
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

function handleInfiniteLoad(callback) {
  if (noMore.value || loadingMore.value) {
    callback()
    return
  }
  
  loadData(false).then(() => {
    callback()
  })
}

function handleSearch() {
  loadData(true)
}

function handleReset() {
  filters.title = ''
  filters.status = null
  filters.type = null
  filters.customerId = null
  filters.dateRange = null
  loadData(true)
}

function handleCreate() {
  router.push('/ticket/create')
}

function handleView(ticket) {
  if (!isAdminOrNoc.value && String(ticket.customerId) !== String(userStore.userId || 1)) {
    window.$message?.error('无权限查看该工单')
    return
  }
  router.push({ path: '/ticket/detail', query: { ticket_id: ticket.id } })
}

function handleEdit(ticket) {
  if (!isAdminOrNoc.value && String(ticket.customerId) !== String(userStore.userId || 1)) {
    window.$message?.error('无权限编辑该工单')
    return
  }
  router.push({ path: '/ticket/edit', query: { ticket_id: ticket.id } })
}

function handleSend(ticket) {
  sendTicket.value = ticket
  sendSelectedUsers.value = []
  sendSubmitting.value = false
  sendModalVisible.value = true
}

function handleCancelSend() {
  sendModalVisible.value = false
  sendSelectedUsers.value = []
  sendTicket.value = null
  sendSubmitting.value = false
}

async function handleConfirmSend() {
  if (sendSubmitting.value) return

  if (sendSelectedUsers.value.length === 0) {
    window.$message?.warning('请至少选择一个用户')
    return
  }

  sendSubmitting.value = true
  try {
    const result = await api.ticketApi.sendEmail({
      ticket_id: sendTicket.value.id,
      user_ids: sendSelectedUsers.value
    })

    if (result.code === 200) {
      const sentEmails = result.data?.sent_emails || []
      const failedEmails = result.data?.failed_emails || []
      const message = failedEmails.length
        ? `已发送 ${sentEmails.length} 个，失败 ${failedEmails.length} 个`
        : `已向 ${sentEmails.length || sendSelectedUsers.value.length} 个用户发送通知`
      window.$message?.success(message)
      sendModalVisible.value = false
      sendSelectedUsers.value = []
      sendTicket.value = null
    } else {
      window.$message?.error(result.msg || '发送失败')
    }
  } catch (error) {
    window.$message?.error(error?.response?.data?.msg || '发送失败')
  } finally {
    sendSubmitting.value = false
  }
}

async function handleStatusChange({ ticket, newStatus }) {
  if (!isAdminOrNoc.value && String(ticket.customerId) !== String(userStore.userId || 1)) {
    window.$message?.error('无权限更改该工单状态')
    return
  }

  if (![0, 1, 2, 3].includes(newStatus)) {
    window.$message?.error('无效的状态值')
    return
  }

  if (newStatus === 0) {
    pendingCompletionTicket.value = ticket
    completionNote.value = ticket.completionNote || ''
    completionSubmitting.value = false
    completionModalVisible.value = true
    return
  }

  try {
    const result = await api.ticketApi.update({ id: ticket.id, ticket_no: ticket.ticketNo, status: newStatus })
    
    if (result.code === 200) {
      const statusNames = { 0: '已完成', 1: '进行中', 2: '未开始', 3: '已关闭' }
      window.$message?.success(`工单状态已更新为：${statusNames[newStatus]}`)
      
      loadData(true)
    } else {
      window.$message?.error(result.msg || '更新失败')
    }
  } catch (error) {
    window.$message?.error('更新失败')
  }
}

function handleCancelCompletion() {
  completionModalVisible.value = false
  completionSubmitting.value = false
  completionNote.value = ''
  pendingCompletionTicket.value = null
}

async function handleConfirmCompletion() {
  if (!pendingCompletionTicket.value || completionSubmitting.value) return

  completionSubmitting.value = true
  const ticket = pendingCompletionTicket.value
  try {
    const result = await api.ticketApi.update({
      id: ticket.id,
      ticket_no: ticket.ticketNo,
      status: 0,
      completion_note: completionNote.value.trim()
    })

    if (result.code === 200) {
      window.$message?.success('工单状态已更新为：已完成')
      handleCancelCompletion()
      loadData(true)
    } else {
      window.$message?.error(result.msg || '更新失败')
    }
  } catch (error) {
    window.$message?.error('更新失败')
  } finally {
    completionSubmitting.value = false
  }
}

async function handleDelete(ticket) {
  if (!isAdminOrNoc.value && String(ticket.customerId) !== String(userStore.userId || 1)) {
    window.$message?.error('无权限删除该工单')
    return
  }

  window.$dialog?.warning({
    title: '确认删除',
    content: `确定要删除工单「${ticket.title}」吗？此操作不可恢复。`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        const result = await api.ticketApi.delete({ ticket_id: ticket.id })
        
        if (result.code === 200) {
          window.$message?.success('删除成功')
          loadData(true)
        } else {
          window.$message?.error(result.msg || '删除失败')
        }
      } catch (error) {
        window.$message?.error('删除失败')
      }
    },
    onNegativeClick: () => {
      window.$message?.info('已取消删除')
    }
  })
}

async function loadUsers() {
  try {
    const result = await api.ticketApi.users()
    
    if (result.code === 200) {
      const users = result.data
      
      customerOptions.value = [{ label: '全部用户', value: null }, ...users.map(u => ({
        label: u.username,
        value: u.id
      }))]
      
      userOptions.value = users.map(u => ({
        label: `${u.username} (${u.email})`,
        value: u.id,
        email: u.email,
        disabled: false
      }))
    }
  } catch (error) {
    console.error('加载用户列表失败', error)
  }
}

onMounted(() => {
  // 只有管理员才加载用户列表（用于筛选和发送通知）
  if (isAdminOrNoc.value) {
    loadUsers()
  }
  loadData(true)
})
</script>

<style scoped>
.ticket-page {
  padding: 16px;
}

.filter-card {
  margin-bottom: 16px;
}

.loading-more {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 8px;
  padding: 16px;
  color: #9e9e9e;
}

.no-more {
  text-align: center;
  padding: 16px;
  color: #9e9e9e;
  font-size: 13px;
}

.loading-container {
  display: flex;
  justify-content: center;
  padding: 40px;
}

.ticket-list-container {
  margin-top: 15px;
}

.scroll-container {
  height: calc(100vh - 280px);
  padding: 16px;
  overflow-y: auto;
  margin: 0 -16px;
}

.cards-wrapper {
  padding: 8px;
}

.send-modal-footer {
  display: flex;
  justify-content: flex-end;
}

.completion-modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
