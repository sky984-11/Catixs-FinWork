<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import api from '@/api'
import CButton from '@/components/public/CButton.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
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
  additional_fee_minutes: {},
  excluded_fee_ids: [],
  ...props.modelValue,
}))
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
          ? `本次人工单价：${customerPricing.hourly_rate ?? '待确认'} ${
              customerPricing.currency
            }/小时，替换原小时单价或固定档位。`
          : customerPricing.kind === 'fixed'
          ? '本次采用施工一口价。'
          : '请确认本次施工报价。'
      }}
    </p>
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
    <section v-if="!fixedPrice && rules?.additional_fees?.length" class="full-row rule-fees">
      <strong>规则附加费用</strong>
      <div v-for="fee in rules.additional_fees" :key="fee.id" class="rule-fee-row">
        <n-checkbox
          :checked="!context.excluded_fee_ids.includes(fee.id)"
          :disabled="disabled"
          @update:checked="
            update(
              'excluded_fee_ids',
              $event
                ? context.excluded_fee_ids.filter((id) => id !== fee.id)
                : [...context.excluded_fee_ids, fee.id]
            )
          "
        >
          {{ fee.name }}
          <small
            >{{ fee.amount ?? '待确认' }} {{ rules.currency }} /
            {{ fee.mode === 'hourly' ? '小时' : '次' }}</small
          >
        </n-checkbox>
        <n-input-number
          v-if="fee.mode === 'hourly' && fee.minutes_source === 'actual'"
          :value="
            context.additional_fee_minutes[fee.id] ??
            (fee.id === 'legacy-transport' ? context.actual_commute_minutes : null)
          "
          :min="0"
          :max="10080"
          :precision="0"
          :disabled="disabled || context.excluded_fee_ids.includes(fee.id)"
          placeholder="实际时长"
          @update:value="
            update('additional_fee_minutes', {
              ...context.additional_fee_minutes,
              [fee.id]: $event,
            })
          "
          ><template #suffix>分钟</template></n-input-number
        >
      </div>
    </section>
    <section v-if="recordExpenses" class="full-row expenses">
      <div class="expenses-heading">
        <div>
          <strong>现场费用</strong>
          <p>按实际支出填写，附件区可上传凭证</p>
        </div>
        <CButton
          class="expense-add"
          show-save
          save-text="添加费用"
          size="small"
          :disabled="disabled || context.expenses.length >= 50"
          @save="addExpense"
          ><template #save-icon><TheIcon icon="mdi:plus" :size="18" /></template
        ></CButton>
      </div>
      <div v-if="!context.expenses.length" class="expense-empty">
        <TheIcon icon="mdi:receipt-text-outline" :size="24" /><span>暂无现场费用</span>
      </div>
      <div v-for="(expense, index) in context.expenses" :key="index" class="expense-row">
        <div class="expense-row-heading">
          <strong>费用 {{ index + 1 }}</strong
          ><CButton
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
      </div>
    </section>
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
  padding: 14px 16px 0;
  border: 1px solid #e5edf6;
  border-radius: 10px;
  background: #f8fbff;
}
@media (max-width: 600px) {
  .expense-row {
    grid-template-columns: minmax(0, 1fr);
  }
}
.expenses-heading,
.expense-row-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.expense-row-heading {
  grid-column: 1 / -1;
}
.expenses-heading p {
  color: #94a3b8;
  font-size: 12px;
  margin: 4px 0 0;
}
.expense-empty {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 8px;
  border: 1px dashed #d9e3ee;
  border-radius: 8px;
  padding: 20px;
  color: #94a3b8;
  font-size: 13px;
}
.expense-add :deep(.n-button) {
  border-radius: 8px;
}
.rule-fees {
  padding: 12px 0;
}
.rule-fee-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 0;
}
.rule-fee-row small {
  color: #94a3b8;
  margin-left: 8px;
}
.rule-fee-row :deep(.n-input-number) {
  max-width: 180px;
}
@media (max-width: 600px) {
  .rule-fee-row,
  .expenses-heading {
    flex-wrap: wrap;
  }
}
</style>
