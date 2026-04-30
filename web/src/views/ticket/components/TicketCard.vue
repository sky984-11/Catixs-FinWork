<template>
  <div class="ticket-card-wrapper">
    <div class="ticket-card" @click="$emit('detail', ticket)">
      <div class="card-header">
      <span class="ticket-title">{{ ticket.title }}</span>
      <div class="header-tags">
        <!-- 状态标签：管理员可点击切换 -->
        <div v-if="isAdminOrNoc" class="status-dropdown-wrapper" @click.stop>
          <span
            class="status-tag status-clickable"
            :class="'status-' + ticket.status"
            @click="toggleStatusDropdown"
          >
            <svg v-if="ticket.status === 2" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 24 24" class="tag-icon">
              <path d="M5 12l5 5L20 7" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path>
            </svg>
            {{ getStatusName(ticket.status) }}
          </span>
          <div v-if="statusDropdownVisible" class="status-dropdown">
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
        <!-- 非管理员：静态标签 -->
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

    <div class="card-actions" @click.stop>
      <button class="btn-detail" @click="$emit('detail', ticket)">详情</button>
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
      <div v-if="ticket.attachments && ticket.attachments.length > 0" class="meta-attach">
        <svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 24 24" class="meta-icon">
          <path d="M16.5 6v11.5c0 2.21-1.79 4-4 4s-4-1.79-4-4V5a2.5 2.5 0 0 1 5 0v10.5c0 .55-.45 1-1 1s-1-.45-1-1V6H10v9.5a2.5 2.5 0 0 0 5 0V5c0-2.21-1.79-4-4-4S7 2.79 7 5v12.5c0 3.04 2.46 5.5 5.5 5.5s5.5-2.46 5.5-5.5V6h-1.5z" fill="currentColor"></path>
        </svg>
        <span>{{ ticket.attachments.length }} 张问题截图</span>
      </div>
    </div>
  </div>
</div>
</template>

<script setup>
import { ref } from 'vue'

const emit = defineEmits(['detail', 'send', 'statusChange', 'delete'])

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

const statusOptions = [
  { label: '未开始', value: 0 },
  { label: '进行中', value: 1 },
  { label: '已完成', value: 2 },
  { label: '已关闭', value: 3 }
]

function toggleStatusDropdown() {
  statusDropdownVisible.value = !statusDropdownVisible.value
}

function handleStatusSelect(newStatus) {
  if (newStatus === props.ticket.status) {
    statusDropdownVisible.value = false
    return
  }
  emit('statusChange', { ticket: props.ticket, newStatus })
  statusDropdownVisible.value = false
}

function getStatusName(status) {
  const map = { 0: '未开始', 1: '进行中', 2: '已完成', 3: '已关闭' }
  return map[status] || '未知'
}

function getTypeName(type) {
  const map = { 0: '故障工单', 1: '服务请求工单', 2: '变更工单', 3: '维护工单' }
  return map[type] || '未知'
}

function getStatusTagType(status) {
  const map = { 0: 'default', 1: 'warning', 2: 'success' }
  return map[status] || 'default'
}

function getTypeTagType(type) {
  const map = { 0: 'error', 1: 'info', 2: 'warning', 3: 'success' }
  return map[type] || 'default'
}
</script>

<style scoped>
.ticket-card-wrapper {
  padding: 4px;
  margin-bottom: 8px;
  margin-left: -4px;
  margin-right: -4px;
}

.ticket-card {
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
  transform: translateY(-4px);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
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

/* 下拉菜单 */
.status-dropdown {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  min-width: 140px;
  background: var(--n-card-color);
  border: 1px solid var(--n-border-color);
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
  padding: 4px;
  z-index: 100;
}

.status-dropdown-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 13px;
  color: var(--n-text-color);
  cursor: pointer;
  transition: background 0.15s ease;
}

.status-dropdown-item:hover {
  background: var(--n-hover-color);
}

.status-dropdown-item.item-active {
  background: rgba(24, 144, 255, 0.1);
  color: var(--n-primary-color);
}

.item-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dot-0 { background: var(--n-text-color-3); }
.dot-1 { background: #fa8c16; }
.dot-2 { background: #52c41a; }
.dot-3 { background: var(--n-text-color-3); }

.item-check {
  width: 16px;
  height: 16px;
  margin-left: auto;
  flex-shrink: 0;
}

.tag-icon {
  width: 13px;
  height: 13px;
}

.status-0 {
  color: #8c8c8c;
  background: rgba(140, 140, 140, 0.1);
  border: 1px solid rgba(140, 140, 140, 0.2);
}

.status-1 {
  color: #fa8c16;
  background: rgba(250, 140, 22, 0.1);
  border: 1px solid rgba(250, 140, 22, 0.2);
}

.status-2 {
  color: #52c41a;
  background: rgba(82, 196, 26, 0.1);
  border: 1px solid rgba(82, 196, 26, 0.2);
}

.status-3 {
  color: var(--n-text-color-3);
  background: rgba(89, 89, 89, 0.1);
  border: 1px solid rgba(89, 89, 89, 0.2);
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
  color: var(--n-text-color-2);
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
  color: var(--n-text-color-3);
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

.meta-attach {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--n-primary-color);
  font-weight: 500;
}

.meta-location {
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--n-text-color-2);
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