<template>
  <n-modal :show="visible" preset="card" title="工单详情" style="width: 720px" @update:show="$emit('update:visible', $event)">
    <div v-if="ticket" class="detail-container" :class="{ 'theme-dark': isDark }">
      <!-- 基本信息卡片 -->
      <div class="info-card">
        <div class="info-card-header">
          <span class="info-card-title">{{ ticket.title }}</span>
          <div class="info-card-tags">
            <span class="detail-tag" :class="'status-' + ticket.status">{{ getStatusName(ticket.status) }}</span>
            <span class="detail-tag" :class="'type-' + ticket.type">{{ getTypeName(ticket.type) }}</span>
          </div>
        </div>
        <p class="info-card-desc">{{ ticket.description }}</p>
      </div>

      <!-- 详细信息卡片 -->
      <div class="detail-grid">
        <div class="detail-item">
          <span class="detail-label">工单编号</span>
          <span class="detail-value mono">{{ ticket.ticketNo }}</span>
        </div>
        <div class="detail-item">
          <span class="detail-label">创建用户</span>
          <span class="detail-value">{{ ticket.customerName }}</span>
        </div>
        <div class="detail-item">
          <span class="detail-label">创建时间</span>
          <span class="detail-value">{{ ticket.createTime }}</span>
        </div>
        <template v-if="ticket.status === 0">
          <div class="detail-item">
            <span class="detail-label">处理人</span>
            <span class="detail-value">{{ ticket.assigneeName || ticket.operatorName || '-' }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">完成时间</span>
            <span class="detail-value">{{ ticket.completeTime || '-' }}</span>
          </div>
        </template>
        <div class="detail-item" v-if="ticket.location">
          <span class="detail-label">地点</span>
          <span class="detail-value">{{ ticket.location }}</span>
        </div>
      </div>

      <!-- 附件卡片 -->
      <div v-if="ticket.attachments && ticket.attachments.length > 0" class="info-card">
        <div class="info-card-header">
          <span class="info-card-title" style="font-size: 15px;">附件内容</span>
        </div>
        <n-image-group>
          <n-space>
            <n-image
              v-for="(img, index) in ticket.attachments"
              :key="index"
              width="120"
              :src="getImageUrl(img)"
            />
          </n-space>
        </n-image-group>
      </div>
    </div>
  </n-modal>
</template>

<script setup>
import { computed } from 'vue'
import { useAppStore } from '@/store'

const emit = defineEmits(['update:visible'])

const placeholderImg = 'https://07akioni.oss-cn-beijing.aliyuncs.com/07akioni.jpeg'

function getImageUrl(img) {
  if (!img) return placeholderImg
  if (img.startsWith('http://') || img.startsWith('https://') || img.startsWith('/') || img.startsWith('data:')) return img
  return placeholderImg
}

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  ticket: {
    type: Object,
    default: null
  }
})

const isDark = computed(() => useAppStore().isDark)

function getStatusName(status) {
  const map = { 0: '已完成', 1: '进行中', 2: '未开始', 3: '已关闭' }
  return map[status] || '未知'
}

function getTypeName(type) {
  const map = { 0: '故障工单', 1: '服务请求工单', 2: '变更工单', 3: '维护工单' }
  return map[type] || '未知'
}
</script>

<style scoped>
.detail-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* 信息卡片 */
.info-card {
  padding: 16px 20px;
  border-radius: 10px;
  background: #ffffff;
  border: none;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}

.theme-dark .info-card {
  background: var(--n-card-color);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.15);
}

.info-card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 8px;
}

.info-card-title {
  font-size: 16px;
  font-weight: 600;
  color: #1a1a1a;
  line-height: 1.4;
}

.theme-dark .info-card-title {
  color: var(--n-text-color);
}

.info-card-tags {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.info-card-desc {
  font-size: 14px;
  color: #6b7280;
  line-height: 1.7;
  margin: 0;
}

.theme-dark .info-card-desc {
  color: var(--n-text-color-2);
}

/* 标签样式 */
.detail-tag {
  display: inline-flex;
  align-items: center;
  padding: 3px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
  line-height: 20px;
  white-space: nowrap;
}

.detail-tag.status-0 {
  color: #52c41a;
  background: #f6ffed;
  border: 1px solid #b7eb8f;
}
.theme-dark .detail-tag.status-0 {
  color: #73d13d;
  background: rgba(82, 196, 26, 0.12);
  border: 1px solid rgba(82, 196, 26, 0.2);
}

.detail-tag.status-1 {
  color: #fa8c16;
  background: #fff7e6;
  border: 1px solid #ffd591;
}
.theme-dark .detail-tag.status-1 {
  color: #ffa940;
  background: rgba(250, 140, 22, 0.12);
  border: 1px solid rgba(250, 140, 22, 0.2);
}

.detail-tag.status-2 {
  color: #8c8c8c;
  background: #f5f5f5;
  border: 1px solid #e8e8e8;
}
.theme-dark .detail-tag.status-2 {
  color: #a0a0a0;
  background: rgba(140, 140, 140, 0.12);
  border: 1px solid rgba(140, 140, 140, 0.2);
}

.detail-tag.status-3 {
  color: #ff4d4f;
  background: #fff2f0;
  border: 1px solid #ffccc7;
}
.theme-dark .detail-tag.status-3 {
  color: #ff7875;
  background: rgba(255, 77, 79, 0.12);
  border: 1px solid rgba(255, 77, 79, 0.2);
}

.detail-tag.type-0 {
  color: #ff4d4f;
  background: #fff2f0;
  border: 1px solid #ffccc7;
}
.theme-dark .detail-tag.type-0 {
  color: #ff7875;
  background: rgba(255, 77, 79, 0.12);
  border: 1px solid rgba(255, 77, 79, 0.2);
}

.detail-tag.type-1 {
  color: #1890ff;
  background: #e6f7ff;
  border: 1px solid #91d5ff;
}
.theme-dark .detail-tag.type-1 {
  color: #69c0ff;
  background: rgba(24, 144, 255, 0.12);
  border: 1px solid rgba(24, 144, 255, 0.2);
}

.detail-tag.type-2 {
  color: #fa8c16;
  background: #fff7e6;
  border: 1px solid #ffd591;
}
.theme-dark .detail-tag.type-2 {
  color: #ffa940;
  background: rgba(250, 140, 22, 0.12);
  border: 1px solid rgba(250, 140, 22, 0.2);
}

.detail-tag.type-3 {
  color: #52c41a;
  background: #f6ffed;
  border: 1px solid #b7eb8f;
}
.theme-dark .detail-tag.type-3 {
  color: #73d13d;
  background: rgba(82, 196, 26, 0.12);
  border: 1px solid rgba(82, 196, 26, 0.2);
}

/* 详情网格 */
.detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0;
  border-radius: 10px;
  border: none;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
  overflow: hidden;
  background: #ffffff;
}

.theme-dark .detail-grid {
  background: var(--n-card-color);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.15);
}

.detail-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 14px 16px;
  background: transparent;
  border-bottom: 1px solid #f0f0f0;
}

.theme-dark .detail-item {
  background: transparent;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.detail-item:nth-child(odd) {
  border-right: 1px solid #f0f0f0;
}

.theme-dark .detail-item:nth-child(odd) {
  border-right: 1px solid rgba(255, 255, 255, 0.05);
}

.detail-label {
  font-size: 13px;
  color: #6b7280;
  font-weight: 400;
}

.theme-dark .detail-label {
  color: var(--n-text-color-3);
}

.detail-value {
  font-size: 14px;
  color: #1a1a1a;
  font-weight: 500;
  word-break: break-all;
}

.theme-dark .detail-value {
  color: var(--n-text-color);
}

.detail-value.mono {
  font-family: 'SF Mono', 'Monaco', 'Menlo', 'Consolas', monospace;
  font-size: 13px;
  color: #4e5969;
}

.theme-dark .detail-value.mono {
  color: var(--n-text-color-2);
}
</style>
