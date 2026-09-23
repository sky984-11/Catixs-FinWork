<script setup>
import { computed, ref, watch } from 'vue'
import CButton from '@/components/public/CButton.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import AdditionalFeeEditor from './AdditionalFeeEditor.vue'
import {
  billingCurrencies,
  editableBillingRules,
  overtimeRoundingOptions,
  validateBillingRules,
} from './billing.mjs'
const props = defineProps({ modelValue: { type: Object, required: true }, disabled: Boolean })
const emit = defineEmits(['update:modelValue'])
const rules = ref(editableBillingRules(props.modelValue))
watch(
  () => props.modelValue,
  (value) => {
    if (JSON.stringify(value) !== JSON.stringify(rules.value))
      rules.value = editableBillingRules(value)
  },
  { deep: true }
)
watch(rules, (value) => emit('update:modelValue', JSON.parse(JSON.stringify(value))), {
  deep: true,
})
const currencies = billingCurrencies.map((value) => ({ label: value, value }))
const pricingOptions = [
  { label: '固定小时单价', value: 'hourly' },
  { label: '按时长固定总价', value: 'package' },
  { label: '分段小时单价', value: 'tiered_hourly' },
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
</script>
<template>
  <div class="billing-editor">
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
        ><template #save-icon><TheIcon icon="mdi:plus" :size="18" /></template
      ></CButton>
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
    <AdditionalFeeEditor
      v-model="rules.additional_fees"
      :currency="rules.currency"
      :disabled="disabled"
    />
    <n-alert v-if="error" type="warning">{{ error }}</n-alert>
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
