<template>
  <div ref="wrapperRef" class="description-wrapper" @click="handleWrapperClick">
    <n-input
      class="description-textarea"
      :value="value"
      type="textarea"
      :placeholder="descriptionPlaceholder"
      :autosize="{ minRows: 10, maxRows: 18 }"
      @update:value="handleInput"
    />
    <pre v-if="hintOverlay" class="description-hints">{{ hintOverlay }}</pre>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import {
  TICKET_DESCRIPTION_CURSOR_PLACEHOLDER,
  cleanupDeprecatedTicketDescription,
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
const wrapperRef = ref(null)
const hiddenHintKeysByType = ref({})

const descriptionPlaceholder = computed(() => '')
const hintOverlay = computed(() => {
  return buildHintOverlay(props.type, props.value || '')
})

watch(
  () => [props.type, props.value],
  ([type, value]) => {
    if (type === null && !(value || '')) {
      hiddenHintKeysByType.value = {}
    }

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
    if (!shouldReplaceTemplate(currentValue, oldType, oldTemplate)) return

    emit('update:value', nextTemplate)
  },
  { immediate: true }
)

function handleInput(nextValue) {
  markEditedSections(props.value || '', nextValue || '')
  emit('update:value', nextValue)
}

function handleWrapperClick(event) {
  const textarea = wrapperRef.value?.querySelector('textarea')
  if (!textarea) return

  const targetPosition = getEmptySectionPositionByClick(event, textarea)
  if (targetPosition === null) return

  window.setTimeout(() => {
    textarea.focus()
    textarea.setSelectionRange(targetPosition, targetPosition)
  }, 0)
}

function buildHintOverlay(type, value) {
  const sections = getTicketDescriptionSections(type)
  if (!sections.length || !value.trim()) return ''
  if (!hasAnySectionTitle(value, sections)) return ''

  return sections
    .map((section, index) => {
      const content = getSectionContent(value, sections, index)
      const shouldShowHint = !getHiddenHintKeys(type).has(section.key) && !content.trim()
      return `\n${shouldShowHint ? section.placeholder : ''}`
    })
    .join('\n')
}

function getHiddenHintKeys(type) {
  return hiddenHintKeysByType.value[String(type)] || new Set()
}

function setHiddenHintKeys(type, keys) {
  hiddenHintKeysByType.value = {
    ...hiddenHintKeysByType.value,
    [String(type)]: keys,
  }
}

function markEditedSections(previousValue, nextValue) {
  const sections = getTicketDescriptionSections(props.type)
  if (!sections.length) return

  if (!nextValue.trim() || !hasAnySectionTitle(nextValue, sections)) {
    setHiddenHintKeys(props.type, new Set(sections.map((section) => section.key)))
    return
  }

  const nextHiddenKeys = new Set(getHiddenHintKeys(props.type))
  sections.forEach((section, index) => {
    const previousContent = getSectionContent(previousValue, sections, index)
    const nextContent = getSectionContent(nextValue, sections, index)
    if (previousContent !== nextContent) {
      nextHiddenKeys.add(section.key)
    }
  })
  setHiddenHintKeys(props.type, nextHiddenKeys)
}

function getEmptySectionPositionByClick(event, textarea) {
  const sections = getTicketDescriptionSections(props.type)
  const value = props.value || ''
  if (!sections.length || !hasAnySectionTitle(value, sections)) return null

  const clickLine = getClickedLine(event, textarea)
  if (clickLine < 0) return null

  const targetSection = sections.find((section, index) => {
    const content = getSectionContent(value, sections, index)
    if (content.trim() || getHiddenHintKeys(props.type).has(section.key)) return false

    const contentStart = getSectionContentStart(value, section)
    if (contentStart < 0) return false

    const contentLine = getLineIndexAtPosition(value, contentStart)
    const nextTitle = sections[index + 1] ? `${sections[index + 1].title}：` : ''
    const nextIndex = nextTitle ? value.indexOf(nextTitle, contentStart) : -1
    const nextTitleLine = nextIndex >= 0 ? getLineIndexAtPosition(value, nextIndex) : Number.POSITIVE_INFINITY
    return clickLine >= contentLine && clickLine < nextTitleLine
  })

  if (!targetSection) return null
  return getSectionContentStart(value, targetSection)
}

function getClickedLine(event, textarea) {
  const rect = textarea.getBoundingClientRect()
  const styles = window.getComputedStyle(textarea)
  const lineHeight = Number.parseFloat(styles.lineHeight) || Number.parseFloat(styles.fontSize) * 1.55
  const paddingTop = Number.parseFloat(styles.paddingTop) || 0
  return Math.floor((event.clientY - rect.top - paddingTop + textarea.scrollTop) / lineHeight)
}

function getSectionContentStart(value, section) {
  const sectionTitle = `${section.title}：`
  const titleStart = value.indexOf(sectionTitle)
  if (titleStart < 0) return -1

  let contentStart = titleStart + sectionTitle.length
  if (value[contentStart] === '\n') contentStart += 1
  return contentStart
}

function getLineIndexAtPosition(value, position) {
  return value.slice(0, position).split('\n').length - 1
}

function hasAnySectionTitle(value, sections) {
  return sections.some((section) => value.includes(`${section.title}：`))
}

function shouldReplaceTemplate(value, oldType, oldTemplate) {
  if (!value.trim()) return true
  if (value === oldTemplate) return true

  const oldSections = getTicketDescriptionSections(oldType)
  if (!oldSections.length || !hasAnySectionTitle(value, oldSections)) return false

  return oldSections.every((section, index) => {
    const content = getSectionContent(value, oldSections, index)
    return !content.trim()
  })
}

function getSectionContent(value, sections, index) {
  const sectionTitle = `${sections[index].title}：`
  const startIndex = value.indexOf(sectionTitle)
  if (startIndex < 0) return ''

  const contentStart = startIndex + sectionTitle.length
  const nextTitle = sections[index + 1] ? `${sections[index + 1].title}：` : ''
  const nextIndex = nextTitle ? value.indexOf(nextTitle, contentStart) : -1
  const content = nextIndex >= 0 ? value.slice(contentStart, nextIndex) : value.slice(contentStart)
  return content.replaceAll(TICKET_DESCRIPTION_CURSOR_PLACEHOLDER, '').trim()
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
