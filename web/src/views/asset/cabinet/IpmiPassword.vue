<template>
  <span class="ipmi-secret">
    <span>{{ available ? '••••••' : '—' }}</span>
    <CButton
      v-if="available && canUnlock && deviceId"
      show-save
      save-text="解锁查看"
      size="small"
      @save="open"
    />
  </span>
  <n-modal
    v-model:show="visible"
    preset="card"
    title="解锁 IPMI 密码"
    style="width: min(460px, 94vw)"
    :mask-closable="!busy"
    :closable="!busy"
    :close-on-esc="!busy"
    @after-leave="clear"
  >
    <n-alert v-if="error" type="error" style="margin-bottom: 14px">{{ error }}</n-alert>
    <template v-if="revealed">
      <p>
        仅显示当前{{ nodeName ? `节点 ${nodeName}` : '设备' }}的密码，{{ remaining }} 秒后隐藏。
      </p>
      <div class="revealed" role="status">{{ revealed }}</div>
    </template>
    <template v-else>
      <p>请输入当前账号的登录密码进行二次验证。</p>
      <n-input
        v-model:value="password"
        type="password"
        placeholder="当前账号登录密码"
        autocomplete="off"
        :disabled="busy"
        @keydown.enter.prevent="unlock"
      />
    </template>
    <template #footer>
      <CButton
        show-cancel
        :show-save="!revealed"
        save-text="验证并查看"
        cancel-text="关闭并隐藏"
        :loading="busy"
        :disabled="busy"
        @save="unlock"
        @cancel="close"
      />
    </template>
  </n-modal>
</template>

<script setup>
import { onBeforeUnmount, onDeactivated, onMounted, ref, watch } from 'vue'
import CButton from '@/components/public/CButton.vue'
import api from '@/api'

const props = defineProps({
  deviceId: { type: Number, default: null },
  nodeName: { type: String, default: '' },
  available: Boolean,
  canUnlock: Boolean,
})
const visible = ref(false),
  busy = ref(false),
  password = ref(''),
  revealed = ref(''),
  error = ref(''),
  remaining = ref(0)
let timer,
  generation = 0
function clear() {
  generation += 1
  clearInterval(timer)
  timer = undefined
  password.value = ''
  revealed.value = ''
  remaining.value = 0
  busy.value = false
}
function close() {
  clear()
  visible.value = false
}
function open() {
  clear()
  error.value = ''
  visible.value = true
}
async function unlock() {
  if (busy.value || !password.value || !visible.value) return
  busy.value = true
  error.value = ''
  const current = generation
  try {
    const response = await api.assetApi.unlockDeviceIpmi({
      device_id: props.deviceId,
      node_name: props.nodeName || null,
      password: password.value,
    })
    if (current !== generation || !visible.value) return
    revealed.value = response.data.ipmi_password
    const expires = Date.now() + Math.min(response.data.expires_in || 60, 60) * 1000
    remaining.value = 60
    timer = setInterval(() => {
      remaining.value = Math.max(0, Math.ceil((expires - Date.now()) / 1000))
      if (!remaining.value) close()
    }, 250)
  } catch (e) {
    if (current === generation) error.value = e?.message || '解锁失败，请重试'
  } finally {
    password.value = ''
    if (current === generation) busy.value = false
  }
}
function hidden() {
  if (document.hidden) close()
}
watch(() => [props.deviceId, props.nodeName], close)
watch(visible, (value) => {
  if (!value) clear()
})
onMounted(() => document.addEventListener('visibilitychange', hidden))
onDeactivated(close)
onBeforeUnmount(() => {
  clear()
  document.removeEventListener('visibilitychange', hidden)
})
</script>

<style scoped>
.ipmi-secret {
  display: inline-flex;
  align-items: center;
  gap: 10px;
}
.revealed {
  padding: 16px;
  background: var(--n-color);
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  overflow-wrap: anywhere;
  font-family: monospace;
}
</style>
