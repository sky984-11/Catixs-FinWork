<template>
  <n-space :size="spaceSize" :wrap="wrap">
    <n-button
      v-if="showCancel"
      class="c-button-cancel"
      round
      secondary
      :size="size"
      :loading="cancelLoading"
      :disabled="disabled"
      @click="handleCancel"
    >
      <template #icon>
        <n-icon>
          <svg v-if="!cancelLoading" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
            <path
              d="M18.3 5.71L12 12l6.3 6.29l-1.41 1.42L10.59 13.41L4.29 19.71L2.88 18.29L9.17 12L2.88 5.71L4.29 4.29l6.3 6.3l6.3-6.3l1.41 1.42z"
              fill="currentColor"
            />
          </svg>
          <svg v-else xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
            <path
              d="M12 4V1L8 5l4 4V6c3.31 0 6 2.69 6 6 0 1.01-.25 1.97-.7 2.8l1.46 1.46C19.54 15.03 20 13.57 20 12c0-4.42-3.58-8-8-8zm0 14c-3.31 0-6-2.69-6-6 0-1.01.25-1.97.7-2.8L5.24 7.74C4.46 8.97 4 10.43 4 12c0 4.42 3.58 8 8 8v3l4-4-4-4v3z"
              fill="currentColor"
            />
          </svg>
        </n-icon>
      </template>
      {{ cancelLoading ? '处理中' : cancelText }}
    </n-button>
    <n-button
      v-if="showSave"
      type="info"
      round
      secondary
      :size="size"
      :loading="saveLoading"
      :disabled="disabled"
      @click="handleSave"
    >
      <template #icon>
        <n-icon>
          <svg v-if="!saveLoading" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
            <path d="M9 16.17L4.83 12l-1.42 1.41L9 19L21 7l-1.41-1.41z" fill="currentColor" />
          </svg>
          <svg v-else xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
            <path
              d="M12 4V1L8 5l4 4V6c3.31 0 6 2.69 6 6 0 1.01-.25 1.97-.7 2.8l1.46 1.46C19.54 15.03 20 13.57 20 12c0-4.42-3.58-8-8-8zm0 14c-3.31 0-6-2.69-6-6 0-1.01.25-1.97.7-2.8L5.24 7.74C4.46 8.97 4 10.43 4 12c0 4.42 3.58 8 8 8v3l4-4-4-4v3z"
              fill="currentColor"
            />
          </svg>
        </n-icon>
      </template>
      {{ saveLoading ? '处理中' : saveText }}
    </n-button>
    <n-button
      v-if="showEdit"
      type="info"
      round
      secondary
      :size="size"
      :loading="editLoading"
      :disabled="disabled"
      @click="handleEdit"
    >
      <template #icon>
        <n-icon>
          <svg
            v-if="!editLoading"
            xmlns="http://www.w3.org/2000/svg"
            xmlns:xlink="http://www.w3.org/1999/xlink"
            viewBox="0 0 24 24"
          >
            <path opacity=".3" d="M5 6h14v2H5z" fill="currentColor"></path>
            <path
              d="M5 10h14v2h2V6c0-1.1-.9-2-2-2h-1V2h-2v2H8V2H6v2H5c-1.11 0-1.99.9-1.99 2L3 20a2 2 0 0 0 2 2h7v-2H5V10zm0-4h14v2H5V6zm17.84 10.28l-.71.71l-2.12-2.12l.71-.71a.996.996 0 0 1 1.41 0l.71.71c.39.39.39 1.02 0 1.41zm-3.54-.7l2.12 2.12l-5.3 5.3H14v-2.12l5.3-5.3z"
              fill="currentColor"
            ></path>
          </svg>
          <svg v-else xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
            <path
              d="M12 4V1L8 5l4 4V6c3.31 0 6 2.69 6 6 0 1.01-.25 1.97-.7 2.8l1.46 1.46C19.54 15.03 20 13.57 20 12c0-4.42-3.58-8-8-8zm0 14c-3.31 0-6-2.69-6-6 0-1.01.25-1.97.7-2.8L5.24 7.74C4.46 8.97 4 10.43 4 12c0 4.42 3.58 8 8 8v3l4-4-4-4v3z"
              fill="currentColor"
            />
          </svg>
        </n-icon>
      </template>
      {{ editLoading ? '处理中' : '编辑' }}
    </n-button>
    <n-button
      v-if="showDelete"
      type="error"
      round
      secondary
      :size="size"
      :loading="deleteLoading"
      :disabled="disabled"
      @click="handleDelete"
    >
      <template #icon>
        <svg
          v-if="!deleteLoading"
          xmlns="http://www.w3.org/2000/svg"
          xmlns:xlink="http://www.w3.org/1999/xlink"
          viewBox="0 0 20 20"
        >
          <g fill="none">
            <path
              d="M7.5 4a2.5 2.5 0 0 1 5 0H17a.5.5 0 0 1 0 1h-.554l-.923 8h-1.007l.922-8H4.561l1.282 11.115a1 1 0 0 0 .994.885h5.248c.066.186.168.356.297.5c-.13.144-.23.314-.297.5H6.837a2 2 0 0 1-1.987-1.77L3.553 5H3a.5.5 0 0 1-.492-.41L2.5 4.5A.5.5 0 0 1 3 4h4.5zm4 0a1.5 1.5 0 0 0-3 0h3zm2 12a.5.5 0 0 0 0 1h5a.5.5 0 0 0 0-1h-5zm0-2a.5.5 0 0 0 0 1h5a.5.5 0 0 0 0-1h-5zm-.5 4.5a.5.5 0 0 1 .5-.5h5a.5.5 0 0 1 0 1h-5a.5.5 0 0 1-.5-.5z"
              fill="currentColor"
            ></path>
          </g>
        </svg>
        <svg v-else xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
          <path
            d="M12 4V1L8 5l4 4V6c3.31 0 6 2.69 6 6 0 1.01-.25 1.97-.7 2.8l1.46 1.46C19.54 15.03 20 13.57 20 12c0-4.42-3.58-8-8-8zm0 14c-3.31 0-6-2.69-6-6 0-1.01.25-1.97.7-2.8L5.24 7.74C4.46 8.97 4 10.43 4 12c0 4.42 3.58 8 8 8v3l4-4-4-4v3z"
            fill="currentColor"
          />
        </svg>
      </template>
      {{ deleteLoading ? '处理中' : '删除' }}
    </n-button>
    <n-button
      v-if="showSend"
      class="c-button-send"
      round
      secondary
      :size="size"
      :loading="sendLoading"
      :disabled="disabled"
      @click="handleSend"
    >
      <template #icon>
        <n-icon>
          <svg v-if="!sendLoading" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
            <path d="M2.01 21L23 12L2.01 3L2 10L17 12L2 14L2.01 21Z" fill="currentColor" />
          </svg>
          <svg v-else xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
            <path
              d="M12 4V1L8 5l4 4V6c3.31 0 6 2.69 6 6 0 1.01-.25 1.97-.7 2.8l1.46 1.46C19.54 15.03 20 13.57 20 12c0-4.42-3.58-8-8-8zm0 14c-3.31 0-6-2.69-6-6 0-1.01.25-1.97.7-2.8L5.24 7.74C4.46 8.97 4 10.43 4 12c0 4.42 3.58 8 8 8v3l4-4-4-4v3z"
              fill="currentColor"
            />
          </svg>
        </n-icon>
      </template>
      {{ sendLoading ? '处理中' : '发送' }}
    </n-button>
  </n-space>
</template>

<script setup>
const emit = defineEmits(['cancel', 'save', 'edit', 'delete', 'send'])

defineProps({
  // 是否显示取消按钮
  showCancel: {
    type: Boolean,
    default: false,
  },
  // 是否显示保存按钮
  showSave: {
    type: Boolean,
    default: false,
  },
  // 是否显示编辑按钮
  showEdit: {
    type: Boolean,
    default: false,
  },
  // 是否显示删除按钮
  showDelete: {
    type: Boolean,
    default: false,
  },
  // 禁用所有按钮
  disabled: {
    type: Boolean,
    default: false,
  },
  // 按钮尺寸
  size: {
    type: String,
    default: 'medium',
  },
  // 按钮间距
  spaceSize: {
    type: [Number, String, Array],
    default: 12,
  },
  // 是否允许换行
  wrap: {
    type: Boolean,
    default: true,
  },
  // 编辑按钮loading状态
  editLoading: {
    type: Boolean,
    default: false,
  },
  // 删除按钮loading状态
  deleteLoading: {
    type: Boolean,
    default: false,
  },
  // 是否显示发送按钮
  showSend: {
    type: Boolean,
    default: false,
  },
  // 发送按钮loading状态
  sendLoading: {
    type: Boolean,
    default: false,
  },
  // 保存按钮loading状态
  saveLoading: {
    type: Boolean,
    default: false,
  },
  // 取消按钮loading状态
  cancelLoading: {
    type: Boolean,
    default: false,
  },
  // 保存按钮文案
  saveText: {
    type: String,
    default: '保存',
  },
  // 取消按钮文案
  cancelText: {
    type: String,
    default: '取消',
  },
})

const handleCancel = () => {
  emit('cancel')
}

const handleSave = () => {
  emit('save')
}

const handleEdit = () => {
  emit('edit')
}

const handleDelete = () => {
  emit('delete')
}

const handleSend = () => {
  emit('send')
}
</script>

<style scoped>
.c-button-cancel {
  --n-text-color: #4b5563 !important;
  --n-text-color-hover: #374151 !important;
  --n-text-color-pressed: #1f2937 !important;
  --n-text-color-focus: #374151 !important;
  --n-color: rgba(107, 114, 128, 0.1) !important;
  --n-color-hover: rgba(107, 114, 128, 0.16) !important;
  --n-color-pressed: rgba(107, 114, 128, 0.22) !important;
  --n-color-focus: rgba(107, 114, 128, 0.16) !important;
  --n-border: 1px solid rgba(107, 114, 128, 0.24) !important;
  --n-border-hover: 1px solid rgba(107, 114, 128, 0.38) !important;
  --n-border-pressed: 1px solid rgba(107, 114, 128, 0.46) !important;
  --n-border-focus: 1px solid rgba(107, 114, 128, 0.38) !important;
}

.c-button-send {
  --n-text-color: #d4380d !important;
  --n-text-color-hover: #d4380d !important;
  --n-text-color-pressed: #ad2b08 !important;
  --n-text-color-focus: #d4380d !important;
  --n-color: rgba(250, 140, 22, 0.12) !important;
  --n-color-hover: rgba(250, 140, 22, 0.18) !important;
  --n-color-pressed: rgba(250, 140, 22, 0.24) !important;
  --n-color-focus: rgba(250, 140, 22, 0.18) !important;
  --n-border: 1px solid rgba(250, 140, 22, 0.28) !important;
  --n-border-hover: 1px solid rgba(250, 140, 22, 0.4) !important;
  --n-border-pressed: 1px solid rgba(250, 140, 22, 0.48) !important;
  --n-border-focus: 1px solid rgba(250, 140, 22, 0.4) !important;
}
</style>
