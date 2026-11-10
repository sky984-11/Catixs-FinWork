<template>
  <n-modal
    :show="show"
    preset="card"
    title="账单预览"
    style="width: min(980px, calc(100vw - 24px))"
    @update:show="$emit('update:show', $event)"
  >
    <div class="invoice-scroll">
      <iframe
        ref="frame"
        title="Invoice 账单预览"
        :srcdoc="html"
        sandbox="allow-same-origin allow-modals"
        @load="ready = true"
      />
    </div>
    <template #footer>
      <CButton
        show-cancel
        show-save
        cancel-text="关闭"
        save-text="打印 / 保存 PDF"
        :disabled="!ready"
        @cancel="$emit('update:show', false)"
        @save="print"
      />
    </template>
  </n-modal>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import CButton from '@/components/public/CButton.vue'
import { invoiceHtml } from '../invoice.mjs'

const props = defineProps({ show: Boolean, bill: { type: Object, default: null } })
defineEmits(['update:show'])
const frame = ref(null)
const ready = ref(false)
const html = computed(() => invoiceHtml(props.bill || {}, window.location.origin))
watch([html, () => props.show], () => {
  ready.value = false
})
function print() {
  try {
    frame.value.contentWindow.focus()
    frame.value.contentWindow.print()
  } catch {
    window.$message?.error('无法打开打印窗口，请重试')
  }
}
</script>

<style scoped>
.invoice-scroll {
  overflow: auto;
  max-height: 75vh;
  background: #fff;
}
iframe {
  display: block;
  width: 100%;
  min-width: 780px;
  height: 1120px;
  border: 0;
}
</style>
