<template>
  <teleport to="body">
    <div
      v-if="visible"
      class="fw-assistant"
      :class="{ open: panelOpen, dragging: draggingState.active }"
      :style="assistantStyle"
    >
      <section
        v-if="panelOpen"
        class="fw-assistant-panel"
        :style="panelStyle"
        aria-label="FW小助手对话"
      >
        <header class="fw-assistant-head">
          <div class="fw-assistant-brand">
            <span class="fw-assistant-avatar">
              <img :src="logoUrl" alt="FW" />
            </span>
            <div>
              <strong>FW小助手</strong>
              <small>{{ assistantStatusText }}</small>
            </div>
          </div>
          <button class="fw-icon-button" type="button" title="关闭" @click="panelOpen = false">
            <TheIcon icon="mdi:close" :size="18" />
          </button>
        </header>

        <div ref="messagesEl" class="fw-assistant-messages">
          <article
            v-for="message in messages"
            :key="message.id"
            class="fw-message"
            :class="`is-${message.role}`"
          >
            <div class="fw-message-bubble">
              <span v-if="message.loading" class="fw-loading-dots" aria-label="正在查询 FinWork 数据">
                <i></i>
                <i></i>
                <i></i>
              </span>
              <div
                v-else-if="message.role === 'assistant'"
                class="fw-markdown"
                v-html="renderMarkdown(message.content)"
              ></div>
              <template v-else>{{ message.content }}</template>
            </div>
          </article>
        </div>

        <form class="fw-assistant-input" @submit.prevent="sendMessage">
          <textarea
            v-model="draft"
            rows="1"
            placeholder="输入问题，按 Enter 发送"
            :disabled="sending"
            @keydown.enter.exact.prevent="sendMessage"
          ></textarea>
          <button type="submit" :disabled="!draft.trim() || sending" title="发送">
            <TheIcon icon="mdi:send" :size="18" />
          </button>
        </form>
      </section>

      <button
        class="fw-assistant-fab"
        type="button"
        title="FW小助手"
        @pointerdown="startDrag($event, 'fab')"
        @click="togglePanel"
      >
        <span class="fw-assistant-orbit"></span>
        <img :src="logoUrl" alt="FW小助手" draggable="false" />
      </button>
    </div>
  </teleport>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/api'
import logoUrl from '@/assets/svg/logo.svg?url'
import TheIcon from '@/components/icon/TheIcon.vue'
import { getToken } from '@/utils'

defineOptions({ name: 'FwAssistant' })

const DEEPSEEK_MODEL = import.meta.env.VITE_FW_ASSISTANT_MODEL || 'deepseek-ai/DeepSeek-V3'

const hiddenPathPrefixes = ['/login', '/asset/cabinet-photo-upload/', '/ops/virtual-machine/console']
const route = useRoute()
const panelOpen = ref(false)
const sending = ref(false)
const draft = ref('')
const messagesEl = ref(null)
const ASSISTANT_POSITION_KEY = 'fw-assistant-position'
const DEFAULT_ASSISTANT_SIZE = 66
const PANEL_WIDTH = 380
const PANEL_HEIGHT = 470
const PANEL_GAP = 14
const assistantPosition = reactive({
  left: 0,
  top: 0,
})
const draggingState = reactive({
  active: false,
  moved: false,
  startX: 0,
  startY: 0,
  offsetX: 0,
  offsetY: 0,
  width: DEFAULT_ASSISTANT_SIZE,
  height: DEFAULT_ASSISTANT_SIZE,
  pointerId: null,
  dragTarget: null,
  source: '',
})
const messages = ref([
  {
    id: Date.now(),
    role: 'assistant',
    content: '你好，我是 FW 小助手。我会先查询 FinWork 实时数据，再帮你分析需求、总结项目、处理工单和生成跟进建议。',
  },
])

const visible = computed(() => {
  const currentPath = route.path
  if (!getToken()) return false
  return !hiddenPathPrefixes.some((prefix) => currentPath.startsWith(prefix))
})

const assistantStatusText = computed(() => DEEPSEEK_MODEL)

const assistantStyle = computed(() => ({
  left: `${assistantPosition.left}px`,
  top: `${assistantPosition.top}px`,
}))
const panelStyle = computed(() => {
  const margin = getAssistantMargin()
  const assistantSize = getAssistantSize()
  const maxPanelWidth = Math.min(PANEL_WIDTH, window.innerWidth - margin * 2)
  const left = clamp(
    0,
    margin - assistantPosition.left,
    window.innerWidth - margin - maxPanelWidth - assistantPosition.left
  )
  const spaceAbove = assistantPosition.top - margin
  const spaceBelow = window.innerHeight - assistantPosition.top - assistantSize - margin
  const shouldOpenBelow = spaceBelow > spaceAbove
  const vertical = shouldOpenBelow
    ? { top: `${assistantSize + PANEL_GAP}px` }
    : { bottom: `${assistantSize + PANEL_GAP}px` }
  return {
    ...vertical,
    left: `${left}px`,
  }
})

watch(
  () => route.path,
  () => {
    if (!visible.value) panelOpen.value = false
  }
)

onMounted(() => {
  restoreAssistantPosition()
  window.addEventListener('resize', keepAssistantInViewport)
})

onBeforeUnmount(() => {
  stopDrag()
  window.removeEventListener('resize', keepAssistantInViewport)
})

function togglePanel(event) {
  if (draggingState.moved) {
    event?.preventDefault()
    draggingState.moved = false
    return
  }
  panelOpen.value = !panelOpen.value
}

function startDrag(event, source = 'fab') {
  if (event.button !== 0) return
  if (source === 'header' && event.target?.closest?.('button, textarea, input, select, a')) return
  const assistantEl = event.currentTarget?.closest?.('.fw-assistant')
  if (!assistantEl) return

  const rect = assistantEl.getBoundingClientRect()
  draggingState.active = true
  draggingState.moved = false
  draggingState.startX = event.clientX
  draggingState.startY = event.clientY
  draggingState.offsetX = event.clientX - rect.left
  draggingState.offsetY = event.clientY - rect.top
  draggingState.width = rect.width
  draggingState.height = rect.height
  draggingState.pointerId = event.pointerId
  draggingState.dragTarget = event.currentTarget
  draggingState.source = source
  event.currentTarget?.setPointerCapture?.(event.pointerId)

  window.addEventListener('pointermove', handleDragMove, { passive: false })
  window.addEventListener('pointerup', stopDrag)
  window.addEventListener('pointercancel', stopDrag)
  window.addEventListener('blur', stopDrag)
}

function handleDragMove(event) {
  if (!draggingState.active) return
  if (draggingState.pointerId !== null && event.pointerId !== draggingState.pointerId) return
  const distance = Math.hypot(event.clientX - draggingState.startX, event.clientY - draggingState.startY)
  if (distance > 4) draggingState.moved = true
  event.preventDefault()

  const margin = getAssistantMargin()
  const maxLeft = Math.max(window.innerWidth - draggingState.width - margin, margin)
  const maxTop = Math.max(window.innerHeight - draggingState.height - margin, margin)
  assistantPosition.left = clamp(
    event.clientX - draggingState.offsetX,
    margin,
    maxLeft
  )
  assistantPosition.top = clamp(
    event.clientY - draggingState.offsetY,
    margin,
    maxTop
  )
}

function stopDrag() {
  if (!draggingState.active) return
  const shouldKeepMoved = draggingState.source === 'fab' && draggingState.moved
  if (draggingState.pointerId !== null) {
    try {
      draggingState.dragTarget?.releasePointerCapture?.(draggingState.pointerId)
    } catch {
      // The pointer may already be released by the browser.
    }
  }
  draggingState.active = false
  draggingState.moved = shouldKeepMoved
  draggingState.pointerId = null
  draggingState.dragTarget = null
  draggingState.source = ''
  window.removeEventListener('pointermove', handleDragMove)
  window.removeEventListener('pointerup', stopDrag)
  window.removeEventListener('pointercancel', stopDrag)
  window.removeEventListener('blur', stopDrag)
  saveAssistantPosition()
}

function keepAssistantInViewport() {
  const assistantEl = document.querySelector('.fw-assistant')
  const rect = assistantEl?.getBoundingClientRect()
  const width = rect?.width || DEFAULT_ASSISTANT_SIZE
  const height = rect?.height || DEFAULT_ASSISTANT_SIZE
  const margin = getAssistantMargin()
  assistantPosition.left = clamp(
    assistantPosition.left,
    margin,
    Math.max(window.innerWidth - width - margin, margin)
  )
  assistantPosition.top = clamp(
    assistantPosition.top,
    margin,
    Math.max(window.innerHeight - height - margin, margin)
  )
  saveAssistantPosition()
}

function restoreAssistantPosition() {
  const margin = getAssistantMargin()
  const assistantSize = getAssistantSize()
  assistantPosition.left = window.innerWidth - assistantSize - margin
  assistantPosition.top = window.innerHeight - assistantSize - margin
  try {
    const parsed = JSON.parse(localStorage.getItem(ASSISTANT_POSITION_KEY) || '{}')
    if (Number.isFinite(parsed.left)) assistantPosition.left = parsed.left
    if (Number.isFinite(parsed.top)) assistantPosition.top = parsed.top
    if (!Number.isFinite(parsed.left) && Number.isFinite(parsed.right)) {
      assistantPosition.left = window.innerWidth - parsed.right - assistantSize
    }
    if (!Number.isFinite(parsed.top) && Number.isFinite(parsed.bottom)) {
      assistantPosition.top = window.innerHeight - parsed.bottom - assistantSize
    }
  } catch {
    // Ignore stale localStorage data.
  }
  keepAssistantInViewport()
}

function saveAssistantPosition() {
  localStorage.setItem(
    ASSISTANT_POSITION_KEY,
    JSON.stringify({ left: assistantPosition.left, top: assistantPosition.top })
  )
}

function getAssistantMargin() {
  return window.innerWidth <= 640 ? 14 : 24
}

function getAssistantSize() {
  return window.innerWidth <= 640 ? 58 : DEFAULT_ASSISTANT_SIZE
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max)
}

function escapeHtml(value = '') {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function renderInlineMarkdown(value = '') {
  return escapeHtml(value)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
}

function renderMarkdown(value = '') {
  const lines = String(value || '').replace(/\r\n/g, '\n').split('\n')
  const html = []
  let inList = false

  const closeList = () => {
    if (inList) {
      html.push('</ul>')
      inList = false
    }
  }

  for (const rawLine of lines) {
    const line = rawLine.trim()
    if (!line) {
      closeList()
      continue
    }

    const heading = line.match(/^(#{1,4})\s+(.+)$/)
    if (heading) {
      closeList()
      const level = Math.min(heading[1].length + 2, 6)
      html.push(`<h${level}>${renderInlineMarkdown(heading[2])}</h${level}>`)
      continue
    }

    const bullet = line.match(/^[-*]\s+(.+)$/)
    if (bullet) {
      if (!inList) {
        html.push('<ul>')
        inList = true
      }
      html.push(`<li>${renderInlineMarkdown(bullet[1])}</li>`)
      continue
    }

    closeList()
    html.push(`<p>${renderInlineMarkdown(line)}</p>`)
  }

  closeList()
  return html.join('')
}

async function sendMessage() {
  const content = draft.value.trim()
  if (!content || sending.value) return
  messages.value.push({ id: Date.now(), role: 'user', content })
  draft.value = ''
  sending.value = true
  const loadingId = Date.now() + 1
  messages.value.push({ id: loadingId, role: 'assistant', content: '正在查询 FinWork 数据...', loading: true })
  await scrollToBottom()
  try {
    const reply = await callAssistantApiWithClient(content)
    const loadingMessage = messages.value.find((item) => item.id === loadingId)
    if (loadingMessage) {
      loadingMessage.content = reply
      loadingMessage.loading = false
    } else {
      messages.value.push({ id: Date.now() + 1, role: 'assistant', content: reply })
    }
  } catch (error) {
    messages.value = messages.value.filter((item) => item.id !== loadingId)
    messages.value.push({
      id: Date.now() + 1,
      role: 'assistant',
      content: error?.message || '小助手暂时无法连接，请稍后再试。',
    })
  } finally {
    sending.value = false
    await scrollToBottom()
  }
}

async function callAssistantApiWithClient(content) {
  const data = await api.fwAssistantChat({
    model: DEEPSEEK_MODEL,
    message: content,
    messages: messages.value
      .filter((item) => !item.loading)
      .map((item) => ({ role: item.role, content: item.content })),
    context: {
      path: route.path,
      title: route.meta?.title || document.title,
    },
  })
  return data?.data?.content || data?.data?.reply || data?.content || data?.reply || '已收到。'
}

async function scrollToBottom() {
  await nextTick()
  if (messagesEl.value) {
    messagesEl.value.scrollTop = messagesEl.value.scrollHeight
  }
}
</script>

<style scoped>
.fw-assistant {
  position: fixed;
  width: 66px;
  height: 66px;
  z-index: 3000;
  pointer-events: none;
}

.fw-assistant-panel,
.fw-assistant-fab {
  pointer-events: auto;
}

.fw-assistant-panel {
  position: absolute;
  width: min(380px, calc(100vw - 32px));
  overflow: hidden;
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 24px 70px rgba(15, 23, 42, 0.18);
  backdrop-filter: blur(12px);
}

.fw-assistant-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 14px 12px;
  border-bottom: 1px solid rgba(226, 232, 240, 0.9);
  background:
    radial-gradient(circle at 16% 0%, rgba(37, 99, 235, 0.14), transparent 35%),
    linear-gradient(135deg, #f8fbff 0%, #f2fbf7 100%);
  user-select: none;
}

.fw-assistant-brand {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 10px;
}

.fw-assistant-brand strong,
.fw-assistant-brand small {
  display: block;
}

.fw-assistant-brand strong {
  color: #0f172a;
  font-size: 15px;
}

.fw-assistant-brand small {
  margin-top: 2px;
  color: #64748b;
  font-size: 12px;
}

.fw-assistant-avatar {
  display: grid;
  width: 38px;
  height: 38px;
  place-items: center;
  border-radius: 50%;
  background: #fff;
  box-shadow: inset 0 0 0 1px rgba(37, 99, 235, 0.12), 0 8px 18px rgba(37, 99, 235, 0.12);
}

.fw-assistant-avatar img {
  width: 27px;
  height: 27px;
}

.fw-icon-button {
  display: grid;
  width: 30px;
  height: 30px;
  place-items: center;
  color: #64748b;
  border: 0;
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
}

.fw-icon-button:hover {
  color: #0f172a;
  background: rgba(148, 163, 184, 0.14);
}

.fw-assistant-messages {
  display: flex;
  height: 320px;
  flex-direction: column;
  gap: 10px;
  overflow-y: auto;
  padding: 14px;
  background:
    linear-gradient(180deg, rgba(248, 250, 252, 0.72), #ffffff 60%);
}

.fw-message {
  display: flex;
}

.fw-message.is-user {
  justify-content: flex-end;
}

.fw-message-bubble {
  max-width: 86%;
  white-space: pre-wrap;
  word-break: break-word;
  border-radius: 10px;
  color: #1f2937;
  font-size: 13px;
  line-height: 1.55;
  padding: 9px 11px;
}

.fw-message.is-assistant .fw-message-bubble {
  border: 1px solid #e2e8f0;
  background: #fff;
}

.fw-message.is-user .fw-message-bubble {
  color: #fff;
  background: linear-gradient(135deg, #2563eb 0%, #0891b2 100%);
}

.fw-markdown {
  white-space: normal;
}

.fw-markdown :deep(h3),
.fw-markdown :deep(h4),
.fw-markdown :deep(h5),
.fw-markdown :deep(h6) {
  margin: 0 0 8px;
  color: #0f172a;
  font-size: 14px;
  font-weight: 700;
  line-height: 1.45;
}

.fw-markdown :deep(p) {
  margin: 0 0 8px;
}

.fw-markdown :deep(p:last-child),
.fw-markdown :deep(ul:last-child) {
  margin-bottom: 0;
}

.fw-markdown :deep(ul) {
  margin: 0 0 8px;
  padding-left: 18px;
}

.fw-markdown :deep(li) {
  margin: 3px 0;
}

.fw-markdown :deep(strong) {
  color: #0f172a;
  font-weight: 700;
}

.fw-markdown :deep(code) {
  border-radius: 4px;
  background: #f1f5f9;
  color: #0f766e;
  font-size: 12px;
  padding: 1px 4px;
}

.fw-loading-dots {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  min-width: 42px;
  min-height: 20px;
}

.fw-loading-dots i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #0891b2;
  opacity: 0.35;
  animation: fw-loading-dot 1s ease-in-out infinite;
}

.fw-loading-dots i:nth-child(2) {
  animation-delay: 0.14s;
}

.fw-loading-dots i:nth-child(3) {
  animation-delay: 0.28s;
}

.fw-assistant-input {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 38px;
  gap: 8px;
  padding: 12px;
  border-top: 1px solid rgba(226, 232, 240, 0.9);
  background: #fff;
}

.fw-assistant-input textarea {
  width: 100%;
  min-height: 38px;
  max-height: 96px;
  resize: vertical;
  border: 1px solid #dbe4ef;
  border-radius: 8px;
  outline: none;
  color: #0f172a;
  font-size: 13px;
  line-height: 1.5;
  padding: 8px 10px;
}

.fw-assistant-input textarea:focus {
  border-color: rgba(37, 99, 235, 0.55);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.fw-assistant-input button {
  display: grid;
  height: 38px;
  place-items: center;
  color: #fff;
  border: 0;
  border-radius: 8px;
  background: linear-gradient(135deg, #2563eb 0%, #06b6d4 54%, #22c55e 100%);
  cursor: pointer;
  box-shadow: 0 10px 18px rgba(37, 99, 235, 0.18);
}

.fw-assistant-input button:disabled {
  cursor: not-allowed;
  opacity: 0.5;
  box-shadow: none;
}

.fw-assistant-fab {
  position: relative;
  display: grid;
  width: 66px;
  height: 66px;
  place-items: center;
  overflow: hidden;
  border: 0;
  border-radius: 50%;
  background:
    radial-gradient(circle at 28% 22%, rgba(255, 255, 255, 0.96) 0 18%, rgba(255, 255, 255, 0.62) 19% 32%, transparent 33%),
    conic-gradient(from 218deg, #2563eb 0deg, #06b6d4 138deg, #22c55e 250deg, #2563eb 360deg);
  cursor: pointer;
  touch-action: none;
  user-select: none;
  box-shadow:
    0 20px 42px rgba(37, 99, 235, 0.3),
    0 8px 18px rgba(6, 182, 212, 0.18),
    inset 0 1px 0 rgba(255, 255, 255, 0.62);
  animation: fw-float 3.6s ease-in-out infinite;
}

.fw-assistant.dragging .fw-assistant-fab {
  cursor: grabbing;
  animation-play-state: paused;
}

.fw-assistant-fab::before {
  position: absolute;
  inset: -9px;
  content: '';
  border-radius: 50%;
  background: radial-gradient(circle, rgba(6, 182, 212, 0.28) 0%, rgba(34, 197, 94, 0.12) 42%, transparent 70%);
  filter: blur(2px);
  opacity: 0.9;
  animation: fw-pulse 2.8s ease-in-out infinite;
}

.fw-assistant-fab::after {
  position: absolute;
  inset: 7px;
  content: '';
  border-radius: 50%;
  background:
    linear-gradient(140deg, rgba(255, 255, 255, 0.34), transparent 45%),
    radial-gradient(circle at 72% 74%, rgba(15, 118, 110, 0.18), transparent 38%);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.48);
}

.fw-assistant-fab img {
  position: relative;
  z-index: 2;
  width: 36px;
  height: 36px;
  padding: 5px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.94);
  box-shadow:
    0 8px 18px rgba(15, 23, 42, 0.18),
    inset 0 0 0 1px rgba(37, 99, 235, 0.12);
  pointer-events: none;
  user-select: none;
  -webkit-user-drag: none;
}

.fw-assistant-orbit {
  position: absolute;
  inset: 8px;
  z-index: 1;
  border: 1px solid rgba(255, 255, 255, 0.58);
  border-radius: 50%;
  box-shadow: 0 0 22px rgba(255, 255, 255, 0.42);
  pointer-events: none;
}

.fw-assistant-fab:hover {
  animation-play-state: paused;
  transform: translateY(-4px) scale(1.03);
  box-shadow:
    0 28px 56px rgba(37, 99, 235, 0.36),
    0 12px 28px rgba(34, 197, 94, 0.24),
    inset 0 1px 0 rgba(255, 255, 255, 0.72);
}

@keyframes fw-float {
  0%,
  100% {
    transform: translateY(0);
  }

  50% {
    transform: translateY(-6px);
  }
}

@keyframes fw-pulse {
  0%,
  100% {
    opacity: 0.58;
    transform: scale(0.92);
  }

  50% {
    opacity: 1;
    transform: scale(1.08);
  }
}

@keyframes fw-loading-dot {
  0%,
  80%,
  100% {
    opacity: 0.35;
    transform: translateY(0);
  }

  40% {
    opacity: 1;
    transform: translateY(-4px);
  }
}

@media (max-width: 640px) {
  .fw-assistant-panel {
    width: calc(100vw - 28px);
  }

  .fw-assistant-messages {
    height: min(52vh, 340px);
  }

  .fw-assistant-fab {
    width: 58px;
    height: 58px;
  }

  .fw-assistant {
    width: 58px;
    height: 58px;
  }
}
</style>
