<template>
  <CButton show-save save-text="机柜联动" @save="open" />
  <n-modal
    v-model:show="visible"
    preset="card"
    title="机柜客户机器 · Ping 自动纳管"
    style="width: min(1320px, 96vw)"
    :mask-closable="!busy"
    :closable="!busy"
  >
    <n-alert type="info" class="gap">
      每 5
      分钟同步在用、待维护及故障客户机器，四节点分别纳管。未指定监控地址时默认使用设备或节点自己的
      IPMI 地址。 Ping 由 Zabbix 执行；失败提醒使用通知管理的默认接收人，同一问题每天最多提醒一次。
    </n-alert>
    <n-alert v-if="error || form.last_error" type="error" class="gap">{{
      error || form.last_error
    }}</n-alert>
    <div class="gap settings">
      <n-form-item label="自动纳管"
        ><n-switch v-model:value="form.enabled" :disabled="busy || !editable"
      /></n-form-item>
      <n-form-item label="Ping 模板"
        ><n-select
          v-model:value="form.template_id"
          :options="templates"
          :disabled="busy || !editable"
      /></n-form-item>
      <n-form-item label="主机组"
        ><n-select
          v-model:value="form.group_id"
          :options="groups"
          filterable
          :disabled="busy || !editable"
      /></n-form-item>
      <n-form-item label="新建主机的执行节点"
        ><n-select v-model:value="form.proxy_id" :options="proxies" :disabled="busy || !editable"
      /></n-form-item>
    </div>
    <n-space justify="space-between" class="gap">
      <span class="muted"
        >共 {{ rows.length }} 台 · 已纳管 {{ managed }} 台 · 待处理
        {{ rows.length - managed }} 台</span
      >
      <span role="status" aria-live="polite" class="muted">{{ status }}</span>
    </n-space>
    <n-input
      v-model:value="keyword"
      placeholder="搜索客户、设备、机柜、地址"
      clearable
      class="gap"
    />
    <n-data-table
      :columns="columns"
      :data="filtered"
      :row-key="(row) => row.key"
      :loading="loading"
      :scroll-x="1420"
      :max-height="420"
      :pagination="{ pageSize: 20 }"
      size="small"
    />
    <p class="muted">
      指定地址留空即使用 IPMI 地址。已有主机保留原代理及其他监控；停用、重复地址会提示处理。
      关闭联动或设备下架仅退出 FinWork 自动范围，不删除 Zabbix 主机和历史。
    </p>
    <template #footer>
      <n-space justify="end">
        <CButton show-save save-text="刷新状态" :disabled="busy" @save="refresh" />
        <CButton
          v-if="editable"
          show-save
          save-text="保存并同步"
          :loading="saving"
          :disabled="busy || !ready"
          @save="save"
        />
      </n-space>
    </template>
  </n-modal>
</template>

<script setup>
import { computed, h, reactive, ref } from 'vue'
import { NButton, NInput, NTag, NTooltip } from 'naive-ui'
import TheIcon from '@/components/icon/TheIcon.vue'
import CButton from '@/components/public/CButton.vue'
import api from '@/api/monitor-events'

const props = defineProps({ editable: Boolean })
const emit = defineEmits(['updated'])
const visible = ref(false)
const loading = ref(false)
const saving = ref(false)
const ready = ref(false)
const error = ref('')
const status = ref('')
const keyword = ref('')
const rows = ref([])
const templates = ref([])
const groups = ref([])
const proxies = ref([{ label: 'Zabbix Server', value: '' }])
const form = reactive({
  revision: 0,
  enabled: false,
  template_id: '',
  group_id: '',
  proxy_id: '',
  overrides: {},
  last_error: '',
})
const busy = computed(() => loading.value || saving.value)
const managed = computed(() => rows.value.filter((r) => r.status === 'managed').length)
const filtered = computed(() =>
  rows.value.filter((r) =>
    [r.customer, r.name, r.cabinet, r.ip]
      .join(' ')
      .toLowerCase()
      .includes(keyword.value.toLowerCase())
  )
)
const columns = [
  { title: '客户', key: 'customer', width: 150, resizable: true, ellipsis: { tooltip: true } },
  { title: '设备 / 节点', key: 'name', width: 190, resizable: true, ellipsis: { tooltip: true } },
  {
    title: '机房 / 机柜 / U 位',
    key: 'position',
    width: 210,
    resizable: true,
    render: (r) => `${r.location} / ${r.cabinet} / ${r.position}`,
  },
  { title: '当前地址', key: 'ip', width: 150, resizable: true, render: (r) => r.ip || '未填写' },
  {
    title: '指定监控地址',
    key: 'override',
    width: 190,
    resizable: true,
    render: (r) =>
      h(NInput, {
        value: form.overrides[r.key] || '',
        placeholder: '使用 IPMI 地址',
        size: 'small',
        disabled: busy.value || !props.editable,
        'onUpdate:value': (value) => {
          if (value.trim()) form.overrides[r.key] = value.trim()
          else delete form.overrides[r.key]
        },
      }),
  },
  {
    title: '纳管状态',
    key: 'status',
    width: 110,
    resizable: true,
    render: (r) =>
      h(
        NTag,
        {
          type: r.status === 'managed' ? 'success' : r.status === 'failed' ? 'error' : 'warning',
          size: 'small',
          bordered: false,
        },
        {
          default: () =>
            ({ managed: '已纳管', failed: '纳管失败', pending: '待同步', excluded: '已移除' }[
              r.status
            ] || r.status),
        }
      ),
  },
  {
    title: '失败原因 / 通知状态',
    key: 'reason',
    width: 320,
    resizable: true,
    render: (r) => [r.reason, r.notification_error].filter(Boolean).join('；') || '—',
  },
  {
    title: '操作',
    key: 'actions',
    width: 100,
    fixed: 'right',
    render: (row) =>
      row.status === 'excluded' && row.host_id
        ? h(NTooltip, null, {
            trigger: () =>
              h(
                NButton,
                {
                  size: 'small',
                  circle: true,
                  quaternary: true,
                  disabled: busy.value || !props.editable,
                  'aria-label': '恢复自动纳管',
                  onClick: (event) => {
                    event.stopPropagation()
                    restore(row)
                  },
                },
                { icon: () => h(TheIcon, { icon: 'mdi:restore', size: 17 }) }
              ),
            default: () => '恢复自动纳管',
          })
        : null,
  },
]

async function restore(row) {
  if (busy.value || !props.editable) return
  saving.value = true
  error.value = ''
  try {
    const current = (await api.cabinet()).data
    const result = (await api.restoreAutomaticHost(row.host_id, current.revision)).data
    form.revision = result.revision
    await api.syncCabinet()
    await refresh()
    status.value = '已恢复自动纳管，稍后刷新查看结果'
  } catch (e) {
    error.value = e?.message || '恢复失败，请重试'
  } finally {
    saving.value = false
  }
}

async function refresh() {
  loading.value = true
  error.value = ''
  try {
    const result = (await api.cabinet()).data
    rows.value = result.rows
    form.last_error = result.last_error
    emit('updated')
    status.value = result.last_checked
      ? `最近检查：${new Date(result.last_checked * 1000).toLocaleString()}`
      : '等待首次同步'
    return result
  } catch (e) {
    error.value = e?.message || '读取失败，请重试'
  } finally {
    loading.value = false
  }
}
async function open() {
  visible.value = true
  ready.value = false
  const result = await refresh()
  if (!result) return
  Object.assign(form, result, { overrides: { ...result.overrides } })
  loading.value = true
  try {
    const choices = (await api.cabinetOptions()).data
    templates.value = choices.templates.map((t) => ({ label: t.name, value: t.templateid }))
    groups.value = choices.groups.map((g) => ({ label: g.name, value: g.groupid }))
    proxies.value = [
      { label: 'Zabbix Server', value: '' },
      ...choices.proxies.map((p) => ({ label: p.name, value: p.proxyid })),
    ]
    form.template_id ||= templates.value.find((t) => t.label === 'IP ICMP Ping')?.value || ''
    form.group_id ||= groups.value.find((g) => g.label === 'IP PING监控')?.value || ''
    ready.value = true
  } catch (e) {
    error.value = e?.message || '读取 Zabbix 配置失败'
  } finally {
    loading.value = false
  }
}
async function save() {
  saving.value = true
  error.value = ''
  try {
    const payload = Object.fromEntries(
      ['revision', 'enabled', 'template_id', 'group_id', 'proxy_id', 'overrides'].map((key) => [
        key,
        form[key],
      ])
    )
    const result = (await api.saveCabinet(payload)).data
    form.revision = result.revision
    if (form.enabled) await api.syncCabinet()
    status.value = form.enabled ? '已保存，后台同步中；稍后刷新状态' : '已保存，自动纳管已关闭'
  } catch (e) {
    error.value = e?.message || '保存失败，请重试'
  } finally {
    saving.value = false
  }
}
defineExpose({ open })
</script>

<style scoped>
.gap {
  margin-bottom: 14px;
}
.settings {
  display: grid;
  grid-template-columns: 110px repeat(3, minmax(160px, 1fr));
  gap: 16px;
}
.muted {
  color: #8b95a5;
  font-size: 12px;
}
@media (max-width: 760px) {
  .settings {
    grid-template-columns: 1fr;
    gap: 0;
  }
}
</style>
