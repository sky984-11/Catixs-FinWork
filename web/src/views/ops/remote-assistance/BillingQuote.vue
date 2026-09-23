<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import api from '@/api'
import CButton from '@/components/public/CButton.vue'
import { billingCurrencies, cloneBillingRules, validateBillingRules } from './billing.mjs'

const props = defineProps({
  rules: { type: Object, default: null },
  arrivedAt: { type: String, default: null },
  leftAt: { type: String, default: null },
  timezone: { type: String, default: 'Asia/Shanghai' },
  region: { type: String, default: '' },
  modelValue: { type: Object, default: () => ({}) },
  disabled: Boolean,
  recordExpenses: Boolean,
  customerPricing: { type: Object, default: null },
})
const emit = defineEmits(['update:modelValue'])
const rules = computed(() => (props.rules ? cloneBillingRules(props.rules) : null))
const fixedPrice = computed(() => props.customerPricing?.kind === 'fixed')
const context = computed(() => ({
  emergency: false,
  service_type: 'standard',
  payment_method: null,
  reimbursed_transport: null,
  actual_commute_minutes: null,
  expenses: [],
  ...props.modelValue,
}))
const payments = computed(() =>
  (rules.value?.payment_methods || []).map((m) => ({ label: m.name, value: m.name }))
)
const result = ref(null)
const loading = ref(false)
const error = ref('')
let timer
let version = 0
function update(key, value) {
  emit('update:modelValue', { ...context.value, [key]: value })
}
function updateExpense(index, key, value) {
  update(
    'expenses',
    context.value.expenses.map((item, i) => (i === index ? { ...item, [key]: value } : item))
  )
}
function addExpense() {
  update('expenses', [
    ...context.value.expenses,
    { name: '', amount: null, currency: rules.value?.currency || 'USD', note: '' },
  ])
}
watch(
  () => [
    props.rules,
    props.arrivedAt,
    props.leftAt,
    props.timezone,
    props.region,
    props.modelValue,
    props.customerPricing,
  ],
  () => {
    clearTimeout(timer)
    const requestId = ++version
    result.value = null
    loading.value = false
    error.value = fixedPrice.value
      ? ''
      : !rules.value
      ? '请选择已配置规则的工程师'
      : validateBillingRules(rules.value)
    if (context.value.expenses.some((item) => !item.name.trim())) error.value = '请填写现场费用名称'
    if (error.value || (!fixedPrice.value && (!props.arrivedAt || !props.leftAt))) return
    loading.value = true
    timer = setTimeout(async () => {
      try {
        const res = await api.remoteAssistanceApi.previewBilling({
          rules: rules.value,
          arrived_at: props.arrivedAt || '',
          left_at: props.leftAt || '',
          timezone: props.timezone,
          region: props.region,
          context: context.value,
          customer_pricing: props.customerPricing,
        })
        if (requestId === version) result.value = res.data
      } catch {
        if (requestId === version) error.value = '试算失败，请检查规则、时间和时区后重试'
      } finally {
        if (requestId === version) loading.value = false
      }
    }, 400)
  },
  { deep: true, immediate: true }
)
onBeforeUnmount(() => {
  clearTimeout(timer)
  version++
})
</script>

<template>
  <div class="billing-quote">
    <p v-if="customerPricing" class="full-row">
      {{
        customerPricing.kind === 'internal'
          ? '本次使用工程师基础规则。'
          : customerPricing.kind === 'hourly'
          ? `客户基础人工：${customerPricing.hourly_rate} ${customerPricing.currency}/小时，替换原小时单价或固定档位。`
          : customerPricing.kind === 'fixed'
          ? '本次采用施工一口价。'
          : '请确认本次施工报价。'
      }}
    </p>
    <n-form-item v-if="!fixedPrice" label="服务类别">
      <n-select
        :value="context.service_type"
        :disabled="disabled"
        :options="[
          { label: '按工时计费', value: 'standard' },
          { label: '项目单独报价', value: 'project' },
        ]"
        @update:value="update('service_type', $event)"
      />
    </n-form-item>
    <n-form-item v-if="!fixedPrice" label="紧急维护">
      <n-switch
        :value="context.emergency"
        :disabled="disabled"
        @update:value="update('emergency', $event)"
      />
    </n-form-item>
    <n-form-item v-if="rules?.transport_mode === 'reimburse'" label="报销交通">
      <n-input-number
        :value="context.reimbursed_transport == null ? null : Number(context.reimbursed_transport)"
        :disabled="disabled"
        :min="0"
        :precision="2"
        placeholder="未确认留空"
        @update:value="update('reimbursed_transport', $event)"
      />
    </n-form-item>
    <n-form-item
      v-if="!fixedPrice && rules?.transport_mode === 'hourly' && rules?.commute_mode === 'actual'"
      label="实际往返通勤（分钟）"
    >
      <n-input-number
        :value="context.actual_commute_minutes"
        :min="0"
        :max="10080"
        :precision="0"
        :disabled="disabled"
        placeholder="未确认留空"
        @update:value="update('actual_commute_minutes', $event)"
      />
    </n-form-item>
    <section v-if="recordExpenses" class="full-row expenses">
      <strong>现场实报实销</strong>
      <p>
        携带大件打车等实际费用在此填写，可在附件区上传凭证。不要重复填写已计入的固定交通费或报销交通费。
      </p>
      <div v-for="(expense, index) in context.expenses" :key="index" class="expense-row">
        <n-form-item label="费用名称">
          <n-input
            :value="expense.name"
            maxlength="100"
            :disabled="disabled"
            placeholder="例如大件打车、材料费"
            @update:value="updateExpense(index, 'name', $event)"
          />
        </n-form-item>
        <n-form-item label="实际金额">
          <n-input-number
            :value="expense.amount == null ? null : Number(expense.amount)"
            :min="0"
            :max="9999999999.99"
            :precision="2"
            :disabled="disabled"
            placeholder="待确认留空"
            @update:value="updateExpense(index, 'amount', $event)"
          />
        </n-form-item>
        <n-form-item label="币种">
          <n-select
            :value="expense.currency"
            :options="billingCurrencies.map((value) => ({ label: value, value }))"
            :disabled="disabled"
            @update:value="updateExpense(index, 'currency', $event)"
          />
        </n-form-item>
        <n-form-item label="说明">
          <n-input
            :value="expense.note"
            maxlength="500"
            :disabled="disabled"
            @update:value="updateExpense(index, 'note', $event)"
          />
        </n-form-item>
        <CButton
          show-delete
          size="small"
          :disabled="disabled"
          @delete="
            update(
              'expenses',
              context.expenses.filter((_, i) => i !== index)
            )
          "
        />
      </div>
      <CButton
        show-save
        save-text="添加现场费用"
        size="small"
        :disabled="disabled || context.expenses.length >= 50"
        @save="addExpense"
      />
    </section>
    <n-form-item v-if="!fixedPrice && payments.length" label="收款方式">
      <n-select
        :value="context.payment_method"
        :disabled="disabled"
        clearable
        :options="payments"
        @update:value="update('payment_method', $event)"
      />
    </n-form-item>
    <n-spin :show="loading">
      <n-alert v-if="error" type="warning">{{ error }}</n-alert>
      <p v-else-if="!fixedPrice && (!arrivedAt || !leftAt)">
        填写北京时间的到场和离场时间后自动试算。
      </p>
      <div v-else-if="result" aria-live="polite">
        <p v-if="!fixedPrice">
          当地时间：{{ result.local_arrived_at || '—' }} 至 {{ result.local_left_at || '—' }}
        </p>
        <p v-if="result.work_minutes != null">
          实际工时 {{ result.work_minutes }} 分钟；当地夜班
          {{ result.night_minutes ?? '待确认' }} 分钟
        </p>
        <div v-for="(line, index) in result.lines" :key="index" class="fee-line">
          <span>{{ line.label }}</span
          ><span>{{ line.amount }} {{ line.currency || result.currency }}</span>
        </div>
        <p>
          <strong>{{
            result.status !== 'calculated'
              ? '费用待确认'
              : result.totals
              ? `合计 ${Object.entries(result.totals)
                  .map(([currency, amount]) => `${amount} ${currency}`)
                  .join(' + ')}`
              : `合计 ${result.total} ${result.currency}`
          }}</strong>
        </p>
        <p v-for="notice in result.notices" :key="notice">{{ notice }}</p>
      </div>
    </n-spin>
  </div>
</template>

<style scoped>
.billing-quote {
  padding: 12px;
  background: #8888880d;
  border-radius: 8px;
  overflow-wrap: anywhere;
}
.fee-line {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 8px;
  margin: 6px 0;
}
.full-row {
  grid-column: 1 / -1;
}
.expenses {
  border-top: 1px solid #edf2f7;
  padding-top: 12px;
}
.expense-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 12px;
  margin-bottom: 12px;
}
@media (max-width: 600px) {
  .expense-row {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
