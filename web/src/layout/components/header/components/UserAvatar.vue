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
            <n-form-item label="群组关键词">
              <n-dynamic-tags v-model:value="tgForm.group_keywords" />
            </n-form-item>
            <n-form-item label="@某人关键词">
              <n-dynamic-tags v-model:value="tgForm.mention_keywords" />
            </n-form-item>
            <n-form-item label="仅接收用户">
              <n-dynamic-tags v-model:value="tgForm.include_user_keywords" />
            </n-form-item>
            <n-form-item label="忽略用户">
              <n-dynamic-tags v-model:value="tgForm.exclude_user_keywords" />
            </n-form-item>
            <n-form-item label="忽略关键词（任意命中即跳过）">
              <n-dynamic-tags v-model:value="tgForm.ignored_keywords" />
            </n-form-item>
          </div>

          <div class="tg-rule-note">
            <n-tag size="small" type="info">匹配关系</n-tag>
            <span>群组、@某人、仅接收用户：填写了几项就必须同时满足几项；每项内部命中任意关键词即可。</span>
            <span>仅接收用户为空表示不限制发送人；忽略用户和忽略关键词优先级最高，命中即不推送。</span>
            <span>启用后如果过滤都不填写，则推送全部符合事件和消息类型的消息。</span>
          </div>

        </n-form>
      </div>
    </n-spin>
  </n-modal>
</template>

<script setup>
import { useUserStore } from '@/store'
import api from '@/api'
import { renderIcon } from '@/utils'
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const router = useRouter()

const userStore = useUserStore()
const tgVisible = ref(false)
const tgLoading = ref(false)
const tgSaving = ref(false)
const tgForm = reactive(createTgForm())

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
    group_keywords: [],
    include_user_keywords: [],
    exclude_user_keywords: [],
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
  const includeUserKeywords = normalizeList(data.include_user_keywords)
  const legacySourceUserKeywords = normalizeList(data.source_user_keywords)
  Object.assign(tgForm, createTgForm(), {
    ...data,
    group_keywords: normalizeList(data.group_keywords),
    include_user_keywords: includeUserKeywords.length ? includeUserKeywords : legacySourceUserKeywords,
    exclude_user_keywords: normalizeList(data.exclude_user_keywords),
    source_user_keywords: [],
    content_keywords: [],
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
    const configRes = await api.getTgAssistantConfig()
    fillTgForm(configRes?.data || {})
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
