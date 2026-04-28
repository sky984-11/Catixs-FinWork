<template>
  <AppPage>
    <div class="my-tickets-page">
      
      <n-card :bordered="false" class="header-card mb-15 rounded-10">
        <div class="header-row">
          <div class="header-item">
            <span class="label">工单标题：</span>
            <n-input v-model:value="filters.title" placeholder="请输入工单标题" style="width: 180px" />
          </div>
          <div class="header-item">
            <span class="label">工单状态：</span>
            <n-select v-model:value="filters.status" :options="statusOptions" placeholder="请选择状态" style="width: 130px" />
          </div>
          <div class="header-item">
            <span class="label">工单类型：</span>
            <n-select v-model:value="filters.type" :options="visibleTypeOptions" placeholder="请选择类型" style="width: 150px" />
          </div>
          <div v-show="isAdminOrNoc" class="header-item">
            <span class="label">用户：</span>
            <n-select v-model:value="filters.customerId" :options="customerOptions" placeholder="请选择用户" style="width: 150px" />
          </div>
          <n-space :size="16" align="center" style="margin-left: auto; flex-shrink: 0;">
            <n-button type="primary" class="action-btn" @click="handleSearch">查询</n-button>
            <n-button class="action-btn" @click="handleReset">重置</n-button>
          </n-space>
        </div>
      </n-card>

      
      <div class="ticket-list-container">
        <div v-if="loading" class="loading-wrapper">
          <n-spin size="large" />
        </div>
        <template v-else>
          <div v-for="ticket in ticketList" :key="ticket.id" class="ticket-item-wrapper">
            <n-card :bordered="false" class="ticket-card">
              
              <div class="card-header">
                <div class="title-section">
                  <span class="ticket-title">{{ ticket.title }}</span>
                </div>
                <div class="tag-section">
                  <n-tag :type="getStatusTagType(ticket.status)" round size="medium" class="status-tag">
                    <span v-if="ticket.status === 2" style="margin-right: 4px;">&#10003;</span>
                    {{ getStatusName(ticket.status) }}
                  </n-tag>
                  <n-tag :type="getTypeTagType(ticket.type)" round size="medium" class="type-tag">
                    {{ getTypeName(ticket.type) }}
                  </n-tag>
                </div>
              </div>

              
              <div class="card-body">
                <div class="body-left">
                  <p class="ticket-desc">{{ ticket.description }}</p>
                  
                  <div class="action-buttons">
                    <n-button size="small" type="info" secondary @click="handleView(ticket)">
                      详情
                    </n-button>
                    <n-button v-show="isAdminOrNoc" size="small" type="primary" @click="handleSend(ticket)">
                      发送
                    </n-button>
                  </div>
                </div>
                <div v-if="ticket.attachments && ticket.attachments.length > 0" class="body-right">
                  <div class="attachment-preview-box" @click="handleView(ticket)">
                    <div class="preview-info">
                      <i class="i-icon-park-outline:file-image" />
                      <span>{{ ticket.attachments.length }} 张问题截图</span>
                    </div>
                    <i class="i-icon-park-outline:right" />
                  </div>
                </div>
              </div>

              
              <div class="card-footer-meta">
                <n-grid :cols="2" :x-gap="12" :y-gap="8">
                  <n-gi>
                    <div class="meta-item">
                      <span class="meta-label">创建时间：</span>
                      <span class="meta-value">{{ ticket.createTime }}</span>
                    </div>
                  </n-gi>
                  <n-gi>
                    <div class="meta-item">
                      <span class="meta-label">更新时间：</span>
                      <span class="meta-value">{{ ticket.updateTime || ticket.createTime }}</span>
                    </div>
                  </n-gi>
                </n-grid>
              </div>
            </n-card>
          </div>
        </template>

        
        <div class="pagination-wrapper">
          <n-pagination
            v-model:page="pagination.page"
            :page-count="Math.ceil(pagination.total / pagination.pageSize)"
            show-quick-jumper
            @update:page="handlePageChange"
          />
        </div>
      </div>

      
      <n-modal v-model:show="createModalVisible" preset="card" title="创建工单" style="width: 600px">
        <n-form :model="createForm" label-placement="top">
          <n-form-item label="工单标题" required>
            <n-input v-model:value="createForm.title" placeholder="请输入工单标题" />
          </n-form-item>
          <n-form-item label="工单类型" required>
            <n-select v-model:value="createForm.type" :options="typeOptions" placeholder="请选择工单类型" @update:value="handleTypeChange" />
          </n-form-item>
          <n-form-item label="工单描述" required>
            <n-input v-model:value="createForm.description" type="textarea" placeholder="请输入工单描述" :rows="4" />
          </n-form-item>
          <n-form-item v-show="isAdminOrNoc" label="用户">
            <n-select v-model:value="createForm.customerId" :options="customerOptions" placeholder="请选择用户" />
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
            <n-button @click="createModalVisible = false">取消</n-button>
            <n-button type="primary" @click="handleSubmitCreate">提交</n-button>
          </n-space>
        </template>
      </n-modal>

      
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

      
      <n-modal v-model:show="viewModalVisible" preset="card" title="工单详情" style="width: 800px">
        <div v-if="currentTicket" class="view-detail-content">
          <n-descriptions bordered label-placement="left" :column="2">
            <n-descriptions-item label="工单编号">{{ currentTicket.ticketNo }}</n-descriptions-item>
            <n-descriptions-item label="工单标题">{{ currentTicket.title }}</n-descriptions-item>
            <n-descriptions-item label="工单类型">{{ getTypeName(currentTicket.type) }}</n-descriptions-item>
            <n-descriptions-item label="当前状态">
              <div class="status-container">
                <span>{{ getStatusName(currentTicket.status) }}</span>
                <div v-if="currentTicket.status === 0 || currentTicket.status === 1">
                  <n-button 
                    v-if="currentTicket.status === 0" 
                    size="small" 
                    type="primary" 
                    @click="handleStatusChange(currentTicket, 1)"
                    style="margin-left: 10px"
                  >
                    开始处理
                  </n-button>
                  <div v-else class="status-buttons">
                    <n-button 
                      size="small" 
                      type="success" 
                      @click="handleStatusChange(currentTicket, 2)"
                      style="margin-left: 10px"
                    >
                      标记完成
                    </n-button>
                    <n-button 
                      size="small" 
                      type="default" 
                      @click="handleStatusChange(currentTicket, 0)"
                      style="margin-left: 5px"
                    >
                      暂停处理
                    </n-button>
                  </div>
                </div>
              </div>
            </n-descriptions-item>
            <n-descriptions-item label="创建用户">{{ currentTicket.customerName }}</n-descriptions-item>
            <n-descriptions-item label="创建时间">
              <span class="meta-value">{{ currentTicket.createTime }}</span>
            </n-descriptions-item>
            <n-descriptions-item label="更新时间">
              <span class="meta-value">{{ currentTicket.updateTime || '-' }}</span>
            </n-descriptions-item>
            <n-descriptions-item label="详细描述" :span="2">{{ currentTicket.description }}</n-descriptions-item>
            <n-descriptions-item v-if="currentTicket.location" label="地点">{{ currentTicket.location }}</n-descriptions-item>
            <n-descriptions-item v-if="currentTicket.planTime" label="计划时间">{{ currentTicket.planTime }}</n-descriptions-item>
          </n-descriptions>

          <div v-if="currentTicket.attachments && currentTicket.attachments.length > 0" class="mt-20">
            <div class="font-bold mb-10">附件内容：</div>
            <n-image-group>
              <n-space>
                <n-image
                  v-for="(img, index) in currentTicket.attachments"
                  :key="index"
                  width="120"
                  src="https://07akioni.oss-cn-beijing.aliyuncs.com/07akioni.jpeg"
                />
              </n-space>
            </n-image-group>
          </div>
        </div>
      </n-modal>
    </div>
  </AppPage>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useUserStore } from '@/store'

defineOptions({ name: 'MyTickets' })

const userStore = useUserStore()
const loading = ref(false)
const createModalVisible = ref(false)
const locationTimeModalVisible = ref(false)
const viewModalVisible = ref(false)
const currentTicket = ref(null)
const uploadedFiles = ref([])


const isAdminOrNoc = computed(() => {
  if (userStore.isSuperUser) return true
  const roles = userStore.role || []
  const result = roles.some(role => {
    const roleName = typeof role === 'string' ? role : role?.name
    return roleName === 'admin' || roleName === 'noc'
  })
  console.log('isAdminOrNoc:', result, 'roles:', roles)
  return result
})

const filters = reactive({
  title: '',
  status: null,
  type: null,
  customerId: null,
  dateRange: null
})

const createForm = reactive({
  title: '',
  type: null,
  description: '',
  customerId: null
})

const locationTimeForm = reactive({
  location: '',
  planTime: null
})

const pendingCreateForm = reactive({
  location: '',
  planTime: null
})

const locationTimeModalTitle = computed(() => {
  const typeMap = {
    0: '故障工单 - 地点和时间',
    1: '服务请求工单 - 地点和时间',
    2: '变更工单 - 地点和时间',
    3: '维护工单 - 地点和时间'
  }
  return typeMap[createForm.type] || '地点和时间'
})

const statusOptions = [
  { label: '全部状态', value: null },
  { label: '未开始', value: 0 },
  { label: '进行中', value: 1 },
  { label: '已完成', value: 2 }
]

const typeOptions = [
  { label: '故障工单', value: 0 },
  { label: '服务请求工单', value: 1 },
  { label: '变更工单', value: 2 },
  { label: '维护工单', value: 3 }
]

const visibleTypeOptions = computed(() => {
  if (isAdminOrNoc.value) {
    return [{ label: '全部类型', value: null }, ...typeOptions]
  }
  return [{ label: '全部类型', value: null }, ...typeOptions.filter(t => t.value !== 3)]
})

const customerOptions = [
  { label: '全部用户', value: null },
  { label: '用户A', value: 1 },
  { label: '用户B', value: 2 },
  { label: '用户C', value: 3 },
  { label: '用户D', value: 4 }
]

const ticketList = ref([])

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0
})

const mockTickets = [
  { id: 1, ticketNo: 'TK20260401001', title: 'sentry磁盘占满', type: 0, status: 2, customerId: 1, customerName: '张三', operatorName: '李四', description: 'sentry磁盘/分区占满86%', createTime: '2026-04-01 09:30:00', updateTime: '2026-04-01 10:21:57', location: '数据中心A区', planTime: '2026-04-01 14:00:00', attachments: ['img1.png'] },
  { id: 2, ticketNo: 'TK20260402001', title: '服务器升级服务', type: 1, status: 1, customerId: 2, customerName: '王五', operatorName: '赵六', description: '申请对Web服务器进行版本升级', createTime: '2026-04-02 10:00:00', updateTime: '2026-04-02 11:30:00', location: '机房B区', planTime: '2026-04-05 08:00:00', attachments: [] },
  { id: 3, ticketNo: 'TK20260403001', title: '数据库变更申请', type: 2, status: 0, customerId: 1, customerName: '张三', operatorName: null, description: '需要对生产数据库进行结构变更', createTime: '2026-04-03 14:20:00', updateTime: null, location: '数据中心', planTime: '2026-04-10 22:00:00', attachments: ['img2.png', 'img3.png'] }
]

function getStatusName(status) {
  const map = { 0: '未开始', 1: '进行中', 2: '已完成' }
  return map[status] || '未知'
}

function getTypeName(type) {
  const map = { 0: '故障工单', 1: '服务请求工单', 2: '变更工单', 3: '维护工单' }
  return map[type] || '未知'
}

function getStatusTagType(status) {
  const map = { 0: 'default', 1: 'warning', 2: 'success' }
  return map[status] || 'default'
}

function getTypeTagType(type) {
  const map = { 0: 'error', 1: 'info', 2: 'warning', 3: 'success' }
  return map[type] || 'default'
}

function loadData() {
  loading.value = true
  setTimeout(() => {
    let filteredData = [...mockTickets]

    
    console.log('isAdminOrNoc.value:', isAdminOrNoc.value)
  console.log('userStore.userId:', userStore.userId)
  console.log('userStore.username:', userStore.username)
  console.log('userStore.role:', userStore.role)
  console.log('userStore.isSuperUser:', userStore.isSuperUser)
  
  if (!isAdminOrNoc.value) {
    const currentUserId = userStore.userId
    console.log('currentUserId:', currentUserId)
    if (currentUserId) {
      filteredData = filteredData.filter(t => {
        console.log('ticket.customerId:', t.customerId, 'currentUserId:', currentUserId, 'match:', String(t.customerId) === String(currentUserId))
        return String(t.customerId) === String(currentUserId)
      })
      if (filteredData.length === 0) {
        console.log('No tickets found for user:', currentUserId)
        
      }
    } else {
      
      console.log('No user ID, returning empty array')
      filteredData = []
    }
  } else {
    console.log('Admin or noc, showing all tickets')
  }
  console.log('filteredData after permission check:', filteredData)

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
    const start = (pagination.page - 1) * pagination.pageSize
    const end = start + pagination.pageSize
    ticketList.value = filteredData.slice(start, end)
    loading.value = false
  }, 300)
}

function handleSearch() {
  pagination.page = 1
  loadData()
}

function handleReset() {
  filters.title = ''
  filters.status = null
  filters.type = null
  filters.customerId = null
  filters.dateRange = null
  pagination.page = 1
  loadData()
}

function handlePageChange(page) {
  pagination.page = page
  loadData()
}

function handleCreate() {
  createForm.title = ''
  createForm.type = null
  createForm.description = ''
  createForm.customerId = null
  uploadedFiles.value = []
  createModalVisible.value = true
}

function handleTypeChange(type) {
  if (type !== null) {
    pendingCreateForm.location = ''
    pendingCreateForm.planTime = null
    locationTimeModalVisible.value = true
  }
}

function handleSubmitLocationTime() {
  locationTimeForm.location = pendingCreateForm.location
  locationTimeForm.planTime = pendingCreateForm.planTime
  locationTimeModalVisible.value = false
}

function handleUploadChange(options) {
  uploadedFiles.value = options.fileList
}

function handleSubmitCreate() {
  if (!createForm.title || !createForm.type || !createForm.description) {
    window.$message?.warning('请填写必填项')
    return
  }

  const newTicket = {
    id: mockTickets.length + 1,
    ticketNo: `TK202604${String(mockTickets.length + 1).padStart(3, '0')}`,
    title: createForm.title,
    type: createForm.type,
    status: 0,
    customerId: isAdminOrNoc.value ? (createForm.customerId || userStore.userId) : userStore.userId,
    customerName: isAdminOrNoc.value 
      ? (customerOptions.find(c => c.value === createForm.customerId)?.label || userStore.name) 
      : userStore.name,
    operatorName: null,
    description: createForm.description,
    createTime: new Date().toLocaleString(),
    updateTime: null,
    location: locationTimeForm.location || null,
    planTime: locationTimeForm.planTime ? new Date(locationTimeForm.planTime).toLocaleString() : null,
    attachments: uploadedFiles.value.map(file => file.name)
  }

  mockTickets.unshift(newTicket)
  window.$message?.success('创建成功')
  createModalVisible.value = false
  loadData()
}

function handleView(ticket) {
  
  if (!isAdminOrNoc.value && String(ticket.customerId) !== String(userStore.userId || 1)) {
    window.$message?.error('无权限查看该工单')
    return
  }
  currentTicket.value = ticket
  viewModalVisible.value = true
}

function handleRemark(ticket) {
  window.$message?.info(`添加备注: ${ticket.title}`)
}

function handleSolution(ticket) {
  window.$message?.info(`查看解决方案: ${ticket.title}`)
}

function handleSend(ticket) {
  window.$message?.success(`已向用户 ${ticket.customerName} 发送通知`)
}

function handleStatusChange(ticket, newStatus) {
  
  if (!isAdminOrNoc.value && String(ticket.customerId) !== String(userStore.userId || 1)) {
    window.$message?.error('无权限更改该工单状态')
    return
  }
  
  
  if (![0, 1, 2].includes(newStatus)) {
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
    
    window.$message?.success(`工单状态已更新为：${getStatusName(newStatus)}`)
    loadData() 
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.my-tickets-page {
  padding: 16px;
}

.header-row {
  display: flex;
  gap: 20px; 
  align-items: center;
  flex-wrap: nowrap; 
  overflow-x: auto; 
}

.header-item {
  display: flex;
  align-items: center;
  gap: 8px; 
}

.label {
  font-weight: 500;
  white-space: nowrap;
}


.action-btn {
  border-radius: 8px !important; 
  padding: 0 20px;
}


.ticket-list-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.ticket-item-wrapper {
  width: 100%;
}


.ticket-card {
  border-radius: 20px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.03);
  transition: all 0.3s ease;
  overflow: hidden;
}

.ticket-card:hover {
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
  transform: translateY(-2px);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.ticket-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--n-text-color);
}

.tag-section {
  display: flex;
  gap: 8px;
}

.status-tag {
  font-weight: 500;
  border: none;
}

.status-container {
  display: flex;
  align-items: center;
  gap: 10px;
}

.status-buttons {
  display: flex;
  align-items: center;
  gap: 5px;
}


.status-tag[type="success"] {
  background-color: rgba(24, 160, 88, 0.1);
  color: #18a058;
}

.status-tag[type="warning"] {
  background-color: rgba(240, 160, 32, 0.1);
  color: #f0a020;
}

.status-tag[type="default"] {
  background-color: rgba(200, 200, 200, 0.15); 
  color: #999;
}

.type-tag {
  background-color: rgba(24, 144, 255, 0.1);
  color: #1890ff;
  border: none;
}

.card-body {
  display: flex;
  gap: 24px;
  margin-bottom: 24px;
}

.body-left {
  flex: 1;
}

.ticket-desc {
  font-size: 15px;
  color: var(--n-text-color-2); 
  line-height: 1.6;
  margin-bottom: 20px;
}

.action-buttons {
  display: flex;
  gap: 12px;
  padding-left: 0; 
}

.action-buttons .n-button {
  border-radius: 10px;
}


.body-right {
  width: 200px;
}

.attachment-preview-box {
  border: 1px solid var(--n-border-color);
  background-color: var(--n-card-color);
  border-radius: 12px;
  padding: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  transition: all 0.2s;
}

.attachment-preview-box:hover {
  border-color: var(--n-primary-color);
  background-color: rgba(24, 144, 255, 0.05);
}

.preview-info {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--n-primary-color);
}

.preview-info i {
  font-size: 20px;
}


.card-footer-meta {
  background-color: var(--n-card-color);
  border-radius: 12px;
  padding: 16px;
  border: 1px solid var(--n-border-color);
}

.meta-item {
  display: flex;
  align-items: center;
  font-size: 13px;
}

.meta-label {
  color: var(--n-text-color-3);
  width: 70px;
}

.meta-value {
  color: var(--n-text-color-2); 
  font-weight: 500;
}


.pagination-wrapper {
  display: flex;
  justify-content: center;
  margin-top: 32px;
}

.loading-wrapper {
  display: flex;
  justify-content: center;
  padding: 40px;
}


[data-theme='dark'] .header-card,
[data-theme='dark'] .ticket-card {
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
}

[data-theme='dark'] .attachment-preview-box {
  background-color: var(--n-card-color);
  border-color: var(--n-border-color);
}

[data-theme='dark'] .card-footer-meta {
  background-color: var(--n-card-color);
}


[data-theme='dark'] .status-tag[type="success"] {
  background-color: rgba(24, 160, 88, 0.2);
  color: #4caf50;
}

[data-theme='dark'] .status-tag[type="warning"] {
  background-color: rgba(240, 160, 32, 0.2);
  color: #ff9800;
}

[data-theme='dark'] .status-tag[type="default"] {
  background-color: rgba(200, 200, 200, 0.2);
  color: #bbb;
}


[data-theme='dark'] .type-tag {
  background-color: rgba(24, 144, 255, 0.2);
  color: #2196f3;
}


[data-theme='dark'] .meta-value {
  color: #999999 !important;
}


.ticket-time {
  color: #666666;
  font-size: 14px;
}

.ticket-meta {
  color: #666666;
  font-size: 14px;
}


.ticket-desc {
  color: #666666;
  font-size: 14px;
  line-height: 1.5;
  margin-bottom: 12px;
}


.attachment-preview-box .preview-info span {
  color: #666666;
  font-size: 14px;
}


.card-footer-meta .meta-label {
  color: #666666;
}

.card-footer-meta .meta-value {
  color: #666666;
}


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
