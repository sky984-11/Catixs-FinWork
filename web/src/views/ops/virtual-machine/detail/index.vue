<template>
  <AppPage :show-footer="false">
    <div class="vm-detail" :style="themeStyle">
      <n-button text class="back-link" @click="back"
        ><template #icon><TheIcon icon="mdi:arrow-left" /></template>返回虚拟机列表</n-button
      >
      <n-alert v-if="error" type="error" :title="error" class="error-banner"
        ><n-button text @click="load">重新加载</n-button></n-alert
      >
      <n-skeleton v-if="loading && !vm" height="180px" :sharp="false" />
      <template v-if="vm">
        <header class="detail-header">
          <div class="identity">
            <span class="machine-icon"
              ><TheIcon :icon="isContainer ? 'mdi:cube-outline' : 'mdi:monitor'" :size="27"
            /></span>
            <div>
              <div class="title-line">
                <h1>{{ vm.name || `VM ${vmid}` }}</h1>
                <n-tag round :bordered="false" :type="status.tone" size="small">{{
                  status.label
                }}</n-tag>
              </div>
              <div class="subtitle">
                <span>#{{ vmid }}</span
                ><span>{{ vm.remote }} / {{ vm.node || '—' }}</span
                ><span><TheIcon :icon="os.icon" :size="14" />{{ os.label }}</span>
              </div>
            </div>
          </div>
          <n-space>
            <n-button secondary :loading="loading" :disabled="busy" @click="load"
              ><template #icon><TheIcon icon="mdi:refresh" /></template>刷新</n-button
            >
            <n-button secondary :disabled="busy || vm.template" @click="consoleVisible = true"
              ><template #icon><TheIcon icon="mdi:console" /></template>控制台</n-button
            >
            <n-button
              :type="vm.status === 'running' ? 'warning' : 'primary'"
              :loading="busy"
              :disabled="
                !['running', 'stopped'].includes(vm.status) || vm.template || Boolean(transition)
              "
              @click="requestAction(vm.status === 'running' ? 'stop' : 'start')"
              ><template #icon><TheIcon icon="mdi:power" /></template
              >{{ vm.status === 'running' ? '关机' : '开机' }}</n-button
            >
          </n-space>
        </header>
        <n-alert v-if="transition" type="info" :show-icon="false"
          >{{ transition }}，正在等待状态更新。</n-alert
        >
        <n-tabs v-model:value="tab" type="line" animated class="detail-tabs">
          <n-tab-pane name="overview" tab="概览">
            <div class="overview-grid">
              <div class="primary-column">
                <section class="detail-card">
                  <h2>运行状态</h2>
                  <div v-for="metric in metrics" :key="metric.label" class="metric-row">
                    <div class="row-label">
                      <TheIcon :icon="metric.icon" :size="17" />{{ metric.label }}
                    </div>
                    <div class="metric-value">
                      <strong>{{ metric.text }}</strong
                      ><n-progress
                        v-if="metric.percent !== null"
                        type="line"
                        :percentage="metric.percent"
                        :show-indicator="false"
                        :height="5"
                        :color="metric.percent >= 90 ? theme.errorColor : theme.primaryColor"
                      />
                    </div>
                  </div>
                  <div class="data-row">
                    <span><TheIcon icon="mdi:clock-outline" />运行时间</span
                    ><strong>{{ uptime }}</strong>
                  </div>
                </section>
                <section class="detail-card">
                  <h2>配置</h2>
                  <div v-for="item in configuration" :key="item.label" class="data-row">
                    <span><TheIcon :icon="item.icon" />{{ item.label }}</span
                    ><strong>{{ item.value }}</strong>
                  </div>
                </section>
              </div>
              <div class="secondary-column">
                <section class="detail-card">
                  <h2>连接信息</h2>
                  <div class="data-row">
                    <span><TheIcon icon="mdi:account-outline" />用户</span
                    ><strong>{{ vm.customer_name || '未分配' }}</strong>
                  </div>
                  <div class="ip-details">
                    <span class="row-label"><TheIcon icon="mdi:ip-network-outline" />IP 地址</span
                    ><span v-if="!ips.length" class="muted">暂未获取 IP</span>
                    <div v-for="ip in ips" :key="ip" class="ip-row">
                      <code>{{ ip }}</code
                      ><n-tooltip
                        ><template #trigger
                          ><n-button
                            quaternary
                            circle
                            size="tiny"
                            aria-label="复制IP"
                            @click="copyIp(ip)"
                            ><template #icon
                              ><TheIcon
                                icon="mdi:content-copy"
                                :size="14" /></template></n-button></template
                        >复制 IP</n-tooltip
                      >
                    </div>
                  </div>
                  <div class="data-row">
                    <span><TheIcon icon="mdi:server-network" />节点</span
                    ><strong>{{ vm.node || vm.remote }}</strong>
                  </div>
                  <div class="data-row">
                    <span><TheIcon icon="mdi:calendar-outline" />创建时间</span
                    ><strong>{{ createdTime(vm.created_at) }}</strong>
                  </div>
                  <n-button
                    secondary
                    block
                    :loading="ipLoading"
                    class="ip-refresh"
                    @click="refreshIps"
                    >获取 IP 地址</n-button
                  >
                </section>
                <section class="detail-card note-card">
                  <h2>备注</h2>
                  <p>{{ config?.description || vm.remark || '暂无备注' }}</p>
                </section>
              </div>
            </div>
          </n-tab-pane>
          <n-tab-pane name="insights" tab="监控" display-directive="if"
            ><div class="monitor-pane"><VmMonitor v-if="vm.name" /></div
          ></n-tab-pane>
          <n-tab-pane name="network" tab="网络与磁盘">
            <n-alert v-if="configError" type="warning" :title="configError" />
            <section class="detail-card">
              <h2>网络接口</h2>
              <n-empty v-if="!config?.networks?.length" description="暂无网络接口数据" />
              <div v-for="nic in config?.networks || []" :key="nic.key" class="hardware-item">
                <strong>{{ nic.key }}</strong
                ><span>{{ nic.model || '—' }} · {{ nic.bridge || '—' }}</span
                ><code>{{ nic.macaddr || '—' }}</code
                ><span>VLAN {{ nic.vlan ?? '—' }} · MTU {{ nic.mtu ?? '默认' }}</span
                ><span
                  >{{ nic.rate ? `${nic.rate} MB/s` : '不限速' }} · 防火墙{{
                    nic.firewall ? '已启用' : '未启用'
                  }}</span
                >
              </div>
            </section>
            <section class="detail-card">
              <h2>磁盘</h2>
              <n-empty v-if="!config?.disks?.length" description="暂无磁盘数据" />
              <div v-for="disk in config?.disks || []" :key="disk.key" class="hardware-item">
                <strong>{{ disk.key }}</strong
                ><span>{{ disk.size_gb }} GiB</span
                ><code>{{ disk.volume || disk.storage || '—' }}</code>
              </div>
            </section>
          </n-tab-pane>
          <n-tab-pane name="settings" tab="设置">
            <section class="detail-card">
              <h2>常规设置</h2>
              <div class="setting-row">
                <div>
                  <strong>资源与用户</strong>
                  <p>调整 CPU、内存、磁盘、网络及所属用户。</p>
                </div>
                <n-button secondary :disabled="busy || isContainer" @click="edit"
                  >编辑配置</n-button
                >
              </div>
              <div class="setting-row">
                <div>
                  <strong>重启虚拟机</strong>
                  <p>向虚拟机发送重启请求。</p>
                </div>
                <n-button
                  secondary
                  :disabled="busy || vm.status !== 'running' || vm.template || Boolean(transition)"
                  @click="requestAction('reboot')"
                  >重启</n-button
                >
              </div>
              <div class="setting-row">
                <div>
                  <strong>迁移节点</strong>
                  <p>选择目标节点并查看迁移任务进度。</p>
                </div>
                <n-button secondary :disabled="busy" @click="migrate">迁移</n-button>
              </div>
            </section>
            <section class="detail-card danger-card">
              <h2>删除虚拟机</h2>
              <div class="setting-row">
                <div>
                  <strong>永久删除 {{ vm.name }}</strong>
                  <p>删除虚拟机及其磁盘前，请确认数据已备份。</p>
                </div>
                <n-button type="error" secondary :disabled="busy" @click="requestAction('delete')"
                  >删除</n-button
                >
              </div>
            </section>
          </n-tab-pane>
        </n-tabs>
        <n-alert v-if="configError && tab === 'overview'" type="warning" :title="configError" />
      </template>
      <n-modal
        v-model:show="confirmation.show"
        preset="card"
        :title="confirmation.title"
        style="width: min(460px, calc(100vw - 32px))"
        :closable="!busy"
        :mask-closable="!busy"
        :close-on-esc="!busy"
      >
        <p>
          {{
            confirmation.action === 'delete'
              ? '此操作无法恢复。请输入虚拟机名称以确认删除：'
              : `确认${confirmation.title}？`
          }}
          <strong>{{ vm?.name }}</strong>
        </p>
        <n-input
          v-if="confirmation.action === 'delete'"
          v-model:value="confirmation.name"
          :disabled="busy"
          placeholder="虚拟机名称"
        />
        <template #footer
          ><div class="confirm-footer">
            <CButton show-cancel :disabled="busy" @cancel="confirmation.show = false" /><CButton
              show-save
              :save-text="confirmation.title"
              :save-loading="busy"
              :disabled="
                busy || (confirmation.action === 'delete' && confirmation.name !== vm?.name)
              "
              @save="executeAction"
            /></div
        ></template>
      </n-modal>
      <n-modal
        v-model:show="consoleVisible"
        preset="card"
        :title="`${vm?.name || '虚拟机'} · 控制台`"
        style="width: min(1200px, 96vw)"
        ><NoVncConsole
          v-if="consoleVisible"
          :remote="remote"
          :vmid="vmid"
          :node="vm?.node || ''"
          :type="vmType"
      /></n-modal>
    </div>
  </AppPage>
</template>

<script setup>
import { waitForVmPower, mergeVmRuntime } from '../utils/power.mjs'
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMessage, useThemeVars } from 'naive-ui'
import api from '@/api'
import TheIcon from '@/components/icon/TheIcon.vue'
import CButton from '@/components/public/CButton.vue'
import NoVncConsole from '../NoVncConsole.vue'
import VmMonitor from '../monitor/index.vue'
import { bytes, percent, vmStatus, vmOs, vmIps, createdTime, numeric } from '../utils/display.mjs'

defineOptions({ name: '虚拟机详情' })
const route = useRoute()
const router = useRouter()
const message = useMessage()
const theme = useThemeVars()
const themeStyle = computed(() => ({
  '--surface': theme.value.cardColor,
  '--border': theme.value.borderColor,
  '--muted': theme.value.textColor3,
  '--text': theme.value.textColor1,
}))
const remote = computed(() => String(route.query.remote || ''))
const vmid = computed(() => Number(route.query.vmid))
const vmType = computed(() => String(route.query.type || 'pve-qemu'))
const vm = ref(null)
const config = ref(null)
const configError = ref('')
const loading = ref(false)
const busy = ref(false)
const ipLoading = ref(false)
const error = ref('')
const transition = ref('')
const consoleVisible = ref(false)
const tab = ref('overview')
const confirmation = reactive({ show: false, action: '', title: '', name: '' })
let generation = 0
let disposed = false
let timer
let transitionDeadline = 0
let expectedStatus = ''
const isContainer = computed(() => vmType.value === 'pve-lxc')
const status = computed(() =>
  transition.value ? { label: transition.value, tone: 'info' } : vmStatus(vm.value)
)
const os = computed(() => vmOs(vm.value))
const ips = computed(() => vmIps(vm.value))
const uptime = computed(() => {
  const seconds = numeric(vm.value?.uptime)
  if (seconds === null) return '—'
  const days = Math.floor(seconds / 86400)
  return `${days ? `${days}天 ` : ''}${Math.floor((seconds % 86400) / 3600)}小时 ${Math.floor(
    (seconds % 3600) / 60
  )}分钟`
})
const metrics = computed(() => [
  {
    label: 'CPU',
    icon: 'mdi:cpu-64-bit',
    percent: vm.value?.cpu == null ? null : Math.min(100, numeric(vm.value?.cpu) || 0),
    text: vm.value?.cpu == null ? '—' : `${vm.value.cpu}% · ${vm.value.maxcpu || '—'} vCPU`,
  },
  {
    label: '内存',
    icon: 'mdi:memory',
    percent: percent(vm.value?.mem, vm.value?.maxmem),
    text: `${bytes(vm.value?.mem)} / ${bytes(vm.value?.maxmem)}`,
  },
  {
    label: '磁盘',
    icon: 'mdi:harddisk',
    percent: percent(vm.value?.disk, vm.value?.maxdisk),
    text: `${bytes(vm.value?.disk)} / ${bytes(vm.value?.maxdisk)}`,
  },
])
const configuration = computed(() => [
  {
    label: 'vCPU',
    icon: 'mdi:cpu-64-bit',
    value: `${vm.value?.maxcpu || '—'} 核`,
  },
  {
    label: '内存',
    icon: 'mdi:memory',
    value: bytes(vm.value?.maxmem),
  },
  { label: '磁盘', icon: 'mdi:harddisk', value: bytes(vm.value?.maxdisk) },
  { label: '系统', icon: os.value.icon, value: os.value.label },
  {
    label: '类型',
    icon: 'mdi:cube-outline',
    value: isContainer.value ? 'LXC 容器' : 'QEMU 虚拟机',
  },
])
function params() {
  return {
    remote: remote.value,
    vmid: vmid.value,
    type: vmType.value,
    node: vm.value?.node || route.query.node || undefined,
  }
}
function back() {
  router.push({
    path: '/ops/virtual-machine',
    query: { selected_node: route.query.selected_node || remote.value },
  })
}
function edit() {
  router.push({
    path: '/virtual-machine/edit',
    query: {
      ...params(),
      name: vm.value?.name,
      selected_node: route.query.selected_node || remote.value,
      return_path: '/virtual-machine/detail',
    },
  })
}
function migrate() {
  router.push({
    path: '/ops/virtual-machine',
    query: { selected_node: remote.value, vmid: vmid.value, action: 'migrate' },
  })
}
async function copyIp(value) {
  try {
    await navigator.clipboard.writeText(value)
    message.success('IP 已复制')
  } catch {
    message.error('复制失败，请手动选择 IP 复制')
  }
}
function schedule() {
  clearTimeout(timer)
  if (!disposed)
    timer = setTimeout(
      async () => {
        if (!document.hidden && !busy.value && !loading.value) await load(false)
        else schedule()
      },
      transition.value ? 3000 : 10000
    )
}
async function load(includeConfig = true) {
  if (loading.value) return
  if (!remote.value || !Number.isInteger(vmid.value) || vmid.value <= 0) {
    error.value = '缺少有效的节点或虚拟机编号'
    return
  }
  const token = generation
  loading.value = true
  try {
    const results = await Promise.allSettled([
      api.virtualMachineApi.pveVms({ node: remote.value, vmid: vmid.value }),
      includeConfig ? api.virtualMachineApi.vmConfig(params()) : Promise.resolve(null),
    ])
    if (disposed || token !== generation || busy.value) return
    if (results[0].status === 'rejected') throw results[0].reason
    const row = results[0].value.data?.items?.find(
      (item) => String(item.vmid) === String(vmid.value) && item.remote === remote.value
    )
    if (!row) {
      vm.value = null
      throw new Error('虚拟机不存在或当前不可访问')
    }
    if (includeConfig) {
      configError.value = results[1].status === 'rejected' ? '读取配置失败，可刷新重试' : ''
      config.value = results[1].status === 'fulfilled' ? results[1].value?.data || null : null
    }
    const oldIps = vmIps(vm.value)
    vm.value = {
      ...row,
      ips: vmIps(row).length ? vmIps(row) : oldIps,
      os_type: config.value?.os_type || row.os_type,
      created_at: config.value?.created_at || row.created_at,
    }
    error.value = ''
    if (transition.value && expectedStatus && row.status === expectedStatus) {
      transition.value = ''
      expectedStatus = ''
    }
    if (transition.value && Date.now() > transitionDeadline) {
      transition.value = ''
      expectedStatus = ''
      message.warning('任务已提交，请刷新确认最终状态')
    }
    if (route.query.name !== vm.value.name)
      await router.replace({ query: { ...route.query, name: vm.value.name } })
  } catch (err) {
    if (token === generation && !disposed) error.value = err.message || '读取虚拟机失败'
  } finally {
    if (token === generation && !disposed) {
      loading.value = false
      schedule()
    }
  }
}
async function refreshIps() {
  if (ipLoading.value) return
  const token = generation
  ipLoading.value = true
  try {
    const response = await api.virtualMachineApi.pveVmIps({ node: remote.value })
    if (disposed || token !== generation) return
    const row = response.data?.items?.find(
      (item) => item.remote === remote.value && String(item.vmid) === String(vmid.value)
    )
    if (vm.value) vm.value = { ...vm.value, ips: row ? vmIps(row) : [] }
  } catch (err) {
    if (!disposed) message.error(err.message || '读取 IP 失败')
  } finally {
    if (token === generation) ipLoading.value = false
  }
}
function requestAction(action) {
  if (action === 'delete' && vm.value?.status !== 'stopped') {
    message.warning('请先关机并确认状态后再删除')
    return
  }
  Object.assign(confirmation, {
    show: true,
    action,
    title: { start: '开机', stop: '关机', reboot: '重启', delete: '删除虚拟机' }[action],
    name: '',
  })
}
async function executeAction() {
  if (busy.value) return
  const action = confirmation.action
  if (action === 'delete' && confirmation.name !== vm.value?.name) return
  busy.value = true
  try {
    if (action === 'delete') {
      await api.virtualMachineApi.deleteVm({
        ...params(),
        status: vm.value.status,
        name: vm.value.name,
      })
      try {
        sessionStorage.removeItem('ops.virtualMachine.pageCache')
      } catch {
        /* Storage can be disabled by the browser. */
      }
      confirmation.show = false
      message.success('虚拟机已删除')
      back()
      return
    }
    if (action === 'reboot') await api.virtualMachineApi.rebootVm(params())
    else {
      const token = generation
      const row = { ...vm.value }
      const response = await api.virtualMachineApi.powerVm({ ...params(), action })
      if (disposed || token !== generation) return
      confirmation.show = false
      transition.value = action === 'start' ? '启动中' : '关机中'
      const completed = await waitForVmPower({
        api: api.virtualMachineApi,
        row,
        upid: response.data?.upid,
        target: action === 'start' ? 'running' : 'stopped',
        cancelled: () => disposed || token !== generation,
        update: (current) => {
          vm.value = mergeVmRuntime(vm.value, current)
        },
      })
      if (disposed || token !== generation) return
      message[completed ? 'success' : 'warning'](
        completed ? '操作完成' : '等待状态超时，请刷新确认'
      )
      transition.value = ''
      return
    }
    confirmation.show = false
    transition.value =
      action === 'reboot' ? '重启任务已提交' : action === 'start' ? '启动中' : '关机中'
    expectedStatus = action === 'reboot' ? '' : action === 'start' ? 'running' : 'stopped'
    transitionDeadline = Date.now() + (action === 'reboot' ? 30000 : 120000)
    schedule()
    message.success('操作已提交')
  } catch (err) {
    transition.value = ''
    if (!disposed) message.error(err.message || '操作失败')
  } finally {
    busy.value = false
  }
}
watch(
  () => `${remote.value}|${vmid.value}|${vmType.value}`,
  () => {
    generation += 1
    clearTimeout(timer)
    vm.value = null
    config.value = null
    error.value = ''
    loading.value = false
    ipLoading.value = false
    transition.value = ''
    consoleVisible.value = false
    load()
  },
  { immediate: true }
)
onBeforeUnmount(() => {
  disposed = true
  generation += 1
  clearTimeout(timer)
})
</script>

<style scoped>
.vm-detail {
  max-width: 1200px;
  margin: 0 auto;
  width: 100%;
  padding: 26px;
  box-sizing: border-box;
  color: var(--text);
}
.back-link {
  margin-bottom: 22px;
  color: var(--muted);
}
.detail-header,
.identity,
.title-line,
.subtitle,
.subtitle span {
  display: flex;
  align-items: center;
}
.detail-header {
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 20px;
  margin-bottom: 28px;
}
.identity {
  gap: 15px;
  min-width: 0;
}
.identity > div {
  min-width: 0;
}
.machine-icon {
  display: grid;
  place-items: center;
  width: 52px;
  height: 52px;
  border: 1px solid var(--border);
  border-radius: 12px;
  flex-shrink: 0;
}
.title-line {
  gap: 12px;
  flex-wrap: wrap;
}
h1 {
  margin: 0;
  font-size: 25px;
  font-weight: 600;
  overflow-wrap: anywhere;
}
.subtitle {
  gap: 12px;
  flex-wrap: wrap;
  font-size: 12px;
  color: var(--muted);
  margin-top: 6px;
}
.subtitle span {
  gap: 5px;
}
.detail-tabs {
  margin-top: 16px;
}
.overview-grid {
  display: grid;
  grid-template-columns: 3fr 2fr;
  align-items: start;
  gap: 20px;
  padding-top: 12px;
}
.primary-column,
.secondary-column {
  display: grid;
  gap: 18px;
  min-width: 0;
}
.detail-card {
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--surface);
  padding: 20px;
  margin-bottom: 18px;
  min-width: 0;
}
.overview-grid .detail-card {
  margin-bottom: 0;
}
h2 {
  font-size: 15px;
  font-weight: 600;
  margin: 0 0 14px;
}
.data-row,
.metric-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 13px 0;
  border-bottom: 1px solid var(--border);
  font-size: 13px;
}
.data-row:last-child,
.metric-row:last-child {
  border-bottom: 0;
}
.data-row > span,
.row-label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--muted);
  flex-shrink: 0;
}
.data-row strong {
  text-align: right;
  overflow-wrap: anywhere;
  min-width: 0;
  font-weight: 500;
}
.metric-value {
  width: 65%;
  text-align: right;
}
.metric-value strong {
  display: block;
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}
.ip-details {
  display: grid;
  gap: 9px;
  padding: 12px 0;
}
.ip-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
code {
  font-size: 12px;
  overflow-wrap: anywhere;
}
.ip-refresh {
  margin-top: 15px;
}
.muted,
.note-card p,
.setting-row p {
  color: var(--muted);
  font-size: 13px;
}
.note-card p {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  line-height: 1.8;
  margin: 0;
}
.hardware-item {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  padding: 15px 0;
  border-top: 1px solid var(--border);
  font-size: 13px;
}
.setting-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
  padding: 13px 0;
  border-top: 1px solid var(--border);
}
.setting-row p {
  margin: 5px 0 0;
}
.danger-card h2 {
  color: #d03050;
}
.confirm-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
.error-banner {
  margin-bottom: 18px;
}
.monitor-pane {
  height: 650px;
  overflow: hidden;
}
.monitor-pane :deep(.monitor-frame-wrap) {
  min-height: 0;
  height: 520px;
}
.monitor-pane :deep(.monitor-page) {
  height: 100%;
  min-height: 0;
}
@media (max-width: 760px) {
  .vm-detail {
    padding: 16px;
  }
  .overview-grid {
    grid-template-columns: 1fr;
  }
  .detail-card {
    padding: 16px;
  }
  .identity {
    gap: 10px;
  }
  h1 {
    font-size: 21px;
  }
  .subtitle {
    gap: 8px;
  }
  .setting-row {
    flex-wrap: wrap;
  }
}
</style>
