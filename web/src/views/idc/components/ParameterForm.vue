<template>
  <n-grid cols="1 680:2" responsive="self" :x-gap="18">
    <n-form-item-gi
      v-for="field in visibleFields"
      :key="field.key"
      :label="field.label + (field.unit ? `（${field.unit}）` : '')"
      :required="field.required && !optional"
    >
      <n-select
        v-if="field.type === 'select'"
        :value="modelValue[field.key] || null"
        :options="field.options"
        :disabled="disabled"
        :placeholder="`请选择${field.label}`"
        @update:value="update(field.key, $event)"
      />
      <n-input-number
        v-else-if="field.type === 'number'"
        :value="modelValue[field.key] ? Number(modelValue[field.key]) : null"
        :min="0.0001"
        :max="1000000000"
        :disabled="disabled"
        style="width: 100%"
        @update:value="update(field.key, $event)"
      />
      <n-input
        v-else
        :value="modelValue[field.key] || ''"
        :disabled="disabled"
        :maxlength="2000"
        :placeholder="`请输入${field.label}`"
        @update:value="update(field.key, $event)"
      />
    </n-form-item-gi>
  </n-grid>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  schema: { type: Object, default: () => ({ fields: [] }) },
  modelValue: { type: Object, required: true },
  disabled: Boolean,
  optional: Boolean,
})
const emit = defineEmits(['update:modelValue'])
const isVisible = (field, values) =>
  Object.entries(field.when || {}).every(([key, allowed]) => allowed.includes(values[key]))
const visibleFields = computed(() =>
  (props.schema.fields || []).filter((field) => isVisible(field, props.modelValue))
)
function update(key, value) {
  const next = { ...props.modelValue, [key]: value }
  for (const field of props.schema.fields || []) {
    if (!isVisible(field, next)) delete next[field.key]
  }
  emit('update:modelValue', next)
}
</script>
