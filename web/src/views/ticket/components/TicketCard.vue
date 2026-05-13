<template>
  <div class="ticket-card-wrapper">
    <div class="ticket-card" @click="$emit('detail', ticket)">
      <!-- 第一行：标题左 + 状态/类型标签右 -->
      <div class="card-header">
        <span class="ticket-title">{{ ticket.title }}</span>
        <div class="header-tags">
          <div v-if="isAdminOrNoc" class="status-dropdown-wrapper" @click.stop>
            <span
              ref="statusTagRef"
              class="status-tag status-clickable"
              :class="'status-' + ticket.status"
              @click="toggleStatusDropdown"
            >
              <svg v-if="ticket.status === 0" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 24 24" class="tag-icon">
                <path d="M5 12l5 5L20 7" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path>
              </svg>
              {{ getStatusName(ticket.status) }}
            </span>
          </div>
          <span v-else class="status-tag" :class="'status-' + ticket.status">
            <svg v-if="ticket.status === 0" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 24 24" class="tag-icon">
              <path d="M5 12l5 5L20 7" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path>
            </svg>
            {{ getStatusName(ticket.status) }}
          </span>
          <span class="type-tag" :class="'type-' + ticket.type">
            {{ getTypeName(ticket.type) }}
          </span>
        </div>
      </div>

      <p class="ticket-desc">{{ ticket.description }}</p>

      <!-- 操作按钮 + 附件按钮行 -->
      <div class="actions-row">
        <div class="card-actions">
          <div @click.stop>
            <CButton
              showEdit
              showDelete
              :show-send="isAdminOrNoc && (ticket.type === 2 || ticket.type === 3)"
              @edit="$emit('edit', ticket)"
              @delete="$emit('delete', ticket)"
              @send="$emit('send', ticket)"
            />
          </div>
        </div>
        <button
          v-if="ticket.attachments && ticket.attachments.length > 0"
          class="btn-attach"
          @click.stop="handleViewAttachment"
        >
          <svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 24 24" class="attach-icon">
            <path d="M16.5 6v11.5c0 2.21-1.79 4-4 4s-4-1.79-4-4V5a2.5 2.5 0 0 1 5 0v10.5c0 .55-.45 1-1 1s-1-.45-1-1V6H10v9.5a2.5 2.5 0 0 0 5 0V5c0-2.21-1.79-4-4-4S7 2.79 7 5v12.5c0 3.04 2.46 5.5 5.5 5.5s5.5-2.46 5.5-5.5V6h-1.5z" fill="currentColor"></path>
          </svg>
          {{ ticket.attachments.length }} 张问题截图
        </button>
      </div>

      <div class="card-meta">
        <div class="meta-time">
          <span style="color: #9e9e9e">创建人：{{ ticket.creatorName || ticket.customerName || '-' }}</span>
          <span class="meta-divider">|</span>
          <span style="color: #9e9e9e">开始时间：{{ ticket.startTime || '-' }}</span>
          <template v-if="ticket.status === 0">
            <span class="meta-divider">|</span>
            <span style="color: #9e9e9e">处理人：{{ ticket.assigneeName || ticket.operatorName || '-' }}</span>
            <span class="meta-divider">|</span>
            <span style="color: #9e9e9e">完成时间：{{ ticket.completeTime || '-' }}</span>
          </template>
        </div>
        <div v-if="ticket.location" class="meta-location">
          <svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 24 24" class="meta-icon">
            <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5a2.5 2.5 0 0 1 0-5a2.5 2.5 0 0 1 0 5z" fill="currentColor"/>
          </svg>
          <span>{{ ticket.location }}</span>
        </div>
      </div>
    </div>

    <n-image
      ref="attachmentImageRef"
      class="attachment-preview-trigger"
      :src="attachmentPreviewSrc"
      :preview-src="attachmentPreviewSrc"
    />

    <!-- 使用Teleport将下拉菜单挂载到body，避免z-index问题 -->
    <Teleport to="body">
      <div
        v-if="statusDropdownVisible && isAdminOrNoc"
        class="status-dropdown-teleport"
        :style="dropdownStyle"
        @click="toggleStatusDropdown"
      >
        <div class="status-dropdown" @click.stop>
          <div
            v-for="option in statusOptions"
            :key="option.value"
            class="status-dropdown-item"
            :class="{ 'item-active': ticket.status === option.value }"
            @click="handleStatusSelect(option.value)"
          >
            <span class="item-dot" :class="'dot-' + option.value"></span>
            {{ option.label }}
            <svg v-if="ticket.status === 0 && option.value === 0" class="item-check" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
              <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" fill="currentColor"/>
            </svg>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, nextTick } from 'vue'
import CButton from '@/components/public/CButton.vue'

const emit = defineEmits(['detail', 'edit', 'send', 'statusChange', 'delete'])

const placeholderImg = 'https://07akioni.oss-cn-beijing.aliyuncs.com/07akioni.jpeg'

const attachmentImageRef = ref(null)
const attachmentPreviewSrc = computed(() => getImageUrl(props.ticket.attachments?.[0]))

function handleViewAttachment() {
  nextTick(() => {
    attachmentImageRef.value?.click?.()
  })
}

const props = defineProps({
  ticket: {
    type: Object,
    required: true
  },
  isAdminOrNoc: {
    type: Boolean,
    default: false
  }
})

const statusDropdownVisible = ref(false)
const statusTagRef = ref(null)
const dropdownPosition = ref({ left: 0, top: 0 })

const dropdownStyle = computed(() => {
  return {
    position: 'fixed',
    left: `${dropdownPosition.value.left}px`,
    top: `${dropdownPosition.value.top}px`,
    zIndex: 9999
  }
})

function toggleStatusDropdown() {
  statusDropdownVisible.value = !statusDropdownVisible.value
  if (statusDropdownVisible.value) {
    nextTick(() => {
      if (statusTagRef.value) {
        const rect = statusTagRef.value.getBoundingClientRect()
        dropdownPosition.value = {
          left: rect.right - 140,
          top: rect.bottom + 6
        }
      }
    })
  }
}

const statusOptions = [
  { label: '已完成', value: 0 },
  { label: '进行中', value: 1 },
  { label: '未开始', value: 2 },
  { label: '已关闭', value: 3 }
]

function handleStatusSelect(newStatus) {
  if (newStatus === props.ticket.status) {
    statusDropdownVisible.value = false
    return
  }
  emit('statusChange', { ticket: props.ticket, newStatus })
  statusDropdownVisible.value = false
}

function getStatusName(status) {
  const map = { 0: '已完成', 1: '进行中', 2: '未开始', 3: '已关闭' }
  return map[status] || '未知'
}

function getTypeName(type) {
  const map = { 0: '故障工单', 1: '服务请求工单', 2: '变更工单', 3: '维护工单' }
  return map[type] || '未知'
}

function getStatusTagType(status) {
  const map = { 0: 'success', 1: 'warning', 2: 'default', 3: 'error' }
  return map[status] || 'default'
}

function getTypeTagType(type) {
  const map = { 0: 'error', 1: 'info', 2: 'warning', 3: 'success' }
  return map[type] || 'default'
}

function getImageUrl(img) {
  if (!img) return placeholderImg
  if (img.startsWith('http://') || img.startsWith('https://') || img.startsWith('/') || img.startsWith('data:')) return img
  return placeholderImg
}
</script>

<style scoped>
.ticket-card-wrapper {
  padding: 4px;
  margin-bottom: 8px;
  margin-left: -4px;
  margin-right: -4px;
}


/* 操作按钮 + 附件按钮行 */
.actions-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  position: relative;
  z-index: 1;
}

.btn-attach {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 24px;
  border-radius: 12px;
  border: 1px solid rgba(24, 144, 255, 0.3);
  background: rgba(24, 144, 255, 0.1);
  color: var(--n-primary-color);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  position: relative;
  z-index: 0;
}

.btn-attach:hover {
  background: rgba(24, 144, 255, 0.18);
  border-color: rgba(24, 144, 255, 0.4);
}

.attach-icon {
  width: 16px;
  height: 16px;
}

.attachment-preview-trigger {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}

.ticket-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 24px 28px;
  border-radius: 12px;
  background: var(--n-card-color);
  border: 1px solid var(--n-border-color);
  box-shadow: 
    0 4px 14px rgba(0, 0, 0, 0.08),
    0 2px 6px rgba(0, 0, 0, 0.05),
    3px 3px 8px rgba(0, 0, 0, 0.04),
    -3px 3px 8px rgba(0, 0, 0, 0.04),
    0 -1px 6px rgba(0, 0, 0, 0.03);
  cursor: pointer;
  transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
}

.ticket-card:hover {
  box-shadow: 
    0 14px 36px rgba(0, 0, 0, 0.15),
    0 8px 20px rgba(0, 0, 0, 0.12),
    6px 6px 16px rgba(0, 0, 0, 0.1),
    -6px 6px 16px rgba(0, 0, 0, 0.1),
    0 -5px 14px rgba(0, 0, 0, 0.08);
  border-color: var(--n-border-color);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  position: relative;
  z-index: 5;
}

.ticket-title {
  font-size: 17px;
  font-weight: 600;
  color: var(--n-text-color);
  line-height: 1.4;
}

.header-tags {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

/* 状态标签 */
.status-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 12px;
  border-radius: 12px;
  font-size: 13px;
  font-weight: 500;
  line-height: 20px;
  white-space: nowrap;
}

.status-clickable {
  cursor: pointer;
  user-select: none;
  transition: box-shadow 0.15s ease;
}

.status-clickable:hover {
  box-shadow: 0 0 0 2px rgba(0, 0, 0, 0.08);
}

/* 状态下拉容器 */
.status-dropdown-wrapper {
  position: relative;
}

/* Teleport下拉菜单容器 */
:deep(.status-dropdown-teleport) {
  position: fixed !important;
  z-index: 99999 !important;
}

/* 下拉菜单 */
:deep(.status-dropdown) {
  min-width: 140px !important;
  background: #ffffff !important;
  border: 1px solid #e8e8e8 !important;
  border-radius: 8px !important;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12) !important;
  padding: 4px !important;
  position: relative !important;
  z-index: 100000 !important;
}

:deep(.status-dropdown-item) {
  display: flex !important;
  align-items: center !important;
  gap: 8px !important;
  padding: 8px 12px !important;
  border-radius: 6px !important;
  font-size: 13px !important;
  color: #1a1a1a !important;
  cursor: pointer !important;
  transition: background 0.15s ease !important;
}

:deep(.status-dropdown-item:hover) {
  background: #f5f5f5 !important;
}

:deep(.status-dropdown-item.item-active) {
  background: rgba(24, 144, 255, 0.1) !important;
  color: #1890ff !important;
}

:deep(.item-dot) {
  width: 8px !important;
  height: 8px !important;
  border-radius: 50% !important;
  flex-shrink: 0 !important;
}

:deep(.dot-0) { background: #52c41a !important; }
:deep(.dot-1) { background: #fa8c16 !important; }
:deep(.dot-2) { background: #8c8c8c !important; }
:deep(.dot-3) { background: #ff4d4f !important; }

:deep(.item-check) {
  width: 16px !important;
  height: 16px !important;
  flex-shrink: 0 !important;
}



.tag-icon {
  width: 13px;
  height: 13px;
}

.status-0 {
  color: #52c41a;
  background: rgba(82, 196, 26, 0.1);
  border: 1px solid rgba(82, 196, 26, 0.2);
}

.status-1 {
  color: #fa8c16;
  background: rgba(250, 140, 22, 0.1);
  border: 1px solid rgba(250, 140, 22, 0.2);
}

.status-2 {
  color: #8c8c8c;
  background: rgba(140, 140, 140, 0.1);
  border: 1px solid rgba(140, 140, 140, 0.2);
}

.status-3 {
  color: #ff4d4f;
  background: rgba(255, 77, 79, 0.1);
  border: 1px solid rgba(255, 77, 79, 0.2);
}

/* 类型标签 */
.type-tag {
  display: inline-flex;
  align-items: center;
  padding: 3px 12px;
  border-radius: 12px;
  font-size: 13px;
  font-weight: 500;
  line-height: 20px;
  white-space: nowrap;
}

.type-0 {
  color: #ff4d4f;
  background: rgba(255, 77, 79, 0.1);
  border: 1px solid rgba(255, 77, 79, 0.2);
}

.type-1 {
  color: #1890ff;
  background: rgba(24, 144, 255, 0.1);
  border: 1px solid rgba(24, 144, 255, 0.2);
}

.type-2 {
  color: #fa8c16;
  background: rgba(250, 140, 22, 0.1);
  border: 1px solid rgba(250, 140, 22, 0.2);
}

.type-3 {
  color: #52c41a;
  background: rgba(82, 196, 26, 0.1);
  border: 1px solid rgba(82, 196, 26, 0.2);
}

.ticket-desc {
  font-size: 15px;
  color: #555555;
  line-height: 1.6;
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 时间信息区域 */
.card-meta {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 10px 14px;
  background: var(--n-hover-color);
  border-radius: 8px;
  font-size: 14px;
  color: #555555;
}

.meta-time {
  display: flex;
  align-items: center;
  gap: 6px;
}

.meta-divider {
  margin: 0 4px;
}


.meta-location {
  display: flex;
  align-items: center;
  gap: 4px;
  color: #555555;
}

.meta-icon {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
}

/* 底部操作区 */
.card-actions {
  display: flex;
  gap: 12px;
  padding-top: 4px;
}

</style>
