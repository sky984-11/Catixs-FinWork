<script setup>
import { h, onMounted, ref } from 'vue'
import {
  NAlert,
  NButton,
  NCheckbox,
  NDatePicker,
  NForm,
  NFormItem,
  NInput,
  NModal,
  NSelect,
  NSpace,
  NSwitch,
  NTag,
  NTooltip,
} from 'naive-ui'
import api from '@/api'
import CommonPage from '@/components/page/CommonPage.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CButton from '@/components/public/CButton.vue'
import TheIcon from '@/components/icon/TheIcon.vue'

defineOptions({ name: 'ApiTokens' })

const table = ref(null)
const query = ref({})
const users = ref([])
const usersLoading = ref(false)
const usersError = ref(false)
const listError = ref('')
const busy = ref(false)
const busyId = ref(null)
const visible = ref(false)
const form = ref({})
const formError = ref('')
const secret = ref('')
const secretVisible = ref(false)
const confirmation = ref(null)
const statusOptions = [
  { label: '启用', value: 'enabled' },
  { label: '停用', value: 'disabled' },
  { label: '已过期', value: 'expired' },
  { label: '用户已停用', value: 'user_disabled' },
]
const dateText = (value) =>
  value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '—'

async function loadUsers() {
  usersLoading.value = true
  usersError.value = false
  try {
    const res = await api.getApiTokenUsers()
    users.value = res.data.map((user) => ({
      label: user.alias ? `${user.username}（${user.alias}）` : user.username,
      value: user.id,
    }))
  } catch {
    usersError.value = true
  } finally {
    usersLoading.value = false
  }
}

async function loadTokens(params) {
  listError.value = ''
  try {
    return await api.getApiTokens(params)
  } catch (error) {
    listError.value = error.message || 'API tokens 加载失败，请重试'
    throw error
  }
}

function edit(row = null) {
  if (busy.value) return
  formError.value = ''
  form.value = row
    ? {
        ...row,
        permanent: !row.expires_at,
        expiry: row.expires_at ? Date.parse(row.expires_at) : null,
      }
    : { name: '', description: '', user_id: null, is_enabled: true, permanent: true, expiry: null }
  visible.value = true
  if (usersError.value) loadUsers()
}

function showSecret(data) {
  secret.value = data.token
  secretVisible.value = true
}

function closeSecret() {
  secretVisible.value = false
  secret.value = ''
}

async function copySecret() {
  try {
    await navigator.clipboard.writeText(secret.value)
    $message.success('Token 已复制')
  } catch {
    $message.error('复制失败，请选中文本手动复制')
  }
}

async function save() {
  if (busy.value) return
  const value = form.value
  if (!value.name?.trim() || !value.user_id) {
    formError.value = '请填写名称并选择用户'
    return
  }
  if (!value.permanent && (!value.expiry || value.expiry <= Date.now())) {
    formError.value = '请选择晚于当前时间的到期时间'
    return
  }
  busy.value = true
  formError.value = ''
  try {
    const payload = {
      name: value.name.trim(),
      description: value.description,
      is_enabled: value.is_enabled,
      expires_at: value.permanent ? null : new Date(value.expiry).toISOString(),
    }
    if (value.id) {
      await api.updateApiToken(value.id, payload)
    } else {
      const res = await api.createApiToken({ ...payload, user_id: value.user_id })
      showSecret(res.data)
    }
    visible.value = false
    table.value?.handleSearch()
    $message.success('已保存')
  } catch (error) {
    formError.value = error.message || '保存失败，请重试'
  } finally {
    busy.value = false
  }
}

async function runAction(row, action) {
  if (busy.value) return
  busy.value = true
  busyId.value = row.id
  try {
    if (action === 'delete') await api.deleteApiToken(row.id)
    else if (action === 'regenerate') showSecret((await api.regenerateApiToken(row.id)).data)
    else await api.setApiTokenStatus(row.id, { is_enabled: !row.is_enabled })
    confirmation.value = null
    table.value?.handleSearch()
    $message.success('操作成功')
  } catch {
    // The shared request handler displays the error; keep the confirmation available for retry.
  } finally {
    busy.value = false
    busyId.value = null
  }
}

function actionButton(row, label, icon, type, handler) {
  return h(NTooltip, null, {
    trigger: () =>
      h(
        NButton,
        {
          size: 'small',
          circle: true,
          quaternary: true,
          type,
          'aria-label': label,
          disabled: busy.value,
          loading: busy.value && busyId.value === row.id,
          onClick: (event) => {
            event.stopPropagation()
            if (!busy.value) handler()
          },
        },
        { icon: () => h(TheIcon, { icon, size: 17 }) }
      ),
    default: () => label,
  })
}

const columns = [
  { title: '名称', key: 'name', width: 180, resizable: true, ellipsis: { tooltip: true } },
  { title: '用户', key: 'username', width: 140, resizable: true },
  {
    title: '状态',
    key: 'status',
    width: 120,
    resizable: true,
    render: (row) =>
      h(
        NTag,
        { type: row.status === 'enabled' ? 'success' : 'warning', size: 'small' },
        () => statusOptions.find((item) => item.value === row.status)?.label
      ),
  },
  {
    title: '到期时间',
    key: 'expires_at',
    width: 190,
    resizable: true,
    render: (row) => (row.expires_at ? dateText(row.expires_at) : '永久有效'),
  },
  {
    title: '最近使用',
    key: 'last_used_at',
    width: 190,
    resizable: true,
    render: (row) => dateText(row.last_used_at),
  },
  { title: '创建人', key: 'created_by_name', width: 130, resizable: true },
  {
    title: '创建时间',
    key: 'created_at',
    width: 190,
    resizable: true,
    render: (row) => dateText(row.created_at),
  },
  { title: '说明', key: 'description', width: 200, resizable: true, ellipsis: { tooltip: true } },
  {
    title: '操作',
    key: 'actions',
    width: 160,
    fixed: 'right',
    resizable: false,
    render: (row) =>
      h(NSpace, { wrap: false, size: 4 }, () => [
        actionButton(row, '编辑', 'material-symbols:edit', 'primary', () => edit(row)),
        actionButton(
          row,
          row.is_enabled ? '停用' : '启用',
          'mdi:power',
          row.is_enabled ? 'warning' : 'success',
          () =>
            row.is_enabled
              ? (confirmation.value = {
                  row,
                  action: 'status',
                  title: '停用 token',
                  message: '停用后该 token 将立即无法认证。',
                })
              : runAction(row, 'status')
        ),
        actionButton(row, '重新生成', 'mdi:refresh', 'warning', () => {
          confirmation.value = {
            row,
            action: 'regenerate',
            title: '重新生成 token',
            message:
              '旧 token 将立即失效，使用它的外部系统需要更新凭据。到期时间和启用状态保持不变。',
          }
        }),
        actionButton(row, '删除', 'material-symbols:delete-outline', 'error', () => {
          confirmation.value = {
            row,
            action: 'delete',
            title: '删除 token',
            message: '删除后该 token 立即失效，且无法恢复。',
          }
        }),
      ]),
  },
]

onMounted(() => {
  table.value?.handleSearch()
  loadUsers()
})
</script>

<template>
  <CommonPage title="API tokens">
    <template #action>
      <NButton type="primary" :disabled="busy" @click="edit()">创建 API token</NButton>
    </template>
    <NAlert type="info" class="mb-16">
      Token 继承所绑定用户的权限，支持永久有效；明文仅在创建或重新生成时显示一次。
    </NAlert>
    <NAlert v-if="listError" type="error" class="mb-16">{{ listError }}</NAlert>
    <CrudTable
      ref="table"
      v-model:query-items="query"
      :columns="columns"
      :get-data="loadTokens"
      :scroll-x="1600"
    >
      <template #queryBar>
        <QueryBarItem label="名称"><NInput v-model:value="query.name" clearable /></QueryBarItem>
        <QueryBarItem label="用户">
          <NSelect
            v-model:value="query.user_id"
            :options="users"
            clearable
            filterable
            :loading="usersLoading"
          />
        </QueryBarItem>
        <QueryBarItem label="状态"
          ><NSelect v-model:value="query.status" :options="statusOptions" clearable
        /></QueryBarItem>
      </template>
    </CrudTable>

    <NModal
      v-model:show="visible"
      preset="card"
      :title="form.id ? '编辑 API token' : '创建 API token'"
      class="token-modal"
      :closable="!busy"
      :mask-closable="!busy"
      :close-on-esc="!busy"
    >
      <NAlert v-if="formError" type="error" class="mb-16">{{ formError }}</NAlert>
      <NAlert v-if="usersError" type="error" class="mb-16">
        用户列表加载失败。
        <CButton
          show-save
          :show-cancel="false"
          save-text="重新加载"
          :save-loading="usersLoading"
          @save="loadUsers"
        />
      </NAlert>
      <NForm label-placement="top" :disabled="busy">
        <NFormItem label="名称" required
          ><NInput v-model:value="form.name" :maxlength="100"
        /></NFormItem>
        <NFormItem label="用户" required>
          <NInput v-if="form.id" :value="form.username" disabled />
          <NSelect
            v-else
            v-model:value="form.user_id"
            :options="users"
            filterable
            :loading="usersLoading"
          />
        </NFormItem>
        <NFormItem label="说明"
          ><NInput v-model:value="form.description" type="textarea" :maxlength="500"
        /></NFormItem>
        <NFormItem label="有效期">
          <NSpace vertical>
            <NCheckbox v-model:checked="form.permanent" :disabled="busy">永久有效</NCheckbox>
            <NDatePicker
              v-if="!form.permanent"
              v-model:value="form.expiry"
              type="datetime"
              clearable
              :disabled="busy"
            />
          </NSpace>
        </NFormItem>
        <NFormItem label="启用"
          ><NSwitch v-model:value="form.is_enabled" :disabled="busy"
        /></NFormItem>
      </NForm>
      <template #footer>
        <CButton
          show-save
          show-cancel
          :disabled="busy"
          :save-loading="busy"
          @save="save"
          @cancel="visible = false"
        />
      </template>
    </NModal>

    <NModal
      :show="secretVisible"
      preset="card"
      title="保存 API token"
      class="token-modal"
      :mask-closable="false"
      @update:show="closeSecret"
    >
      <NAlert type="warning" class="mb-16"
        >请立即复制保存，关闭后无法再次查看。不要将 token 放入 URL 或公开文档。</NAlert
      >
      <NInput :value="secret" readonly type="textarea" :autosize="{ minRows: 3 }" />
      <p>调用方式：请求头 token: &lt;token&gt; 或 Authorization: Bearer &lt;token&gt;。</p>
      <template #footer
        ><CButton
          show-save
          show-cancel
          save-text="复制 token"
          cancel-text="关闭"
          @save="copySecret"
          @cancel="closeSecret"
      /></template>
    </NModal>

    <NModal
      :show="!!confirmation"
      preset="card"
      :title="confirmation?.title"
      class="token-modal"
      :closable="!busy"
      :mask-closable="!busy"
      :close-on-esc="!busy"
      @update:show="confirmation = null"
    >
      <p>{{ confirmation?.row.name }}</p>
      <p>{{ confirmation?.message }}</p>
      <template #footer>
        <CButton
          show-save
          show-cancel
          save-text="确认"
          :disabled="busy"
          :save-loading="busy"
          @save="runAction(confirmation.row, confirmation.action)"
          @cancel="confirmation = null"
        />
      </template>
    </NModal>
  </CommonPage>
</template>

<style scoped>
.token-modal {
  width: min(600px, calc(100vw - 32px));
  max-height: 90vh;
  overflow: auto;
}
</style>
