<template>
  <div v-if="sections.length" class="description-input">
    <div v-for="section in sections" :key="section.key" class="description-section">
      <div class="description-title">{{ section.title }}：</div>
      <n-input
        type="textarea"
        :value="fields[section.key]"
        :placeholder="section.placeholder"
        :bordered="false"
        :autosize="{ minRows: section.minRows || 1, maxRows: 6 }"
        @update:value="(value) => updateField(section.key, value)"
      />
    </div>
  </div>
  <n-input
    v-else
    :value="value"
    type="textarea"
    placeholder="请选择工单类型后填写描述"
    :autosize="{ minRows: 7, maxRows: 14 }"
    @update:value="(nextValue) => emit('update:value', nextValue)"
  />
</template>

<script setup>
import { computed, reactive, watch } from 'vue'
import { getTicketDescriptionSections } from '../utils/ticketDescriptionTemplates'

const props = defineProps({
  value: {
    type: String,
    default: '',
  },
  type: {
    type: Number,
    default: null,
  },
})

const emit = defineEmits(['update:value'])

const fields = reactive({})
const sections = computed(() => getTicketDescriptionSections(props.type))

watch(
  () => [props.type, props.value],
  ([type, value]) => {
    if (!getTicketDescriptionSections(type).length) return
    const currentValue = buildDescription()
    if (value === currentValue) return
    resetFields(parseDescription(type, value || ''))
    if (!value) {
      emitDescription()
    }
  },
  { immediate: true }
)

function resetFields(nextFields) {
  Object.keys(fields).forEach((key) => {
    delete fields[key]
  })
  sections.value.forEach((section) => {
    fields[section.key] = nextFields[section.key] || ''
  })
}

function updateField(key, value) {
  fields[key] = value
  emitDescription()
}

function emitDescription() {
  emit('update:value', buildDescription())
}

function buildDescription() {
  return sections.value
    .map((section) => {
      const content = fields[section.key]?.trimEnd() || ''
      return `${section.title}：\n${content}`
    })
    .join('\n\n')
}

function parseDescription(type, value) {
  const nextFields = {}
  const currentSections = getTicketDescriptionSections(type)
  currentSections.forEach((section, index) => {
    const startPattern = escapeRegExp(`${section.title}：`)
    const nextSection = currentSections[index + 1]
    const endPattern = nextSection ? `(?=\\n\\s*${escapeRegExp(`${nextSection.title}：`)})` : '$'
    const match = value.match(new RegExp(`${startPattern}\\s*\\n?([\\s\\S]*?)${endPattern}`))
    const content = match?.[1]?.trim() || ''
    nextFields[section.key] = content === section.placeholder.trim() ? '' : content
  })
  return nextFields
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}
</script>

<style scoped>
.description-input {
  box-sizing: border-box;
  width: 100%;
  min-width: 0;
  overflow: hidden;
  border: 1px solid var(--n-border-color, #e0e0e6);
  border-radius: var(--n-border-radius, 3px);
  background: var(--n-color, #fff);
  transition: border-color 0.3s var(--n-bezier), box-shadow 0.3s var(--n-bezier);
}

.description-input:hover {
  border-color: var(--n-border-hover, #36ad6a);
}

.description-input:focus-within {
  border-color: var(--n-border-focus, #36ad6a);
  box-shadow: 0 0 0 2px var(--n-box-shadow-focus, rgb(24 160 88 / 20%));
}

.description-section {
  padding: 9px 12px 7px;
}

.description-section + .description-section {
  padding-top: 10px;
}

.description-title {
  margin-bottom: 2px;
  color: var(--n-text-color, #333639);
  font-size: 14px;
  line-height: 1.5;
}

.description-section :deep(.n-input) {
  width: 100%;
  --n-padding-left: 0;
  --n-padding-right: 0;
  --n-color: transparent;
  --n-color-focus: transparent;
  --n-color-disabled: transparent;
}

.description-section :deep(.n-input__textarea-el),
.description-section :deep(.n-input__placeholder) {
  line-height: 1.55;
}
</style>
