<template>
  <div class="novnc-console" :class="{ embedded }">
    <header class="novnc-toolbar">
      <div class="console-title">
        <span>{{ remote || '-' }}</span>
        <strong>{{ title || `VM ${vmid || '-'}` }}</strong>
      </div>
      <n-space align="center" :wrap="false">
        <n-tag round :type="connected ? 'success' : 'warning'">{{ statusText }}</n-tag>
        <n-button size="small" :loading="loading" @click="connect">重连</n-button>
        <n-button size="small" @click="disconnect">断开</n-button>
      </n-space>
    </header>

    <main ref="screenRef" class="novnc-screen">
      <n-spin v-if="loading" />
      <n-result v-else-if="error" status="error" title="noVNC 连接失败" :description="error" />
    </main>
  </div>
</template>

<script setup>
import RFB from '@novnc/novnc'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import api from '@/api'
import { getToken } from '@/utils'

const props = defineProps({
  remote: { type: String, default: '' },
  vmid: { type: [String, Number], default: '' },
  node: { type: String, default: '' },
  type: { type: String, default: 'pve-qemu' },
  title: { type: String, default: '' },
  embedded: { type: Boolean, default: false },
  autoConnect: { type: Boolean, default: true },
})

const screenRef = ref(null)
const loading = ref(false)
const connected = ref(false)
const error = ref('')
let rfb = null
let connectTimer = null

const statusText = computed(() => {
  if (connected.value) return '已连接'
  if (loading.value) return '连接中'
  return '未连接'
})

function disconnect() {
  clearConnectTimer()
  if (rfb) {
    rfb.disconnect()
    rfb = null
  }
  connected.value = false
}

function clearConnectTimer() {
  if (connectTimer) {
    clearTimeout(connectTimer)
    connectTimer = null
  }
}

function bindRfbEvents(instance) {
  instance.addEventListener('connect', () => {
    clearConnectTimer()
    connected.value = true
    loading.value = false
    error.value = ''
  })
  instance.addEventListener('disconnect', (event) => {
    clearConnectTimer()
    connected.value = false
    loading.value = false
    if (event.detail?.clean) return
    if (!error.value) {
      error.value = '连接已断开，请检查后端 WebSocket 代理或虚拟机控制台状态'
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

function websocketUrl(path) {
  let url
  if (path.startsWith('ws://') || path.startsWith('wss://')) {
    url = path
  } else if (import.meta.env.VITE_WS_BASE_API) {
    const wsBaseApi = import.meta.env.VITE_WS_BASE_API
    const normalizedBase = wsBaseApi.replace(/\/$/, '')
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

async function connect() {
  disconnect()
  error.value = ''
  loading.value = true
  await nextTick()

  try {
    const res = await api.virtualMachineApi.novnc({
      remote: props.remote,
      vmid: Number(props.vmid),
      node: props.node || undefined,
      type: props.type || 'pve-qemu',
    })
    if (!res.data?.wsUrl) {
      throw new Error('后端未返回 noVNC websocket 地址')
    }
    rfb = new RFB(screenRef.value, websocketUrl(res.data.wsUrl), {
      credentials: { password: res.data.password },
      wsProtocols: ['binary'],
    })
    rfb._catixsPassword = res.data.password
    rfb.scaleViewport = true
    rfb.resizeSession = true
    rfb.focusOnClick = true
    bindRfbEvents(rfb)
    connectTimer = setTimeout(() => {
      if (!connected.value) {
        disconnect()
        loading.value = false
        error.value = '连接超时，请检查后端服务是否已重启，以及反向代理是否开启 WebSocket Upgrade'
      }
    }, 15000)
  } catch (err) {
    clearConnectTimer()
    loading.value = false
    error.value = err.message || '打开 noVNC 失败'
  }
}

watch(
  () => [props.remote, props.vmid, props.node, props.type],
  () => {
    if (props.autoConnect && props.remote && props.vmid) {
      connect()
    }
  }
)

onMounted(() => {
  if (props.autoConnect && props.remote && props.vmid) {
    connect()
  }
})

onBeforeUnmount(disconnect)
</script>

<style scoped>
.novnc-console {
  display: flex;
  height: 100vh;
  min-width: 960px;
  flex-direction: column;
  background: #0f172a;
  color: #e2e8f0;
}

.novnc-console.embedded {
  height: min(76vh, 760px);
  min-width: 0;
  border-radius: 0 0 8px 8px;
  overflow: hidden;
}

.novnc-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.22);
  padding: 8px 12px;
  background: #111827;
}

.novnc-toolbar {
  min-height: 52px;
}

.console-title {
  display: flex;
  min-width: 0;
  align-items: baseline;
  gap: 12px;
}

.console-title span,
.console-title strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.console-title span {
  color: #94a3b8;
  font-size: 13px;
}

.console-title strong {
  color: #e2e8f0;
  font-size: 16px;
}

.novnc-screen {
  position: relative;
  display: flex;
  min-height: 0;
  flex: 1;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  background: #020617;
}

.novnc-screen :deep(canvas) {
  outline: none;
}

@media (max-width: 720px) {
  .novnc-console {
    min-width: 0;
  }

  .novnc-toolbar {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
