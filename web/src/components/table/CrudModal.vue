<template>
  <n-modal
    v-model:show="show"
    :style="{ width: modalWidth }"
    preset="card"
    :title="title"
    size="huge"
    :bordered="false"
    :mask-closable="false"
  >
    <slot />
    <template v-if="showFooter" #footer>
      <footer flex justify-end>
        <slot name="footer">
          <CButton
            show-cancel
            show-save
            :save-loading="loading"
            @cancel="show = false"
            @save="emit('save')"
          />
        </slot>
      </footer>
    </template>
  </n-modal>
</template>

<script setup>
import CButton from '@/components/public/CButton.vue'

const props = defineProps({
  width: {
    type: String,
    default: '600px',
  },
  title: {
    type: String,
    default: '',
  },
  showFooter: {
    type: Boolean,
    default: true,
  },
  visible: {
    type: Boolean,
    required: true,
  },
  loading: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['update:visible', 'onSave'])
const modalWidth = computed(() => {
  const value = String(props.width || '').trim()
  if (!value) return 'min(600px, calc(100vw - 32px))'
  if (value.startsWith('min(') || value.startsWith('clamp(')) return value
  return `min(${value}, calc(100vw - 32px))`
})
const show = computed({
  get() {
    return props.visible
  },
  set(v) {
    emit('update:visible', v)
  },
})
</script>
