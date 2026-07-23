<script setup>
import { computed, h, nextTick, onMounted, reactive, ref } from 'vue'
import {
  NButton,
  NCheckbox,
  NDatePicker,
  NDrawer,
  NDrawerContent,
  NDropdown,
  NEmpty,
  NForm,
  NFormItemGi,
  NGrid,
  NImage,
  NImageGroup,
  NInput,
  NInputNumber,
  NModal,
  NPopconfirm,
  NProgress,
  NSelect,
  NSlider,
  NSpace,
  NTabPane,
  NTabs,
  NTag,
  NTooltip,
  NUpload,
} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import CrudModal from '@/components/table/CrudModal.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import api from '@/api'
import { useRoute, useRouter } from 'vue-router'
import { buildPinyinSearchText, pinyinOptionFilter } from '@/utils/pinyin-search'

defineOptions({ name: '项目看板' })

const loading = ref(false)
const modalVisible = ref(false)
const modalLoading = ref(false)
const modalAction = ref('add')
const modalFormRef = ref(null)
const detailVisible = ref(false)
const detailLoading = ref(false)
const activeDetailTab = ref('overview')
const projects = ref([])
const customerList = ref([])
const userList = ref([])
const detailProject = ref(null)
const draggedProject = ref(null)
const dragTargetStatus = ref('')
const discussionText = ref('')
const referencedTaskId = ref(null)
const referencedAttachmentId = ref(null)
const attachmentRemark = ref('')
const projectFileRemark = ref('')
const projectFileLink = ref('')
const projectFileLinkLoading = ref(false)
const activeTaskId = ref(null)
const collapsedTaskIds = ref(new Set())
const taskReplyText = reactive({})
const taskReplyAttachmentId = reactive({})
const taskAttachmentLink = reactive({})
const taskAttachmentLinkLoading = reactive({})
const taskEditVisible = ref(false)
const taskEditLoading = ref(false)
const progressSaving = ref(false)
const shareVisible = ref(false)
const shareLoading = ref(false)
const shareProject = ref(null)
const shareUsers = ref([])
const dailySummaryTestLoading = ref(false)
const taskContextMenu = reactive({
  show: false,
  x: 0,
  y: 0,
  task: null,
})
const queryItems = reactive({
  keyword: '',
  customer_id: null,
  priority: '',
  health: '',
})

const boardColumns = [
  { key: 'planning', label: '规划中', icon: 'mdi:clipboard-text-clock-outline', tone: 'slate' },
  { key: 'active', label: '进行中', icon: 'mdi:rocket-launch-outline', tone: 'blue' },
  { key: 'acceptance', label: '验收中', icon: 'mdi:clipboard-check-outline', tone: 'amber' },
  { key: 'completed', label: '已完成', icon: 'mdi:check-circle-outline', tone: 'green' },
]

const priorityOptions = [
  { label: '低', value: 'low' },
  { label: '中', value: 'medium' },
  { label: '高', value: 'high' },
  { label: '紧急', value: 'urgent' },
]

const healthOptions = [
  { label: '健康', value: 'green' },
  { label: '关注', value: 'yellow' },
  { label: '风险', value: 'red' },
]

const currencyOptions = ['USD', 'CNY', 'HKD', 'EUR', 'GBP', 'SGD', 'JPY'].map((item) => ({
  label: item,
  value: item,
}))

const modalForm = reactive(createEmptyForm())
const taskForm = reactive(createEmptyTaskForm())
const taskEditForm = reactive(createEmptyTaskEditForm())
const route = useRoute()
const router = useRouter()
let progressSaveTimer = null
let progressSaveSeq = 0

const modalTitle = computed(() => (modalAction.value === 'add' ? '新增项目' : '编辑项目'))
const customerOptions = computed(() =>
  customerList.value.map((item) => {
    const mainLabel = getCustomerMainLabel(item)
    const subjectLabel = item.contract_company_name ? `主体：${item.contract_company_name}` : ''
    return {
      label: subjectLabel ? `${mainLabel} [${subjectLabel}]` : mainLabel,
      value: item.id,
      mainLabel,
      subjectLabel,
      searchText: buildPinyinSearchText([
        mainLabel,
        item.legal_name,
        item.name,
        item.code,
        item.contract_company_name,
        subjectLabel,
      ]),
    }
  })
)
const userOptions = computed(() =>
  userList.value.map((item) => {
    const name = getUserDisplayName(item)
    return {
      label: item.email ? `${name} - ${item.email}` : name,
      value: name,
    }
  })
)
const visibleProjects = computed(() =>
  projects.value.filter((project) => {
    if (queryItems.keyword) {
      const keyword = queryItems.keyword.toLowerCase()
      const haystack = [
        project.name,
        project.code,
        project.customer_name,
        project.contract_no,
        project.owner,
      ].join(' ').toLowerCase()
      if (!haystack.includes(keyword)) return false
    }
    if (queryItems.customer_id && project.customer_id !== queryItems.customer_id) return false
    if (queryItems.priority && project.priority !== queryItems.priority) return false
    if (queryItems.health && project.health !== queryItems.health) return false
    return project.status !== 'archived'
  })
)
const summary = computed(() => {
  const rows = visibleProjects.value
  return {
    total: rows.length,
    active: rows.filter((item) => normalizeProjectStatus(item.status) === 'active').length,
    overdue: rows.filter((item) => isOverdue(item)).length,
  }
})
const taskStats = computed(() => {
  const tasks = detailProject.value?.tasks || []
  const done = tasks.filter((item) => item.is_done).length
  return {
    total: tasks.length,
    done,
    percent: tasks.length ? Math.round((done / tasks.length) * 100) : 0,
  }
})
const discussionTaskOptions = computed(() =>
  (detailProject.value?.tasks || []).map((task) => ({
    label: `${task.is_done ? '已完成' : '未完成'} · ${task.title}`,
    value: task.id,
  }))
)
const discussionAttachmentOptions = computed(() =>
  getAllProjectAttachments().map((item) => ({
    label: `${item.task_title ? `${item.task_title} · ` : ''}${item.remark || item.name}`,
    value: item.id,
  }))
)
const taskContextOptions = [
  { label: '编辑任务', key: 'edit', icon: () => renderContextIcon('mdi:pencil-outline') },
  { label: '回复任务', key: 'reply', icon: () => renderContextIcon('mdi:reply-outline') },
]

const rules = {
  name: [{ required: true, message: '请输入项目名称', trigger: ['input', 'blur'] }],
  customer_id: [{ required: true, type: 'number', message: '请选择客户', trigger: 'change' }],
  owner: [{ required: true, message: '请选择负责人', trigger: ['change', 'blur'] }],
}

function createEmptyForm() {
  return {
    id: null,
    name: '',
    code: '',
    customer_id: null,
    status: 'planning',
    priority: 'medium',
    health: 'green',
    owner: '',
    shared_users: [],
    contract_no: '',
    start_date: null,
    due_date: null,
    progress: 0,
    budget_amount: null,
    budget_currency: 'USD',
    description: '',
  }
}

function createEmptyTaskForm() {
  return {
    title: '',
    assignee: '',
    due_date: null,
    remark: '',
  }
}

function createEmptyTaskEditForm() {
  return {
    id: null,
    title: '',
    assignee: '',
    due_date: null,
    remark: '',
    is_done: false,
    sort_order: 0,
  }
}

async function loadCustomers() {
  const res = await api.getCompanyList({ page: 1, page_size: 9999, role: 1, status: true })
  customerList.value = res?.data || []
}

async function loadUsers() {
  const res = await api.getUserList({ page: 1, page_size: 9999 })
  userList.value = (res?.data || []).filter((item) => item.is_active !== false)
}

async function loadProjects() {
  loading.value = true
  try {
    const res = await api.projectApi.list({ page: 1, page_size: 9999 })
    projects.value = res?.data || []
  } finally {
    loading.value = false
  }
}

async function sendDailySummaryTest() {
  dailySummaryTestLoading.value = true
  try {
    const res = await api.projectApi.testDailySummary()
    const data = res?.data || {}
    window.$message?.success?.(
      `测试总结已发送，项目数 ${data.project_count ?? '-'}，未完成子任务 ${data.open_task_count ?? '-'}，链接地址 ${data.web_base_url || '-'}`
    )
  } finally {
    dailySummaryTestLoading.value = false
  }
}

async function loadProjectDetail(projectId) {
  detailLoading.value = true
  try {
    const res = await api.projectApi.get({ project_id: projectId })
    detailProject.value = res?.data || null
  } finally {
    detailLoading.value = false
  }
}

async function openDetail(project) {
  const projectId = Number(project?.id || project)
  detailVisible.value = true
  activeDetailTab.value = 'overview'
  await loadProjectDetail(projectId)
  syncDetailRoute(projectId)
}

async function openDetailFromRoute() {
  const projectId = Number(route.query.project_id || 0)
  if (!projectId) return
  const taskId = Number(route.query.task_id || 0)
  detailVisible.value = true
  activeDetailTab.value = taskId ? 'tasks' : 'overview'
  await loadProjectDetail(projectId)
  if (taskId) {
    activeTaskId.value = taskId
    expandTask(taskId)
    await nextTick()
    document.getElementById(`project-task-${taskId}`)?.scrollIntoView({ block: 'center', behavior: 'smooth' })
  }
}

function syncDetailRoute(projectId, taskId = null) {
  router.replace({
    path: route.path,
    query: {
      ...route.query,
      project_id: projectId,
      task_id: taskId || undefined,
    },
  })
}

function resetForm() {
  Object.assign(modalForm, createEmptyForm())
}

function resetTaskForm() {
  Object.assign(taskForm, createEmptyTaskForm())
}

function openAdd(status = 'planning') {
  modalAction.value = 'add'
  resetForm()
  modalForm.status = status
  modalVisible.value = true
}

function openEdit(project) {
  modalAction.value = 'edit'
  resetForm()
  Object.assign(modalForm, {
    ...project,
    progress: Number(project.progress || 0),
    budget_amount:
      project.budget_amount === null || project.budget_amount === undefined
        ? null
        : Number(project.budget_amount),
  })
  modalVisible.value = true
}

async function handleSave() {
  try {
    modalLoading.value = true
    await modalFormRef.value?.validate()
    const payload = { ...modalForm }
    if (payload.budget_amount === null) delete payload.budget_amount
    if (modalAction.value === 'add') {
      delete payload.id
      await api.projectApi.create(payload)
      window.$message?.success?.('新增成功')
    } else {
      await api.projectApi.update(payload)
      window.$message?.success?.('保存成功')
    }
    modalVisible.value = false
    await loadProjects()
    if (detailProject.value?.id === payload.id) await loadProjectDetail(payload.id)
  } finally {
    modalLoading.value = false
  }
}

function normalizeProgressValue(value) {
  const progress = Number(value || 0)
  return Math.min(100, Math.max(0, Math.round(progress)))
}

function getProgressColor(value) {
  const progress = normalizeProgressValue(value)
  const stops = [
    { progress: 0, color: [239, 68, 68] },
    { progress: 50, color: [249, 115, 22] },
    { progress: 75, color: [234, 179, 8] },
    { progress: 100, color: [34, 197, 94] },
  ]
  const nextIndex = stops.findIndex((stop) => progress <= stop.progress)
  const next = stops[nextIndex === -1 ? stops.length - 1 : nextIndex]
  const prev = stops[Math.max(0, (nextIndex === -1 ? stops.length - 1 : nextIndex) - 1)]
  const range = Math.max(1, next.progress - prev.progress)
  const ratio = Math.min(1, Math.max(0, (progress - prev.progress) / range))
  const [r, g, b] = next.color.map((channel, index) =>
    Math.round(prev.color[index] + (channel - prev.color[index]) * ratio)
  )
  return `rgb(${r}, ${g}, ${b})`
}

function getProgressStyle(value) {
  return {
    '--progress-color': getProgressColor(value),
  }
}

function syncProjectProgress(projectId, progress) {
  if (detailProject.value?.id === projectId) detailProject.value.progress = progress
  const project = projects.value.find((item) => item.id === projectId)
  if (project) project.progress = progress
}

function buildProjectUpdatePayload(project, progress) {
  const payload = {
    id: project.id,
    name: project.name,
    code: project.code || '',
    customer_id: project.customer_id,
    status: project.status || 'planning',
    priority: project.priority || 'medium',
    health: project.health || 'green',
    owner: project.owner || '',
    contract_no: project.contract_no || '',
    shared_users: project.shared_users || [],
    start_date: project.start_date || null,
    due_date: project.due_date || null,
    progress,
    shared_users: project.shared_users || [],
    budget_amount: project.budget_amount,
    budget_currency: project.budget_currency || 'USD',
    description: project.description || '',
    sort_order: project.sort_order || 0,
  }
  if (payload.budget_amount === null || payload.budget_amount === undefined) delete payload.budget_amount
  return payload
}

function openShare(project) {
  shareProject.value = project
  shareUsers.value = [...(project.shared_users || [])]
  shareVisible.value = true
}

async function submitShare() {
  if (!shareProject.value) return
  shareLoading.value = true
  try {
    const sharedUsers = [...new Set((shareUsers.value || []).filter(Boolean))]
    const payload = buildProjectUpdatePayload(shareProject.value, normalizeProgressValue(shareProject.value.progress))
    payload.shared_users = sharedUsers
    await api.projectApi.update(payload)
    shareProject.value.shared_users = sharedUsers
    if (detailProject.value?.id === shareProject.value.id) detailProject.value.shared_users = sharedUsers
    const project = projects.value.find((item) => item.id === shareProject.value.id)
    if (project) project.shared_users = sharedUsers
    shareVisible.value = false
    window.$message?.success?.('共享设置已保存')
  } finally {
    shareLoading.value = false
  }
}

function handleDetailProgressUpdate(value) {
  if (!detailProject.value) return
  const projectId = detailProject.value.id
  const progress = normalizeProgressValue(value)
  syncProjectProgress(projectId, progress)
  if (progressSaveTimer) clearTimeout(progressSaveTimer)
  progressSaveTimer = setTimeout(() => {
    saveDetailProgress(projectId, progress).catch(() => {})
  }, 500)
}

async function saveDetailProgress(projectId, progress) {
  const project = detailProject.value?.id === projectId
    ? detailProject.value
    : projects.value.find((item) => item.id === projectId)
  if (!project) return
  const seq = ++progressSaveSeq
  progressSaving.value = true
  try {
    await api.projectApi.update(buildProjectUpdatePayload(project, progress))
  } catch (error) {
    await loadProjectDetail(projectId)
    throw error
  } finally {
    if (seq === progressSaveSeq) progressSaving.value = false
  }
}

async function handleDelete(project) {
  await api.projectApi.delete({ project_id: project.id })
  window.$message?.success?.('删除成功')
  if (detailProject.value?.id === project.id) detailVisible.value = false
  await loadProjects()
}

async function addDiscussion() {
  const content = discussionText.value.trim()
  if (!content || !detailProject.value) return
  await api.projectApi.createDiscussion({
    project_id: detailProject.value.id,
    content,
    task_id: referencedTaskId.value,
    attachment_id: referencedAttachmentId.value,
  })
  discussionText.value = ''
  referencedTaskId.value = null
  referencedAttachmentId.value = null
  await loadProjectDetail(detailProject.value.id)
}

async function addTaskDiscussion(task) {
  const content = String(taskReplyText[task.id] || '').trim()
  if (!content || !detailProject.value) return
  await api.projectApi.createDiscussion({
    project_id: detailProject.value.id,
    task_id: task.id,
    content,
    attachment_id: taskReplyAttachmentId[task.id] || null,
  })
  taskReplyText[task.id] = ''
  taskReplyAttachmentId[task.id] = null
  await loadProjectDetail(detailProject.value.id)
}

async function deleteDiscussion(item) {
  await api.projectApi.deleteDiscussion({ discussion_id: item.id })
  await loadProjectDetail(detailProject.value.id)
}

async function addTask() {
  if (!taskForm.title.trim() || !detailProject.value) return
  await api.projectApi.createTask({
    project_id: detailProject.value.id,
    ...taskForm,
    title: taskForm.title.trim(),
  })
  resetTaskForm()
  await loadProjectDetail(detailProject.value.id)
}

async function updateTask(task, patch = {}) {
  await api.projectApi.updateTask({
    project_id: detailProject.value.id,
    ...task,
    ...patch,
  })
  await loadProjectDetail(detailProject.value.id)
}

function openEditTask(task) {
  Object.assign(taskEditForm, createEmptyTaskEditForm(), {
    id: task.id,
    title: task.title || '',
    assignee: task.assignee || '',
    due_date: normalizeTaskDueDateTime(task.due_date),
    remark: task.remark || '',
    is_done: Boolean(task.is_done),
    sort_order: Number(task.sort_order || 0),
  })
  taskEditVisible.value = true
}

async function submitTaskEdit() {
  if (!detailProject.value || !taskEditForm.id) return
  const title = taskEditForm.title.trim()
  if (!title) {
    window.$message?.warning?.('请输入任务标题')
    return
  }
  taskEditLoading.value = true
  try {
    await api.projectApi.updateTask({
      project_id: detailProject.value.id,
      ...taskEditForm,
      title,
      assignee: taskEditForm.assignee || '',
      due_date: taskEditForm.due_date || null,
      remark: taskEditForm.remark || '',
    })
    taskEditVisible.value = false
    await loadProjectDetail(detailProject.value.id)
  } finally {
    taskEditLoading.value = false
  }
}

async function deleteTask(task) {
  await api.projectApi.deleteTask({ task_id: task.id })
  await loadProjectDetail(detailProject.value.id)
}

async function handleAttachmentChange({ file }) {
  if (!file?.file || !detailProject.value) return
  if (!String(file.file.type || '').startsWith('image/')) {
    window.$message?.warning?.('请上传图片截图')
    return
  }
  const data = await readFileAsDataUrl(file.file)
  await api.projectApi.uploadAttachment({
    project_id: detailProject.value.id,
    filename: file.file.name,
    content_type: file.file.type,
    data,
    remark: attachmentRemark.value,
  })
  attachmentRemark.value = ''
  await loadProjectDetail(detailProject.value.id)
}

async function handleProjectFileChange({ file }) {
  if (!file?.file || !detailProject.value) return
  const data = await readFileAsDataUrl(file.file)
  await api.projectApi.uploadAttachment({
    project_id: detailProject.value.id,
    filename: file.file.name,
    content_type: file.file.type || 'application/octet-stream',
    data,
    remark: projectFileRemark.value,
  })
  projectFileRemark.value = ''
  await loadProjectDetail(detailProject.value.id)
}

async function addProjectFileLink() {
  const linkUrl = projectFileLink.value.trim()
  if (!detailProject.value) return
  if (!isValidExternalLink(linkUrl)) {
    window.$message?.warning?.('请输入 http:// 或 https:// 开头的链接')
    return
  }
  projectFileLinkLoading.value = true
  try {
    await api.projectApi.uploadAttachment({
      project_id: detailProject.value.id,
      filename: projectFileRemark.value || linkUrl,
      content_type: 'text/uri-list',
      link_url: linkUrl,
      remark: projectFileRemark.value || '外部链接',
    })
    projectFileRemark.value = ''
    projectFileLink.value = ''
    await loadProjectDetail(detailProject.value.id)
    window.$message?.success?.('链接已添加')
  } finally {
    projectFileLinkLoading.value = false
  }
}

async function handleTaskAttachmentChange({ file }, task) {
  if (!file?.file || !detailProject.value) return
  const data = await readFileAsDataUrl(file.file)
  await api.projectApi.uploadAttachment({
    project_id: detailProject.value.id,
    task_id: task.id,
    filename: file.file.name,
    content_type: file.file.type || 'application/octet-stream',
    data,
    remark: '',
  })
  activeTaskId.value = task.id
  expandTask(task.id)
  await loadProjectDetail(detailProject.value.id)
}

async function addTaskAttachmentLink(task) {
  const linkUrl = String(taskAttachmentLink[task.id] || '').trim()
  if (!detailProject.value) return
  if (!isValidExternalLink(linkUrl)) {
    window.$message?.warning?.('请输入 http:// 或 https:// 开头的链接')
    return
  }
  taskAttachmentLinkLoading[task.id] = true
  try {
    await api.projectApi.uploadAttachment({
      project_id: detailProject.value.id,
      task_id: task.id,
      filename: linkUrl,
      content_type: 'text/uri-list',
      link_url: linkUrl,
      remark: '外部链接',
    })
    taskAttachmentLink[task.id] = ''
    activeTaskId.value = task.id
    expandTask(task.id)
    await loadProjectDetail(detailProject.value.id)
    window.$message?.success?.('链接已添加')
  } finally {
    taskAttachmentLinkLoading[task.id] = false
  }
}

async function deleteAttachment(item) {
  await api.projectApi.deleteAttachment({ attachment_id: item.id })
  await loadProjectDetail(detailProject.value.id)
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result)
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

function isValidExternalLink(value) {
  return /^https?:\/\/\S+/i.test(String(value || '').trim())
}

function getProjectsByStatus(status) {
  return visibleProjects.value
    .filter((project) => normalizeProjectStatus(project.status) === status)
    .sort((left, right) => Number(left.sort_order || 0) - Number(right.sort_order || 0))
}

function onDragStart(project) {
  draggedProject.value = project
}

function onDragEnter(status) {
  dragTargetStatus.value = status
}

async function onDrop(status) {
  const project = draggedProject.value
  draggedProject.value = null
  dragTargetStatus.value = ''
  if (!project || project.status === status) return
  const nextOrder = getProjectsByStatus(status).length + 1
  project.status = status
  project.sort_order = nextOrder
  await api.projectApi.updateStatus({ id: project.id, status, sort_order: nextOrder })
  window.$message?.success?.('状态已更新')
}

function clearFilters() {
  queryItems.keyword = ''
  queryItems.customer_id = null
  queryItems.priority = ''
  queryItems.health = ''
}

function getStatusLabel(value) {
  return boardColumns.find((item) => item.key === normalizeProjectStatus(value))?.label || '规划中'
}

function normalizeProjectStatus(status) {
  return status === 'blocked' ? 'active' : status
}

function getProjectInitial(project) {
  return String(project?.name || project?.customer_name || 'P').trim().slice(0, 1).toUpperCase()
}

function getDateRangeLabel(project) {
  if (!project?.start_date && !project?.due_date) return '未设置周期'
  return `${project.start_date || '未设置'} - ${project.due_date || '未设置'}`
}

function getProjectCycleTip(project) {
  return `开始日期：${project?.start_date || '未设置'}；截止日期：${project?.due_date || '未设置'}；当前状态：${getDueStateLabel(project)}`
}

function getDueStateLabel(project) {
  if (!project?.due_date) return '无截止日期'
  if (isOverdue(project)) return '已逾期'
  if (normalizeProjectStatus(project.status) === 'completed') return '已完成'
  return '按计划推进'
}

function getUserDisplayName(user) {
  return user?.alias || user?.username || user?.email || ''
}

function getCustomerMainLabel(customer) {
  return customer.legal_name || customer.name || '-'
}

function renderCustomerOptionLabel(option) {
  return h(
    'div',
    {
      style: {
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '12px',
        minWidth: 0,
        width: '100%',
        maxWidth: '100%',
      },
    },
    [
      h(
        'span',
        {
          style: {
            flex: '1 1 auto',
            minWidth: 0,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          },
        },
        option.mainLabel || option.label
      ),
      option.subjectLabel
        ? h(
            'span',
            {
              style: {
                flex: 'none',
                marginLeft: 'auto',
                maxWidth: '150px',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                borderRadius: '4px',
                background: '#f1f5f9',
                color: '#64748b',
                fontSize: '12px',
                lineHeight: '20px',
                padding: '0 6px',
              },
            },
            option.subjectLabel
          )
        : null,
    ]
  )
}

function getPriorityLabel(value) {
  return priorityOptions.find((item) => item.value === value)?.label || '中'
}

function getPriorityType(value) {
  if (value === 'urgent') return 'error'
  if (value === 'high') return 'warning'
  if (value === 'low') return 'default'
  return 'info'
}

function getHealthLabel(value) {
  return healthOptions.find((item) => item.value === value)?.label || '健康'
}

function getHealthType(value) {
  if (value === 'red') return 'error'
  if (value === 'yellow') return 'warning'
  return 'success'
}

function formatBudget(project) {
  if (project.budget_amount === null || project.budget_amount === undefined) return '-'
  return `${project.budget_currency || ''} ${Number(project.budget_amount || 0).toLocaleString()}`
}

function formatTime(value) {
  return value ? String(value).slice(0, 16) : '-'
}

function getOpenTasks(project) {
  return (project?.open_tasks || []).filter((task) => !task.is_done)
}

function getVisibleOpenTasks(project) {
  return getOpenTasks(project).slice(0, 6)
}

function getHiddenOpenTaskCount(project) {
  return Math.max(getOpenTasks(project).length - getVisibleOpenTasks(project).length, 0)
}

function getTaskDueClass(task) {
  if (!task?.due_date) return 'muted'
  const dueText = normalizeTaskDueDateTime(task.due_date)
  const nowText = formatLocalDateTime(new Date())
  const today = nowText.slice(0, 10)
  if (dueText < nowText) return 'danger'
  if (dueText.slice(0, 10) === today) return 'warning'
  return 'normal'
}

function normalizeTaskDueDateTime(value) {
  if (!value) return null
  const text = String(value).replace('T', ' ').slice(0, 16)
  return /^\d{4}-\d{2}-\d{2}$/.test(text) ? `${text} 00:00` : text
}

function formatLocalDateTime(value) {
  const date = value instanceof Date ? value : new Date(value)
  const pad = (num) => String(num).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function isOverdue(project) {
  if (!project.due_date || ['completed', 'archived'].includes(project.status)) return false
  return project.due_date < new Date().toISOString().slice(0, 10)
}

function getDueClass(project) {
  if (isOverdue(project)) return 'danger'
  return project.due_date ? 'normal' : 'muted'
}

function getImageUrl(url) {
  if (!url) return ''
  if (url.startsWith('http://') || url.startsWith('https://') || url.startsWith('/')) return url
  return ''
}

function isImageAttachment(item) {
  return String(item?.content_type || '').startsWith('image/')
}

function getAllProjectAttachments() {
  const files = [...(detailProject.value?.attachments || [])]
  for (const task of detailProject.value?.tasks || []) {
    for (const attachment of task.attachments || []) {
      files.push({ ...attachment, task_title: task.title })
    }
  }
  return files
}

function openFile(url) {
  if (!url) return
  window.open(getImageUrl(url), '_blank')
}

function showTaskContextMenu(event, task) {
  event.preventDefault()
  taskContextMenu.show = false
  taskContextMenu.x = event.clientX
  taskContextMenu.y = event.clientY
  taskContextMenu.task = task
  window.setTimeout(() => {
    taskContextMenu.show = true
  })
}

function handleTaskContextSelect(key) {
  const task = taskContextMenu.task
  taskContextMenu.show = false
  if (!task) return
  if (key === 'edit') {
    openEditTask(task)
    return
  }
  if (key === 'reply') {
    expandTask(task.id)
    activeTaskId.value = task.id
  }
}

function renderContextIcon(icon) {
  return h(TheIcon, { icon, size: 16 })
}

function isTaskCollapsed(taskId) {
  return collapsedTaskIds.value.has(taskId)
}

function expandTask(taskId) {
  if (!collapsedTaskIds.value.has(taskId)) return
  const next = new Set(collapsedTaskIds.value)
  next.delete(taskId)
  collapsedTaskIds.value = next
}

function toggleTaskCollapse(task) {
  const next = new Set(collapsedTaskIds.value)
  if (next.has(task.id)) {
    next.delete(task.id)
  } else {
    next.add(task.id)
    if (activeTaskId.value === task.id) activeTaskId.value = null
  }
  collapsedTaskIds.value = next
}

onMounted(async () => {
  await Promise.all([loadCustomers(), loadUsers()])
  await loadProjects()
  await openDetailFromRoute()
})
</script>

<template>
  <CommonPage show-footer title="项目看板">
    <template #action>
      <NSpace>
        <NButton secondary round @click="loadProjects">
          <TheIcon icon="mdi:refresh" :size="18" class="mr-5" />
          刷新
        </NButton>
        <NButton secondary round type="warning" :loading="dailySummaryTestLoading" @click="sendDailySummaryTest">
          <TheIcon icon="mdi:bell-ring-outline" :size="18" class="mr-5" />
          测试飞书总结
        </NButton>
        <NButton type="primary" round @click="openAdd()">
          <TheIcon icon="material-symbols:add" :size="18" class="mr-5" />
          新增项目
        </NButton>
      </NSpace>
    </template>

    <div class="project-toolbar">
      <NInput
        v-model:value="queryItems.keyword"
        clearable
        placeholder="搜索项目、客户、编号、合同、负责人"
      />
      <NSelect
        v-model:value="queryItems.customer_id"
        clearable
        filterable
        :options="customerOptions"
        :filter="pinyinOptionFilter"
        :render-label="renderCustomerOptionLabel"
        placeholder="客户"
      />
      <NSelect
        v-model:value="queryItems.priority"
        clearable
        :options="priorityOptions"
        placeholder="优先级"
      />
      <NSelect
        v-model:value="queryItems.health"
        clearable
        :options="healthOptions"
        placeholder="健康度"
      />
      <NButton secondary round @click="clearFilters">
        <template #icon><TheIcon icon="mdi:filter-remove-outline" :size="18" /></template>
      </NButton>
    </div>

    <div class="summary-strip">
      <div class="summary-cell">
        <span>项目总数</span>
        <strong>{{ summary.total }}</strong>
      </div>
      <div class="summary-cell active">
        <span>进行中</span>
        <strong>{{ summary.active }}</strong>
      </div>
      <div class="summary-cell overdue">
        <span>已逾期</span>
        <strong>{{ summary.overdue }}</strong>
      </div>
    </div>

    <div class="board-shell" :class="{ loading }">
      <section
        v-for="column in boardColumns"
        :key="column.key"
        class="board-column"
        :class="[column.tone, { active: dragTargetStatus === column.key }]"
        @dragover.prevent
        @dragenter="onDragEnter(column.key)"
        @drop="onDrop(column.key)"
      >
        <header class="column-header">
          <div>
            <TheIcon :icon="column.icon" :size="18" />
            <strong>{{ column.label }}</strong>
          </div>
          <NTag size="small" round bordered>
            {{ getProjectsByStatus(column.key).length }}
          </NTag>
        </header>

        <div class="project-list">
          <article
            v-for="project in getProjectsByStatus(column.key)"
            :key="project.id"
            class="project-card"
            draggable="true"
            @click="openDetail(project)"
            @dragstart="onDragStart(project)"
          >
            <div class="card-head">
              <div class="project-title">
                <strong>{{ project.name }}</strong>
                <span>{{ project.customer_name || '未绑定客户' }}</span>
              </div>
              <NSpace size="small" :wrap="false" @click.stop>
                <NTooltip trigger="hover" placement="top">
                  <template #trigger>
                    <NButton size="tiny" type="primary" secondary circle round @click="openEdit(project)">
                      <template #icon><TheIcon icon="material-symbols:edit" :size="15" /></template>
                    </NButton>
                  </template>
                  编辑
                </NTooltip>
                <NTooltip trigger="hover" placement="top">
                  <template #trigger>
                    <NButton size="tiny" type="info" secondary circle round @click="openShare(project)">
                      <template #icon><TheIcon icon="mdi:share-variant-outline" :size="15" /></template>
                    </NButton>
                  </template>
                  共享
                </NTooltip>
                <NPopconfirm @positive-click="handleDelete(project)">
                  <template #trigger>
                    <NTooltip trigger="hover" placement="top">
                      <template #trigger>
                        <NButton size="tiny" type="error" secondary circle round>
                          <template #icon><TheIcon icon="material-symbols:delete-outline" :size="15" /></template>
                        </NButton>
                      </template>
                      删除
                    </NTooltip>
                  </template>
                  确定删除该项目吗？
                </NPopconfirm>
              </NSpace>
            </div>

            <p v-if="project.description" class="project-desc">{{ project.description }}</p>

            <div class="tag-row">
              <NTag size="small" :type="getPriorityType(project.priority)" round :bordered="false">
                {{ getPriorityLabel(project.priority) }}
              </NTag>
              <NTag size="small" :type="getHealthType(project.health)" round :bordered="false">
                {{ getHealthLabel(project.health) }}
              </NTag>
              <NTag v-if="project.code" size="small" round bordered>
                {{ project.code }}
              </NTag>
            </div>

            <NProgress
              class="project-progress"
              :style="getProgressStyle(project.progress)"
              type="line"
              :percentage="Number(project.progress || 0)"
              :height="6"
              :show-indicator="false"
              :color="getProgressColor(project.progress)"
            />

            <div class="meta-grid">
              <span>负责人</span>
              <strong>{{ project.owner || '-' }}</strong>
              <span>截止</span>
              <strong :class="getDueClass(project)">{{ project.due_date || '-' }}</strong>
              <span>预算</span>
              <strong>{{ formatBudget(project) }}</strong>
            </div>

            <div v-if="getOpenTasks(project).length" class="project-task-tip">
              <div class="task-tip-head">
                <span>未完成子任务</span>
                <strong>{{ getOpenTasks(project).length }}</strong>
              </div>
              <div class="task-tip-list">
                <div v-for="task in getVisibleOpenTasks(project)" :key="task.id" class="task-tip-item">
                  <div>
                    <strong>{{ task.title }}</strong>
                    <span>{{ task.assignee || '未设置负责人' }}</span>
                  </div>
                  <em :class="getTaskDueClass(task)">{{ task.due_date || '无 ETA' }}</em>
                </div>
              </div>
              <div v-if="getHiddenOpenTaskCount(project)" class="task-tip-more">
                还有 {{ getHiddenOpenTaskCount(project) }} 个未完成子任务
              </div>
            </div>
          </article>

          <button class="add-card" type="button" @click="openAdd(column.key)">
            <TheIcon icon="material-symbols:add" :size="18" />
            <span>新增到{{ column.label }}</span>
          </button>
        </div>
      </section>
    </div>

    <NDrawer v-model:show="detailVisible" :width="900" placement="right">
      <NDrawerContent :title="detailProject?.name || '项目详情'" closable>
        <template #header-extra>
          <NButton v-if="detailProject" secondary round size="small" @click="openEdit(detailProject)">
            <template #icon><TheIcon icon="material-symbols:edit" :size="16" /></template>
            编辑
          </NButton>
        </template>

        <div v-if="detailProject" class="detail-shell">
          <section class="detail-hero-panel">
            <div class="project-avatar">{{ getProjectInitial(detailProject) }}</div>
            <div class="detail-hero-main">
              <div class="detail-title-row">
                <div>
                  <h2>{{ detailProject.name }}</h2>
                  <p>{{ detailProject.customer_name || '未绑定客户' }}</p>
                </div>
                <NSpace size="small">
                  <NTag :type="getPriorityType(detailProject.priority)" :bordered="false" round>
                    {{ getPriorityLabel(detailProject.priority) }}
                  </NTag>
                  <NTag :type="getHealthType(detailProject.health)" :bordered="false" round>
                    {{ getHealthLabel(detailProject.health) }}
                  </NTag>
                  <NTag bordered round>{{ getStatusLabel(detailProject.status) }}</NTag>
                </NSpace>
              </div>
              <div class="hero-meta-grid">
                <div>
                  <span>项目编号</span>
                  <strong>{{ detailProject.code || '-' }}</strong>
                </div>
                <div>
                  <span>合同编号</span>
                  <strong>{{ detailProject.contract_no || '-' }}</strong>
                </div>
                <div>
                  <span>项目周期</span>
                  <NTooltip trigger="hover">
                    <template #trigger>
                      <strong class="with-tip">{{ getDateRangeLabel(detailProject) }}</strong>
                    </template>
                    {{ getProjectCycleTip(detailProject) }}
                  </NTooltip>
                </div>
                <div>
                  <span>截止状态</span>
                  <strong :class="getDueClass(detailProject)">{{ getDueStateLabel(detailProject) }}</strong>
                </div>
              </div>
            </div>
          </section>

          <NTabs v-model:value="activeDetailTab" type="line" animated class="detail-tabs">
            <NTabPane name="overview" tab="概览">
              <div class="overview-grid">
                <div class="info-card owner-card">
                  <TheIcon icon="mdi:account-tie-outline" :size="20" class="info-icon" />
                  <span>负责人</span>
                  <strong>{{ detailProject.owner || '-' }}</strong>
                </div>
                <div class="info-card">
                  <TheIcon icon="mdi:calendar-range-outline" :size="20" class="info-icon" />
                  <span>起止日期</span>
                  <NTooltip trigger="hover">
                    <template #trigger>
                      <strong class="with-tip">{{ getDateRangeLabel(detailProject) }}</strong>
                    </template>
                    {{ getProjectCycleTip(detailProject) }}
                  </NTooltip>
                </div>
                <div class="info-card">
                  <TheIcon icon="mdi:cash-multiple" :size="20" class="info-icon" />
                  <span>预算</span>
                  <strong>{{ formatBudget(detailProject) }}</strong>
                </div>
                <div class="info-card">
                  <TheIcon icon="mdi:format-list-checks" :size="20" class="info-icon" />
                  <span>任务进度</span>
                  <strong>{{ taskStats.done }} / {{ taskStats.total }}（{{ taskStats.percent }}%）</strong>
                </div>
              </div>
              <div class="detail-section">
                <div class="section-title">项目进度</div>
                <div class="progress-editor">
                  <NSlider
                    class="progress-slider"
                    :style="getProgressStyle(detailProject.progress)"
                    :value="Number(detailProject.progress || 0)"
                    :min="0"
                    :max="100"
                    :step="1"
                    @update:value="handleDetailProgressUpdate"
                  />
                  <strong class="progress-value">{{ Number(detailProject.progress || 0) }}%</strong>
                  <span v-if="progressSaving" class="progress-saving">保存中</span>
                </div>
              </div>
              <div class="detail-section">
                <div class="section-title">项目说明</div>
                <p class="description-text">{{ detailProject.description || '-' }}</p>
              </div>
            </NTabPane>

            <NTabPane name="tasks" tab="任务">
              <div class="task-create">
                <NInput v-model:value="taskForm.title" placeholder="任务标题" />
                <NSelect
                  v-model:value="taskForm.assignee"
                  filterable
                  clearable
                  :options="userOptions"
                  placeholder="负责人"
                />
                <NDatePicker
                  v-model:formatted-value="taskForm.due_date"
                  type="datetime"
                  value-format="yyyy-MM-dd HH:mm"
                  format="yyyy-MM-dd HH:mm"
                  clearable
                />
                <NButton type="primary" round @click="addTask">添加任务</NButton>
              </div>
              <NProgress
                class="task-progress"
                type="line"
                :percentage="taskStats.percent"
                :height="8"
              />
              <div v-if="detailProject.tasks?.length" class="task-list">
                <article
                  v-for="task in detailProject.tasks"
                  :key="task.id"
                  :id="`project-task-${task.id}`"
                  :class="['task-card', { focused: activeTaskId === task.id }]"
                  @contextmenu="showTaskContextMenu($event, task)"
                >
                  <div class="task-card-head">
                    <NCheckbox
                      :checked="task.is_done"
                      @update:checked="(checked) => updateTask(task, { is_done: checked })"
                    />
                    <div class="task-main">
                      <strong :class="{ done: task.is_done }">{{ task.title }}</strong>
                      <span>{{ task.assignee || '-' }} · {{ task.due_date || '无截止日期' }}</span>
                    </div>
                    <NSpace size="small" :wrap="false">
                      <NButton text size="small" @click="openEditTask(task)">编辑</NButton>
                      <NButton text size="small" @click="toggleTaskCollapse(task)">
                        <template #icon>
                          <TheIcon
                            :icon="isTaskCollapsed(task.id) ? 'mdi:chevron-down' : 'mdi:chevron-up'"
                            :size="17"
                          />
                        </template>
                        {{ isTaskCollapsed(task.id) ? '展开' : '折叠' }}
                      </NButton>
                      <NPopconfirm @positive-click="deleteTask(task)">
                        <template #trigger>
                          <NButton text type="error" size="small">删除</NButton>
                        </template>
                        确定删除这个任务吗？
                      </NPopconfirm>
                    </NSpace>
                  </div>

                  <div v-if="!isTaskCollapsed(task.id)" class="task-content">
                  <p v-if="task.remark" class="task-remark">{{ task.remark }}</p>

                  <div v-if="task.attachments?.length" class="task-attachment-row">
                    <button
                      v-for="file in task.attachments"
                      :key="file.id"
                      type="button"
                      class="task-file-chip"
                      @click="openFile(file.file_url)"
                    >
                      <TheIcon :icon="isImageAttachment(file) ? 'mdi:image-outline' : 'mdi:file-outline'" :size="15" />
                      <span>{{ file.remark || file.name }}</span>
                    </button>
                  </div>

                  <div v-if="task.discussions?.length" class="task-replies">
                    <article v-for="reply in task.discussions" :key="reply.id" class="task-reply">
                      <div class="timeline-meta">
                        <strong>{{ reply.author_name || '未知用户' }}</strong>
                        <span>{{ formatTime(reply.created_at) }}</span>
                        <NPopconfirm @positive-click="deleteDiscussion(reply)">
                          <template #trigger>
                            <NButton text type="error" size="tiny">删除</NButton>
                          </template>
                          确定删除这条回复吗？
                        </NPopconfirm>
                      </div>
                      <p>{{ reply.content }}</p>
                      <div v-if="reply.referenced_attachment" class="reference-row single">
                        <div class="reference-card attachment-reference">
                          <NImage
                            v-if="isImageAttachment(reply.referenced_attachment)"
                            :src="getImageUrl(reply.referenced_attachment.file_url)"
                            object-fit="cover"
                            width="64"
                            height="48"
                          />
                          <TheIcon v-else icon="mdi:file-outline" :size="24" />
                          <div>
                            <span>引用文件</span>
                            <strong>{{ reply.referenced_attachment.remark || reply.referenced_attachment.name }}</strong>
                            <em>{{ formatTime(reply.referenced_attachment.created_at) }}</em>
                          </div>
                        </div>
                      </div>
                    </article>
                  </div>

                  <div v-if="activeTaskId === task.id" class="task-workbench">
                    <NInput
                      v-model:value="taskReplyText[task.id]"
                      type="textarea"
                      :autosize="{ minRows: 2, maxRows: 5 }"
                      placeholder="回复这个任务，记录处理过程、客户反馈或风险点"
                    />
                    <div class="task-workbench-actions">
                      <NSelect
                        v-model:value="taskReplyAttachmentId[task.id]"
                        clearable
                        :options="discussionAttachmentOptions"
                        placeholder="引用项目/任务文件"
                      />
                      <NUpload
                        :default-upload="false"
                        :show-file-list="false"
                        @change="(options) => handleTaskAttachmentChange(options, task)"
                      >
                        <NButton secondary round>
                          <template #icon><TheIcon icon="mdi:paperclip" :size="17" /></template>
                          上传截图/文件
                        </NButton>
                      </NUpload>
                      <NInput
                        v-model:value="taskAttachmentLink[task.id]"
                        clearable
                        placeholder="飞书文件/文件夹链接"
                      />
                      <NButton
                        secondary
                        round
                        :loading="Boolean(taskAttachmentLinkLoading[task.id])"
                        @click="addTaskAttachmentLink(task)"
                      >
                        <template #icon><TheIcon icon="mdi:link-variant" :size="17" /></template>
                        添加链接
                      </NButton>
                      <NButton type="primary" round @click="addTaskDiscussion(task)">发布回复</NButton>
                    </div>
                  </div>
                  </div>
                </article>
              </div>
              <NEmpty v-else description="暂无任务" />
            </NTabPane>

            <NTabPane name="attachments" tab="项目文件">
              <div class="upload-row">
                <NInput
                  v-model:value="projectFileRemark"
                  class="upload-remark-input"
                  placeholder="文件说明"
                  clearable
                />
                <NInput
                  v-model:value="projectFileLink"
                  class="upload-link-input"
                  placeholder="飞书文件/文件夹链接"
                  clearable
                />
                <NUpload
                  :default-upload="false"
                  :show-file-list="false"
                  @change="handleProjectFileChange"
                >
                  <NButton type="primary" round>
                    <template #icon><TheIcon icon="mdi:file-upload-outline" :size="18" /></template>
                    上传文件
                  </NButton>
                </NUpload>
                <NButton secondary round :loading="projectFileLinkLoading" @click="addProjectFileLink">
                  <template #icon><TheIcon icon="mdi:link-variant" :size="18" /></template>
                  添加链接
                </NButton>
              </div>
              <NImageGroup v-if="detailProject.attachments?.length">
                <div class="attachment-grid">
                  <article v-for="item in detailProject.attachments" :key="item.id" class="attachment-card">
                    <NImage
                      v-if="isImageAttachment(item)"
                      :src="getImageUrl(item.file_url)"
                      object-fit="cover"
                      width="100%"
                      height="160"
                    />
                    <button v-else type="button" class="file-preview" @click="openFile(item.file_url)">
                      <TheIcon icon="mdi:file-outline" :size="34" />
                      <span>{{ item.name }}</span>
                    </button>
                    <div>
                      <strong>{{ item.remark || item.name }}</strong>
                      <span>{{ item.uploader_name || '-' }} · {{ formatTime(item.created_at) }}</span>
                    </div>
                    <NPopconfirm @positive-click="deleteAttachment(item)">
                      <template #trigger>
                        <NButton text type="error" size="small">删除</NButton>
                      </template>
                      确定删除这个文件吗？
                    </NPopconfirm>
                  </article>
                </div>
              </NImageGroup>
              <NEmpty v-else description="暂无项目文件" />
            </NTabPane>
          </NTabs>
        </div>
      </NDrawerContent>
    </NDrawer>

    <NDropdown
      placement="bottom-start"
      trigger="manual"
      :x="taskContextMenu.x"
      :y="taskContextMenu.y"
      :options="taskContextOptions"
      :show="taskContextMenu.show"
      @clickoutside="taskContextMenu.show = false"
      @select="handleTaskContextSelect"
    />

    <NModal
      v-model:show="taskEditVisible"
      preset="card"
      title="编辑任务"
      class="task-edit-modal"
      :bordered="false"
    >
      <NForm label-placement="top" :model="taskEditForm">
        <NGrid :cols="2" :x-gap="14">
          <NFormItemGi :span="2" label="任务标题" required>
            <NInput v-model:value="taskEditForm.title" placeholder="任务标题" clearable />
          </NFormItemGi>
          <NFormItemGi label="负责人">
            <NSelect
              v-model:value="taskEditForm.assignee"
              filterable
              clearable
              :options="userOptions"
              placeholder="负责人"
            />
          </NFormItemGi>
          <NFormItemGi label="ETA">
            <NDatePicker
              v-model:formatted-value="taskEditForm.due_date"
              type="datetime"
              value-format="yyyy-MM-dd HH:mm"
              format="yyyy-MM-dd HH:mm"
              clearable
            />
          </NFormItemGi>
          <NFormItemGi label="完成状态">
            <NCheckbox v-model:checked="taskEditForm.is_done">已完成</NCheckbox>
          </NFormItemGi>
          <NFormItemGi :span="2" label="备注">
            <NInput
              v-model:value="taskEditForm.remark"
              type="textarea"
              :autosize="{ minRows: 3, maxRows: 6 }"
              placeholder="任务备注"
            />
          </NFormItemGi>
        </NGrid>
      </NForm>
      <template #footer>
        <NSpace justify="end">
          <NButton @click="taskEditVisible = false">取消</NButton>
          <NButton type="primary" :loading="taskEditLoading" @click="submitTaskEdit">保存</NButton>
        </NSpace>
      </template>
    </NModal>

    <NModal
      v-model:show="shareVisible"
      preset="card"
      title="共享项目"
      class="share-modal"
      :bordered="false"
    >
      <div class="share-project-title">
        <strong>{{ shareProject?.name || '-' }}</strong>
        <span>共享后，对应用户可以在项目看板中看到该项目。</span>
      </div>
      <NSelect
        v-model:value="shareUsers"
        multiple
        filterable
        clearable
        :options="userOptions"
        placeholder="选择共享用户"
      />
      <template #footer>
        <NSpace justify="end">
          <NButton @click="shareVisible = false">取消</NButton>
          <NButton type="primary" :loading="shareLoading" @click="submitShare">保存</NButton>
        </NSpace>
      </template>
    </NModal>

    <CrudModal
      v-model:visible="modalVisible"
      width="860px"
      :title="modalTitle"
      :loading="modalLoading"
      @save="handleSave"
    >
      <NForm
        ref="modalFormRef"
        label-placement="left"
        label-align="left"
        :label-width="90"
        :model="modalForm"
        :rules="rules"
      >
        <NGrid :cols="2" :x-gap="16">
          <NFormItemGi label="项目名称" path="name">
            <NInput v-model:value="modalForm.name" clearable />
          </NFormItemGi>
          <NFormItemGi label="项目编号" path="code">
            <NInput v-model:value="modalForm.code" clearable />
          </NFormItemGi>
          <NFormItemGi label="客户" path="customer_id">
            <NSelect
              v-model:value="modalForm.customer_id"
              filterable
              clearable
              :options="customerOptions"
              :filter="pinyinOptionFilter"
              :render-label="renderCustomerOptionLabel"
            />
          </NFormItemGi>
          <NFormItemGi label="合同编号" path="contract_no">
            <NInput v-model:value="modalForm.contract_no" clearable />
          </NFormItemGi>
          <NFormItemGi label="状态" path="status">
            <NSelect
              v-model:value="modalForm.status"
              :options="boardColumns.map((item) => ({ label: item.label, value: item.key }))"
            />
          </NFormItemGi>
          <NFormItemGi label="优先级" path="priority">
            <NSelect v-model:value="modalForm.priority" :options="priorityOptions" />
          </NFormItemGi>
          <NFormItemGi label="健康度" path="health">
            <NSelect v-model:value="modalForm.health" :options="healthOptions" />
          </NFormItemGi>
          <NFormItemGi label="负责人" path="owner">
            <NSelect
              v-model:value="modalForm.owner"
              filterable
              :options="userOptions"
            />
          </NFormItemGi>
          <NFormItemGi label="开始日期" path="start_date">
            <NDatePicker
              v-model:formatted-value="modalForm.start_date"
              type="date"
              value-format="yyyy-MM-dd"
              clearable
            />
          </NFormItemGi>
          <NFormItemGi label="截止日期" path="due_date">
            <NDatePicker
              v-model:formatted-value="modalForm.due_date"
              type="date"
              value-format="yyyy-MM-dd"
              clearable
            />
          </NFormItemGi>
          <NFormItemGi label="项目进度" path="progress">
            <NInputNumber v-model:value="modalForm.progress" :min="0" :max="100" :precision="0" />
          </NFormItemGi>
          <NFormItemGi label="预算币种" path="budget_currency">
            <NSelect v-model:value="modalForm.budget_currency" filterable tag :options="currencyOptions" />
          </NFormItemGi>
          <NFormItemGi label="预算金额" path="budget_amount">
            <NInputNumber v-model:value="modalForm.budget_amount" :min="0" :precision="2" />
          </NFormItemGi>
          <NFormItemGi :span="2" label="项目说明" path="description">
            <NInput
              v-model:value="modalForm.description"
              type="textarea"
              :autosize="{ minRows: 3, maxRows: 6 }"
            />
          </NFormItemGi>
        </NGrid>
      </NForm>
    </CrudModal>
  </CommonPage>
</template>

<style scoped>
.project-toolbar {
  display: grid;
  grid-template-columns: minmax(220px, 1.8fr) minmax(180px, 1fr) 130px 130px 42px;
  gap: 10px;
  margin-bottom: 12px;
}

.task-edit-modal {
  width: min(640px, calc(100vw - 32px));
}

.summary-strip {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 12px;
}

.summary-cell {
  display: flex;
  min-height: 62px;
  align-items: center;
  justify-content: space-between;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  padding: 12px 14px;
}

.summary-cell span {
  color: #64748b;
  font-size: 13px;
}

.summary-cell strong {
  color: #0f172a;
  font-size: 24px;
  font-variant-numeric: tabular-nums;
}

.summary-cell.active strong {
  color: #2563eb;
}

.summary-cell.overdue strong {
  color: #dc2626;
}

.board-shell {
  display: grid;
  min-height: calc(100vh - 310px);
  grid-template-columns: repeat(4, minmax(240px, 1fr));
  gap: 12px;
  overflow-x: auto;
  padding-bottom: 8px;
}

.board-column {
  min-width: 240px;
  border: 1px solid #e2e8f0;
  border-top: 3px solid #64748b;
  border-radius: 8px;
  background: #f8fafc;
}

.board-column.blue {
  border-top-color: #2563eb;
}

.board-column.amber {
  border-top-color: #d97706;
}

.board-column.green {
  border-top-color: #16a34a;
}

.board-column.active {
  outline: 2px solid #94a3b8;
  outline-offset: -2px;
}

.column-header {
  display: flex;
  height: 48px;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #e2e8f0;
  padding: 0 12px;
}

.column-header div {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #0f172a;
}

.project-list {
  display: flex;
  min-height: 180px;
  flex-direction: column;
  gap: 10px;
  padding: 10px;
}

.project-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 10px;
  border: 1px solid #dbe3ef;
  border-radius: 8px;
  background: #fff;
  padding: 12px;
  box-shadow: 0 1px 2px rgb(15 23 42 / 6%);
  cursor: pointer;
}

.project-card:active {
  cursor: grabbing;
}

.project-task-tip {
  position: absolute;
  z-index: 30;
  right: 10px;
  bottom: calc(100% + 10px);
  left: 10px;
  visibility: hidden;
  transform: translateY(6px);
  border: 1px solid #dbe3ef;
  border-radius: 8px;
  background: rgb(255 255 255 / 98%);
  box-shadow: 0 18px 38px rgb(15 23 42 / 16%);
  opacity: 0;
  padding: 10px;
  pointer-events: none;
  transition: opacity 0.16s ease, transform 0.16s ease, visibility 0.16s ease;
}

.project-card:hover .project-task-tip {
  visibility: visible;
  transform: translateY(0);
  opacity: 1;
}

.project-progress :deep(.n-progress-graph-line-fill) {
  background: var(--progress-color) !important;
}

.project-task-tip::after {
  position: absolute;
  right: 24px;
  bottom: -7px;
  width: 12px;
  height: 12px;
  transform: rotate(45deg);
  border-right: 1px solid #dbe3ef;
  border-bottom: 1px solid #dbe3ef;
  background: #fff;
  content: '';
}

.task-tip-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}

.task-tip-head span {
  color: #475569;
  font-size: 12px;
  font-weight: 600;
}

.task-tip-head strong {
  display: inline-flex;
  min-width: 22px;
  height: 22px;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: #fff1ed;
  color: #f4511e;
  font-size: 12px;
}

.task-tip-list {
  display: grid;
  gap: 6px;
}

.task-tip-item {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  border-radius: 6px;
  background: #f8fafc;
  padding: 8px;
}

.task-tip-item > div {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 2px;
}

.task-tip-item strong {
  overflow: hidden;
  color: #0f172a;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-tip-item span {
  overflow: hidden;
  color: #64748b;
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-tip-item em {
  border-radius: 999px;
  background: #eef2ff;
  color: #475569;
  font-size: 11px;
  font-style: normal;
  line-height: 20px;
  padding: 0 8px;
  white-space: nowrap;
}

.task-tip-item em.danger {
  background: #fee2e2;
  color: #dc2626;
}

.task-tip-item em.warning {
  background: #fef3c7;
  color: #b45309;
}

.task-tip-item em.muted {
  background: #f1f5f9;
  color: #64748b;
}

.task-tip-more {
  margin-top: 8px;
  color: #64748b;
  font-size: 12px;
  text-align: center;
}

.card-head,
.timeline-meta,
.task-card-head,
.upload-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.project-title,
.attachment-card div {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 3px;
}

.project-title strong,
.attachment-card strong,
.task-main strong {
  overflow: hidden;
  color: #0f172a;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.project-title span,
.project-desc,
.meta-grid span,
.timeline-meta span,
.task-main span,
.attachment-card span {
  color: #64748b;
  font-size: 12px;
}

.project-desc {
  display: -webkit-box;
  overflow: hidden;
  margin: 0;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-height: 1.45;
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.meta-grid {
  display: grid;
  grid-template-columns: 52px minmax(0, 1fr);
  gap: 5px 8px;
}

.meta-grid strong {
  overflow: hidden;
  color: #334155;
  font-size: 12px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.meta-grid .danger {
  color: #dc2626;
}

.meta-grid .muted {
  color: #94a3b8;
}

.add-card {
  display: flex;
  height: 38px;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  background: transparent;
  color: #64748b;
  cursor: pointer;
}

.add-card:hover {
  border-color: #2563eb;
  color: #2563eb;
}

.detail-shell {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.detail-hero-panel {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  gap: 16px;
  border: 1px solid #dbe3ef;
  border-radius: 8px;
  background: linear-gradient(180deg, #fff, #f8fafc);
  padding: 18px;
  box-shadow: 0 8px 22px rgb(15 23 42 / 6%);
}

.project-avatar {
  display: flex;
  width: 72px;
  height: 72px;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: #0f172a;
  color: #fff;
  font-size: 30px;
  font-weight: 800;
}

.detail-hero-main {
  min-width: 0;
}

.detail-title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.detail-title-row h2 {
  overflow-wrap: anywhere;
  margin: 0;
  color: #0f172a;
  font-size: 22px;
  line-height: 1.25;
}

.detail-title-row p {
  margin: 5px 0 0;
  color: #64748b;
}

.hero-meta-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-top: 16px;
}

.hero-meta-grid > div {
  min-width: 0;
  border-radius: 8px;
  background: #f1f5f9;
  padding: 10px 12px;
}

.hero-meta-grid :deep(.n-tooltip-trigger) {
  min-width: 0;
}

.hero-meta-grid span {
  display: block;
  color: #64748b;
  font-size: 12px;
}

.hero-meta-grid strong {
  display: block;
  overflow: hidden;
  margin-top: 4px;
  color: #0f172a;
  font-size: 13px;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.hero-meta-grid .danger {
  color: #dc2626;
}

.hero-meta-grid .muted {
  color: #94a3b8;
}

.detail-tabs {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  padding: 0 14px 14px;
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(120px, 1fr));
  gap: 10px;
  margin-bottom: 14px;
  overflow-x: auto;
  padding-bottom: 2px;
}

.info-card {
  display: grid;
  min-height: 82px;
  grid-template-columns: 24px minmax(0, 1fr);
  align-content: center;
  gap: 4px 8px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
  padding: 10px 12px;
}

.info-card :deep(.n-tooltip-trigger) {
  grid-column: 2;
  min-width: 0;
}

.info-icon {
  grid-row: 1 / span 2;
  grid-column: 1;
  color: #2563eb;
}

.info-card span,
.section-title {
  color: #64748b;
  font-size: 12px;
}

.info-card > span {
  grid-column: 2;
}

.info-card strong {
  grid-column: 2;
  display: block;
  min-width: 0;
  overflow: hidden;
  color: #0f172a;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.with-tip {
  cursor: help;
  text-decoration: underline dotted #94a3b8;
  text-underline-offset: 3px;
}

.detail-section {
  margin-top: 14px;
}

.section-title {
  margin-bottom: 8px;
  font-weight: 700;
}

.progress-editor {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 44px 48px;
  align-items: center;
  gap: 10px;
  min-height: 28px;
}

.progress-slider {
  min-width: 0;
}

.progress-slider :deep(.n-slider-rail__fill) {
  background: var(--progress-color) !important;
}

.progress-slider :deep(.n-slider-handle) {
  border-color: var(--progress-color) !important;
}

.progress-value {
  color: #334155;
  font-size: 13px;
  font-weight: 700;
  text-align: right;
}

.progress-saving {
  color: #64748b;
  font-size: 12px;
}

.share-modal {
  width: min(520px, calc(100vw - 32px));
}

.share-project-title {
  display: grid;
  gap: 6px;
  margin-bottom: 14px;
}

.share-project-title strong {
  color: #0f172a;
  font-size: 16px;
}

.share-project-title span {
  color: #64748b;
  font-size: 13px;
}

.description-text {
  margin: 0;
  border-radius: 8px;
  background: #f8fafc;
  padding: 14px;
  color: #334155;
  line-height: 1.65;
  white-space: pre-wrap;
}

.comment-box,
.task-create {
  display: grid;
  gap: 10px;
  margin-bottom: 14px;
}

.comment-box {
  grid-template-columns: minmax(0, 1fr) 230px;
  align-items: end;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
  padding: 12px;
}

.comment-actions {
  display: grid;
  gap: 8px;
}

.task-create {
  grid-template-columns: minmax(180px, 1fr) minmax(150px, 0.8fr) 160px auto;
}

.timeline-list,
.task-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.timeline-item,
.task-card,
.attachment-card {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  padding: 12px;
  box-shadow: 0 1px 2px rgb(15 23 42 / 4%);
}

.timeline-item p {
  margin: 8px 0 0;
  color: #334155;
  line-height: 1.6;
  white-space: pre-wrap;
}

.timeline-meta {
  align-items: center;
}

.timeline-meta strong {
  color: #0f172a;
}

.reference-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin-top: 10px;
}

.reference-card {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 8px;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #eff6ff;
  padding: 8px;
}

.reference-card > div {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 2px;
}

.reference-card span,
.reference-card em {
  color: #64748b;
  font-size: 11px;
  font-style: normal;
}

.reference-card strong {
  overflow: hidden;
  color: #0f172a;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-progress {
  margin-bottom: 12px;
}

.task-card {
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.task-card.focused {
  border-color: #ff7a45;
  box-shadow: 0 0 0 3px rgb(255 122 69 / 14%), 0 10px 24px rgb(15 23 42 / 8%);
}

.task-card:hover,
.attachment-card:hover,
.timeline-item:hover {
  border-color: #cbd5e1;
  box-shadow: 0 8px 18px rgb(15 23 42 / 7%);
}

.task-card-head {
  align-items: center;
}

.task-main {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 3px;
}

.task-main .done {
  color: #94a3b8;
  text-decoration: line-through;
}

.task-remark {
  margin: 8px 0 0 28px;
  color: #64748b;
  line-height: 1.5;
}

.task-attachment-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 10px 0 0 28px;
}

.task-file-chip {
  display: inline-flex;
  max-width: 220px;
  align-items: center;
  gap: 5px;
  border: 1px solid #dbeafe;
  border-radius: 999px;
  background: #eff6ff;
  padding: 4px 9px;
  color: #1d4ed8;
  cursor: pointer;
}

.task-file-chip span {
  overflow: hidden;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-replies {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin: 10px 0 0 28px;
}

.task-reply {
  border-radius: 8px;
  background: #f8fafc;
  padding: 10px;
}

.task-reply p {
  margin: 7px 0 0;
  color: #334155;
  line-height: 1.55;
  white-space: pre-wrap;
}

.task-workbench {
  display: grid;
  gap: 8px;
  margin: 12px 0 0 28px;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #f8fafc;
  padding: 10px;
}

.task-workbench-actions {
  display: grid;
  grid-template-columns: minmax(150px, 1fr) auto minmax(180px, 1fr) auto auto;
  gap: 8px;
  align-items: center;
}

.upload-row {
  display: grid;
  grid-template-columns: minmax(180px, 0.9fr) minmax(260px, 1.4fr) auto auto;
  gap: 10px;
  align-items: center;
  margin-bottom: 14px;
}

.upload-row .n-button {
  white-space: nowrap;
}

.upload-remark-input,
.upload-link-input {
  min-width: 0;
}

.attachment-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.attachment-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow: hidden;
}

.file-preview {
  display: flex;
  min-height: 160px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  background: #f8fafc;
  color: #475569;
  cursor: pointer;
}

.file-preview span {
  max-width: 80%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 960px) {
  .project-toolbar,
  .task-create {
    grid-template-columns: 1fr 1fr;
  }

  .summary-strip,
  .hero-meta-grid,
  .attachment-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .detail-title-row {
    flex-direction: column;
  }
}

@media (max-width: 560px) {
  .project-toolbar,
  .summary-strip,
  .hero-meta-grid,
  .task-create,
  .task-workbench-actions,
  .upload-row,
  .comment-box,
  .reference-row,
  .attachment-grid {
    grid-template-columns: 1fr;
  }

  .detail-hero-panel {
    grid-template-columns: 1fr;
  }

  .project-avatar {
    width: 58px;
    height: 58px;
    font-size: 24px;
  }
}
</style>
