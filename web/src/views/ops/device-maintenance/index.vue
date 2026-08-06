<template>
  <AppPage :show-footer="false">
    <div class="maintenance-page">
      <section class="summary-grid">
        <article>
          <span class="summary-icon orange"><TheIcon icon="mdi:server-network" :size="21" /></span>
          <div><small>待维护设备</small><strong>{{ devices.length }}</strong></div>
        </article>
        <article>
          <span class="summary-icon blue"><TheIcon icon="mdi:clipboard-clock-outline" :size="21" /></span>
          <div><small>待处理计划</small><strong>{{ pendingTaskCount }}</strong></div>
        </article>
        <article>
          <span class="summary-icon green"><TheIcon icon="mdi:progress-wrench" :size="21" /></span>
          <div><small>处理中</small><strong>{{ processingTaskCount }}</strong></div>
        </article>
        <article>
          <span class="summary-icon gray"><TheIcon icon="mdi:bell-check-outline" :size="21" /></span>
          <div><small>已通知</small><strong>{{ sentTaskCount }}</strong></div>
        </article>
      </section>

      <section class="workspace-panel">
        <n-tabs v-model:value="activeTab" type="line" animated>
          <n-tab-pane name="devices" tab="待维护设备">
            <div class="table-toolbar">
              <div class="filter-row">
                <n-input v-model:value="deviceKeyword" clearable placeholder="搜索资产编号、设备名、IP、地区或机房">
                  <template #prefix><TheIcon icon="mdi:magnify" :size="17" /></template>
                </n-input>
              </div>
              <n-space>
                <n-button secondary circle :loading="loading" title="刷新" @click="fetchOverview">
                  <template #icon><TheIcon icon="mdi:refresh" :size="18" /></template>
                </n-button>
              </n-space>
            </div>
            <div class="maintenance-table-wrap">
              <n-data-table
                :loading="loading"
                :columns="deviceColumns"
                :data="filteredDevices"
                :pagination="devicePagination"
                :row-key="(row) => row.id"
                :scroll-x="1180"
                flex-height
                striped
              >
                <template #empty><n-empty description="暂无待维护设备" /></template>
              </n-data-table>
            </div>
          </n-tab-pane>

          <n-tab-pane name="tasks" tab="维护计划">
            <div class="table-toolbar">
              <div class="filter-row task-filter">
                <n-input v-model:value="taskKeyword" clearable placeholder="搜索计划、设备、负责人、地区、机柜或U数">
                  <template #prefix><TheIcon icon="mdi:magnify" :size="17" /></template>
                </n-input>
                <n-select v-model:value="taskStatus" clearable placeholder="计划状态" :options="statusOptions" />
              </div>
              <n-space>
                <n-button secondary circle :loading="loading" title="刷新" @click="fetchOverview">
                  <template #icon><TheIcon icon="mdi:refresh" :size="18" /></template>
                </n-button>
                <n-button type="primary" round @click="openTaskEditor()">
                  <template #icon><TheIcon icon="mdi:plus" :size="18" /></template>
                  新增维护计划
                </n-button>
              </n-space>
            </div>
            <div class="maintenance-table-wrap">
              <n-data-table
                :loading="loading"
                :columns="taskColumns"
                :data="filteredTasks"
                :pagination="taskPagination"
                :row-key="(row) => row.id"
                :scroll-x="1680"
                flex-height
                striped
              >
                <template #empty><n-empty description="暂无维护计划" /></template>
              </n-data-table>
            </div>
          </n-tab-pane>
        </n-tabs>
      </section>

      <n-modal
        v-model:show="taskEditor.show"
        preset="card"
        title="新增维护计划"
        class="task-modal"
        style="width: min(680px, calc(100vw - 40px))"
        :bordered="false"
      >
        <n-form label-placement="left" label-width="88" size="small" :model="taskEditor.form">
          <n-form-item label="维护设备" required>
            <n-select
              v-model:value="taskEditor.form.device_ids"
              multiple
              filterable
              clearable
              max-tag-count="responsive"
              :options="deviceOptions"
              placeholder="选择待维护设备"
            />
          </n-form-item>
          <n-form-item label="计划标题" required>
            <n-input v-model:value="taskEditor.form.title" maxlength="200" show-count placeholder="维护计划标题" />
          </n-form-item>
          <n-form-item label="负责人">
            <n-select
              v-model:value="taskEditor.form.assignee_ids"
              multiple
              filterable
              clearable
              max-tag-count="responsive"
              :options="userOptions"
              placeholder="选择飞书通知接收人"
            />
          </n-form-item>
          <div class="form-grid">
            <n-form-item label="计划时间">
              <n-date-picker
                v-model:formatted-value="taskEditor.form.due_at"
                type="datetime"
                format="yyyy-MM-dd HH:mm"
                value-format="yyyy-MM-dd'T'HH:mm"
                clearable
                style="width: 100%"
              />
            </n-form-item>
            <n-form-item label="优先级">
              <n-select v-model:value="taskEditor.form.priority" :options="priorityOptions" />
            </n-form-item>
          </div>
          <n-form-item label="维护说明">
            <n-input
              v-model:value="taskEditor.form.description"
              type="textarea"
              :autosize="{ minRows: 3, maxRows: 6 }"
              placeholder="维护内容、处理要求、注意事项"
            />
          </n-form-item>
          <n-form-item label="备注">
            <n-input v-model:value="taskEditor.form.remark" maxlength="500" show-count placeholder="内部备注" />
          </n-form-item>
          <div class="modal-footer">
            <n-checkbox v-model:checked="taskEditor.form.notify">创建后立即发送飞书通知</n-checkbox>
            <n-space>
              <n-button @click="taskEditor.show = false">取消</n-button>
              <n-button type="primary" :loading="saving" @click="submitTask">保存</n-button>
            </n-space>
          </div>
        </n-form>
      </n-modal>
    </div>
  </AppPage>
</template>

<script setup>
import { computed, h, onMounted, reactive, ref } from 'vue'
import { NButton, NSpace, NTag, useMessage } from 'naive-ui'
import { useRouter } from 'vue-router'
import api from '@/api'

const message = useMessage()
const router = useRouter()
const loading = ref(false)
const saving = ref(false)
const activeTab = ref('devices')
const deviceKeyword = ref('')
const taskKeyword = ref('')
const taskStatus = ref(null)
const devices = ref([])
const tasks = ref([])
const users = ref([])

const devicePagination = reactive({ pageSize: 20, showSizePicker: true, pageSizes: [20, 50, 100] })
const taskPagination = reactive({ pageSize: 20, showSizePicker: true, pageSizes: [20, 50, 100] })

const taskEditor = reactive({
  show: false,
  form: initialTaskForm(),
})

const statusOptions = [
  { label: '待处理', value: 'pending' },
  { label: '处理中', value: 'processing' },
  { label: '已完成', value: 'done' },
  { label: '已取消', value: 'cancelled' },
]

const priorityOptions = [
  { label: '低', value: 'low' },
  { label: '中', value: 'medium' },
  { label: '高', value: 'high' },
  { label: '紧急', value: 'urgent' },
]

const statusMap = {
  pending: { label: '待处理', type: 'warning' },
  processing: { label: '处理中', type: 'info' },
  done: { label: '已完成', type: 'success' },
  cancelled: { label: '已取消', type: 'default' },
}

const priorityMap = {
  low: { label: '低', type: 'default' },
  medium: { label: '中', type: 'info' },
  high: { label: '高', type: 'warning' },
  urgent: { label: '紧急', type: 'error' },
}

const notifyMap = {
  pending: { label: '未通知', type: 'default' },
  sent: { label: '已通知', type: 'success' },
  failed: { label: '通知失败', type: 'error' },
}

const pendingTaskCount = computed(() => tasks.value.filter((item) => item.status === 'pending').length)
const processingTaskCount = computed(() => tasks.value.filter((item) => item.status === 'processing').length)
const sentTaskCount = computed(() => tasks.value.filter((item) => item.notify_status === 'sent').length)

const deviceOptions = computed(() =>
  devices.value.map((item) => ({
    label: compactDeviceLabel(item),
    value: item.id,
  }))
)

const userOptions = computed(() =>
  users.value.map((item) => ({
    label: item.label || item.username || `#${item.id}`,
    value: item.id,
  }))
)

const filteredDevices = computed(() => {
  const keyword = normalize(deviceKeyword.value)
  if (!keyword) return devices.value
  return devices.value.filter((item) =>
    normalize(
      [
        item.name,
        item.brand,
        item.model,
        item.mgmt_ip,
        item.business_ip,
        item.region,
        item.location,
        item.cabinet,
        item.remark,
      ].join(' ')
    ).includes(keyword)
  )
})

const filteredTasks = computed(() => {
  const keyword = normalize(taskKeyword.value)
  return tasks.value.filter((item) => {
    if (taskStatus.value && item.status !== taskStatus.value) return false
    if (!keyword) return true
    const device = item.device || {}
    return normalize(
      [
        item.title,
        item.description,
        item.assignee_names,
        item.remark,
        ...(item.devices || []).flatMap((device) => [
          device.name,
          device.mgmt_ip,
          device.region,
          device.cabinet,
          device.u_position,
        ]),
      ].join(' ')
    ).includes(keyword)
  })
})

const deviceColumns = [
  {
    title: '设备名称',
    key: 'name',
    width: 170,
    ellipsis: { tooltip: true },
    sorter: textSorter('name'),
    render(row) {
      return renderDeviceLink(row)
    },
  },
  { title: '管理IP', key: 'mgmt_ip', width: 150, ellipsis: { tooltip: true }, sorter: textSorter('mgmt_ip') },
  {
    title: '型号',
    key: 'model',
    width: 180,
    ellipsis: { tooltip: true },
    sorter: (a, b) => compareText(deviceModelText(a), deviceModelText(b)),
    render(row) {
      return deviceModelText(row) || '-'
    },
  },
  { title: '地区', key: 'region', width: 130, ellipsis: { tooltip: true }, sorter: textSorter('region') },
  { title: '机柜', key: 'cabinet', width: 130, ellipsis: { tooltip: true }, sorter: textSorter('cabinet') },
  {
    title: 'U数',
    key: 'u_position',
    width: 100,
    sorter: numberSorter('u_position'),
    render(row) {
      return formatU(row)
    },
  },
  { title: '备注', key: 'remark', minWidth: 180, ellipsis: { tooltip: true }, sorter: textSorter('remark') },
  {
    title: '操作',
    key: 'actions',
    width: 130,
    fixed: 'right',
    render(row) {
      return h(
        NButton,
        { size: 'small', type: 'primary', secondary: true, onClick: () => openTaskEditor(row) },
        { default: () => '添加计划' }
      )
    },
  },
]

const taskColumns = [
  {
    title: '状态',
    key: 'status',
    width: 100,
    sorter: textSorter('status'),
    render(row) {
      return renderTag(statusMap[row.status] || statusMap.pending)
    },
  },
  {
    title: '优先级',
    key: 'priority',
    width: 90,
    sorter: textSorter('priority'),
    render(row) {
      return renderTag(priorityMap[row.priority] || priorityMap.medium)
    },
  },
  { title: '计划标题', key: 'title', width: 220, ellipsis: { tooltip: true }, sorter: textSorter('title') },
  {
    title: '设备',
    key: 'device',
    width: 210,
    ellipsis: { tooltip: true },
    sorter: (a, b) => compareText(taskFirstDeviceName(a), taskFirstDeviceName(b)),
    render(row) {
      const selectedDevices = row.devices || []
      if (!selectedDevices.length) return `#${row.device_id}`
      const links = selectedDevices.slice(0, 3).map((device) => renderDeviceLink(device))
      if (selectedDevices.length > 3) {
        links.push(h('span', { class: 'device-more-count' }, `+${selectedDevices.length - 3}`))
      }
      return h(NSpace, { size: 6, wrap: false }, { default: () => links })
    },
  },
  {
    title: '管理IP',
    key: 'mgmt_ip',
    width: 150,
    ellipsis: { tooltip: true },
    sorter: (a, b) => compareText(taskFirstDeviceValue(a, 'mgmt_ip'), taskFirstDeviceValue(b, 'mgmt_ip')),
    render(row) {
      return taskFirstDeviceValue(row, 'mgmt_ip') || '-'
    },
  },
  {
    title: '地区',
    key: 'region',
    width: 130,
    ellipsis: { tooltip: true },
    sorter: (a, b) => compareText(taskFirstDeviceValue(a, 'region'), taskFirstDeviceValue(b, 'region')),
    render(row) {
      return taskFirstDeviceValue(row, 'region') || '-'
    },
  },
  {
    title: '机柜',
    key: 'cabinet',
    width: 130,
    ellipsis: { tooltip: true },
    sorter: (a, b) => compareText(taskFirstDeviceValue(a, 'cabinet'), taskFirstDeviceValue(b, 'cabinet')),
    render(row) {
      return taskFirstDeviceValue(row, 'cabinet') || '-'
    },
  },
  {
    title: 'U数',
    key: 'u_position',
    width: 100,
    sorter: (a, b) => compareNumber(taskFirstDeviceValue(a, 'u_position'), taskFirstDeviceValue(b, 'u_position')),
    render(row) {
      return formatU((row.devices || [])[0] || {})
    },
  },
  { title: '负责人', key: 'assignee_names', width: 160, ellipsis: { tooltip: true }, sorter: textSorter('assignee_names') },
  { title: '计划时间', key: 'due_at', width: 150, sorter: textSorter('due_at') },
  {
    title: '通知',
    key: 'notify_status',
    width: 120,
    sorter: textSorter('notify_status'),
    render(row) {
      return renderTag(notifyMap[row.notify_status] || notifyMap.pending)
    },
  },
  { title: '通知结果', key: 'notify_message', width: 190, ellipsis: { tooltip: true }, sorter: textSorter('notify_message') },
  {
    title: '操作',
    key: 'actions',
    width: 260,
    fixed: 'right',
    render(row) {
      const actions = []
      if (row.status === 'pending') {
        actions.push(actionButton('开始处理', () => updateStatus(row, 'processing')))
      }
      if (row.status !== 'done' && row.status !== 'cancelled') {
        actions.push(actionButton('完成', () => updateStatus(row, 'done'), 'success'))
      }
      actions.push(actionButton('通知', () => sendNotify(row), 'primary'))
      return h(NSpace, { size: 8 }, { default: () => actions })
    },
  },
]

function initialTaskForm(device = null) {
  return {
    device_ids: device?.id ? [device.id] : [],
    title: '',
    description: '',
    assignee_ids: [],
    due_at: null,
    priority: 'medium',
    remark: '',
    notify: false,
  }
}

function normalize(value) {
  return String(value || '').trim().toLowerCase()
}

function deviceLocation(device) {
  return [
    device.region,
    device.cabinet,
    device.u_position ? `U${device.u_position}` : '',
  ]
    .filter(Boolean)
    .join(' / ')
}

function compactDeviceLabel(device) {
  return [device?.name, device?.mgmt_ip].filter(Boolean).join(' / ') || `#${device?.id || ''}`
}

function deviceRouteId(device) {
  return device?.device_db_id || device?.parent_id || device?.id
}

function normalizeDeviceDbId(device) {
  const source = deviceRouteId(device)
  const parsed = Number(String(source || '').split(':', 1)[0])
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null
}

function findDeviceLocation(device) {
  const deviceId = normalizeDeviceDbId(device)
  if (!deviceId) return device
  return devices.value.find((item) => normalizeDeviceDbId(item) === deviceId && item.cabinet_id) || device
}

async function loadDeviceLocation(device) {
  const deviceId = normalizeDeviceDbId(device)
  if (!deviceId) return device
  try {
    const res = await api.assetApi.getDevice({ device_id: deviceId })
    return { ...device, ...(res.data || {}) }
  } catch (error) {
    return device
  }
}

async function openDeviceInCabinet(device) {
  const localDevice = findDeviceLocation(device)
  const targetDevice = localDevice?.cabinet_id ? localDevice : await loadDeviceLocation(localDevice)
  const deviceId = normalizeDeviceDbId(targetDevice)
  if (!targetDevice?.cabinet_id || !deviceId) {
    message.warning('该设备缺少机柜定位信息')
    return
  }
  const query = {
    cabinet_id: String(targetDevice.cabinet_id),
    device_id: String(deviceId),
  }
  if (targetDevice.region_id) query.region_id = String(targetDevice.region_id)
  router.push({ path: '/asset/cabinet', query })
}

function renderDeviceLink(device) {
  const label = compactDeviceLabel(device)
  return h(
    NButton,
    {
      text: true,
      type: 'primary',
      title: deviceLocation(device) || label,
      class: 'device-link-button',
      onClick: () => openDeviceInCabinet(device),
    },
    { default: () => label }
  )
}

function deviceModelText(device) {
  return [device?.brand, device?.model].filter(Boolean).join(' / ')
}

function formatU(device) {
  if (!device?.u_position) return '-'
  return device.u_height && Number(device.u_height) > 1
    ? `U${device.u_position} / ${device.u_height}U`
    : `U${device.u_position}`
}

function compareText(a, b) {
  return String(a || '').localeCompare(String(b || ''), 'zh-Hans-CN')
}

function compareNumber(a, b) {
  return Number(a || 0) - Number(b || 0)
}

function textSorter(key) {
  return (a, b) => compareText(a?.[key], b?.[key])
}

function numberSorter(key) {
  return (a, b) => compareNumber(a?.[key], b?.[key])
}

function taskFirstDevice(row) {
  return (row.devices || [])[0] || {}
}

function taskFirstDeviceName(row) {
  return compactDeviceLabel(taskFirstDevice(row))
}

function taskFirstDeviceValue(row, key) {
  return taskFirstDevice(row)?.[key]
}

function renderTag(meta) {
  return h(NTag, { size: 'small', round: true, type: meta.type }, { default: () => meta.label })
}

function actionButton(label, onClick, type = 'default') {
  return h(
    NButton,
    { size: 'small', secondary: true, type, onClick },
    { default: () => label }
  )
}

function openTaskEditor(device = null) {
  taskEditor.form = initialTaskForm(device)
  taskEditor.show = true
}

async function fetchOverview() {
  loading.value = true
  try {
    const res = await api.deviceMaintenanceApi.overview()
    const data = res.data || {}
    devices.value = data.devices || []
    tasks.value = data.tasks || []
    users.value = data.users || []
  } finally {
    loading.value = false
  }
}

async function submitTask() {
  if (!taskEditor.form.device_ids.length) {
    message.warning('请选择维护设备')
    return
  }
  if (!normalize(taskEditor.form.title)) {
    message.warning('请填写维护计划标题')
    return
  }
  saving.value = true
  try {
    const res = await api.deviceMaintenanceApi.createTask(taskEditor.form)
    message.success(res.msg || '维护计划已创建')
    taskEditor.show = false
    activeTab.value = 'tasks'
    await fetchOverview()
  } finally {
    saving.value = false
  }
}

async function updateStatus(row, status) {
  const res = await api.deviceMaintenanceApi.updateTaskStatus(row.id, { status, remark: row.remark || '' })
  message.success(res.msg || '维护计划状态已更新')
  await fetchOverview()
}

async function sendNotify(row) {
  const res = await api.deviceMaintenanceApi.notifyTask(row.id)
  if (res.code === 200) {
    message.success(res.msg || '飞书通知已发送')
  }
  await fetchOverview()
}

onMounted(fetchOverview)
</script>

<style scoped>
.maintenance-page {
  display: flex;
  height: 100%;
  min-height: 0;
  flex-direction: column;
  gap: 12px;
  overflow: hidden;
}

.summary-grid {
  display: grid;
  flex: 0 0 auto;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.summary-grid article {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 76px;
  padding: 14px 16px;
  border: 1px solid var(--n-border-color);
  border-radius: 8px;
  background: var(--n-color);
}

.summary-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  border-radius: 8px;
}

.summary-icon.orange {
  color: #b54708;
  background: #fff4e5;
}

.summary-icon.blue {
  color: #175cd3;
  background: #eaf2ff;
}

.summary-icon.green {
  color: #067647;
  background: #e8f8ef;
}

.summary-icon.gray {
  color: #475467;
  background: #f2f4f7;
}

.summary-grid small {
  display: block;
  margin-bottom: 4px;
  color: #667085;
  font-size: 13px;
}

.summary-grid strong {
  color: #101828;
  font-size: 24px;
  line-height: 1;
}

.workspace-panel {
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  padding: 16px;
  border: 1px solid var(--n-border-color);
  border-radius: 8px;
  background: var(--n-color);
  overflow: hidden;
}

.workspace-panel :deep(.n-tabs),
.workspace-panel :deep(.n-tabs .n-tabs-pane-wrapper),
.workspace-panel :deep(.n-tabs .n-tab-pane),
.workspace-panel :deep(.n-tab-pane),
.workspace-panel :deep(.n-data-table) {
  min-height: 0;
}

.workspace-panel :deep(.n-tabs),
.workspace-panel :deep(.n-tabs .n-tabs-pane-wrapper),
.workspace-panel :deep(.n-tabs .n-tab-pane),
.workspace-panel :deep(.n-tab-pane) {
  display: flex;
  flex: 1;
  flex-direction: column;
}

.maintenance-table-wrap {
  display: flex;
  min-height: 0;
  flex: 1;
  overflow: hidden;
}

.maintenance-table-wrap :deep(.n-data-table) {
  width: 100%;
  height: 100%;
}

.maintenance-table-wrap :deep(.n-data-table .n-data-table-base-table) {
  min-height: 0;
}

.table-toolbar {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.filter-row {
  display: grid;
  grid-template-columns: minmax(260px, 420px);
  gap: 10px;
  width: min(100%, 560px);
}

.task-filter {
  grid-template-columns: minmax(260px, 420px) 150px;
  width: min(100%, 620px);
}

.form-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 180px;
  gap: 12px;
}

.modal-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-top: 4px;
}

.device-link-button {
  max-width: 100%;
}

.device-link-button :deep(.n-button__content) {
  display: block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-more-count {
  color: #667085;
}

@media (max-width: 900px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .table-toolbar,
  .modal-footer {
    align-items: stretch;
    flex-direction: column;
  }

  .filter-row,
  .task-filter,
  .form-grid {
    grid-template-columns: 1fr;
    width: 100%;
  }
}
</style>
