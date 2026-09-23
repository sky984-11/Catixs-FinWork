<script setup>
import { computed, reactive, ref, watch } from 'vue'
import CButton from '@/components/public/CButton.vue'
import BillingQuote from './BillingQuote.vue'
import {
  billingCurrencies,
  billingTemplates,
  exampleBillingRules,
  cloneBillingRules,
  overtimeRoundingOptions,
  validateBillingRules,
  timezoneOptions,
  beijingDateTime,
} from './billing.mjs'
const props = defineProps({ modelValue: { type: Object, required: true }, disabled: Boolean })
const emit = defineEmits(['update:modelValue'])
const rules = ref(cloneBillingRules(props.modelValue))
watch(
  () => props.modelValue,
  (value) => {
    if (JSON.stringify(value) !== JSON.stringify(rules.value))
      rules.value = cloneBillingRules(value)
  },
  { deep: true }
)
watch(rules, (value) => emit('update:modelValue', JSON.parse(JSON.stringify(value))), {
  deep: true,
})
const template = ref(null)
const preview = reactive({
  arrived_at: beijingDateTime(),
  left_at: beijingDateTime(new Date(Date.now() + 3600000)),
  timezone: 'Asia/Shanghai',
  region: '',
  context: {},
})
const currencies = billingCurrencies.map((value) => ({ label: value, value }))
const pricingOptions = [
  { label: '固定小时单价', value: 'hourly' },
  { label: '按时长固定总价', value: 'package' },
  { label: '分段小时单价', value: 'tiered_hourly' },
]
const transportOptions = [
  { label: '无额外费用', value: 'none' },
  { label: '每次固定交通费', value: 'fixed' },
  { label: '每次通勤工时费', value: 'hourly' },
  { label: '实报实销', value: 'reimburse' },
]
const taxOptions = [
  { label: '不另加税', value: 'none' },
  { label: '报价已含税', value: 'included' },
  { label: '按约定税率另加', value: 'extra' },
  { label: '税费待确认', value: 'confirm' },
]
const error = computed(() => validateBillingRules(rules.value))
const currentTiers = computed(() =>
  rules.value.pricing === 'package' ? rules.value.tiers : rules.value.hourly_tiers
)
function addTier() {
  const tiers = currentTiers.value
  if (tiers.length >= 20) return
  if (rules.value.pricing === 'package')
    tiers.push({ up_to_minutes: (tiers.at(-1)?.up_to_minutes || 0) + 60, total_fee: 0 })
  else {
    if (tiers.length)
      tiers.at(-1).up_to_minutes = (tiers.length > 1 ? tiers.at(-2).up_to_minutes : 0) + 60
    tiers.push({ up_to_minutes: null, hourly_rate: 0 })
  }
}
function changePricing(value) {
  rules.value.pricing = value
  if (value !== 'hourly' && !currentTiers.value.length) addTier()
}
function removeTier(index) {
  currentTiers.value.splice(index, 1)
  if (rules.value.pricing === 'tiered_hourly' && currentTiers.value.length)
    currentTiers.value.at(-1).up_to_minutes = null
}
function addPayment() {
  rules.value.payment_methods.push({
    name: '',
    tax_mode: 'none',
    tax_rate: null,
    tax_base: 'subtotal',
    note: '',
  })
}
function applyTemplate() {
  rules.value = exampleBillingRules(template.value)
  preview.context = {}
}
</script>
<template>
  <div class="billing-editor">
    <n-form-item label="参考模板">
      <n-select
        v-model:value="template"
        clearable
        :options="billingTemplates"
        :disabled="disabled"
        placeholder="可选；不会自动应用实例价格"
      />
    </n-form-item>
    <CButton
      show-save
      save-text="用模板替换当前规则"
      size="small"
      :disabled="disabled || !template"
      @save="applyTemplate"
    />
    <p>
      模板为Catixs本公司报价。本次施工可在计划或记录中填写小时报价或一口价；现场实报实销在记录中填写。未确认的单价和时段留空。
    </p>
    <div class="billing-grid">
      <n-form-item label="计费模式"
        ><n-select
          :value="rules.pricing"
          :options="pricingOptions"
          :disabled="disabled"
          @update:value="changePricing"
      /></n-form-item>
      <n-form-item label="币种"
        ><n-select v-model:value="rules.currency" :options="currencies" :disabled="disabled"
      /></n-form-item>
    </div>
    <n-form-item v-if="rules.pricing === 'hourly'" label="小时单价"
      ><n-input-number
        v-model:value="rules.hourly_rate"
        :min="0"
        :max="9999999999.99"
        :precision="2"
        :disabled="disabled"
        placeholder="已确认的具体单价"
    /></n-form-item>
    <template v-else>
      <p>
        {{
          rules.pricing === 'package'
            ? '按工时所在档位收取该档总价；超过最后一档按加班规则计算。'
            : '各时长区间按对应小时单价累加，最后一档不限时长。'
        }}
      </p>
      <div v-for="(tier, index) in currentTiers" :key="index" class="billing-tier">
        <n-form-item label="累计分钟">
          <span v-if="rules.pricing === 'tiered_hourly' && index === currentTiers.length - 1"
            >不限</span
          >
          <n-input-number
            v-else
            v-model:value="tier.up_to_minutes"
            :min="1"
            :max="525600"
            :precision="0"
            :disabled="disabled"
          />
        </n-form-item>
        <n-form-item :label="rules.pricing === 'package' ? '档位总价' : '小时单价'">
          <n-input-number
            v-if="rules.pricing === 'package'"
            v-model:value="tier.total_fee"
            :min="0"
            :precision="2"
            :disabled="disabled"
          />
          <n-input-number
            v-else
            v-model:value="tier.hourly_rate"
            :min="0"
            :precision="2"
            :disabled="disabled"
          />
        </n-form-item>
        <CButton
          show-delete
          size="small"
          :disabled="disabled || currentTiers.length === 1"
          @delete="removeTier(index)"
        />
      </div>
      <CButton
        show-save
        save-text="添加档位"
        size="small"
        :disabled="disabled || currentTiers.length >= 20"
        @save="addTier"
      />
    </template>
    <div class="billing-grid">
      <n-form-item label="最低分钟"
        ><n-input-number
          v-model:value="rules.minimum_minutes"
          :min="0"
          :max="10080"
          :precision="0"
          :disabled="disabled"
      /></n-form-item>
      <n-form-item label="计费步长"
        ><n-input-number
          v-model:value="rules.billing_increment_minutes"
          :min="1"
          :max="1440"
          :precision="0"
          :disabled="disabled"
      /></n-form-item>
    </div>
    <p>按实际工时补足最低分钟，再按步长向上取整；0分钟不产生费用。步长1表示按分钟折算。</p>
    <template v-if="rules.pricing === 'package'">
      <n-form-item label="超时加班"
        ><n-switch v-model:value="rules.overtime_enabled" :disabled="disabled"
      /></n-form-item>
      <template v-if="rules.overtime_enabled">
        <n-form-item label="小时单价"
          ><n-input-number
            v-model:value="rules.overtime_hourly_rate"
            :min="0"
            :precision="2"
            :disabled="disabled"
        /></n-form-item>
        <n-form-item label="起计分钟"
          ><n-input-number
            v-model:value="rules.overtime_threshold_minutes"
            :min="1"
            :max="60"
            :precision="0"
            :disabled="disabled"
        /></n-form-item>
        <n-form-item label="取整方式"
          ><n-select
            v-model:value="rules.overtime_rounding"
            :options="overtimeRoundingOptions"
            :disabled="disabled"
        /></n-form-item>
      </template>
    </template>
    <n-divider>当地夜班</n-divider>
    <n-form-item label="夜班加价"
      ><n-switch v-model:value="rules.night_enabled" :disabled="disabled"
    /></n-form-item>
    <template v-if="rules.night_enabled">
      <div class="billing-grid">
        <n-form-item label="当地开始"
          ><n-time-picker
            v-model:formatted-value="rules.night_start"
            format="HH:mm"
            value-format="HH:mm"
            :disabled="disabled"
        /></n-form-item>
        <n-form-item label="当地结束"
          ><n-time-picker
            v-model:formatted-value="rules.night_end"
            format="HH:mm"
            value-format="HH:mm"
            :disabled="disabled"
        /></n-form-item>
        <n-form-item label="人工倍率"
          ><n-input-number
            v-model:value="rules.night_multiplier"
            :min="1"
            :max="10"
            :precision="2"
            :disabled="disabled"
        /></n-form-item>
      </div>
      <n-form-item label="适用方式"
        ><n-select
          v-model:value="rules.night_basis"
          :disabled="disabled"
          :options="[
            { label: '按实际夜班分钟占比分摊人工费', value: 'proportional' },
            { label: '区间内涉及夜班则该区间全额加价', value: 'any_overlap' },
          ]"
      /></n-form-item>
      <p>
        入场、出场按北京时间记录，夜班按每次运维的时区判断；支持跨午夜与夏令时。未确认起止时段时费用待确认。
      </p>
    </template>
    <n-divider>紧急维护与交通</n-divider>
    <n-form-item label="紧急加收"
      ><n-input-number
        v-model:value="rules.emergency_fee"
        :min="0"
        :precision="2"
        :disabled="disabled"
        placeholder="仅在本次勾选紧急时计入"
    /></n-form-item>
    <n-form-item label="到场分钟"
      ><n-input-number
        v-model:value="rules.emergency_response_minutes"
        :min="1"
        :max="10080"
        :precision="0"
        :disabled="disabled"
    /></n-form-item>
    <n-form-item label="适用地区"
      ><n-select
        v-model:value="rules.emergency_regions"
        filterable
        tag
        multiple
        :options="[]"
        :disabled="disabled"
        placeholder="留空表示地区不限；填写与记录一致的地区名"
    /></n-form-item>
    <n-form-item label="待确认区"
      ><n-select
        v-model:value="rules.emergency_confirmation_regions"
        multiple
        filterable
        tag
        :options="[]"
        :disabled="disabled"
    /></n-form-item>
    <n-form-item label="紧急夜班"
      ><n-checkbox v-model:checked="rules.night_applies_to_emergency" :disabled="disabled"
        >紧急加收参与夜班倍率</n-checkbox
      ></n-form-item
    >
    <n-form-item label="交通规则"
      ><n-select
        v-model:value="rules.transport_mode"
        :options="transportOptions"
        :disabled="disabled"
    /></n-form-item>
    <n-form-item v-if="rules.transport_mode === 'fixed'" label="每次金额"
      ><n-input-number
        v-model:value="rules.transport_fee"
        :min="0"
        :precision="2"
        :disabled="disabled"
    /></n-form-item>
    <template v-if="rules.transport_mode === 'hourly'">
      <n-form-item label="通勤方式">
        <n-select
          v-model:value="rules.commute_mode"
          :disabled="disabled"
          :options="[
            { label: '每次固定通勤时长', value: 'fixed' },
            { label: '按记录填写实际往返时长', value: 'actual' },
          ]"
        />
      </n-form-item>
      <n-form-item v-if="rules.commute_mode === 'actual'" label="通勤步长（分钟）">
        <n-input-number
          v-model:value="rules.commute_increment_minutes"
          :min="1"
          :max="1440"
          :precision="0"
          :disabled="disabled"
        />
      </n-form-item>
      <n-form-item v-else label="通勤分钟"
        ><n-input-number
          v-model:value="rules.commute_minutes"
          :min="1"
          :max="10080"
          :precision="0"
          :disabled="disabled"
      /></n-form-item>
      <n-form-item label="通勤单价"
        ><n-input-number
          v-model:value="rules.commute_hourly_rate"
          :min="0"
          :precision="2"
          :disabled="disabled"
          placeholder="按小时计费时，留空沿用人工小时单价"
      /></n-form-item>
    </template>
    <n-form-item v-if="rules.transport_mode !== 'none'" label="免交通区"
      ><n-select
        v-model:value="rules.transport_included_regions"
        multiple
        filterable
        tag
        :options="[]"
        :disabled="disabled"
        placeholder="留空表示每次收取；区外收交通费"
    /></n-form-item>
    <p>固定交通费或通勤费用每次只加一次，不占运维工时、不参与夜班倍率。</p>
    <n-divider>项目、结算与收款</n-divider>
    <n-form-item label="单独报价"
      ><n-select
        v-model:value="rules.project_services"
        multiple
        filterable
        tag
        :options="[]"
        :disabled="disabled"
        placeholder="可选，如设备上架、综合布线"
    /></n-form-item>
    <n-form-item label="结算周期"
      ><n-select
        v-model:value="rules.settlement_cycles"
        multiple
        filterable
        tag
        :options="['日结', '周结', '月结', '按次结算'].map((value) => ({ label: value, value }))"
        :disabled="disabled"
        placeholder="可选或自定义"
    /></n-form-item>
    <div v-for="(method, index) in rules.payment_methods" :key="index" class="billing-tier">
      <n-form-item label="收款方式"
        ><n-input
          v-model:value="method.name"
          maxlength="100"
          :disabled="disabled"
          placeholder="例如公司转账、个人收款"
      /></n-form-item>
      <n-form-item label="税费规则"
        ><n-select v-model:value="method.tax_mode" :options="taxOptions" :disabled="disabled"
      /></n-form-item>
      <template v-if="method.tax_mode === 'extra'">
        <n-form-item label="约定税率"
          ><n-input-number
            v-model:value="method.tax_rate"
            :min="0"
            :max="100"
            :precision="2"
            :disabled="disabled"
            placeholder="未确认留空"
            ><template #suffix>%</template></n-input-number
          ></n-form-item
        >
        <n-form-item label="计税范围"
          ><n-select
            v-model:value="method.tax_base"
            :disabled="disabled"
            :options="[
              { label: '人工费', value: 'labor' },
              { label: '人工费＋交通费', value: 'subtotal' },
            ]"
        /></n-form-item>
      </template>
      <n-form-item label="收款说明"
        ><n-input v-model:value="method.note" maxlength="500" :disabled="disabled"
      /></n-form-item>
      <CButton
        show-delete
        size="small"
        :disabled="disabled"
        @delete="rules.payment_methods.splice(index, 1)"
      />
    </div>
    <CButton
      show-save
      save-text="添加收款方式"
      size="small"
      :disabled="disabled || rules.payment_methods.length >= 20"
      @save="addPayment"
    />
    <n-form-item label="规则说明"
      ><n-input v-model:value="rules.note" type="textarea" maxlength="2000" :disabled="disabled"
    /></n-form-item>
    <n-alert v-if="error" type="warning">{{ error }}</n-alert>
    <n-divider>按时间试算</n-divider>
    <n-form-item label="到场北京"
      ><n-date-picker
        v-model:formatted-value="preview.arrived_at"
        type="datetime"
        :actions="['clear', 'confirm']"
        format="yyyy-MM-dd HH:mm"
        value-format="yyyy-MM-dd'T'HH:mm"
        :disabled="disabled"
    /></n-form-item>
    <n-form-item label="离场北京"
      ><n-date-picker
        v-model:formatted-value="preview.left_at"
        type="datetime"
        :actions="['clear', 'confirm']"
        format="yyyy-MM-dd HH:mm"
        value-format="yyyy-MM-dd'T'HH:mm"
        :disabled="disabled"
    /></n-form-item>
    <n-form-item label="运维时区"
      ><n-select
        v-model:value="preview.timezone"
        filterable
        tag
        :options="timezoneOptions"
        :disabled="disabled"
    /></n-form-item>
    <n-form-item label="服务地区"
      ><n-input
        v-model:value="preview.region"
        :disabled="disabled"
        placeholder="如北京、上海、东京；按规则地区名称填写"
    /></n-form-item>
    <BillingQuote
      v-model="preview.context"
      :rules="rules"
      :arrived-at="preview.arrived_at"
      :left-at="preview.left_at"
      :timezone="preview.timezone"
      :region="preview.region"
      :disabled="disabled"
    />
  </div>
</template>
<style scoped>
.billing-editor {
  margin-bottom: 16px;
}
.billing-tier {
  padding: 12px;
  margin: 12px 0;
  border: 1px solid #d9d9d94d;
  border-radius: 8px;
}
.billing-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 12px;
}
.billing-editor :deep(.n-input-number) {
  width: 100%;
}
@media (max-width: 640px) {
  .billing-grid {
    grid-template-columns: 1fr;
  }
}
</style>
