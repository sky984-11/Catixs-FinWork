<template>
  <teleport to="body">
    <div v-if="visible" class="fw-assistant" :class="{ open: panelOpen }">
      <section v-if="panelOpen" class="fw-assistant-panel" aria-label="FW小助手对话">
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
            <div class="fw-message-bubble">{{ message.content }}</div>
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

      <button class="fw-assistant-fab" type="button" title="FW小助手" @click="panelOpen = !panelOpen">
        <span class="fw-assistant-orbit"></span>
        <img :src="logoUrl" alt="FW小助手" />
      </button>
    </div>
  </teleport>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import logoUrl from '@/assets/svg/logo.svg?url'
import TheIcon from '@/components/icon/TheIcon.vue'
import { getToken } from '@/utils'

defineOptions({ name: 'FwAssistant' })

const DEEPSEEK_API_ENDPOINT = import.meta.env.VITE_FW_ASSISTANT_API_URL || ''
const DEEPSEEK_MODEL = import.meta.env.VITE_FW_ASSISTANT_MODEL || 'deepseek-chat'

const hiddenPathPrefixes = ['/login', '/asset/cabinet-photo-upload/', '/ops/virtual-machine/console']
const route = useRoute()
const panelOpen = ref(false)
const sending = ref(false)
const draft = ref('')
const messagesEl = ref(null)
const messages = ref([
  {
    id: Date.now(),
    role: 'assistant',
    content: '你好，我是 FW 小助手。DeepSeek API 接入后，我可以帮你分析需求、总结项目、处理工单和生成跟进建议。',
  },
])

const visible = computed(() => {
  if (!getToken()) return false
  return !hiddenPathPrefixes.some((prefix) => route.path.startsWith(prefix))
})

const assistantStatusText = computed(() => (DEEPSEEK_API_ENDPOINT ? DEEPSEEK_MODEL : '待接入 DeepSeek'))

watch(
  () => route.path,
  () => {
    if (!visible.value) panelOpen.value = false
  }
)

async function sendMessage() {
  const content = draft.value.trim()
  if (!content || sending.value) return
  messages.value.push({ id: Date.now(), role: 'user', content })
  draft.value = ''
  sending.value = true
  await scrollToBottom()
  try {
    const reply = await callAssistantApi(content)
    messages.value.push({ id: Date.now() + 1, role: 'assistant', content: reply })
  } catch (error) {
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

async function callAssistantApi(content) {
  if (!DEEPSEEK_API_ENDPOINT) {
    return `已收到：${content}\n\n当前为本地占位回复。后续配置 VITE_FW_ASSISTANT_API_URL 后，会把消息发送到你的后端 DeepSeek 代理接口。`
  }
  const response = await fetch(DEEPSEEK_API_ENDPOINT, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      token: getToken() || '',
    },
    body: JSON.stringify({
      model: DEEPSEEK_MODEL,
      message: content,
      messages: messages.value.map((item) => ({ role: item.role, content: item.content })),
      context: {
        path: route.path,
        title: route.meta?.title || document.title,
      },
    }),
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok || data?.code && data.code !== 200) {
    throw new Error(data?.msg || data?.message || 'AI 接口调用失败')
  }
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
  right: 24px;
  bottom: 24px;
  z-index: 3000;
  pointer-events: none;
}

.fw-assistant-panel,
.fw-assistant-fab {
  pointer-events: auto;
}

.fw-assistant-panel {
  width: min(380px, calc(100vw - 32px));
  margin-bottom: 14px;
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
  box-shadow:
    0 20px 42px rgba(37, 99, 235, 0.3),
    0 8px 18px rgba(6, 182, 212, 0.18),
    inset 0 1px 0 rgba(255, 255, 255, 0.62);
  animation: fw-float 3.6s ease-in-out infinite;
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
}

.fw-assistant-orbit {
  position: absolute;
  inset: 8px;
  z-index: 1;
  border: 1px solid rgba(255, 255, 255, 0.58);
  border-radius: 50%;
  box-shadow: 0 0 22px rgba(255, 255, 255, 0.42);
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

@media (max-width: 640px) {
  .fw-assistant {
    right: 14px;
    bottom: 14px;
  }

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
}
</style>
