<script setup>
import { computed } from 'vue'
import { billingCurrencies } from './billing.mjs'

const props = defineProps({ modelValue: { type: Object, default: null }, disabled: Boolean })
const emit = defineEmits(['update:modelValue'])
const price = computed(() => ({
  kind: 'pending',
  hourly_rate: null,
  fixed_fee: null,
  currency: 'USD',
  expenses_included: false,
  note: '',
  ...props.modelValue,
}))
function update(key, value) {
  emit('update:modelValue', { ...price.value, [key]: value })
}
</script>

<template>
  <section class="job-price">
    <n-form-item label="本次施工报价">
      <n-select
        :value="price.kind"
        :disabled="disabled"
        :options="[
          { label: '报价待确认', value: 'pending' },
          { label: '按工程师规则', value: 'internal' },
          { label: '本次按小时报价', value: 'hourly' },
          { label: '本次一口价', value: 'fixed' },
        ]"
        @update:value="update('kind', $event)"
      />
    </n-form-item>
    <template v-if="['hourly', 'fixed'].includes(price.kind)">
      <n-form-item :label="price.kind === 'fixed' ? '一口价总额' : '本次小时单价'">
        <n-input-number
          :value="
            price.kind === 'fixed'
              ? price.fixed_fee == null
                ? null
                : Number(price.fixed_fee)
              : price.hourly_rate == null
              ? null
              : Number(price.hourly_rate)
          "
          :min="0"
          :max="9999999999.99"
          :precision="2"
          :disabled="disabled"
          placeholder="未确认留空"
          @update:value="update(price.kind === 'fixed' ? 'fixed_fee' : 'hourly_rate', $event)"
        />
      </n-form-item>
      <n-form-item label="本次报价币种">
        <n-select
          :value="price.currency"
          :options="billingCurrencies.map((value) => ({ label: value, value }))"
          :disabled="disabled"
          @update:value="update('currency', $event)"
        />
      </n-form-item>
    </template>
    <template v-if="price.kind === 'fixed'">
      <n-form-item label="现场报销已含在一口价中">
        <n-switch
          :value="price.expenses_included"
          :disabled="disabled"
          @update:value="update('expenses_included', $event)"
        />
      </n-form-item>
      <p>一口价不再叠加工时、通勤、夜班、紧急和规则税费。关闭“报销已含”时，现场费用另行累加。</p>
    </template>
    <n-form-item label="报价说明">
      <n-input
        :value="price.note"
        type="textarea"
        maxlength="1000"
        :disabled="disabled"
        placeholder="填写本次施工范围、报价及含税约定"
        @update:value="update('note', $event)"
      />
    </n-form-item>
  </section>
</template>

<style scoped>
.job-price {
  width: 100%;
}
.job-price p {
  margin: 0 0 12px;
  color: #64748b;
  font-size: 12px;
}
</style>
