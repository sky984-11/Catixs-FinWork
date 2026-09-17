<template>
  <div class="attachments">
    <template v-if="!readonly">
      <CButton
        show-save
        save-text="上传附件"
        :disabled="busy || disabled || modelValue.length >= 50"
        :save-loading="busy"
        @save="input.click()"
      />
      <input ref="input" type="file" hidden @change="upload" />
      <p class="hint">单个文件不超过 20MiB。删除立即生效，取消编辑不会恢复附件。</p>
    </template>
    <div v-for="item in modelValue" :key="item.id" class="attachment">
      <span class="filename">{{ item.name }} · {{ (item.size / 1024).toFixed(1) }} KB</span>
      <CButton
        show-save
        save-text="下载"
        :show-delete="!readonly"
        size="small"
        :disabled="busy || disabled"
        @save="download(item)"
        @delete="remove(item)"
      />
    </div>
    <NEmpty v-if="!modelValue.length" description="暂无附件" size="small" />
    <NAlert v-if="error" type="error">{{ error }}</NAlert>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import CButton from '@/components/public/CButton.vue'
import api from '@/api'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  vendorId: { type: Number, default: null },
  disabled: Boolean,
  readonly: Boolean,
})
const emit = defineEmits(['update:modelValue', 'busy'])
const input = ref(null)
const busy = ref(false)
const error = ref('')
function setBusy(value) {
  busy.value = value
  emit('busy', value)
}
async function upload(event) {
  const file = event.target.files?.[0]
  if (!file || busy.value || props.disabled) return
  error.value = ''
  if (!file.size || file.size > 20 * 1024 * 1024) {
    error.value = '请选择非空且不超过 20MiB 的文件'
    event.target.value = ''
    return
  }
  setBusy(true)
  try {
    const data = await new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => resolve(reader.result)
      reader.onerror = () => reject(new Error('文件读取失败，请重新选择'))
      reader.onabort = () => reject(new Error('文件读取已中断'))
      reader.readAsDataURL(file)
    })
    const response = await api.uploadVendorAttachment({
      filename: file.name,
      content_type: file.type || 'application/octet-stream',
      data,
      vendor_id: props.vendorId,
    })
    emit('update:modelValue', [...props.modelValue, response.data])
  } catch (e) {
    error.value = e?.message || '上传失败，请重新选择文件重试'
  } finally {
    setBusy(false)
    event.target.value = ''
  }
}
async function remove(item) {
  if (busy.value || props.disabled) return
  setBusy(true)
  error.value = ''
  try {
    await api.deleteVendorAttachment(item.id)
    emit(
      'update:modelValue',
      props.modelValue.filter((value) => value.id !== item.id)
    )
  } catch (e) {
    error.value = e?.message || '删除失败，请重试'
  } finally {
    setBusy(false)
  }
}
async function download(item) {
  if (busy.value) return
  setBusy(true)
  error.value = ''
  try {
    const response = await api.downloadVendorAttachment(item.id)
    const url = URL.createObjectURL(response.data)
    const link = document.createElement('a')
    link.href = url
    link.download = item.name
    link.click()
    URL.revokeObjectURL(url)
  } catch {
    error.value = '下载失败，请重试'
  } finally {
    setBusy(false)
  }
}
</script>

<style scoped>
.attachments {
  width: 100%;
}
.attachment {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin: 12px 0;
  flex-wrap: wrap;
}
.filename {
  overflow-wrap: anywhere;
  min-width: 0;
  flex: 1;
}
.hint {
  color: #718096;
  font-size: 12px;
}
</style>
