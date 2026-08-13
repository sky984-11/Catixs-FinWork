<template>
  <n-dropdown :options="options" @select="handleSelect">
    <div flex cursor-pointer items-center>
      <img :src="userStore.avatar" mr10 h-35 w-35 rounded-full />
      <span>{{ userStore.name }}</span>
    </div>
  </n-dropdown>

  <n-modal
    v-model:show="tgVisible"
    preset="card"
    title="TG助手"
    style="width: min(920px, calc(100vw - 32px))"
  >
    <n-spin :show="tgLoading">
      <div class="tg-layout">
        <n-form label-placement="top" :model="tgForm">
          <div class="tg-toolbar">
            <n-switch v-model:value="tgForm.is_enabled">
              <template #checked>已启用</template>
              <template #unchecked>未启用</template>
            </n-switch>
            <n-button type="primary" :loading="tgSaving" @click="saveTgAssistant">保存</n-button>
          </div>

          <div class="tg-grid">
            <n-form-item label="通知用户/发送人关键词（组内 OR）">
              <n-dynamic-tags v-model:value="tgForm.source_user_keywords" />
            </n-form-item>
            <n-form-item label="内容包含关键词（组内 OR）">
              <n-dynamic-tags v-model:value="tgForm.content_keywords" />
            </n-form-item>
            <n-form-item label="@某人关键词（组内 OR）">
              <n-dynamic-tags v-model:value="tgForm.mention_keywords" />
            </n-form-item>
            <n-form-item label="忽略关键词（任意命中即跳过）">
              <n-dynamic-tags v-model:value="tgForm.ignored_keywords" />
            </n-form-item>
          </div>

          <div class="tg-rule-note">
            <n-tag size="small" type="info">匹配关系</n-tag>
            <span>发送人、内容、@某人三组：填写了几组就必须同时满足几组；每组内部命中任意关键词即可。</span>
            <span>启用后如果三组都不填写，则推送全部符合事件和消息类型的消息。</span>
            <span>忽略关键词优先级最高，任意命中就不推送。</span>
          </div>

          <div class="tg-grid">
            <n-form-item label="Chatwoot 事件">
              <n-select v-model:value="tgForm.event_types" multiple :options="eventOptions" />
            </n-form-item>
            <n-form-item label="消息类型">
              <n-select v-model:value="tgForm.message_types" multiple :options="messageTypeOptions" />
            </n-form-item>
          </div>

        </n-form>

        <section>
          <div class="tg-section-title">最近记录</div>
          <n-data-table
            size="small"
            :columns="logColumns"
            :data="tgLogs"
            :pagination="false"
            :bordered="false"
          />
        </section>
      </div>
    </n-spin>
  </n-modal>
</template>

<script setup>
import { useUserStore } from '@/store'
import api from '@/api'
import { renderIcon } from '@/utils'
import { h, reactive, ref } from 'vue'
import { NTag } from 'naive-ui'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const router = useRouter()

const userStore = useUserStore()
const tgVisible = ref(false)
const tgLoading = ref(false)
const tgSaving = ref(false)
const tgLogs = ref([])
const tgForm = reactive(createTgForm())

const eventOptions = [
  { label: '新消息', value: 'message_created' },
  { label: '消息更新', value: 'message_updated' },
]

const messageTypeOptions = [
  { label: '客户消息 incoming', value: 'incoming' },
  { label: '客服回复 outgoing', value: 'outgoing' },
  { label: '系统活动 activity', value: 'activity' },
  { label: '模板 template', value: 'template' },
]

const logColumns = [
  { title: '时间', key: 'created_at', width: 150 },
  {
    title: '状态',
    key: 'status',
    width: 80,
    render(row) {
      const type = row.status === 'sent' ? 'success' : row.status === 'failed' ? 'error' : 'default'
      return h(NTag, { type, size: 'small' }, { default: () => statusLabel(row.status) })
    },
  },
  { title: '客户', key: 'contact_name', ellipsis: { tooltip: true } },
  { title: '发送人', key: 'sender_name', ellipsis: { tooltip: true } },
  { title: '原因', key: 'reason', ellipsis: { tooltip: true } },
]

const options = [
  {
    label: t('header.label_profile'),
    key: 'profile',
    icon: renderIcon('mdi-account-arrow-right-outline', { size: '14px' }),
  },
  {
    label: 'TG助手',
    key: 'tg-assistant',
    icon: renderIcon('mdi:message-badge-outline', { size: '14px' }),
  },
  {
    label: t('header.label_logout'),
    key: 'logout',
    icon: renderIcon('mdi:exit-to-app', { size: '14px' }),
  },
]

function handleSelect(key) {
  if (key === 'profile') {
    router.push('/profile')
  } else if (key === 'tg-assistant') {
    openTgAssistant()
  } else if (key === 'logout') {
    $dialog.confirm({
      title: t('header.label_logout_dialog_title'),
      type: 'warning',
      content: t('header.text_logout_confirm'),
      confirm() {
        userStore.logout()
        $message.success(t('header.text_logout_success'))
      },
    })
  }
}

function createTgForm() {
  return {
    is_enabled: false,
    source_user_keywords: [],
    content_keywords: [],
    mention_keywords: [],
    ignored_keywords: [],
    event_types: ['message_created', 'message_updated'],
    message_types: ['incoming'],
    include_private: false,
    show_message_detail: true,
  }
}

function normalizeList(value) {
  return Array.isArray(value) ? value.filter(Boolean) : []
}

function fillTgForm(data = {}) {
  Object.assign(tgForm, createTgForm(), {
    ...data,
    source_user_keywords: normalizeList(data.source_user_keywords),
    content_keywords: normalizeList(data.content_keywords),
    mention_keywords: normalizeList(data.mention_keywords),
    ignored_keywords: normalizeList(data.ignored_keywords),
    event_types: normalizeList(data.event_types).length ? normalizeList(data.event_types) : ['message_created', 'message_updated'],
    message_types: normalizeList(data.message_types).length ? normalizeList(data.message_types) : ['incoming'],
  })
}

async function openTgAssistant() {
  tgVisible.value = true
  tgLoading.value = true
  try {
    const [configRes, logsRes] = await Promise.all([
      api.getTgAssistantConfig(),
      api.getTgAssistantLogs({ limit: 20 }),
    ])
    fillTgForm(configRes?.data || {})
    tgLogs.value = logsRes?.data || []
  } finally {
    tgLoading.value = false
  }
}

async function saveTgAssistant() {
  tgSaving.value = true
  try {
    const res = await api.saveTgAssistantConfig({ ...tgForm })
    fillTgForm(res?.data || tgForm)
    $message.success('TG助手配置已保存')
  } finally {
    tgSaving.value = false
  }
}

function statusLabel(status) {
  return { sent: '已推送', failed: '失败', skipped: '跳过' }[status] || status || '-'
}
</script>

<style scoped>
.tg-layout {
  display: grid;
  gap: 18px;
}

.tg-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.tg-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.tg-rule-note {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin: -2px 0 14px;
  color: #5c6878;
  font-size: 13px;
  line-height: 1.6;
}

.tg-section-title {
  margin-bottom: 10px;
  font-weight: 600;
}

@media (max-width: 720px) {
  .tg-grid {
    grid-template-columns: 1fr;
  }

  .tg-toolbar {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
