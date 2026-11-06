<template>
  <span class="field-label">
    <span>{{ label }}</span>
    <n-popover
      v-model:show="show"
      trigger="hover"
      placement="top"
      :style="{ maxWidth: 'min(340px, calc(100vw - 40px))' }"
    >
      <template #trigger>
        <span
          class="field-help"
          role="button"
          tabindex="0"
          :aria-label="`${label}填写说明`"
          :aria-expanded="show"
          @click.stop.prevent="show = true"
          @focus="show = true"
          @blur="show = false"
          @keydown.enter.stop.prevent="show = !show"
          @keydown.space.stop.prevent="show = !show"
          @keydown.esc.stop="show = false"
          >?</span
        >
      </template>
      <div class="field-help-content">{{ help }}</div>
    </n-popover>
  </span>
</template>

<script setup>
import { ref } from 'vue'
import { NPopover } from 'naive-ui'

defineProps({ label: { type: String, required: true }, help: { type: String, required: true } })
const show = ref(false)
</script>

<style scoped>
.field-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.field-help {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 16px;
  height: 16px;
  border: 1px solid currentColor;
  border-radius: 50%;
  opacity: 0.65;
  font-size: 12px;
  line-height: 1;
  cursor: help;
}
.field-help:hover,
.field-help:focus-visible {
  opacity: 1;
  outline: 2px solid currentColor;
  outline-offset: 2px;
}
.field-help-content {
  line-height: 1.7;
  white-space: pre-line;
  overflow-wrap: anywhere;
}
</style>
