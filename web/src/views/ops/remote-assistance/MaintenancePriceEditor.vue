<script setup>
import { computed } from 'vue'
import { billingCurrencies } from './billing.mjs'

const props = defineProps({
  modelValue: { type: Object, default: null },
  disabled: Boolean,
  allowCustom: Boolean,
  engineerRules: { type: Object, default: null },
})
const emit = defineEmits(['update:modelValue'])
const price = computed(() => ({
  kind: 'internal',
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
const custom = computed(() => ['fixed', 'hourly'].includes(price.value.kind))
const selectedMode = computed(() =>
  props.allowCustom && custom.value
    ? 'custom'
    : ['internal', 'fixed'].includes(price.value.kind)
    ? price.value.kind
    : null
)
function selectCustomKind(kind) {
  const next = { ...price.value, kind }
  if (kind === 'hourly' && next.hourly_rate == null) {
    const rules = props.engineerRules
    next.hourly_rate = rules?.pricing === 'hourly' ? rules.hourly_rate ?? null : null
    next.currency = rules?.currency || next.currency
  }
  emit('update:modelValue', next)
}
</script>

<template>
  <section class="job-price">
    <n-form-item label="本次施工报价">
      <n-radio-group
        :value="selectedMode"
        :disabled="disabled"
        class="price-modes"
        @update:value="selectCustomKind($event === 'custom' ? 'fixed' : $event)"
      >
        <n-radio-button value="internal">工程师规则</n-radio-button>
        <n-radio-button :value="allowCustom ? 'custom' : 'fixed'">{{
          allowCustom ? '自定义' : '一口价'
        }}</n-radio-button>
      </n-radio-group>
    </n-form-item>
    <div v-if="allowCustom && custom" class="price-switch-card">
      <div>
        <strong>自定义方式</strong>
        <p>切换一口价与工程师单价微调</p>
      </div>
      <n-switch
        :value="price.kind"
        checked-value="hourly"
        unchecked-value="fixed"
        size="large"
        aria-label="自定义方式：一口价或工程师单价微调"
        :disabled="disabled"
        @update:value="selectCustomKind"
      >
        <template #checked>工程师单价微调</template>
        <template #unchecked>一口价</template>
      </n-switch>
    </div>
    <n-alert v-if="!selectedMode" type="info" class="legacy-price"
      >已保留这条记录的历史报价，需调整时请选择工程师规则或一口价。</n-alert
    >
    <div
      v-if="price.kind === 'fixed' || (allowCustom && price.kind === 'hourly')"
      class="price-fields"
    >
      <n-form-item :label="price.kind === 'hourly' ? '本次人工小时单价' : '一口价总额'">
        <n-input-number
          :value="
            price.kind === 'hourly'
              ? price.hourly_rate == null
                ? null
                : Number(price.hourly_rate)
              : price.fixed_fee == null
              ? null
              : Number(price.fixed_fee)
          "
          :min="0"
          :max="9999999999.99"
          :precision="2"
          :disabled="disabled"
          placeholder="未确认留空"
          @update:value="update(price.kind === 'hourly' ? 'hourly_rate' : 'fixed_fee', $event)"
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
    </div>
    <p v-if="allowCustom && price.kind === 'hourly'">
      仅调整本次人工小时单价，不修改工程师档案。最低工时、取整、夜班及附加费用继续按规则计算；原固定档位改按本次小时单价计费。
    </p>
    <template v-if="price.kind === 'fixed'">
      <div class="price-switch-card">
        <div>
          <strong>现场费用</strong>
          <p>{{ price.expenses_included ? '已包含在一口价中' : '按实际支出另行累加' }}</p>
        </div>
        <n-switch
          :value="price.expenses_included"
          :disabled="disabled"
          aria-label="现场费用是否包含在一口价中"
          @update:value="update('expenses_included', $event)"
          ><template #checked>已含</template><template #unchecked>另计</template></n-switch
        >
      </div>
      <p>一口价不再叠加工程师人工和规则附加费用。</p>
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
.price-modes {
  display: flex;
  width: 100%;
  padding: 4px;
  border-radius: 10px;
  background: #f1f5f9;
}
.price-modes :deep(.n-radio-button) {
  flex: 1;
  text-align: center;
  border-radius: 7px;
  overflow: hidden;
}
.price-switch-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  padding: 14px 16px;
  margin-bottom: 18px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #f8fafc;
}
.price-switch-card strong {
  font-size: 13px;
  color: #334155;
}
.price-switch-card p {
  margin: 4px 0 0;
}
.job-price :deep(.n-input),
.job-price :deep(.n-base-selection) {
  border-radius: 8px;
}
.price-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}
.legacy-price {
  margin-bottom: 16px;
}
@media (max-width: 600px) {
  .price-fields {
    grid-template-columns: minmax(0, 1fr);
    gap: 0;
  }
}
</style>
