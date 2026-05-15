<template>
  <div class="description-wrapper">
    <n-input
      class="description-textarea"
      :value="value"
      type="textarea"
      :placeholder="descriptionPlaceholder"
      :autosize="{ minRows: 10, maxRows: 18 }"
      @update:value="(nextValue) => emit('update:value', nextValue)"
    />
    <pre v-if="hintOverlay" class="description-hints">{{ hintOverlay }}</pre>
  </div>
</template>

<script setup>
import { computed, watch } from 'vue'
import {
  cleanupDeprecatedTicketDescription,
  getTicketDescriptionPlaceholder,
  getTicketDescriptionSections,
  getTicketDescriptionTitleTemplate,
} from '../utils/ticketDescriptionTemplates'

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

const descriptionPlaceholder = computed(() => getTicketDescriptionPlaceholder(props.type))
const hintOverlay = computed(() => buildHintOverlay(props.type, props.value || ''))

watch(
  () => [props.type, props.value],
  ([type, value]) => {
    const cleanedValue = cleanupDeprecatedTicketDescription(type, value || '')
    if (cleanedValue !== (value || '')) {
      emit('update:value', cleanedValue)
    }
  },
  { immediate: true }
)

watch(
  () => props.type,
  (type, oldType) => {
    const nextTemplate = getTicketDescriptionTitleTemplate(type)
    if (!nextTemplate) return

    const oldTemplate = getTicketDescriptionTitleTemplate(oldType)
    const currentValue = props.value || ''
    if (currentValue.trim() && currentValue !== oldTemplate) return

    emit('update:value', nextTemplate)
  },
  { immediate: true }
)

function buildHintOverlay(type, value) {
  const sections = getTicketDescriptionSections(type)
  if (!sections.length || !value.trim()) return ''

  return sections
    .map((section, index) => {
      const content = getSectionContent(value, sections, index)
      return `\n${content.trim() ? '' : section.placeholder}`
    })
    .join('\n')
}

function getSectionContent(value, sections, index) {
  const sectionTitle = `${sections[index].title}：`
  const startIndex = value.indexOf(sectionTitle)
  if (startIndex < 0) return ''

  const contentStart = startIndex + sectionTitle.length
  const nextTitle = sections[index + 1] ? `${sections[index + 1].title}：` : ''
  const nextIndex = nextTitle ? value.indexOf(nextTitle, contentStart) : -1
  const content = nextIndex >= 0 ? value.slice(contentStart, nextIndex) : value.slice(contentStart)
  return content.trim()
}
</script>

<style scoped>
.description-wrapper {
  position: relative;
  width: 100%;
}

.description-hints {
  position: absolute;
  inset: 0;
  box-sizing: border-box;
  margin: 0;
  padding: 8px 12px;
  color: #b7bdc7;
  font-family: inherit;
  font-size: 14px;
  line-height: 1.55;
  pointer-events: none;
  white-space: pre-wrap;
  word-break: break-word;
}

.description-textarea :deep(.n-input__textarea-el) {
  line-height: 1.55;
}
</style>
