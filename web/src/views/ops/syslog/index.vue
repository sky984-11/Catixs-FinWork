<template>
  <AppPage :show-footer="false">
    <div class="syslog-page">
      <section class="toolbar-band">
        <div class="filter-grid">
          <n-select
            v-model:value="filters.device"
            filterable
            clearable
            placeholder="选择设备 IP"
            :options="deviceOptions"
            :loading="loading.devices"
            @update:value="handleDeviceChange"
          />
          <n-select
            v-model:value="filters.file"
            filterable
            clearable
            placeholder="日志文件"
            :options="fileOptions"
            :loading="loading.files"
          />
          <n-input v-model:value="filters.keyword" clearable placeholder="关键字" @keyup.enter="fetchLogs">
            <template #prefix>
              <TheIcon icon="mdi:magnify" :size="18" />
            </template>
          </n-input>
          <n-select v-model:value="filters.level" clearable placeholder="级别" :options="levelOptions" />
          <n-select v-model:value="filters.vendor" clearable placeholder="厂商" :options="vendorOptions" />
          <n-input-number v-model:value="filters.tail" :min="100" :max="20000" :step="100" placeholder="读取行数" />
        </div>
        <div class="actions">
          <n-button secondary round @click="resetFilters">
            <template #icon>
              <TheIcon icon="mdi:refresh" :size="18" />
            </template>
            重置
          </n-button>
          <n-button type="primary" round :disabled="!canQuery" :loading="loading.logs" @click="fetchLogs">
            <template #icon>
              <TheIcon icon="mdi:file-search-outline" :size="18" />
            </template>
            查询
          </n-button>
          <n-button secondary round :disabled="!canQuery" :loading="loading.raw" @click="openRawModal">
            <template #icon>
              <TheIcon icon="mdi:console-line" :size="18" />
            </template>
            原始日志
          </n-button>
        </div>
      </section>

      <section class="summary-band">
        <article>
          <span>日志主机</span>
          <strong>45.67.201.229</strong>
        </article>
        <article>
          <span>设备目录</span>
          <strong>{{ deviceOptions.length }}</strong>
        </article>
        <article>
          <span>当前文件</span>
          <strong>{{ filters.file || '未选择' }}</strong>
        </article>
        <article>
          <span>匹配日志</span>
          <strong>{{ pagination.itemCount }}</strong>
        </article>
      </section>

      <section class="content-panel">
        <div class="panel-head">
          <div>
            <span class="eyebrow">Syslog</span>
            <h2>日志解析列表</h2>
          </div>
          <n-tag type="info" round>支持华为 / 锐捷 / 思科 / Juniper / Arista</n-tag>
        </div>
        <n-data-table
          remote
          :loading="loading.logs"
          :columns="columns"
          :data="logs"
          :pagination="pagination"
          :row-key="(row) => row.id"
          @update:page="handlePageChange"
          @update:page-size="handlePageSizeChange"
        />
      </section>

      <n-modal v-model:show="rawModal.show" preset="card" title="原始日志" class="raw-modal">
        <n-spin :show="loading.raw">
          <pre class="raw-content">{{ rawModal.content || '暂无日志内容' }}</pre>
        </n-spin>
      </n-modal>
    </div>
  </AppPage>
</template>

<script setup>
import { computed, h, onMounted, reactive, ref } from 'vue'
import { NTag, useMessage } from 'naive-ui'
import api from '@/api'

const message = useMessage()

const loading = reactive({
  devices: false,
  files: false,
  logs: false,
  raw: false,
})

const filters = reactive({
  device: null,
  file: null,
  keyword: '',
  level: null,
  vendor: null,
  tail: 2000,
})

const logs = ref([])
const deviceOptions = ref([])
const fileOptions = ref([])
const rawModal = reactive({
  show: false,
  content: '',
})

const canQuery = computed(() => Boolean(filters.device && filters.file))

const pagination = reactive({
  page: 1,
  pageSize: 50,
  itemCount: 0,
  showSizePicker: true,
  pageSizes: [20, 50, 100, 200],
})

const levelOptions = [
  { label: 'Emergency', value: 'emergency' },
  { label: 'Alert', value: 'alert' },
  { label: 'Critical', value: 'critical' },
  { label: 'Error', value: 'error' },
  { label: 'Warning', value: 'warning' },
  { label: 'Notice', value: 'notice' },
  { label: 'Info', value: 'info' },
  { label: 'Debug', value: 'debug' },
  { label: 'Unknown', value: 'unknown' },
]

const vendorOptions = ['Huawei', 'Ruijie', 'Cisco', 'Juniper', 'Arista', 'Unknown'].map((item) => ({
  label: item,
  value: item,
}))

const levelTagMap = {
  emergency: 'error',
  alert: 'error',
  critical: 'error',
  error: 'error',
  warning: 'warning',
  notice: 'info',
  info: 'success',
  debug: 'default',
  unknown: 'default',
}

const columns = [
  { title: '时间', key: 'time', width: 170, ellipsis: { tooltip: true } },
  { title: '设备', key: 'device', width: 140 },
  { title: '来源主机', key: 'host', width: 160, ellipsis: { tooltip: true } },
  {
    title: '厂商',
    key: 'vendor',
    width: 110,
    render(row) {
      return h(NTag, { size: 'small', round: true }, { default: () => row.vendor || 'Unknown' })
    },
  },
  {
    title: '级别',
    key: 'level',
    width: 110,
    render(row) {
      return h(
        NTag,
        { size: 'small', round: true, type: levelTagMap[row.level] || 'default' },
        { default: () => row.level || 'unknown' }
      )
    },
  },
  { title: '日志内容', key: 'message', ellipsis: { tooltip: true } },
]

async function fetchDevices() {
  loading.devices = true
  try {
    const res = await api.syslogApi.devices()
    deviceOptions.value = res.data || []
  } finally {
    loading.devices = false
  }
}

async function fetchFiles() {
  if (!filters.device) {
    fileOptions.value = []
    return
  }
  loading.files = true
  try {
    const res = await api.syslogApi.files({ device: filters.device })
    fileOptions.value = (res.data || []).map((item) => ({
      label: `${item.name} (${formatBytes(item.size)}, ${item.mtime})`,
      value: item.name,
    }))
  } finally {
    loading.files = false
  }
}

async function fetchLogs() {
  if (!filters.device) {
    message.warning('请选择设备 IP')
    return
  }
  if (!filters.file) {
    message.warning('请选择日志文件')
    return
  }
  loading.logs = true
  try {
    const res = await api.syslogApi.logs({
      page: pagination.page,
      page_size: pagination.pageSize,
      device: filters.device,
      file: filters.file,
      keyword: filters.keyword || '',
      level: filters.level || '',
      vendor: filters.vendor || '',
      tail: filters.tail || 2000,
    })
    logs.value = res.data || []
    pagination.itemCount = res.total || 0
  } finally {
    loading.logs = false
  }
}

async function openRawModal() {
  if (!filters.device) {
    message.warning('请选择设备 IP')
    return
  }
  if (!filters.file) {
    message.warning('请选择日志文件')
    return
  }
  rawModal.show = true
  loading.raw = true
  try {
    const res = await api.syslogApi.raw({
      device: filters.device,
      file: filters.file,
      tail: Math.min(filters.tail || 300, 5000),
    })
    rawModal.content = res.data?.content || ''
  } finally {
    loading.raw = false
  }
}

function handleDeviceChange() {
  filters.file = null
  pagination.page = 1
  logs.value = []
  pagination.itemCount = 0
  fetchFiles()
}

function resetFilters() {
  filters.file = null
  filters.keyword = ''
  filters.level = null
  filters.vendor = null
  filters.tail = 2000
  pagination.page = 1
  if (canQuery.value) fetchLogs()
}

function handlePageChange(page) {
  pagination.page = page
  fetchLogs()
}

function handlePageSizeChange(pageSize) {
  pagination.pageSize = pageSize
  pagination.page = 1
  fetchLogs()
}

function formatBytes(value) {
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let size = Number(value || 0)
  let index = 0
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024
    index += 1
  }
  return `${size.toFixed(index ? 1 : 0)}${units[index]}`
}

onMounted(fetchDevices)
</script>

<style scoped>
.syslog-page {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 16px;
}

.toolbar-band,
.content-panel,
.summary-band article {
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.04);
}

.toolbar-band {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 14px;
}

.filter-grid {
  display: grid;
  grid-template-columns: 180px 260px minmax(220px, 1fr) 130px 130px 120px;
  gap: 10px;
}

.actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.summary-band {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.summary-band article {
  min-width: 0;
  padding: 14px 16px;
}

.summary-band span {
  display: block;
  color: #64748b;
  font-size: 13px;
}

.summary-band strong {
  display: block;
  overflow: hidden;
  margin-top: 6px;
  color: #0f172a;
  font-size: 20px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.content-panel {
  padding: 14px;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.panel-head h2 {
  margin: 4px 0 0;
  color: #0f172a;
  font-size: 18px;
}

.eyebrow {
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}

.raw-modal {
  width: min(1100px, 92vw);
}

.raw-content {
  max-height: 68vh;
  overflow: auto;
  border-radius: 6px;
  background: #0f172a;
  color: #dbeafe;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  line-height: 1.6;
  margin: 0;
  padding: 14px;
  white-space: pre-wrap;
  word-break: break-word;
}

html.dark .toolbar-band,
html.dark .content-panel,
html.dark .summary-band article {
  border-color: rgba(148, 163, 184, 0.2);
  background: rgba(17, 24, 39, 0.86);
}

html.dark .panel-head h2,
html.dark .summary-band strong {
  color: #e5e7eb;
}

html.dark .summary-band span,
html.dark .eyebrow {
  color: #94a3b8;
}

@media (max-width: 1100px) {
  .filter-grid,
  .summary-band {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 680px) {
  .filter-grid,
  .summary-band {
    grid-template-columns: 1fr;
  }

  .actions,
  .panel-head {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
