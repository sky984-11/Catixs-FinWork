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
          <n-button text type="primary" @click="handleCreate">新增工单</n-button>
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
              @send="handleSend"
              @status-change="handleStatusChange"
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
        :is-admin-or-noc="isAdminOrNoc"
        :type-options="typeOptions"
        :customer-options="customerOptions"
        @submit="handleSubmitCreate"
        @type-change="handleTypeChange"
      />

      <n-modal v-model:show="locationTimeModalVisible" preset="card" :title="locationTimeModalTitle" style="width: 500px">
        <n-form :model="locationTimeForm" label-placement="top">
          <n-form-item label="地点">
            <n-input v-model:value="locationTimeForm.location" placeholder="请输入地点" />
          </n-form-item>
          <n-form-item label="计划时间">
            <n-date-picker v-model:value="locationTimeForm.planTime" type="datetime" placeholder="请选择计划时间" style="width: 100%" />
          </n-form-item>
        </n-form>
        <template #footer>
          <n-space justify="end">
            <n-button @click="locationTimeModalVisible = false">取消</n-button>
            <n-button type="primary" @click="handleSubmitLocationTime">确定</n-button>
          </n-space>
        </template>
      </n-modal>

      
      <ViewTicketModal
        v-model:visible="viewModalVisible"
        :ticket="currentTicket"
      />
    </div>
  </AppPage>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useUserStore } from '@/store'
import TicketFilter from './components/TicketFilter.vue'
import TicketCard from './components/TicketCard.vue'
import CreateTicketModal from './components/CreateTicketModal.vue'
import ViewTicketModal from './components/ViewTicketModal.vue'

defineOptions({ name: 'MyTickets' })

const userStore = useUserStore()
const loading = ref(false)
const createModalVisible = ref(false)
const locationTimeModalVisible = ref(false)
const viewModalVisible = ref(false)
const currentTicket = ref(null)

const isAdminOrNoc = computed(() => {
  if (userStore.isSuperUser) return true
  const roles = userStore.role || []
  const result = roles.some(role => {
    const roleName = typeof role === 'string' ? role : role?.name
    return roleName === 'admin' || roleName === 'noc'
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

const locationTimeForm = reactive({
  location: '',
  planTime: null
})

const pendingCreateForm = reactive({
  location: '',
  planTime: null,
  type: null
})

const locationTimeModalTitle = computed(() => {
  const typeMap = {
    0: '故障工单 - 地点和时间',
    1: '服务请求工单 - 地点和时间',
    2: '变更工单 - 地点和时间',
    3: '维护工单 - 地点和时间'
  }
  return typeMap[pendingCreateForm.type] || '地点和时间'
})

const statusOptions = [
  { label: '全部状态', value: null },
  { label: '未开始', value: 0 },
  { label: '进行中', value: 1 },
  { label: '已完成', value: 2 },
  { label: '已关闭', value: 3 }
]

const typeOptions = [
  { label: '故障工单', value: 0 },
  { label: '服务请求工单', value: 1 },
  { label: '变更工单', value: 2 },
  { label: '维护工单', value: 3 }
]

const customerOptions = [
  { label: '全部用户', value: null },
  { label: '用户A', value: 1 },
  { label: '用户B', value: 2 },
  { label: '用户C', value: 3 },
  { label: '用户D', value: 4 }
]

const ticketList = ref([])
const loadingMore = ref(false)
const noMore = ref(false)

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0
})

const fullFilteredList = ref([])

const mockTickets = [
  { id: 1, ticketNo: 'TK20260401001', title: 'sentry磁盘占满', type: 0, status: 2, customerId: 1, customerName: '张三', operatorName: '李四', description: 'sentry磁盘/分区占满86%', createTime: '2026-04-01 09:30:00', updateTime: '2026-04-01 10:21:57', location: '数据中心A区', planTime: '2026-04-01 14:00:00', attachments: ['img1.png'] },
  { id: 2, ticketNo: 'TK20260402001', title: '服务器升级服务', type: 1, status: 1, customerId: 2, customerName: '王五', operatorName: '赵六', description: '申请对Web服务器进行版本升级', createTime: '2026-04-02 10:00:00', updateTime: '2026-04-02 11:30:00', location: '机房B区', planTime: '2026-04-05 08:00:00', attachments: [] },
  { id: 3, ticketNo: 'TK20260403001', title: '数据库变更申请', type: 2, status: 0, customerId: 1, customerName: '张三', operatorName: null, description: '需要对生产数据库进行结构变更', createTime: '2026-04-03 14:20:00', updateTime: null, location: '数据中心', planTime: '2026-04-10 22:00:00', attachments: ['img2.png', 'img3.png'] }
]

function loadData(reset = false) {
  if (reset) {
    loading.value = true
    pagination.page = 1
    noMore.value = false
    ticketList.value = []
  } else {
    loadingMore.value = true
    pagination.page++
  }

  setTimeout(() => {
    let filteredData = [...mockTickets]

    if (!isAdminOrNoc.value) {
      const currentUserId = userStore.userId
      if (currentUserId) {
        filteredData = filteredData.filter(t => String(t.customerId) === String(currentUserId))
      } else {
        filteredData = []
      }
    }

    if (filters.title) {
      filteredData = filteredData.filter(t => t.title.includes(filters.title))
    }
    if (filters.status !== null) {
      filteredData = filteredData.filter(t => t.status === filters.status)
    }
    if (filters.type !== null) {
      filteredData = filteredData.filter(t => t.type === filters.type)
    }
    if (filters.customerId !== null && isAdminOrNoc.value) {
      filteredData = filteredData.filter(t => t.customerId === filters.customerId)
    }
    if (filters.dateRange) {
      const [start, end] = filters.dateRange
      filteredData = filteredData.filter(t => {
        const time = new Date(t.createTime).getTime()
        return time >= start && time <= end
      })
    }

    pagination.total = filteredData.length
    fullFilteredList.value = filteredData

    const start = (pagination.page - 1) * pagination.pageSize
    const end = start + pagination.pageSize
    const pageData = filteredData.slice(start, end)

    if (reset) {
      ticketList.value = pageData
      loading.value = false
    } else {
      ticketList.value = [...ticketList.value, ...pageData]
      loadingMore.value = false
    }

    if (end >= filteredData.length) {
      noMore.value = true
    }
  }, 300)
}

function handleInfiniteLoad(callback) {
  const start = pagination.page * pagination.pageSize
  if (start >= fullFilteredList.value.length) {
    callback()
    noMore.value = true
    return
  }

  setTimeout(() => {
    pagination.page++
    const s = (pagination.page - 1) * pagination.pageSize
    const e = s + pagination.pageSize
    const pageData = fullFilteredList.value.slice(s, e)
    ticketList.value = [...ticketList.value, ...pageData]

    if (e >= fullFilteredList.value.length) {
      noMore.value = true
    }
    callback()
  }, 500)
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

function handleTypeChange(type) {
  if (type !== null) {
    pendingCreateForm.location = ''
    pendingCreateForm.planTime = null
    pendingCreateForm.type = type
    locationTimeModalVisible.value = true
  }
}

function handleSubmitLocationTime() {
  locationTimeForm.location = pendingCreateForm.location
  locationTimeForm.planTime = pendingCreateForm.planTime
  locationTimeModalVisible.value = false
}

function handleSubmitCreate(formData) {
  const newTicket = {
    id: mockTickets.length + 1,
    ticketNo: `TK202604${String(mockTickets.length + 1).padStart(3, '0')}`,
    title: formData.title,
    type: formData.type,
    status: 0,
    customerId: isAdminOrNoc.value ? (formData.customerId || userStore.userId) : userStore.userId,
    customerName: isAdminOrNoc.value 
      ? (customerOptions.find(c => c.value === formData.customerId)?.label || userStore.name) 
      : userStore.name,
    operatorName: null,
    description: formData.description,
    createTime: new Date().toLocaleString(),
    updateTime: null,
    location: locationTimeForm.location || null,
    planTime: locationTimeForm.planTime ? new Date(locationTimeForm.planTime).toLocaleString() : null,
    attachments: formData.attachments || []
  }

  mockTickets.unshift(newTicket)
  window.$message?.success('创建成功')
  createModalVisible.value = false
  loadData(true)
}

function handleView(ticket) {
  if (!isAdminOrNoc.value && String(ticket.customerId) !== String(userStore.userId || 1)) {
    window.$message?.error('无权限查看该工单')
    return
  }
  currentTicket.value = ticket
  viewModalVisible.value = true
}

function handleSend(ticket) {
  window.$message?.success(`已向用户 ${ticket.customerName} 发送通知`)
}

function handleStatusChange({ ticket, newStatus }) {
  if (!isAdminOrNoc.value && String(ticket.customerId) !== String(userStore.userId || 1)) {
    window.$message?.error('无权限更改该工单状态')
    return
  }

  if (![0, 1, 2, 3].includes(newStatus)) {
    window.$message?.error('无效的状态值')
    return
  }

  const ticketIndex = mockTickets.findIndex(t => t.id === ticket.id)
  if (ticketIndex !== -1) {
    mockTickets[ticketIndex].status = newStatus
    mockTickets[ticketIndex].updateTime = new Date().toLocaleString()

    if (currentTicket.value && currentTicket.value.id === ticket.id) {
      currentTicket.value.status = newStatus
      currentTicket.value.updateTime = mockTickets[ticketIndex].updateTime
    }

    const statusNames = { 0: '未开始', 1: '进行中', 2: '已完成', 3: '已关闭' }
    window.$message?.success(`工单状态已更新为：${statusNames[newStatus]}`)
    loadData(true)
  }
}

onMounted(() => {
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
  color: var(--n-text-color-3);
}

.no-more {
  text-align: center;
  padding: 16px;
  color: var(--n-text-color-3);
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