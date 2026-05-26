<script setup>
import { h, onMounted, ref, resolveDirective, withDirectives } from 'vue'
import {
  NButton,
  NDataTable,
  NEmpty,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NModal,
  NPopconfirm,
  NSelect,
  NSwitch,
  NTag,
} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import CrudModal from '@/components/table/CrudModal.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import { useCRUD } from '@/composables'
import { renderIcon } from '@/utils'
import api from '@/api'

defineOptions({ name: '定时任务' })

const $table = ref(null)
const queryItems = ref({})
const vPermission = resolveDirective('permission')
const logVisible = ref(false)
const logLoading = ref(false)
const logRows = ref([])
const selectedTask = ref(null)
const selectedLog = ref(null)

const taskTypeOptions = [
  { label: '脚本任务', value: 'script' },
  { label: '数据库备份', value: 'db_backup' },
  { label: '命令任务', value: 'command' },
]
const scheduleTypeOptions = [
  { label: '每天', value: 'daily' },
  { label: '每周', value: 'weekly' },
  { label: '间隔', value: 'interval' },
]
const weekdayOptions = [
  { label: '周一', value: 0 },
  { label: '周二', value: 1 },
  { label: '周三', value: 2 },
  { label: '周四', value: 3 },
  { label: '周五', value: 4 },
  { label: '周六', value: 5 },
  { label: '周日', value: 6 },
]
const enabledOptions = [
  { label: '启用', value: true },
  { label: '停用', value: false },
]

const {
  modalVisible,
  modalTitle,
  modalLoading,
  handleSave,
  modalForm,
  modalFormRef,
  handleEdit,
  handleDelete,
  handleAdd,
} = useCRUD({
  name: '定时任务',
  initForm: {
    task_type: 'script',
    script_path: '',
    command: '',
    schedule_type: 'weekly',
    day_of_week: 6,
    hour: 2,
    minute: 0,
    interval_minutes: null,
    is_enabled: true,
  },
  doCreate: api.createTask,
  doUpdate: api.updateTask,
  doDelete: api.deleteTask,
  refresh: () => $table.value?.handleSearch(),
})

onMounted(() => {
  $table.value?.handleSearch()
})

const taskRules = {
  name: [{ required: true, message: '请输入任务名称', trigger: ['input', 'blur'] }],
  task_type: [{ required: true, message: '请选择任务类型', trigger: ['change'] }],
  schedule_type: [{ required: true, message: '请选择调度类型', trigger: ['change'] }],
}

function weekdayLabel(value) {
  return weekdayOptions.find((item) => item.value === value)?.label || '-'
}

function scheduleText(row) {
  if (row.schedule_type === 'interval') return `每 ${row.interval_minutes || '-'} 分钟`
  const time = `${String(row.hour).padStart(2, '0')}:${String(row.minute).padStart(2, '0')}`
  if (row.schedule_type === 'daily') return `每天 ${time}`
  return `${weekdayLabel(row.day_of_week)} ${time}`
}

async function handleToggle(row, value) {
  await api.toggleTask({ id: row.id, is_enabled: value })
  $message.success(value ? '已启用' : '已停用')
  $table.value?.handleSearch()
}

async function handleRun(row) {
  await api.runTask({ id: row.id })
  $message.success('执行完成')
  $table.value?.handleSearch()
}

async function openLogs(row) {
  selectedTask.value = row
  selectedLog.value = null
  logVisible.value = true
  logLoading.value = true
  try {
    const res = await api.getTaskLogs({ task_id: row.id, page: 1, page_size: 50 })
    logRows.value = res?.data || []
    selectedLog.value = logRows.value[0] || null
  } finally {
    logLoading.value = false
  }
}

async function reloadLogs() {
  if (!selectedTask.value) return
  await openLogs(selectedTask.value)
}

async function clearLogs() {
  if (!selectedTask.value) return
  await window.$dialog?.warning({
    title: '清理日志',
    content: `确定清空「${selectedTask.value.name}」的执行日志吗？`,
    positiveText: '清理',
    negativeText: '取消',
    onPositiveClick: async () => {
      const res = await api.clearTaskLogs({ task_id: selectedTask.value.id })
      window.$message?.success(`已清理 ${res?.data?.deleted_count || 0} 条日志`)
      await reloadLogs()
    },
  })
}

function getLogText(log) {
  if (!log) return ''
  return [
    log.stderr ? `STDERR\n${log.stderr}` : '',
    log.error ? `ERROR\n${log.error}` : '',
    log.stdout ? `STDOUT\n${log.stdout}` : '',
  ].filter(Boolean).join('\n\n')
}

const logColumns = [
  { title: '执行时间', key: 'started_at', width: 160 },
  {
    title: '状态',
    key: 'status',
    width: 90,
    align: 'center',
    render(row) {
      return h(
        NTag,
        { size: 'small', type: row.status === 'success' ? 'success' : 'error' },
        { default: () => (row.status === 'success' ? '成功' : '失败') }
      )
    },
  },
  { title: '退出码', key: 'return_code', width: 80, align: 'center', render: (row) => row.return_code ?? '-' },
  { title: '耗时', key: 'duration_ms', width: 90, render: (row) => `${row.duration_ms || 0} ms` },
  { title: '摘要', key: 'message', minWidth: 220, ellipsis: { tooltip: true } },
  {
    title: '操作',
    key: 'actions',
    width: 80,
    align: 'center',
    render(row) {
      return h(NButton, { size: 'small', secondary: true, onClick: () => (selectedLog.value = row) }, { default: () => '查看' })
    },
  },
]

const columns = [
  {
    title: '任务名称',
    key: 'name',
    minWidth: 130,
    ellipsis: { tooltip: true },
  },
  {
    title: '类型',
    key: 'task_type',
    width: 110,
    align: 'center',
    render(row) {
      const label = taskTypeOptions.find((item) => item.value === row.task_type)?.label || row.task_type
      return h(NTag, { size: 'small', type: row.task_type === 'db_backup' ? 'success' : 'info' }, { default: () => label })
    },
  },
  {
    title: '调度',
    key: 'schedule_type',
    width: 130,
    align: 'center',
    render: (row) => scheduleText(row),
  },
  {
    title: '启用',
    key: 'is_enabled',
    width: 90,
    align: 'center',
    render(row) {
      return withDirectives(
        h(NSwitch, {
          value: row.is_enabled,
          'onUpdate:value': (value) => handleToggle(row, value),
        }),
        [[vPermission, 'post/api/v1/task/toggle']]
      )
    },
  },
  {
    title: '上次状态',
    key: 'last_status',
    width: 110,
    align: 'center',
    render(row) {
      if (!row.last_status) return '-'
      return h(
        NTag,
        { size: 'small', type: row.last_status === 'success' ? 'success' : 'error' },
        { default: () => (row.last_status === 'success' ? '成功' : '失败') }
      )
    },
  },
  {
    title: '上次执行',
    key: 'last_run_at',
    width: 170,
    ellipsis: { tooltip: true },
  },
  {
    title: '下次执行',
    key: 'next_run_at',
    width: 170,
    ellipsis: { tooltip: true },
  },
  {
    title: '执行结果',
    key: 'last_message',
    minWidth: 180,
    ellipsis: { tooltip: true },
  },
  {
    title: '操作',
    key: 'actions',
    width: 310,
    align: 'center',
    fixed: 'right',
    render(row) {
      return [
        withDirectives(
          h(
            NButton,
            {
              size: 'small',
              type: 'primary',
              style: 'margin-right: 8px;',
              onClick: () => handleEdit(row),
            },
            { default: () => '编辑', icon: renderIcon('material-symbols:edit', { size: 16 }) }
          ),
          [[vPermission, 'post/api/v1/task/update']]
        ),
        withDirectives(
          h(
            NButton,
            {
              size: 'small',
              type: 'warning',
              style: 'margin-right: 8px;',
              onClick: () => handleRun(row),
            },
            { default: () => '执行', icon: renderIcon('material-symbols:play-arrow', { size: 16 }) }
          ),
          [[vPermission, 'post/api/v1/task/run']]
        ),
        withDirectives(
          h(
            NButton,
            {
              size: 'small',
              secondary: true,
              style: 'margin-right: 8px;',
              onClick: () => openLogs(row),
            },
            { default: () => '日志', icon: renderIcon('mdi:text-box-search-outline', { size: 16 }) }
          ),
          [[vPermission, 'get/api/v1/task/logs']]
        ),
        h(
          NPopconfirm,
          { onPositiveClick: () => handleDelete({ id: row.id }) },
          {
            trigger: () =>
              withDirectives(
                h(
                  NButton,
                  { size: 'small', type: 'error' },
                  { default: () => '删除', icon: renderIcon('material-symbols:delete-outline', { size: 16 }) }
                ),
                [[vPermission, 'delete/api/v1/task/delete']]
              ),
            default: () => h('div', {}, '确定删除该定时任务吗？'),
          }
        ),
      ]
    },
  },
]
</script>

<template>
  <CommonPage show-footer title="定时任务列表">
    <template #action>
      <NButton
        v-permission="'post/api/v1/task/create'"
        class="float-right mr-15"
        type="primary"
        @click="handleAdd"
      >
        <TheIcon icon="material-symbols:add" :size="18" class="mr-5" />新增任务
      </NButton>
    </template>

    <CrudTable
      ref="$table"
      v-model:query-items="queryItems"
      :columns="columns"
      :get-data="api.getTaskList"
      :scroll-x="1300"
    >
      <template #queryBar>
        <QueryBarItem label="任务名称" :label-width="70">
          <NInput
            v-model:value="queryItems.name"
            clearable
            type="text"
            placeholder="请输入任务名称"
            @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="任务类型" :label-width="70">
          <NSelect
            v-model:value="queryItems.task_type"
            style="width: 180px"
            :options="taskTypeOptions"
            clearable
            placeholder="请选择任务类型"
          />
        </QueryBarItem>
        <QueryBarItem label="状态" :label-width="40">
          <NSelect
            v-model:value="queryItems.is_enabled"
            style="width: 140px"
            :options="enabledOptions"
            clearable
            placeholder="请选择状态"
          />
        </QueryBarItem>
      </template>
    </CrudTable>

    <CrudModal
      v-model:visible="modalVisible"
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
        :rules="taskRules"
      >
        <NFormItem label="任务名称" path="name">
          <NInput v-model:value="modalForm.name" clearable placeholder="请输入任务名称" />
        </NFormItem>
        <NFormItem label="任务类型" path="task_type">
          <NSelect v-model:value="modalForm.task_type" :options="taskTypeOptions" />
        </NFormItem>
        <NFormItem v-if="modalForm.task_type !== 'command'" label="脚本路径" path="script_path">
          <NInput v-model:value="modalForm.script_path" clearable placeholder="scripts/backup_database.py" />
        </NFormItem>
        <NFormItem v-if="modalForm.task_type === 'command'" label="执行命令" path="command">
          <NInput v-model:value="modalForm.command" clearable placeholder="请输入命令" />
        </NFormItem>
        <NFormItem label="调度类型" path="schedule_type">
          <NSelect v-model:value="modalForm.schedule_type" :options="scheduleTypeOptions" />
        </NFormItem>
        <NFormItem v-if="modalForm.schedule_type === 'weekly'" label="执行日期" path="day_of_week">
          <NSelect v-model:value="modalForm.day_of_week" :options="weekdayOptions" />
        </NFormItem>
        <NFormItem v-if="modalForm.schedule_type !== 'interval'" label="执行时间">
          <div class="time-row">
            <NInputNumber v-model:value="modalForm.hour" :min="0" :max="23" />
            <span>:</span>
            <NInputNumber v-model:value="modalForm.minute" :min="0" :max="59" />
          </div>
        </NFormItem>
        <NFormItem v-if="modalForm.schedule_type === 'interval'" label="间隔分钟" path="interval_minutes">
          <NInputNumber v-model:value="modalForm.interval_minutes" :min="1" />
        </NFormItem>
        <NFormItem label="是否启用" path="is_enabled">
          <NSwitch v-model:value="modalForm.is_enabled" />
        </NFormItem>
      </NForm>
    </CrudModal>

    <NModal v-model:show="logVisible" preset="card" :title="`${selectedTask?.name || '任务'} - 执行日志`" class="task-log-modal">
      <template #header-extra>
        <NButton
          v-permission="'delete/api/v1/task/logs'"
          size="small"
          type="error"
          secondary
          :disabled="!logRows.length"
          @click="clearLogs"
        >
          清理日志
        </NButton>
      </template>
      <NDataTable
        :columns="logColumns"
        :data="logRows"
        :loading="logLoading"
        :bordered="false"
        :pagination="false"
        :max-height="280"
        size="small"
      />
      <div v-if="selectedLog" class="log-detail">
        <div class="log-meta">
          <span>Started: {{ selectedLog.started_at || '-' }}</span>
          <span>Finished: {{ selectedLog.finished_at || '-' }}</span>
          <span>Command: {{ selectedLog.command || '-' }}</span>
        </div>
        <pre>{{ getLogText(selectedLog) || selectedLog.message || 'No output' }}</pre>
      </div>
      <NEmpty v-else-if="!logLoading" description="暂无执行日志" />
    </NModal>
  </CommonPage>
</template>

<style scoped>
.time-row {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  gap: 8px;
  width: 180px;
}

.task-log-modal {
  width: min(1100px, 94vw);
}

.log-detail {
  margin-top: 14px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: #0f172a;
  color: #e5e7eb;
}

.log-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  border-bottom: 1px solid rgb(255 255 255 / 12%);
  padding: 10px 12px;
  color: #cbd5e1;
  font-size: 12px;
}

.log-detail pre {
  max-height: 360px;
  margin: 0;
  overflow: auto;
  padding: 12px;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
