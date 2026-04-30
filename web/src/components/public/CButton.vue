<template>
  <n-space :size="12">
    <n-button
      v-if="showEdit"
      type="info"
      round
      secondary
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
            <path d="M12 4V1L8 5l4 4V6c3.31 0 6 2.69 6 6 0 1.01-.25 1.97-.7 2.8l1.46 1.46C19.54 15.03 20 13.57 20 12c0-4.42-3.58-8-8-8zm0 14c-3.31 0-6-2.69-6-6 0-1.01.25-1.97.7-2.8L5.24 7.74C4.46 8.97 4 10.43 4 12c0 4.42 3.58 8 8 8v3l4-4-4-4v3z" fill="currentColor"/>
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
          <path d="M12 4V1L8 5l4 4V6c3.31 0 6 2.69 6 6 0 1.01-.25 1.97-.7 2.8l1.46 1.46C19.54 15.03 20 13.57 20 12c0-4.42-3.58-8-8-8zm0 14c-3.31 0-6-2.69-6-6 0-1.01.25-1.97.7-2.8L5.24 7.74C4.46 8.97 4 10.43 4 12c0 4.42 3.58 8 8 8v3l4-4-4-4v3z" fill="currentColor"/>
        </svg>
      </template>
      {{ deleteLoading ? '处理中' : '删除' }}
    </n-button>
    <n-button
      v-if="showDetail"
      type="info"
      size="small"
      @click="handleDetail"
    >
      详情
    </n-button>
    <n-button
      v-if="showSend"
      type="primary"
      size="small"
      secondary
      @click="handleSend"
    >
      发送
    </n-button>
  </n-space>
</template>

<script setup>
const emit = defineEmits(['edit', 'delete', 'detail', 'send'])

defineProps({
  // 是否显示编辑按钮
  showEdit: {
    type: Boolean,
    default: false
  },
  // 是否显示删除按钮
  showDelete: {
    type: Boolean,
    default: false
  },
  // 禁用所有按钮
  disabled: {
    type: Boolean,
    default: false
  },
  // 编辑按钮loading状态
  editLoading: {
    type: Boolean,
    default: false
  },
  // 删除按钮loading状态
  deleteLoading: {
    type: Boolean,
    default: false
  },
  // 是否显示详情按钮
  showDetail: {
    type: Boolean,
    default: false
  },
  // 是否显示发送按钮
  showSend: {
    type: Boolean,
    default: false
  }
})

const handleEdit = () => {
  emit('edit')
}

const handleDelete = () => {
  emit('delete')
}

const handleDetail = () => {
  emit('detail')
}

const handleSend = () => {
  emit('send')
}
</script>
