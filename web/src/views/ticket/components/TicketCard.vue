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
              <svg v-if="ticket.status === 2" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 24 24" class="tag-icon">
                <path d="M5 12l5 5L20 7" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path>
              </svg>
              {{ getStatusName(ticket.status) }}
            </span>
          </div>
          <span v-else class="status-tag" :class="'status-' + ticket.status">
            <svg v-if="ticket.status === 2" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 24 24" class="tag-icon">
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
      <div class="actions-row" @click.stop>
        <div class="card-actions">
          <button class="btn-detail" @click="$emit('detail', ticket)">详情</button>
          <button class="btn-edit" @click="$emit('edit', ticket)">编辑</button>
          <button
            v-show="isAdminOrNoc && (ticket.type === 2 || ticket.type === 3)"
            class="btn-send"
            @click="$emit('send', ticket)"
          >
            发送
          </button>
          <button
            v-show="isAdminOrNoc"
            class="btn-delete"
            @click="$emit('delete', ticket)"
          >
            删除
          </button>
        </div>
        <button
          v-if="ticket.attachments && ticket.attachments.length > 0"
          class="btn-attach"
          @click="handleViewAttachment"
        >
          <svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 24 24" class="attach-icon">
            <path d="M16.5 6v11.5c0 2.21-1.79 4-4 4s-4-1.79-4-4V5a2.5 2.5 0 0 1 5 0v10.5c0 .55-.45 1-1 1s-1-.45-1-1V6H10v9.5a2.5 2.5 0 0 0 5 0V5c0-2.21-1.79-4-4-4S7 2.79 7 5v12.5c0 3.04 2.46 5.5 5.5 5.5s5.5-2.46 5.5-5.5V6h-1.5z" fill="currentColor"></path>
          </svg>
          {{ ticket.attachments.length }} 张问题截图
        </button>
      </div>

      <div class="card-meta">
        <div class="meta-time">
          <svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 24 24" class="meta-icon">
            <path d="M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zM12 20c-4.42 0-8-3.58-8-8s3.58-8 8-8s8 3.58 8 8s-3.58 8-8 8zm.5-13H11v6l5.25 3.15l.75-1.23l-4.5-2.67z" fill="currentColor"></path>
          </svg>
          <span>{{ ticket.createTime }}</span>
          <span class="meta-divider">|</span>
          <span>{{ ticket.updateTime || ticket.createTime }}</span>
        </div>
        <div v-if="ticket.location" class="meta-location">
          <svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 24 24" class="meta-icon">
            <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5a2.5 2.5 0 0 1 0-5a2.5 2.5 0 0 1 0 5z" fill="currentColor"/>
          </svg>
          <span>{{ ticket.location }}</span>
        </div>
      </div>
    </div>

    <!-- 附件图片预览弹窗 -->
    <n-modal v-model:show="attachmentModalVisible" preset="card" title="问题截图" style="width: 620px" :mask-closable="false">
      <n-image-group>
        <n-space>
          <n-image
            v-for="(img, index) in ticket.attachments"
            :key="index"
            width="200"
            :src="getImageUrl(img)"
            object-fit="contain"
          />
        </n-space>
      </n-image-group>
      <template #footer>
        <n-button @click="attachmentModalVisible = false">关闭</n-button>
      </template>
    </n-modal>

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
            <svg v-if="ticket.status === option.value" class="item-check" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
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

const emit = defineEmits(['detail', 'send', 'statusChange', 'delete'])

const placeholderImg = 'https://07akioni.oss-cn-beijing.aliyuncs.com/07akioni.jpeg'

const attachmentModalVisible = ref(false)

function handleViewAttachment() {
  attachmentModalVisible.value = true
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
  color: var(--n-border-color);
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

/* 详情按钮 */
.btn-detail {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 80px;
  height: 34px;
  padding: 0 20px;
  font-size: 14px;
  font-weight: 500;
  color: var(--n-primary-color);
  background: rgba(24, 144, 255, 0.1);
  border: 1px solid rgba(24, 144, 255, 0.25);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
  outline: none;
  white-space: nowrap;
}

.btn-detail:hover {
  background: rgba(24, 144, 255, 0.18);
  border-color: rgba(24, 144, 255, 0.35);
}

/* 编辑按钮 */
.btn-edit {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 80px;
  height: 34px;
  padding: 0 20px;
  font-size: 14px;
  font-weight: 500;
  color: #52c41a;
  background: rgba(82, 196, 26, 0.1);
  border: 1px solid rgba(82, 196, 26, 0.25);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
  outline: none;
  white-space: nowrap;
}

.btn-edit:hover {
  background: rgba(82, 196, 26, 0.18);
  border-color: rgba(82, 196, 26, 0.35);
}

/* 发送按钮 */
.btn-send {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 80px;
  height: 34px;
  padding: 0 20px;
  font-size: 14px;
  font-weight: 500;
  color: #d4380d;
  background: rgba(212, 56, 13, 0.1);
  border: 1px solid rgba(212, 56, 13, 0.25);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
  outline: none;
  white-space: nowrap;
}

.btn-send:hover {
  background: rgba(212, 56, 13, 0.18);
  border-color: rgba(212, 56, 13, 0.35);
}

/* 删除按钮 */
.btn-delete {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 80px;
  height: 34px;
  padding: 0 20px;
  font-size: 14px;
  font-weight: 500;
  color: #ff4d4f;
  background: rgba(255, 77, 79, 0.1);
  border: 1px solid rgba(255, 77, 79, 0.25);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
  outline: none;
  white-space: nowrap;
}

.btn-delete:hover {
  background: rgba(255, 77, 79, 0.18);
  border-color: rgba(255, 77, 79, 0.35);
}
</style>