<template>
  <div class="charge-editor">
    <n-alert type="info" :show-icon="false">
      周期单价按选定周期填写。用量收费须说明采样、方向、单位与缺样处理；0元与未报价不同。
    </n-alert>
    <section v-for="(charge, index) in modelValue" :key="index" class="charge-card">
      <div class="charge-head">
        <strong>费用组件 {{ index + 1 }}</strong>
        <CButton
          show-delete
          :disabled="disabled || modelValue.length === 1"
          @delete="remove(index)"
        />
      </div>
      <n-grid cols="1 640:2" responsive="self" :x-gap="16">
        <n-form-item-gi label="组件编码" required
          ><n-input v-model:value="charge.code" :disabled="disabled" placeholder="例如 mrc、setup"
        /></n-form-item-gi>
        <n-form-item-gi label="费用名称" required
          ><n-input v-model:value="charge.name" :disabled="disabled"
        /></n-form-item-gi>
        <n-form-item-gi label="费用类型"
          ><n-select v-model:value="charge.kind" :disabled="disabled" :options="kinds"
        /></n-form-item-gi>
        <n-form-item-gi label="包含关系"
          ><n-select
            v-model:value="charge.treatment"
            :disabled="disabled"
            :options="treatments"
            @update:value="setTreatment(charge)"
        /></n-form-item-gi>
        <n-form-item-gi label="未税单价" required
          ><n-input-number
            v-model:value="charge.amount"
            :min="0"
            :max="1000000000"
            :disabled="disabled || charge.treatment !== 'separate'"
        /></n-form-item-gi>
        <n-form-item-gi label="税率（0–1，如0.06）"
          ><n-input-number
            v-model:value="charge.tax_rate"
            :min="0"
            :max="1"
            :step="0.01"
            :disabled="disabled"
        /></n-form-item-gi>
        <n-form-item-gi label="计量单位"
          ><n-input v-model:value="charge.unit" :disabled="disabled"
        /></n-form-item-gi>
        <template v-if="charge.kind !== 'nrc'">
          <n-form-item-gi label="结算周期"
            ><n-select v-model:value="charge.interval" :disabled="disabled" :options="intervals"
          /></n-form-item-gi>
          <n-form-item-gi v-if="charge.kind === 'recurring'" label="周期计费时点"
            ><n-select v-model:value="charge.timing" :disabled="disabled" :options="timings"
          /></n-form-item-gi>
          <n-form-item-gi v-if="charge.kind === 'recurring'" label="首尾期折算"
            ><n-select v-model:value="charge.proration" :disabled="disabled" :options="prorations"
          /></n-form-item-gi>
        </template>
        <template v-if="charge.kind === 'usage'">
          <n-form-item-gi label="计量模式"
            ><n-select v-model:value="charge.usage_mode" :disabled="disabled" :options="usageModes"
          /></n-form-item-gi>
          <n-form-item-gi label="包内额度 / 承诺值"
            ><n-input-number v-model:value="charge.allowance" :min="0" :disabled="disabled"
          /></n-form-item-gi>
          <n-form-item-gi label="最低计量数量"
            ><n-input-number v-model:value="charge.minimum" :min="0" :disabled="disabled"
          /></n-form-item-gi>
          <n-form-item-gi v-if="charge.usage_mode === 'hours'" label="工时进位单位"
            ><n-input-number
              v-model:value="charge.step"
              :min="0.01"
              :step="0.25"
              :disabled="disabled"
          /></n-form-item-gi>
          <n-form-item-gi label="费用封顶（可不填）"
            ><n-input-number v-model:value="charge.cap" :min="0" clearable :disabled="disabled"
          /></n-form-item-gi>
          <n-form-item-gi label="计量规则与核实依据" required
            ><n-input v-model:value="charge.meter_rule" type="textarea" :disabled="disabled"
          /></n-form-item-gi>
        </template>
      </n-grid>
    </section>
    <CButton show-save save-text="添加费用组件" :disabled="disabled" @save="add" />
  </div>
</template>

<script setup>
import CButton from '@/components/public/CButton.vue'
const props = defineProps({ modelValue: { type: Array, required: true }, disabled: Boolean })
const emit = defineEmits(['update:modelValue'])
const options = (entries) => entries.map(([value, label]) => ({ value, label }))
const kinds = options([
  ['recurring', '周期费用'],
  ['nrc', '一次性费用'],
  ['usage', '用量费用'],
])
const treatments = options([
  ['separate', '单独计费'],
  ['included', '主产品已含'],
  ['free', '免费'],
  ['customer', '客户自备'],
])
const intervals = options([
  [1, '月'],
  [3, '季度'],
  [12, '年'],
])
const timings = options([
  ['arrears', '周期结束出账'],
  ['advance', '周期开始出账'],
])
const prorations = options([
  ['actual_days', '实际天数'],
  ['30_days', '每月30天'],
  ['full_period', '整周期不折算'],
])
const usageModes = options([
  ['quantity', '核实用量'],
  ['95th', '核实95值'],
  ['hours', '工时'],
])
function setTreatment(charge) {
  if (charge.treatment !== 'separate') charge.amount = 0
}
function add() {
  emit('update:modelValue', [
    ...props.modelValue,
    {
      code: `fee_${props.modelValue.length + 1}`,
      name: '',
      kind: 'recurring',
      amount: null,
      tax_rate: 0,
      treatment: 'separate',
      unit: '项',
      interval: 1,
      proration: 'actual_days',
      timing: 'arrears',
      usage_mode: 'quantity',
      minimum: 0,
      step: 1,
      allowance: 0,
      cap: null,
      meter_rule: '',
    },
  ])
}
function remove(index) {
  emit(
    'update:modelValue',
    props.modelValue.filter((_, i) => i !== index)
  )
}
</script>

<style scoped>
.charge-editor {
  display: grid;
  gap: 16px;
}
.charge-card {
  padding: 16px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
}
.charge-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.charge-editor :deep(.n-input-number) {
  width: 100%;
}
</style>
