<template>
  <div class="device-vnc-console">
    <header class="device-vnc-toolbar">
      <div class="console-title">
        <i class="console-indicator" :class="{ online: connected }"></i>
        <div class="console-title-text">
          <span>{{ subtitle || 'VNC Console' }}</span>
          <strong>{{ title || '-' }}</strong>
        </div>
        <em v-if="target">{{ target }}</em>
      </div>
      <n-space align="center" :wrap="false">
        <n-tag round size="small" :type="connected ? 'success' : 'warning'">{{ statusText }}</n-tag>
        <n-button size="small" secondary :disabled="!connected" @click="refreshScreen">刷新画面</n-button>
        <n-button size="small" secondary :loading="loading" @click="connect">重连</n-button>
        <n-button size="small" tertiary @click="closeConsole">断开</n-button>
      </n-space>
    </header>

    <section class="device-vnc-body">
      <main ref="screenRef" class="device-vnc-screen">
        <div v-if="loading" class="console-loading">
          <n-spin />
          <span>正在连接控制台</span>
        </div>
        <n-result v-else-if="error" status="error" title="VNC 连接失败" :description="error" />
      </main>
    </section>
  </div>
</template>

<script setup>
import RFB from '@novnc/novnc'
import { encodings } from '@novnc/novnc/core/encodings.js'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { getToken } from '@/utils'

const props = defineProps({
  title: { type: String, default: '' },
  subtitle: { type: String, default: '' },
  wsUrl: { type: String, default: '' },
  password: { type: String, default: '' },
  target: { type: String, default: '' },
  profile: { type: String, default: 'default' },
  autoConnect: { type: Boolean, default: true },
})
const emit = defineEmits(['close'])

const screenRef = ref(null)
const loading = ref(false)
const connected = ref(false)
const error = ref('')
let rfb = null
let connectTimer = null
let resizeObserver = null
const defaultSendEncodings = RFB.prototype._sendEncodings

const statusText = computed(() => {
  if (connected.value) return '已连接'
  if (loading.value) return '连接中'
  return '未连接'
})

function clearConnectTimer() {
  if (connectTimer) {
    clearTimeout(connectTimer)
    connectTimer = null
  }
}

function websocketUrl(path) {
  let url
  if (path.startsWith('ws://') || path.startsWith('wss://')) {
    url = path
  } else if (import.meta.env.VITE_WS_BASE_API) {
    const normalizedBase = import.meta.env.VITE_WS_BASE_API.replace(/\/$/, '')
    const normalizedPath = path.replace(/^\/api\/v1/, '').replace(/^\//, '')
    url = `${normalizedBase}/${normalizedPath}`
  } else if (import.meta.env.VITE_BASE_API?.startsWith('http')) {
    const baseApi = new URL(import.meta.env.VITE_BASE_API)
    baseApi.protocol = baseApi.protocol === 'https:' ? 'wss:' : 'ws:'
    const normalizedBase = baseApi.toString().replace(/\/$/, '')
    const normalizedPath = path.replace(/^\/api\/v1/, '').replace(/^\//, '')
    url = `${normalizedBase}/${normalizedPath}`
  } else {
    const scheme = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const normalizedPath = path.startsWith('/') ? path : `/${path}`
    url = `${scheme}//${window.location.host}${normalizedPath}`
  }

  const token = getToken()
  if (!token) return url
  const parsed = new URL(url)
  parsed.searchParams.set('token', token)
  return parsed.toString()
}

function disconnect() {
  clearConnectTimer()
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
  if (rfb) {
    rfb.disconnect()
    rfb = null
  }
  connected.value = false
}

function closeConsole() {
  disconnect()
  emit('close')
}

function bindRfbEvents(instance) {
  instance.addEventListener('connect', () => {
    clearConnectTimer()
    connected.value = true
    loading.value = false
    error.value = ''
    requestAnimationFrame(() => {
      instance.scaleViewport = true
      instance.resizeSession = false
      instance.clipViewport = false
      instance.focus()
      window.dispatchEvent(new Event('resize'))
    })
    setTimeout(refreshScreen, 600)
  })
  instance.addEventListener('disconnect', (event) => {
    clearConnectTimer()
    connected.value = false
    loading.value = false
    if (!event.detail?.clean && !error.value) {
      error.value = '连接已断开，请检查 VNC 服务、端口和防火墙'
    }
  })
  instance.addEventListener('securityfailure', (event) => {
    const reason = event.detail?.reason || `状态码 ${event.detail?.status ?? '-'}`
    error.value = `VNC 认证失败：${reason}`
  })
  instance.addEventListener('credentialsrequired', () => {
    instance.sendCredentials({ password: instance._catixsPassword })
  })
}

function refreshScreen() {
  if (!rfb) return
  rfb.scaleViewport = true
  rfb.resizeSession = false
  rfb.clipViewport = false
  rfb.focus()
  window.dispatchEvent(new Event('resize'))
}

function applyEncodingProfile() {
  if (props.profile === 'huawei') {
    RFB.prototype._sendEncodings = defaultSendEncodings
    return
  }
  RFB.prototype._sendEncodings = function sendDeviceCompatibleEncodings() {
    RFB.messages.clientEncodings(this._sock, [
      encodings.encodingCopyRect,
      encodings.encodingRaw,
      encodings.pseudoEncodingDesktopSize,
      encodings.pseudoEncodingLastRect,
      encodings.pseudoEncodingDesktopName,
      encodings.pseudoEncodingCursor,
    ])
  }
}

async function connect() {
  disconnect()
  error.value = ''
  if (!props.wsUrl) {
    error.value = '缺少 VNC websocket 地址'
    return
  }
  loading.value = true
  await nextTick()
  try {
    applyEncodingProfile()
    rfb = new RFB(screenRef.value, websocketUrl(props.wsUrl), {
      credentials: { password: props.password },
      wsProtocols: ['binary'],
      shared: true,
    })
    rfb._catixsPassword = props.password
    rfb.scaleViewport = true
    rfb.resizeSession = false
    rfb.clipViewport = false
    rfb.focusOnClick = true
    rfb.qualityLevel = 6
    rfb.compressionLevel = 2
    rfb.showDotCursor = true
    bindRfbEvents(rfb)
    if (window.ResizeObserver && screenRef.value) {
      resizeObserver = new ResizeObserver(refreshScreen)
      resizeObserver.observe(screenRef.value)
    }
    connectTimer = setTimeout(() => {
      if (!connected.value) {
        disconnect()
        loading.value = false
        error.value = '连接超时，请检查 VNC 服务是否可达'
      }
    }, 15000)
  } catch (err) {
    clearConnectTimer()
    loading.value = false
    error.value = err.message || '打开 VNC 失败'
  }
}

watch(
  () => [props.wsUrl, props.password, props.profile],
  () => {
    if (props.autoConnect && props.wsUrl) connect()
  }
)

onMounted(() => {
  if (props.autoConnect && props.wsUrl) connect()
})

onBeforeUnmount(disconnect)
</script>

<style scoped>
.device-vnc-console {
  display: flex;
  height: min(78vh, 780px);
  min-width: 0;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid #171717;
  border-radius: 8px;
  background: #000;
  color: #e5e7eb;
}

.device-vnc-toolbar {
  display: flex;
  min-height: 60px;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid #171717;
  padding: 10px 14px;
  background: #000;
}

.console-title {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 12px;
}

.console-indicator {
  width: 10px;
  height: 10px;
  flex: 0 0 auto;
  border-radius: 999px;
  background: #f59e0b;
  box-shadow: 0 0 0 4px rgba(245, 158, 11, 0.14);
}

.console-indicator.online {
  background: #10b981;
  box-shadow: 0 0 0 4px rgba(16, 185, 129, 0.16);
}

.console-title-text {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 2px;
}

.console-title-text span,
.console-title-text strong,
.console-title em {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.console-title-text span {
  color: #8b95a7;
  font-size: 12px;
}

.console-title-text strong {
  color: #f8fafc;
  font-size: 16px;
  line-height: 1.2;
}

.console-title em {
  border: 1px solid #242424;
  border-radius: 999px;
  background: #090909;
  color: #cbd5e1;
  font-size: 12px;
  font-style: normal;
  padding: 3px 8px;
}

.device-vnc-body {
  min-height: 0;
  flex: 1;
  background: #000;
  padding: 10px;
}

.device-vnc-screen {
  position: relative;
  display: flex;
  width: 100%;
  height: 100%;
  min-height: 0;
  align-items: stretch;
  justify-content: stretch;
  overflow: hidden;
  border: 1px solid #171717;
  border-radius: 7px;
  background: #000;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.025);
}

.console-loading {
  display: flex;
  align-items: center;
  gap: 10px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.72);
  color: #e2e8f0;
  font-size: 13px;
  padding: 10px 14px;
}

.device-vnc-screen :deep(canvas) {
  background: #000;
  outline: none;
}

.device-vnc-screen :deep(.rfb) {
  width: 100%;
  height: 100%;
  background: #000;
}
</style>
