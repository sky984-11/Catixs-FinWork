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

      
      <CreateTicketModal
        v-model:visible="createModalVisible"
        :type-options="typeOptions"
        @submit="handleSubmitCreate"
      />

      
      <ViewTicketModal
        v-model:visible="viewModalVisible"
        :ticket="currentTicket"
      />

      <EditTicketModal
        v-model:visible="editModalVisible"
        :ticket="currentTicket"
        :type-options="typeOptions"
        @submit="handleSubmitEdit"
      />

      <n-modal v-model:show="sendModalVisible" preset="card" title="发送通知" style="width: 600px">
        <n-transfer
          v-model:value="sendSelectedUsers"
          :options="userOptions"
          :titles="['可选用户', '已选用户']"
          filterable
          search-placeholder="搜索用户"
        />
        <template #footer>
          <n-space justify="end">
            <n-button @click="sendModalVisible = false">取消</n-button>
            <n-button type="primary" @click="handleConfirmSend">发送</n-button>
          </n-space>
        </template>
      </n-modal>
    </div>
  </AppPage>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useUserStore } from '@/store'
import api from '@/api'
import TicketFilter from './components/TicketFilter.vue'
import TicketCard from './components/TicketCard.vue'
import CreateTicketModal from './components/CreateTicketModal.vue'
import ViewTicketModal from './components/ViewTicketModal.vue'
import EditTicketModal from './components/EditTicketModal.vue'

defineOptions({ name: 'MyTickets' })

const userStore = useUserStore()

function formatTimeToMinute(dateStr) {
  const date = new Date(dateStr)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  return `${year}-${month}-${day} ${hours}:${minutes}`
}

const loading = ref(false)
const createModalVisible = ref(false)
const viewModalVisible = ref(false)
const editModalVisible = ref(false)
const sendModalVisible = ref(false)
const currentTicket = ref(null)
const sendTicket = ref(null)

const sendSelectedUsers = ref([])
const userOptions = ref([])
const customerOptions = ref([{ label: '全部用户', value: null }])

const isAdminOrNoc = computed(() => {
  if (userStore.isSuperUser) return true
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
  { label: '未开始', value: 2 },
  { label: '已关闭', value: 3 }
]

const typeOptions = [
  { label: '故障工单', value: 0 },
  { label: '服务请求工单', value: 1 },
  { label: '变更工单', value: 2 },
  { label: '维护工单', value: 3 }
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
        customerName: ticket.user_id ? customerOptions.value.find(c => c.value === ticket.user_id)?.label || '未知用户' : userStore.name,
        operatorName: ticket.assignee_id ? `处理人${ticket.assignee_id}` : null,
        description: ticket.desc,
        createTime: ticket.created_at,
        updateTime: ticket.updated_at,
        location: ticket.location,
        planTime: ticket.start_time,
        attachments: ticket.attachment_url ? [ticket.attachment_url] : []
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
  createModalVisible.value = true
}

async function handleSubmitCreate(formData) {
  try {
    // 先上传附件图片
    let attachmentUrl = undefined
    if (formData.attachments?.length > 0) {
      const uploadFormData = new FormData()
      uploadFormData.append('file', formData.attachments[0])
      const uploadRes = await api.ticketApi.upload(uploadFormData)
      if (uploadRes.code === 200) {
        attachmentUrl = uploadRes.data.url
      } else {
        window.$message?.warning('附件上传失败')
        return
      }
    }

    const data = {
        title: formData.title,
        type: formData.type,
        user_id: userStore.userId,
        desc: formData.description,
        location: formData.location || undefined,
        start_time: formData.planTime ? formatTimeToMinute(formData.planTime) : undefined,
        attachment_url: attachmentUrl
      }

    const result = await api.ticketApi.create(data)
    
    if (result.code === 200) {
      window.$message?.success('创建成功')
      createModalVisible.value = false
      loadData(true)
    } else {
      window.$message?.error(result.msg || '创建失败')
    }
  } catch (error) {
    window.$message?.error('创建失败')
  }
}

function handleView(ticket) {
  if (!isAdminOrNoc.value && String(ticket.customerId) !== String(userStore.userId || 1)) {
    window.$message?.error('无权限查看该工单')
    return
  }
  currentTicket.value = ticket
  viewModalVisible.value = true
}

function handleEdit(ticket) {
  if (!isAdminOrNoc.value && String(ticket.customerId) !== String(userStore.userId || 1)) {
    window.$message?.error('无权限编辑该工单')
    return
  }
  currentTicket.value = ticket
  editModalVisible.value = true
}

function handleSend(ticket) {
  sendTicket.value = ticket
  sendSelectedUsers.value = []
  sendModalVisible.value = true
}

function handleConfirmSend() {
  if (sendSelectedUsers.value.length === 0) {
    window.$message?.warning('请至少选择一个用户')
    return
  }
  
  const selectedEmails = sendSelectedUsers.value.map(userId => {
    const user = userOptions.value.find(u => u.value === userId)
    return user?.email || ''
  }).filter(Boolean)
  
  window.$message?.success(`已向 ${sendSelectedUsers.value.length} 个用户发送通知\n邮箱：${selectedEmails.join(', ')}`)
  sendModalVisible.value = false
  sendSelectedUsers.value = []
  sendTicket.value = null
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

  try {
    const result = await api.ticketApi.update({ id: ticket.id, ticket_no: ticket.ticketNo, status: newStatus })
    
    if (result.code === 200) {
      const statusNames = { 0: '已完成', 1: '进行中', 2: '未开始', 3: '已关闭' }
      window.$message?.success(`工单状态已更新为：${statusNames[newStatus]}`)
      
      if (currentTicket.value && currentTicket.value.id === ticket.id) {
        currentTicket.value.status = newStatus
        currentTicket.value.updateTime = new Date().toLocaleString()
      }
      
      loadData(true)
    } else {
      window.$message?.error(result.msg || '更新失败')
    }
  } catch (error) {
    window.$message?.error('更新失败')
  }
}

async function handleSubmitEdit(formData) {
  try {
    const data = {
      id: formData.id,
      ticket_no: formData.ticketNo,
      title: formData.title,
      type: formData.type,
      desc: formData.description,
      location: formData.location,
      start_time: formData.planTime ? formatTimeToMinute(formData.planTime) : undefined
    }

    const result = await api.ticketApi.update(data)
    
    if (result.code === 200) {
      window.$message?.success('编辑成功')
      editModalVisible.value = false
      loadData(true)
    } else {
      window.$message?.error(result.msg || '编辑失败')
    }
  } catch (error) {
    console.error('编辑工单失败:', error)
    window.$message?.error('编辑失败')
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
          
          if (currentTicket.value && currentTicket.value.id === ticket.id) {
            viewModalVisible.value = false
            currentTicket.value = null
          }
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
    const result = await api.getUserList({ page: 1, page_size: 9999 })
    
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
</style>
