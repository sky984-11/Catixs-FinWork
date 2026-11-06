<template>
  <AppPage>
    <div class="billing-page">
      <div class="toolbar">
        <div>
          <h2>账单管理</h2>
          <p>从订单出账，按币种管理应收、回款与逾期。</p>
        </div>
        <CButton
          v-if="can('post', '/preview')"
          show-save
          save-text="从订单出账 / 建立计划"
          :disabled="busy || optionsLoading"
          @save="openGenerate"
        />
      </div>
      <n-alert v-if="optionsError" type="error"
        >{{ optionsError }}<CButton show-save save-text="重试加载客户" @save="loadCustomers"
      /></n-alert>
      <n-tabs v-model:value="tab" type="line" @update:value="refresh">
        <n-tab-pane name="bills" tab="账单">
          <div class="filters">
            <n-input
              v-model:value="query.keyword"
              clearable
              placeholder="账单号 / 名称"
              @keyup.enter="search"
            />
            <n-select
              v-model:value="query.customer_id"
              :options="customerOptions"
              clearable
              filterable
              placeholder="客户"
            />
            <n-select
              v-model:value="query.status"
              :options="statusOptions"
              clearable
              placeholder="账单状态"
            />
            <n-checkbox v-model:checked="query.overdue">仅逾期</n-checkbox>
            <CButton show-save save-text="查询" :disabled="loading" @save="search" />
          </div>
          <div v-if="summary.length" class="summaries">
            <div v-for="group in summary" :key="group.currency" class="summary-card">
              <strong>{{ group.currency }}</strong>
              <span>待收 {{ money(group.receivable) }}</span
              ><span>已收 {{ money(group.paid) }}</span>
              <span class="overdue">逾期 {{ money(group.overdue) }}</span>
            </div>
          </div>
          <p class="hint">汇总随筛选条件变化，仅计入已锁定账单，草稿及作废账单不计入应收。</p>
          <n-alert v-if="error" type="error"
            >{{ error }}<CButton show-save save-text="重试" @save="loadBills"
          /></n-alert>
          <n-data-table
            :columns="columns"
            :data="rows"
            :loading="loading"
            :scroll-x="1510"
            :row-key="(row) => row.id"
          />
          <n-pagination
            v-model:page="page"
            :page-size="20"
            :item-count="total"
            class="pagination"
            @update:page="loadBills"
          />
        </n-tab-pane>
        <n-tab-pane name="plans" tab="自动出账计划">
          <n-alert type="info" class="gap"
            >每日按上海时区检查到期计划，生成待审核草稿。预付在账期开始日出账，后付在账期结束次日出账。失败保留原因，可手动重试；停用后不会继续出账。</n-alert
          >
          <n-alert v-if="error" type="error"
            >{{ error }}<CButton show-save save-text="重试" @save="loadPlans"
          /></n-alert>
          <n-data-table
            :columns="planColumns"
            :data="plans"
            :loading="loading"
            :scroll-x="1160"
            :row-key="(row) => row.id"
          />
        </n-tab-pane>
      </n-tabs>
    </div>

    <n-modal
      v-model:show="editor.show"
      preset="card"
      :title="editor.id ? '调整账单草稿' : '订单出账'"
      style="width: min(1080px, calc(100vw - 24px))"
      :closable="!busy"
      :mask-closable="!busy"
      :close-on-esc="!busy"
    >
      <n-form label-placement="top" :disabled="busy">
        <div class="form-grid">
          <n-form-item label="账单名称" required
            ><n-input v-model:value="form.title" :maxlength="160"
          /></n-form-item>
          <n-form-item v-if="!editor.id" label="客户（正式名称）" required
            ><n-select
              v-model:value="form.customer_id"
              :options="activeCustomerOptions"
              filterable
              @update:value="changeCustomer"
          /></n-form-item>
          <n-form-item v-if="!editor.id" label="关联订单" required class="wide"
            ><n-select
              v-model:value="form.order_ids"
              filterable
              multiple
              :options="orderOptions"
              :loading="ordersLoading"
              placeholder="选择同一客户的订单"
          /></n-form-item>
          <n-form-item v-if="!editor.id" label="出账币种" required
            ><n-select v-model:value="form.currency" :options="currencies"
          /></n-form-item>
          <n-form-item v-if="!editor.id" label="计费方式"
            ><n-select
              v-model:value="form.calendar_mode"
              :options="[
                { label: '自然月（按月内实际天数折算）', value: 'calendar' },
                { label: '周年日（按服务起始日对齐）', value: 'anniversary' },
              ]"
          /></n-form-item>
          <n-form-item v-if="!editor.id" label="账期开始日" required
            ><n-date-picker
              v-model:formatted-value="form.period_start"
              value-format="yyyy-MM-dd"
              type="date"
          /></n-form-item>
          <n-form-item v-if="!editor.id" label="计费周期"
            ><n-select
              v-model:value="form.months"
              :options="[1, 3, 6, 12, 24, 36].map((value) => ({ value, label: `${value} 个月` }))"
          /></n-form-item>
          <n-form-item v-if="!editor.id" label="服务计费开始日" required
            ><n-date-picker
              v-model:formatted-value="form.service_start"
              value-format="yyyy-MM-dd"
              type="date"
          /></n-form-item>
          <n-form-item v-if="!editor.id" label="服务结束日（可选，含当天）"
            ><n-date-picker
              v-model:formatted-value="form.service_end"
              clearable
              value-format="yyyy-MM-dd"
              type="date"
          /></n-form-item>
          <n-form-item v-if="!editor.id" label="付款安排"
            ><n-select
              v-model:value="form.payment_timing"
              :options="[
                { value: 'prepaid', label: '预付' },
                { value: 'postpaid', label: '后付' },
              ]"
          /></n-form-item>
          <n-form-item v-if="!editor.id" label="首次收取 NRC"
            ><n-switch v-model:value="form.include_nrc" /><span class="hint inline"
              >已计收的订单不重复收取</span
            ></n-form-item
          >
          <n-form-item label="账单日期" required
            ><n-date-picker
              v-model:formatted-value="form.bill_date"
              value-format="yyyy-MM-dd"
              type="date"
          /></n-form-item>
          <n-form-item label="付款到期日" required
            ><n-date-picker
              v-model:formatted-value="form.due_date"
              value-format="yyyy-MM-dd"
              type="date"
          /></n-form-item>
          <n-form-item label="折扣金额"
            ><n-input v-model:value="form.discount" placeholder="0.00"
          /></n-form-item>
          <n-form-item label="变更差额（可为负）"
            ><n-input v-model:value="form.adjustment" placeholder="0.00"
          /></n-form-item>
          <n-form-item label="税率（%）"
            ><n-input v-model:value="form.tax_rate" placeholder="0"
          /></n-form-item>
          <n-form-item label="折扣 / 差额原因"
            ><n-input v-model:value="form.adjustment_reason" :maxlength="500"
          /></n-form-item>
          <n-form-item label="本位币"
            ><n-select v-model:value="form.local_currency" :options="currencies"
          /></n-form-item>
          <n-form-item label="汇率（1 账单币 = 本位币金额）"
            ><n-input v-model:value="form.fx_rate"
          /></n-form-item>
          <n-form-item label="汇率来源" required
            ><n-input v-model:value="form.fx_source" :maxlength="160"
          /></n-form-item>
          <n-form-item label="汇率日期" required
            ><n-date-picker
              v-model:formatted-value="form.fx_date"
              value-format="yyyy-MM-dd"
              type="date"
          /></n-form-item>
          <n-form-item label="备注" class="wide"
            ><n-input v-model:value="form.remark" type="textarea" :maxlength="2000"
          /></n-form-item>
        </div>
      </n-form>
      <n-alert v-if="!editor.id" type="info" class="gap"
        >服务日期适用于本次所选订单，起止日期不同请分别出账。MRC = 单价 × 数量 × 月数折算系数，NRC =
        单价 × 数量。多币种请分别预览出账。</n-alert
      >
      <n-alert v-if="!editor.id" type="warning" class="gap"
        >自动计划固定当前订单价格、折扣、税率及汇率，沿用账单日期与到期日的间隔。以后变价请停用旧计划并建立新计划；跨币种汇率请由财务定期复核。</n-alert
      >
      <div v-if="preview" class="gap preview">
        <h3>
          出账预览 · {{ preview.currency }} · {{ preview.period_start }} 至 {{ preview.period_end }}
        </h3>
        <n-data-table :columns="lineColumns" :data="preview.lines" :scroll-x="1140" />
        <p class="amounts">
          小计 {{ money(preview.subtotal) }} · 税额 {{ money(preview.tax_amount) }} ·
          <strong>应收 {{ money(preview.amount) }}</strong> · 本位币 {{ form.local_currency }}
          {{ money(preview.local_amount) }}
        </p>
      </div>
      <template #footer
        ><n-space justify="end">
          <CButton show-cancel :disabled="busy" @cancel="editor.show = false" />
          <CButton
            v-if="editor.id"
            show-save
            save-text="保存草稿"
            :disabled="busy"
            :save-loading="saving"
            @save="saveDraft"
          />
          <template v-else>
            <CButton
              show-save
              save-text="预览金额"
              :disabled="busy || ordersLoading"
              :save-loading="saving"
              @save="previewBill"
            />
            <CButton
              show-save
              save-text="生成账单草稿"
              :disabled="busy || !preview || !can('post', '/generate')"
              @save="commit(false)"
            />
            <CButton
              show-save
              save-text="建立自动出账计划"
              :disabled="busy || !preview || !can('post', '/plans')"
              @save="commit(true)"
            />
          </template> </n-space
      ></template>
    </n-modal>

    <n-modal
      v-model:show="detailShow"
      preset="card"
      title="账单详情"
      style="width: min(1160px, calc(100vw - 24px))"
      :closable="!busy"
      :mask-closable="!busy"
      :close-on-esc="!busy"
    >
      <template v-if="detail">
        <div class="toolbar">
          <div>
            <h2>{{ detail.title }}</h2>
            <p>{{ detail.bill_no }} · {{ statusLabel(detail.status) }}</p>
          </div>
          <CButton show-save save-text="导出账单明细" :disabled="busy" @save="exportDetail" />
        </div>
        <div class="detail-meta">
          <div>
            <small>客户</small><strong>{{ detail.customer_name }}</strong>
          </div>
          <div>
            <small>签约主体</small><strong>{{ detail.signing_entity_name || '—' }}</strong>
          </div>
          <div>
            <small>计费期间</small
            ><strong>{{ detail.period_start }} 至 {{ detail.period_end }}</strong>
          </div>
          <div>
            <small>账单 / 到期日期</small
            ><strong>{{ detail.bill_date }} / {{ detail.due_date }}</strong>
          </div>
        </div>
        <div class="summaries">
          <div class="summary-card">
            <small>账单金额</small><strong>{{ detail.currency }} {{ money(detail.amount) }}</strong>
          </div>
          <div class="summary-card">
            <small>已收</small
            ><strong>{{ detail.currency }} {{ money(detail.paid_amount) }}</strong>
          </div>
          <div class="summary-card">
            <small>未收</small
            ><strong>{{ detail.currency }} {{ money(detail.outstanding) }}</strong>
          </div>
          <div class="summary-card">
            <small>逾期 / 催收</small
            ><strong>{{ detail.overdue_days }} 天 / {{ detail.reminder_level }} 次</strong>
          </div>
        </div>
        <n-data-table :columns="lineColumns" :data="detail.lines" :scroll-x="1140" />
        <p class="amounts">
          费用小计 {{ money(detail.subtotal) }} − 折扣 {{ money(detail.discount) }} + 变更差额
          {{ money(detail.adjustment) }} + 税额 {{ money(detail.tax_amount) }}（{{
            detail.tax_rate
          }}%）
        </p>
        <p class="hint">
          本位币 {{ detail.local_currency }} {{ money(detail.local_amount) }} · 汇率
          {{ detail.fx_rate }} · 来源 {{ detail.fx_source }} · {{ detail.fx_date }}
        </p>
        <p v-if="detail.settings.adjustment_reason">
          调整原因：{{ detail.settings.adjustment_reason }}
        </p>
        <p v-if="detail.remark">备注：{{ detail.remark }}</p>
        <n-space class="gap">
          <CButton
            v-if="detail.status === 'draft' && can('put', '/bills/{document_id}')"
            show-save
            save-text="调整草稿"
            :disabled="busy"
            @save="editDraft(detail)"
          />
          <CButton
            v-if="detail.status === 'draft' && can('post', '/bills/{document_id}/actions')"
            show-save
            save-text="审核并锁定"
            :disabled="busy"
            @save="ask('issue', detail)"
          />
          <CButton
            v-if="
              ['issued', 'partial'].includes(detail.status) &&
              can('post', '/bills/{document_id}/payments')
            "
            show-save
            save-text="登记收款"
            :disabled="busy"
            @save="openPayment(detail)"
          />
          <CButton
            v-if="detail.overdue_days > 0 && can('post', '/bills/{document_id}/actions')"
            show-save
            save-text="登记催收"
            :disabled="busy"
            @save="ask('remind', detail)"
          />
        </n-space>
        <h3 class="gap">收款流水</h3>
        <n-data-table :data="detail.payments" :columns="paymentColumns" :scroll-x="880" />
        <h3 class="gap">操作记录</h3>
        <div v-for="log in detail.audits" :key="log.id" class="audit">
          <strong>{{ actionLabels[log.action] || log.action }}</strong
          ><span>{{ log.operator_name }} · {{ log.created_at }}</span>
          <p>{{ log.comment || '—' }}</p>
          <p v-if="log.before.amount || log.after.amount" class="hint">
            账单金额 {{ log.before.amount ?? '—' }} → {{ log.after.amount ?? '—' }}；已收
            {{ log.before.paid_amount ?? '—' }} → {{ log.after.paid_amount ?? '—' }}
          </p>
        </div>
      </template>
    </n-modal>

    <n-modal
      v-model:show="paymentForm.show"
      preset="card"
      title="登记收款"
      style="width: min(600px, calc(100vw - 24px))"
      :closable="!busy"
      :mask-closable="!busy"
      :close-on-esc="!busy"
    >
      <n-form label-placement="top" :disabled="busy"
        ><div class="form-grid">
          <n-form-item label="收款流水号" required
            ><n-input v-model:value="paymentForm.reference" :maxlength="100"
          /></n-form-item>
          <n-form-item :label="`收款金额（${paymentForm.currency}）`" required
            ><n-input v-model:value="paymentForm.amount"
          /></n-form-item>
          <n-form-item label="收款日期" required
            ><n-date-picker
              v-model:formatted-value="paymentForm.payment_date"
              type="date"
              value-format="yyyy-MM-dd"
          /></n-form-item>
          <n-form-item label="收款方式" required
            ><n-input v-model:value="paymentForm.method" :maxlength="80"
          /></n-form-item>
          <n-form-item label="备注" class="wide"
            ><n-input v-model:value="paymentForm.remark" type="textarea" :maxlength="500"
          /></n-form-item></div
      ></n-form>
      <template #footer
        ><CButton
          show-save
          show-cancel
          :disabled="busy"
          :save-loading="saving"
          @cancel="paymentForm.show = false"
          @save="savePayment"
      /></template>
    </n-modal>
    <n-modal
      v-model:show="confirmation.show"
      preset="card"
      :title="actionLabels[confirmation.action] || '确认操作'"
      style="width: min(520px, calc(100vw - 24px))"
      :closable="!busy"
      :mask-closable="!busy"
      :close-on-esc="!busy"
    >
      <p>
        {{
          confirmation.action === 'enable'
            ? '确认启用此计划？将沿用原价格及计费规则，从下个未出账账期继续执行，已到期的账期会自动补出草稿。'
            : confirmation.action === 'plan_delete'
            ? '确认删除此自动出账计划？删除后不再执行，已生成账单和历史关联会保留，此计划不能再启用。'
            : confirmation.action === 'delete'
            ? '确认删除此账单？删除后从默认列表移除，可筛选“已删除”查看历史。对应账期可重新出账，自动计划仍按原进度执行。'
            : confirmation.action === 'issue'
            ? '审核后锁定金额及价格快照，不能直接修改。'
            : confirmation.action === 'reverse'
            ? '冲销后恢复应收余额，原收款流水仍保留。'
            : confirmation.action === 'stop'
            ? '停用后不再自动生成账单，已生成账单保持不变。'
            : '仅登记跟进记录，不会自动向客户发送消息。'
        }}
      </p>
      <n-input
        v-if="!['stop', 'enable'].includes(confirmation.action)"
        v-model:value="confirmation.comment"
        type="textarea"
        placeholder="请填写操作原因 / 审核意见"
        :maxlength="500"
        :disabled="busy"
      />
      <template #footer
        ><CButton
          show-save
          show-cancel
          save-text="确认"
          :disabled="busy"
          :save-loading="saving"
          @cancel="confirmation.show = false"
          @save="confirmAction"
      /></template>
    </n-modal>
  </AppPage>
</template>

<script setup>
import { computed, h, onMounted, reactive, ref, watch } from 'vue'
import { NButton, NSpace, NTag, NTooltip } from 'naive-ui'
import api from '@/api'
import service from '@/api/crm-billing'
import { usePermissionStore, useUserStore } from '@/store'
import CButton from '@/components/public/CButton.vue'
import TheIcon from '@/components/icon/TheIcon.vue'

const userStore = useUserStore()
const permissionStore = usePermissionStore()
function can(method, path) {
  return (
    userStore.isSuperUser || permissionStore.apis.includes(`${method}/api/v1/crm-billing${path}`)
  )
}

const tab = ref('bills'),
  rows = ref([]),
  plans = ref([]),
  customers = ref([]),
  orders = ref([])
const loading = ref(false),
  saving = ref(false),
  optionsLoading = ref(false),
  ordersLoading = ref(false)
const error = ref(''),
  optionsError = ref(''),
  total = ref(0),
  page = ref(1),
  summary = ref([])
const busy = computed(() => saving.value)
const query = reactive({ keyword: '', customer_id: null, status: null, overdue: false })
const editor = reactive({ show: false, id: null })
const form = reactive({}),
  preview = ref(null),
  previewPayload = ref(null)
const detail = ref(null),
  detailShow = ref(false),
  paymentForm = reactive({ show: false })
const confirmation = reactive({ show: false, action: '', row: null, comment: '' })
const currencies = ['CNY', 'USD', 'EUR', 'JPY', 'HKD'].map((value) => ({ value, label: value }))
const statusOptions = [
  { value: 'draft', label: '草稿' },
  { value: 'issued', label: '已锁定 / 未收款' },
  { value: 'partial', label: '部分收款' },
  { value: 'paid', label: '已结清' },
  { value: 'void', label: '历史作废' },
  { value: 'deleted', label: '已删除' },
]
const statusLabel = (value) => statusOptions.find((row) => row.value === value)?.label || value
const actionLabels = {
  generate: '生成草稿',
  edit: '调整草稿',
  issue: '审核锁定',
  void: '作废账单',
  delete: '删除账单',
  payment: '登记收款',
  reverse: '冲销收款',
  remind: '登记催收',
  scheduled: '自动出账',
  stop: '停用计划',
  enable: '启用计划',
  plan_delete: '删除计划',
}
const customerOptions = computed(() =>
  customers.value.map((row) => ({
    value: row.id,
    label: `${row.legal_name || row.name}${
      row.signing_entity_name ? ` · ${row.signing_entity_name}` : ''
    }`,
  }))
)
const activeCustomerOptions = computed(() =>
  customerOptions.value.filter((option) =>
    customers.value.some(
      (row) => row.id === option.value && row.status && row.lifecycle !== 'terminated'
    )
  )
)
const orderOptions = computed(() =>
  orders.value.map((row) => ({ value: row.id, label: `${row.name} · ${row.order_no}` }))
)
function money(value) {
  if (value == null) return '—'
  const [integer, fraction = ''] = String(value).split('.')
  return `${integer.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}.${fraction.padEnd(2, '0')}`
}
function dateString(date = new Date()) {
  return new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Shanghai' }).format(date)
}
function key() {
  return `BILL-${Date.now()}-${Math.random().toString(36).slice(2)}`
}
async function allPages(fetcher, params = {}) {
  const result = []
  for (let index = 1; ; index++) {
    const response = await fetcher({ ...params, page: index, page_size: 100 })
    result.push(...(response.data || []))
    if (!response.data?.length || result.length >= response.total) return result
  }
}
async function loadCustomers() {
  optionsLoading.value = true
  optionsError.value = ''
  try {
    customers.value = await allPages(api.customerCenterApi.listCustomers)
  } catch (e) {
    optionsError.value = e.message || '客户加载失败'
  } finally {
    optionsLoading.value = false
  }
}
async function loadBills() {
  loading.value = true
  error.value = ''
  try {
    const result = await service.list({
      ...query,
      status: query.status || '',
      page: page.value,
      page_size: 20,
    })
    rows.value = result.data
    total.value = result.total
    summary.value = result.summary || []
  } catch (e) {
    error.value = e.message || '账单加载失败'
    rows.value = []
    summary.value = []
  } finally {
    loading.value = false
  }
}
async function loadPlans() {
  loading.value = true
  error.value = ''
  try {
    plans.value = (await service.plans()).data
  } catch (e) {
    error.value = e.message || '计划加载失败'
  } finally {
    loading.value = false
  }
}
function refresh() {
  return tab.value === 'bills' ? loadBills() : loadPlans()
}
function search() {
  page.value = 1
  loadBills()
}
function openGenerate() {
  editor.id = null
  preview.value = null
  previewPayload.value = null
  orders.value = []
  const day = dateString()
  Object.keys(form).forEach((name) => delete form[name])
  Object.assign(form, {
    title: '',
    customer_id: null,
    order_ids: [],
    currency: 'USD',
    calendar_mode: 'calendar',
    period_start: `${day.slice(0, 7)}-01`,
    months: 1,
    service_start: `${day.slice(0, 7)}-01`,
    service_end: null,
    payment_timing: 'prepaid',
    include_nrc: true,
    bill_date: day,
    due_date: dateString(new Date(Date.now() + 30 * 86400000)),
    discount: '0.00',
    adjustment: '0.00',
    tax_rate: '0',
    adjustment_reason: '',
    remark: '',
    local_currency: 'USD',
    fx_rate: '1',
    fx_source: '同币种',
    fx_date: day,
    request_key: key(),
  })
  editor.show = true
}
async function changeCustomer() {
  form.order_ids = []
  orders.value = []
  ordersLoading.value = true
  const selected = form.customer_id
  try {
    const result = await allPages(api.productCenterApi.listOrders, { customer_id: selected })
    if (form.customer_id === selected) orders.value = result
  } catch {
    /* 请求封装展示错误，可重新选择客户重试 */
  } finally {
    ordersLoading.value = false
  }
}
watch(
  form,
  () => {
    preview.value = null
    previewPayload.value = null
  },
  { deep: true }
)
async function execute(callback) {
  if (busy.value) return
  saving.value = true
  try {
    await callback()
  } catch {
    /* 请求封装展示错误，保留输入以便重试 */
  } finally {
    saving.value = false
  }
}
async function previewBill() {
  if (!form.customer_id || !form.order_ids.length || !form.title.trim())
    return window.$message?.warning('请填写账单名称、客户和订单')
  await execute(async () => {
    const payload = JSON.parse(JSON.stringify(form))
    const result = await service.preview(payload)
    preview.value = result.data
    previewPayload.value = { ...payload, preview_token: result.data.preview_token }
  })
}
async function commit(plan) {
  if (!previewPayload.value) return
  await execute(async () => {
    const result = await (plan
      ? service.createPlan(previewPayload.value)
      : service.generate(previewPayload.value))
    editor.show = false
    window.$message?.success(plan ? '自动出账计划已建立' : '账单草稿已生成')
    if (plan) {
      tab.value = 'plans'
      await loadPlans()
    } else {
      detail.value = result.data
      detailShow.value = true
      tab.value = 'bills'
      await loadBills()
    }
  })
}
async function openDetail(row) {
  await execute(async () => {
    detail.value = (await service.detail(row.id)).data
    detailShow.value = true
  })
}
const termFields = [
  'title',
  'bill_date',
  'due_date',
  'discount',
  'adjustment',
  'tax_rate',
  'adjustment_reason',
  'remark',
  'local_currency',
  'fx_rate',
  'fx_source',
  'fx_date',
]
function editDraft(row) {
  Object.keys(form).forEach((name) => delete form[name])
  for (const name of termFields) form[name] = row.settings[name]
  editor.id = row.id
  editor.show = true
}
async function saveDraft() {
  await execute(async () => {
    detail.value = (await service.update(editor.id, form)).data
    editor.show = false
    await loadBills()
    window.$message?.success('草稿已更新')
  })
}
function openPayment(row) {
  Object.assign(paymentForm, {
    show: true,
    id: row.id,
    reference: '',
    amount: row.outstanding,
    currency: row.currency,
    payment_date: dateString(),
    method: '银行转账',
    remark: '',
  })
}
async function savePayment() {
  await execute(async () => {
    const { id, ...payload } = paymentForm
    delete payload.show
    detail.value = (await service.payment(id, payload)).data
    paymentForm.show = false
    await loadBills()
    window.$message?.success('收款已登记')
  })
}
function ask(action, row) {
  Object.assign(confirmation, { show: true, action, row, comment: '' })
}
async function confirmAction() {
  if (!['stop', 'enable'].includes(confirmation.action) && !confirmation.comment.trim())
    return window.$message?.warning('请填写操作原因')
  await execute(async () => {
    const { action, row, comment } = confirmation
    if (action === 'stop') {
      await service.stopPlan(row.id)
      await loadPlans()
    } else if (action === 'enable') {
      await service.enablePlan(row.id)
      await loadPlans()
    } else if (action === 'plan_delete') {
      await service.deletePlan(row.id, { reason: comment })
      await loadPlans()
    } else if (action === 'delete') {
      await service.remove(row.id, { reason: comment })
      if (detail.value?.id === row.id) detailShow.value = false
      await loadBills()
      if (!rows.value.length && page.value > 1) {
        page.value -= 1
        await loadBills()
      }
    } else {
      const result =
        action === 'reverse'
          ? await service.reverse(detail.value.id, row.id, { reason: comment })
          : await service.action(row.id, { action, comment })
      detail.value = result.data
      await loadBills()
    }
    confirmation.show = false
    window.$message?.success('操作成功')
  })
}
function action(label, icon, callback, type = 'default') {
  const paths = {
    冲销: '/bills/{document_id}/payments/{payment_id}/reverse',
    停用: '/plans/{plan_id}/stop',
    启用: '/plans/{plan_id}/enable',
    '检查 / 重试': '/plans/{plan_id}/run',
  }
  if (paths[label] && !can('post', paths[label])) return null
  return h(NTooltip, null, {
    trigger: () =>
      h(
        NButton,
        {
          size: 'small',
          circle: true,
          quaternary: true,
          type,
          'aria-label': label,
          disabled: busy.value,
          loading: busy.value,
          onClick: (event) => {
            event.stopPropagation()
            if (!busy.value) callback()
          },
        },
        { icon: () => h(TheIcon, { icon, size: 17 }) }
      ),
    default: () => label,
  })
}
function businessColumns(cols) {
  return cols.map((col) => ({ ...col, resizable: col.key !== 'actions' }))
}
const columns = businessColumns([
  { title: '账单号', key: 'bill_no', width: 240, ellipsis: { tooltip: true } },
  { title: '客户', key: 'customer_name', width: 210, ellipsis: { tooltip: true } },
  { title: '账单名称', key: 'title', width: 200, ellipsis: { tooltip: true } },
  { title: '币种', key: 'currency', width: 80 },
  { title: '应收金额', key: 'amount', width: 130, render: (row) => money(row.amount) },
  { title: '已收', key: 'paid_amount', width: 120, render: (row) => money(row.paid_amount) },
  { title: '未收', key: 'outstanding', width: 120, render: (row) => money(row.outstanding) },
  {
    title: '状态',
    key: 'status',
    width: 150,
    render: (row) =>
      h(
        NTag,
        {
          size: 'small',
          type: row.status === 'paid' ? 'success' : row.overdue_days ? 'error' : 'default',
        },
        { default: () => statusLabel(row.status) }
      ),
  },
  { title: '到期日', key: 'due_date', width: 120 },
  { title: '逾期天数', key: 'overdue_days', width: 100 },
  {
    title: '操作',
    key: 'actions',
    fixed: 'right',
    width: 100,
    render: (row) =>
      h(
        NSpace,
        { wrap: false, size: 4 },
        {
          default: () => [
            action('详情', 'mdi:eye-outline', () => openDetail(row)),
            ['draft', 'void'].includes(row.status) && can('delete', '/bills/{document_id}')
              ? action('删除', 'mdi:trash-can-outline', () => ask('delete', row), 'error')
              : null,
          ],
        }
      ),
  },
])
const lineColumns = businessColumns([
  { title: '订单', key: 'order_name', width: 180, ellipsis: { tooltip: true } },
  {
    title: '产品 / 规格',
    key: 'product_name',
    width: 210,
    ellipsis: { tooltip: true },
    render: (row) => `${row.product_name}${row.variant_name ? ` · ${row.variant_name}` : ''}`,
  },
  { title: '数量', key: 'quantity', width: 70 },
  { title: 'MRC 单价', key: 'mrc', width: 120 },
  {
    title: '折算月数',
    key: 'month_factor',
    width: 110,
    render: (row) => Number(row.month_factor).toFixed(6),
  },
  { title: 'MRC 小计', key: 'mrc_amount', width: 130, render: (row) => money(row.mrc_amount) },
  { title: 'NRC 小计', key: 'nrc_amount', width: 130, render: (row) => money(row.nrc_amount) },
  { title: '合计', key: 'amount', width: 140, render: (row) => money(row.amount) },
])
const paymentColumns = businessColumns([
  { title: '流水号', key: 'reference', width: 200 },
  { title: '日期', key: 'payment_date', width: 120 },
  {
    title: '金额',
    key: 'amount',
    width: 130,
    render: (row) => `${row.currency} ${money(row.amount)}`,
  },
  { title: '方式', key: 'method', width: 110 },
  {
    title: '状态',
    key: 'reversed',
    width: 100,
    render: (row) => (row.reversed ? '已冲销' : '已核销'),
  },
  { title: '备注', key: 'remark', width: 150, ellipsis: { tooltip: true } },
  {
    title: '操作',
    key: 'actions',
    fixed: 'right',
    width: 70,
    render: (row) =>
      row.reversed ? null : action('冲销', 'mdi:undo-variant', () => ask('reverse', row), 'error'),
  },
])
const planColumns = businessColumns([
  { title: '计划名称', key: 'name', width: 200, ellipsis: { tooltip: true } },
  {
    title: '币种 / 周期',
    key: 'template',
    width: 120,
    render: (row) => `${row.template.currency} / ${row.template.months} 月`,
  },
  { title: '下个账期', key: 'next_period', width: 120 },
  { title: '出账日', key: 'next_run', width: 120 },
  { title: '状态', key: 'enabled', width: 100, render: (row) => (row.enabled ? '启用' : '已停用') },
  { title: '最近失败原因', key: 'last_error', width: 330, ellipsis: { tooltip: true } },
  {
    title: '操作',
    key: 'actions',
    fixed: 'right',
    width: 130,
    render: (row) =>
      h(
        NSpace,
        { wrap: false, size: 4 },
        {
          default: () => [
            row.enabled
              ? action('检查 / 重试', 'mdi:refresh', () =>
                  execute(async () => {
                    const result = await service.runPlan(row.id)
                    window.$message?.success(result.msg)
                    await loadPlans()
                  })
                )
              : null,
            row.enabled
              ? action('停用', 'mdi:stop-circle-outline', () => ask('stop', row), 'error')
              : action('启用', 'mdi:play-circle-outline', () => ask('enable', row), 'success'),
            can('delete', '/plans/{plan_id}')
              ? action('删除计划', 'mdi:trash-can-outline', () => ask('plan_delete', row), 'error')
              : null,
          ],
        }
      ),
  },
])
function exportDetail() {
  const bill = detail.value
  const escape = (value) =>
    `"${String(value ?? '')
      .replace(/^[=+\-@\t\r]/, "'$&")
      .replaceAll('"', '""')}"`
  const csv = [
    ['账单号', bill.bill_no, '客户', bill.customer_name, '币种', bill.currency],
    ['账期', bill.period_start, bill.period_end],
    ['订单', '产品', '规格', '数量', 'MRC 单价', 'MRC 小计', 'NRC 小计', '合计'],
    ...bill.lines.map((row) => [
      row.order_no,
      row.product_name,
      row.variant_name,
      row.quantity,
      row.mrc,
      row.mrc_amount,
      row.nrc_amount,
      row.amount,
    ]),
    ['费用小计', bill.subtotal, '折扣', bill.discount, '变更差额', bill.adjustment],
    ['税额', bill.tax_amount, '总额', bill.amount, '已收', bill.paid_amount],
    ['本位币', bill.local_currency, '本位币金额', bill.local_amount, '汇率', bill.fx_rate],
  ]
    .map((row) => row.map(escape).join(','))
    .join('\r\n')
  const url = URL.createObjectURL(new Blob(['\ufeff', csv], { type: 'text/csv;charset=utf-8' }))
  const link = document.createElement('a')
  link.href = url
  link.download = `${bill.bill_no}.csv`
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
onMounted(() => {
  loadCustomers()
  loadBills()
})
</script>

<style scoped>
.billing-page {
  padding: 20px;
}
.toolbar {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  align-items: center;
  margin-bottom: 20px;
}
.toolbar h2 {
  margin: 0 0 6px;
  font-size: 21px;
}
.toolbar p,
.hint {
  opacity: 0.65;
  font-size: 13px;
}
.filters {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: center;
  margin: 16px 0;
}
.filters > .n-input {
  width: 220px;
}
.filters > .n-select {
  width: 220px;
}
.summaries {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin: 18px 0;
}
.summary-card {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  align-items: center;
  background: var(--n-color-modal, #f6f8fb);
  border: 1px solid #e6e9ef;
  border-radius: 10px;
  padding: 16px;
}
.overdue {
  color: #d03050;
}
.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 20px;
}
.form-grid .wide {
  grid-column: 1/-1;
}
.form-grid :deep(.n-date-picker) {
  width: 100%;
}
.gap {
  margin-top: 18px;
  margin-bottom: 18px;
}
.inline {
  margin-left: 12px;
}
.pagination {
  justify-content: flex-end;
  margin-top: 18px;
}
.detail-meta {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px;
  margin-bottom: 18px;
}
.detail-meta small,
.detail-meta strong {
  display: block;
}
.detail-meta small {
  opacity: 0.6;
  margin-bottom: 5px;
}
.amounts {
  text-align: right;
  font-variant-numeric: tabular-nums;
  line-height: 2;
}
.audit {
  border-bottom: 1px solid #eee;
  padding: 12px 0;
}
.audit span {
  margin-left: 18px;
  opacity: 0.6;
  font-size: 12px;
}
.audit p {
  margin: 6px 0;
  overflow-wrap: anywhere;
}
@media (max-width: 640px) {
  .billing-page {
    padding: 8px;
  }
  .toolbar {
    align-items: flex-start;
    flex-direction: column;
  }
  .form-grid,
  .detail-meta {
    grid-template-columns: 1fr;
  }
  .filters > .n-input,
  .filters > .n-select {
    width: 100%;
  }
  .summary-card {
    width: 100%;
  }
  .amounts {
    text-align: left;
  }
}
</style>
