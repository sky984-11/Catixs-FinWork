<template>
  <AppPage>
    <n-card title="通知管理">
      <template #header-extra
        ><n-space>
          <CButton show-save save-text="刷新" :disabled="busy" @save="reload" />
          <CButton
            v-if="canPreview"
            show-save
            save-text="预览飞书卡片"
            :disabled="busy"
            @save="previewOpen = true"
          />
          <CButton
            v-if="canSave"
            show-save
            save-text="保存通知配置"
            :save-loading="saving"
            :disabled="busy || !ready"
            @save="save"
          /> </n-space
      ></template>
      <n-alert v-if="error" type="error" class="gap">{{ error }}</n-alert>
      <n-spin :show="loading">
        <n-space class="gap">
          <n-tag :type="form.enabled ? 'success' : 'default'">{{
            form.enabled ? '通知已启用' : '通知已关闭'
          }}</n-tag>
          <n-tag :type="metadata.feishu_configured ? 'success' : 'warning'"
            >飞书{{ metadata.feishu_configured ? '已配置' : '未配置' }}</n-tag
          >
          <n-tag :type="metadata.ai_configured ? 'success' : 'warning'"
            >AI{{ metadata.ai_configured ? '已配置' : '未配置，将使用规则建议' }}</n-tag
          >
        </n-space>
        <n-alert type="info" class="gap"
          >启用后约每分钟检查一次，只通知启用后新发生的纳管范围内事件及已通知事件的恢复。同一事件、状态、接收人只生成一条通知；关闭后停止发送，重新启用不补发旧告警。</n-alert
        >
        <n-form label-placement="top" class="form-grid" :disabled="busy || !canSave">
          <n-form-item label="启用飞书通知"><n-switch v-model:value="form.enabled" /></n-form-item>
          <n-form-item label="最低告警级别"
            ><n-select v-model:value="form.minimum_severity" :options="severityOptions"
          /></n-form-item>
          <n-form-item label="默认接收用户"
            ><n-select
              v-model:value="form.recipient_ids"
              :options="userOptions"
              filterable
              clearable
              multiple
              placeholder="选择 FinWork 用户，可通过飞书绑定身份或邮箱送达"
          /></n-form-item>
          <n-form-item label="通知分类"
            ><n-select
              v-model:value="form.category_keys"
              :options="categoryOptions"
              multiple
              clearable
              placeholder="不选择则通知全部平台分类"
          /></n-form-item>
          <n-form-item label="恢复时通知"
            ><n-switch v-model:value="form.notify_recovery"
          /></n-form-item>
          <n-form-item label="跳过被抑制的告警"
            ><n-switch v-model:value="form.skip_suppressed"
          /></n-form-item>
          <n-form-item label="附带 AI 排查建议"
            ><n-switch v-model:value="form.ai_enabled"
          /></n-form-item>
        </n-form>
        <section class="recipient-rules">
          <div class="recipient-heading">
            <h3>按分类配置接收人</h3>
            <div class="save-status" role="status" aria-live="polite">
              <span>{{ saving ? '正在保存…' : loading ? '正在刷新…' : categorySaveStatus }}</span>
              <n-tooltip
                ><template #trigger
                  ><n-button
                    size="small"
                    circle
                    quaternary
                    :disabled="busy"
                    :loading="loading"
                    aria-label="刷新通知配置"
                    @click.stop="reload"
                    ><template #icon
                      ><TheIcon icon="mdi:refresh" :size="17" /></template></n-button></template
                >刷新通知配置</n-tooltip
              >
            </div>
          </div>
          <p class="muted">
            分类开关和接收人变更后自动保存。未单独配置时使用默认接收人；单独配置留空表示不通知。其他通知设置需点击顶部保存按钮。
          </p>
          <div
            v-for="category in recipientCategoryOptions"
            :key="category.value"
            class="recipient-rule"
          >
            <div class="recipient-rule-name">
              <n-tag size="small" type="info">{{ category.label }}</n-tag
              ><span
                v-if="form.category_keys.length && !form.category_keys.includes(category.value)"
                class="muted"
                >不在当前通知范围</span
              >
            </div>
            <n-space align="center"
              ><n-switch
                :value="hasCategoryRule(category.value)"
                :disabled="busy || !canSave || !ready"
                @update:value="(value) => toggleCategoryRule(category.value, value)"
              /><span>{{
                hasCategoryRule(category.value) ? '单独配置' : '使用默认'
              }}</span></n-space
            >
            <n-select
              v-if="hasCategoryRule(category.value)"
              v-model:value="form.category_recipients[category.value]"
              :options="userOptions"
              multiple
              filterable
              clearable
              :disabled="busy || !canSave || !ready"
              placeholder="选择该分类接收用户（留空不通知）"
              @update:value="saveCategoryRecipients"
            />
            <div v-else class="muted">{{ defaultRecipientNames || '未设置默认接收人' }}</div>
          </div>
        </section>
        <p class="muted">
          AI 使用系统已配置的服务，分析告警摘要、相关主机/IP
          和当前指标。建议需人工核实，不执行操作；服务异常时回退为规则建议。接收人须处于飞书应用可见范围。
        </p>
        <p class="muted">
          最近轮询：{{ date(metadata.last_poll_at) }}
          <span v-if="metadata.enabled_since"> · 本次启用：{{ date(metadata.enabled_since) }}</span>
        </p>
        <n-alert v-if="metadata.last_error" type="warning" class="gap">{{
          metadata.last_error
        }}</n-alert>
      </n-spin>
    </n-card>
    <n-card v-if="canLogs" title="发送记录" class="gap">
      <template #header-extra
        ><n-space>
          <n-select
            v-model:value="logStatus"
            :options="statusOptions"
            clearable
            placeholder="全部状态"
            style="width: 150px"
            :disabled="logsLoading"
            @update:value="changeLogFilter"
          />
          <CButton
            show-save
            save-text="刷新记录"
            :disabled="logsLoading"
            @save="loadLogs"
          /> </n-space
      ></template>
      <n-alert v-if="logError" type="error" class="gap">{{ logError }}</n-alert>
      <n-data-table
        :columns="columns"
        :data="logs"
        :loading="logsLoading"
        :row-key="(row) => row.id"
        :scroll-x="1280"
        :max-height="400"
        striped
        size="small"
      />
      <n-pagination
        v-model:page="page"
        :item-count="total"
        :page-size="20"
        class="gap"
        @update:page="loadLogs"
      />
    </n-card>

    <n-modal
      v-model:show="previewOpen"
      preset="card"
      title="飞书卡片预览（不发送）"
      style="width: min(800px, calc(100vw - 24px))"
      :closable="!previewLoading"
      :mask-closable="!previewLoading"
      :close-on-esc="!previewLoading"
    >
      <n-space class="gap" align="center"
        ><n-input
          v-model:value="previewEventId"
          placeholder="事件 ID（留空使用示例）"
          :disabled="previewLoading" /><CButton
          show-save
          save-text="生成预览"
          :save-loading="previewLoading"
          :disabled="previewLoading"
          @save="preview"
      /></n-space>
      <p class="muted">
        预览使用已保存的 AI 配置，不发送飞书消息。可填写纳管范围内的事件 ID 查看实际建议。
      </p>
      <n-alert v-if="previewError" type="error" class="gap">{{ previewError }}</n-alert>
      <div v-if="previewData" class="card-preview">
        <h3 :class="previewData.card.header.template">
          {{ previewData.card.header.title.content }}
        </h3>
        <template v-for="(block, index) in previewData.card.elements" :key="index">
          <hr v-if="block.tag === 'hr'" class="card-divider" />
          <div v-else-if="block.fields" class="card-fields">
            <div v-for="(field, fieldIndex) in block.fields" :key="fieldIndex">
              <span class="muted">{{ field.text.content.split('\n')[0] }}</span>
              <div class="card-value">{{ field.text.content.split('\n').slice(1).join('\n') }}</div>
            </div>
          </div>
          <div
            v-else-if="block.tag === 'div' && block.text"
            class="card-text"
            :class="{ 'card-event': index === 0 }"
          >
            {{ block.text.content }}
          </div>
          <p v-else-if="block.tag === 'note'" class="muted card-note">
            {{ block.elements.map((e) => e.content).join(' ') }}
          </p>
          <div v-else-if="block.tag === 'action'" class="card-link">
            {{ block.actions[0].text.content }}
          </div>
        </template>
      </div>
    </n-modal>
    <n-modal
      v-model:show="detailOpen"
      preset="card"
      title="通知详情"
      style="width: min(760px, calc(100vw - 24px))"
    >
      <template v-if="selected"
        ><h3>{{ selected.event_name }}</h3>
        <p>
          {{ selected.user_name }} · {{ statusLabels[selected.status] }} · {{ selected.message }}
        </p>
        <strong v-if="selected.phase !== 'recovery'">{{
          selected.advice_source === 'ai' ? 'AI 排查建议' : '规则排查建议'
        }}</strong>
        <p v-if="selected.phase !== 'recovery'" class="advice">
          {{ selected.advice || '尚未生成建议' }}
        </p></template
      >
    </n-modal>
    <n-modal
      v-model:show="retryOpen"
      preset="card"
      title="确认重试通知"
      style="width: min(480px, calc(100vw - 24px))"
      :closable="!retrying"
      :mask-closable="!retrying"
      :close-on-esc="!retrying"
    >
      <p>
        发送失败可能是响应超时，请先确认接收人是否已经收到。确认后将重新排队发送给
        {{ selected?.user_name }}。
      </p>
      <n-alert v-if="retryError" type="error" class="gap">{{ retryError }}</n-alert>
      <template #footer
        ><CButton
          show-save
          show-cancel
          save-text="确认重试"
          :save-loading="retrying"
          :disabled="retrying"
          @save="retry"
          @cancel="retryOpen = false"
      /></template>
    </n-modal>
  </AppPage>
</template>

<script setup>
import { computed, h, onMounted, reactive, ref } from 'vue'
import { NButton, NSpace, NTag, NTooltip } from 'naive-ui'
import CButton from '@/components/public/CButton.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import api from '@/api/monitor-events'
import { usePermissionStore, useUserStore } from '@/store'

const user = useUserStore(),
  permissions = usePermissionStore()
const allowed = (path) => user.isSuperUser || permissions.apis.includes(path)
const canSave = computed(() => allowed('put/api/v1/monitor-events/notifications'))
const canLogs = computed(() => allowed('get/api/v1/monitor-events/notifications/deliveries'))
const canPreview = computed(() => allowed('post/api/v1/monitor-events/notifications/preview'))
const canRetry = computed(() =>
  allowed('post/api/v1/monitor-events/notifications/deliveries/{delivery_id}/retry')
)
const form = reactive({
  revision: 0,
  enabled: false,
  recipient_ids: [],
  category_recipients: {},
  category_keys: [],
  minimum_severity: 2,
  notify_recovery: true,
  skip_suppressed: true,
  ai_enabled: true,
})
const metadata = reactive({ users: [], categories: [] })
const loading = ref(false),
  saving = ref(false),
  ready = ref(false),
  error = ref('')
const busy = computed(() => loading.value || saving.value)
const userOptions = computed(() =>
  metadata.users.map((u) => ({
    label: `${u.name}${u.reachable ? '' : '（缺少飞书身份/邮箱）'}`,
    value: u.id,
    disabled: !u.reachable,
  }))
)
const categoryOptions = computed(() => [
  ...metadata.categories.map((c) => ({ label: c.label, value: c.key })),
  { label: '未分类', value: 'unclassified' },
])
const recipientCategoryOptions = computed(() => [
  ...categoryOptions.value,
  ...Object.keys(form.category_recipients)
    .filter((key) => !categoryOptions.value.some((c) => c.value === key))
    .map((key) => ({ value: key, label: `已删除分类：${key}` })),
])
const defaultRecipientNames = computed(() =>
  form.recipient_ids
    .map((id) => metadata.users.find((u) => u.id === id)?.name || `用户 ${id}`)
    .join('、')
)
const hasCategoryRule = (key) => Object.prototype.hasOwnProperty.call(form.category_recipients, key)
const categorySaveStatus = ref('自动保存已开启')
async function toggleCategoryRule(key, enabled) {
  if (busy.value || !canSave.value || !ready.value) return
  if (enabled) form.category_recipients[key] = [...form.recipient_ids]
  else delete form.category_recipients[key]
  await saveCategoryRecipients()
}
async function saveCategoryRecipients() {
  if (busy.value || !canSave.value || !ready.value) return
  saving.value = true
  error.value = ''
  try {
    // Persist only category rules against the last saved configuration.
    const payload = Object.fromEntries(Object.keys(form).map((key) => [key, metadata[key]]))
    payload.category_recipients = JSON.parse(JSON.stringify(form.category_recipients))
    const data = (await api.saveNotifications(payload)).data
    Object.assign(metadata, JSON.parse(JSON.stringify(data)))
    form.revision = data.revision
    form.category_recipients = JSON.parse(JSON.stringify(data.category_recipients || {}))
    categorySaveStatus.value = `已保存 · ${new Date().toLocaleTimeString('zh-CN', {
      hour12: false,
    })}`
  } catch (e) {
    error.value = `${e.message || '保存失败'}，分类接收人尚未保存，请重试`
    categorySaveStatus.value = '保存失败，修改尚未保存'
    window.$message?.error(error.value)
  } finally {
    saving.value = false
  }
}
const severityOptions = ['未分类', '信息', '警告', '一般严重', '严重', '灾难'].map(
  (label, value) => ({ label, value })
)
const statusLabels = {
  pending: '等待发送',
  sending: '发送中',
  sent: '已发送',
  failed: '失败 / 未确认',
  skipped: '已跳过',
}
const statusOptions = Object.entries(statusLabels).map(([value, label]) => ({ label, value }))
const statusColors = {
  pending: 'default',
  sending: 'info',
  sent: 'success',
  failed: 'error',
  skipped: 'warning',
}
const date = (value) =>
  value ? new Date(value * 1000).toLocaleString('zh-CN', { hour12: false }) : '—'
const logs = ref([]),
  total = ref(0),
  page = ref(1),
  logStatus = ref(null),
  logsLoading = ref(false),
  logError = ref('')
const previewOpen = ref(false),
  previewLoading = ref(false),
  previewEventId = ref(''),
  previewError = ref(''),
  previewData = ref(null)
const detailOpen = ref(false),
  selected = ref(null),
  retryOpen = ref(false),
  retrying = ref(false),
  retryError = ref('')
function action(label, icon, callback) {
  return h(NTooltip, null, {
    trigger: () =>
      h(
        NButton,
        {
          size: 'small',
          circle: true,
          quaternary: true,
          disabled: retrying.value,
          'aria-label': label,
          onClick: (event) => {
            event.stopPropagation()
            if (!retrying.value) callback()
          },
        },
        { icon: () => h(TheIcon, { icon, size: 17 }) }
      ),
    default: () => label,
  })
}
const columns = [
  ...[
    { title: '告警 / 事件', key: 'event_name', width: 300 },
    { title: '接收人', key: 'user_name', width: 130 },
    {
      title: '类型',
      key: 'phase',
      width: 90,
      render: (row) => (row.phase === 'recovery' ? '恢复通知' : '告警通知'),
    },
    {
      title: '状态',
      key: 'status',
      width: 130,
      render: (row) =>
        h(
          NTag,
          { size: 'small', bordered: false, type: statusColors[row.status] },
          { default: () => statusLabels[row.status] }
        ),
    },
    { title: '发送时间', key: 'sent_at', width: 190, render: (row) => date(row.sent_at) },
    { title: '尝试次数', key: 'attempts', width: 90 },
    { title: '说明', key: 'message', width: 250 },
  ].map((c) => ({ ...c, resizable: true, ellipsis: { tooltip: true } })),
  {
    title: '操作',
    key: 'actions',
    width: 100,
    fixed: 'right',
    render: (row) =>
      h(
        NSpace,
        { wrap: false },
        {
          default: () => [
            action('查看详情', 'mdi:eye-outline', () => {
              selected.value = row
              detailOpen.value = true
            }),
            canRetry.value && row.status === 'failed' && row.attempts < 5
              ? action('重试通知', 'mdi:refresh', () => {
                  selected.value = row
                  retryError.value = ''
                  retryOpen.value = true
                })
              : null,
          ],
        }
      ),
  },
]
async function reload() {
  if (busy.value) return
  loading.value = true
  error.value = ''
  ready.value = false
  try {
    const data = (await api.notifications()).data
    Object.assign(metadata, data)
    for (const key of Object.keys(form)) form[key] = JSON.parse(JSON.stringify(data[key]))
    ready.value = true
    categorySaveStatus.value = '已同步最新配置'
  } catch (e) {
    error.value = e.message || '通知配置加载失败'
    categorySaveStatus.value = '刷新失败'
  } finally {
    loading.value = false
  }
}
async function save() {
  if (busy.value || !canSave.value) return
  saving.value = true
  error.value = ''
  try {
    const data = (await api.saveNotifications({ ...form })).data
    Object.assign(metadata, data)
    for (const key of Object.keys(form)) form[key] = JSON.parse(JSON.stringify(data[key]))
    categorySaveStatus.value = `已保存 · ${new Date().toLocaleTimeString('zh-CN', {
      hour12: false,
    })}`
  } catch (e) {
    error.value = e.message || '保存失败'
    categorySaveStatus.value = '保存失败，修改尚未保存'
  } finally {
    saving.value = false
  }
}
async function loadLogs() {
  if (!canLogs.value) return
  logsLoading.value = true
  logError.value = ''
  try {
    const data = (
      await api.notificationDeliveries({
        page: page.value,
        page_size: 20,
        ...(logStatus.value ? { status: logStatus.value } : {}),
      })
    ).data
    logs.value = data.rows
    total.value = data.total
  } catch (e) {
    logError.value = e.message || '记录加载失败'
  } finally {
    logsLoading.value = false
  }
}
function changeLogFilter() {
  page.value = 1
  loadLogs()
}
async function preview() {
  if (previewLoading.value) return
  previewLoading.value = true
  previewError.value = ''
  previewData.value = null
  try {
    previewData.value = (
      await api.previewNotification({ event_id: previewEventId.value.trim() || null })
    ).data
  } catch (e) {
    previewError.value = e.message || '预览生成失败'
  } finally {
    previewLoading.value = false
  }
}
async function retry() {
  if (retrying.value) return
  retrying.value = true
  retryError.value = ''
  try {
    await api.retryNotification(selected.value.id)
    retryOpen.value = false
    window.$message?.success('已加入发送队列')
    await loadLogs()
  } catch (e) {
    retryError.value = e.message || '重试失败'
  } finally {
    retrying.value = false
  }
}
onMounted(() => {
  reload()
  loadLogs()
})
</script>
<style scoped>
.gap {
  margin: 14px 0;
}
.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 24px;
}
.recipient-rules {
  border-top: 1px solid rgba(128, 128, 128, 0.15);
  padding-top: 12px;
}
.recipient-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
}
.save-status {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #9ca3af;
  font-size: 12px;
}
.recipient-rule {
  display: grid;
  grid-template-columns: minmax(150px, 1fr) 140px minmax(260px, 3fr);
  gap: 16px;
  align-items: center;
  padding: 14px 0;
  border-bottom: 1px solid rgba(128, 128, 128, 0.12);
}
.recipient-rule-name {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
}
@media (max-width: 700px) {
  .recipient-rule {
    grid-template-columns: 1fr;
    gap: 8px;
  }
}
.muted {
  opacity: 0.7;
  font-size: 12px;
}
.card-preview {
  border: 1px solid #dce2eb;
  border-radius: 10px;
  overflow: hidden;
}
.card-preview h3 {
  margin: 0;
  padding: 16px;
  color: #fff;
  background: #d38a24;
}
.card-preview h3.red {
  background: #cd4852;
}
.card-preview h3.green {
  background: #269b76;
}
.card-fields {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px;
  padding: 20px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.card-text {
  padding: 14px 20px 4px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  line-height: 1.75;
}
.card-event {
  font-size: 16px;
  font-weight: 600;
}
.card-value {
  font-weight: 500;
  margin-top: 4px;
}
.card-divider {
  margin: 14px 20px 0;
  border: 0;
  border-top: 1px solid #e5e7eb;
}
.card-note {
  padding: 0 20px;
  overflow-wrap: anywhere;
}
.card-link {
  margin: 12px 20px 20px;
  padding: 8px 14px;
  border: 1px solid #bcd5f8;
  border-radius: 6px;
  color: #2878da;
  width: fit-content;
}
.advice {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  padding: 0 20px;
  line-height: 1.7;
}
.card-preview > .muted {
  padding: 0 20px 12px;
}
@media (max-width: 700px) {
  .form-grid,
  .card-fields {
    grid-template-columns: 1fr;
  }
}
</style>
