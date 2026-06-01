<script setup>
import { h, onMounted, ref, resolveDirective, withDirectives } from 'vue'
import {
  NButton,
  NDrawer,
  NDrawerContent,
  NForm,
  NFormItem,
  NInput,
  NPopconfirm,
  NSpace,
  NTag,
} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudModal from '@/components/table/CrudModal.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import TheIcon from '@/components/icon/TheIcon.vue'

import { renderIcon } from '@/utils'
import { useCRUD } from '@/composables'
// import { loginTypeMap, loginTypeOptions } from '@/constant/data'
import api from '@/api'

defineOptions({ name: 'API管理' })

const $table = ref(null)
const queryItems = ref({})
const vPermission = resolveDirective('permission')
const docsVisible = ref(false)
const docsLoading = ref(false)
const apiDocs = ref({ items: [], total: 0 })
const apiDocsUrl = `${window.location.origin}${import.meta.env.VITE_BASE_API}/api/docs`
const openApiDocsUrl = `${window.location.origin}${import.meta.env.VITE_BASE_API}/api/docs/openapi`

const {
  modalVisible,
  modalTitle,
  modalLoading,
  handleSave,
  modalForm,
  modalFormRef,
  handleEdit,
  handleDelete,
  handleAdd,
} = useCRUD({
  name: 'API',
  initForm: {},
  doCreate: api.createApi,
  doUpdate: api.updateApi,
  doDelete: api.deleteApi,
  refresh: () => $table.value?.handleSearch(),
})

onMounted(() => {
  $table.value?.handleSearch()
})

async function handleRefreshApi() {
  await $dialog.confirm({
    title: '提示',
    type: 'warning',
    content: '此操作会根据后端 app.routes 进行路由更新，确定继续刷新 API 操作？',
    async confirm() {
      await api.refreshApi()
      $message.success('刷新完成')
      $table.value?.handleSearch()
    },
  })
}

async function handleOpenDocs() {
  docsVisible.value = true
  docsLoading.value = true
  try {
    const res = await api.getApiDocs()
    apiDocs.value = res.data || { items: [], total: 0 }
  } finally {
    docsLoading.value = false
  }
}

async function handleCopyDocsUrl(url) {
  await navigator.clipboard.writeText(url)
  $message.success('文档地址已复制')
}

const addAPIRules = {
  path: [
    {
      required: true,
      message: '请输入API路径',
      trigger: ['input', 'blur', 'change'],
    },
  ],
  method: [
    {
      required: true,
      message: '请输入请求方式',
      trigger: ['input', 'blur', 'change'],
    },
  ],
  summary: [
    {
      required: true,
      message: '请输入API简介',
      trigger: ['input', 'blur', 'change'],
    },
  ],
  tags: [
    {
      required: true,
      message: '请输入Tags',
      trigger: ['input', 'blur', 'change'],
    },
  ],
}

const columns = [
  {
    title: 'API路径',
    key: 'path',
    width: 'auto',
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    title: '请求方式',
    key: 'method',
    align: 'center',
    width: 'auto',
    ellipsis: { tooltip: true },
  },
  {
    title: 'API简介',
    key: 'summary',
    width: 'auto',
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    title: 'Tags',
    key: 'tags',
    width: 'auto',
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    title: '操作',
    key: 'actions',
    width: 'auto',
    align: 'center',
    fixed: 'right',
    render(row) {
      return [
        withDirectives(
          h(
            NButton,
            {
              size: 'small',
              type: 'primary',
              style: 'margin-right: 8px;',
              onClick: () => {
                handleEdit(row)
                modalForm.value.roles = row.roles.map((e) => (e = e.id))
              },
            },
            {
              default: () => '编辑',
              icon: renderIcon('material-symbols:edit', { size: 16 }),
            }
          ),
          [[vPermission, 'post/api/v1/api/update']]
        ),
        h(
          NPopconfirm,
          {
            onPositiveClick: () => handleDelete({ api_id: row.id }, false),
            onNegativeClick: () => {},
          },
          {
            trigger: () =>
              withDirectives(
                h(
                  NButton,
                  {
                    size: 'small',
                    type: 'error',
                    style: 'margin-right: 8px;',
                  },
                  {
                    default: () => '删除',
                    icon: renderIcon('material-symbols:delete-outline', { size: 16 }),
                  }
                ),
                [[vPermission, 'delete/api/v1/api/delete']]
              ),
            default: () => h('div', {}, '确定删除该API吗?'),
          }
        ),
      ]
    },
  },
]
</script>

<template>
  <!-- 业务页面 -->
  <CommonPage show-footer title="API列表">
    <template #action>
      <div>
        <NButton
          v-permission="'post/api/v1/api/create'"
          class="float-right mr-15"
          type="primary"
          @click="handleAdd"
        >
          <TheIcon icon="material-symbols:add" :size="18" class="mr-5" />新建API
        </NButton>
        <NButton
          v-permission="'post/api/v1/api/refresh'"
          class="float-right mr-15"
          type="warning"
          @click="handleRefreshApi"
        >
          <TheIcon icon="material-symbols:refresh" :size="18" class="mr-5" />刷新API
        </NButton>
        <NButton class="float-right mr-15" type="info" @click="handleOpenDocs">
          <TheIcon icon="material-symbols:description-outline" :size="18" class="mr-5" />API文档
        </NButton>
      </div>
    </template>
    <!-- 表格 -->
    <CrudTable
      ref="$table"
      v-model:query-items="queryItems"
      :columns="columns"
      :get-data="api.getApis"
    >
      <template #queryBar>
        <QueryBarItem label="路径" :label-width="40">
          <NInput
            v-model:value="queryItems.path"
            clearable
            type="text"
            placeholder="请输入API路径"
            @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="API简介" :label-width="70">
          <NInput
            v-model:value="queryItems.summary"
            clearable
            type="text"
            placeholder="请输入API简介"
            @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="Tags" :label-width="40">
          <NInput
            v-model:value="queryItems.tags"
            clearable
            type="text"
            placeholder="请输入API模块"
            @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
      </template>
    </CrudTable>

    <!-- 新增/编辑 弹窗 -->
    <CrudModal
      v-model:visible="modalVisible"
      :title="modalTitle"
      :loading="modalLoading"
      @save="handleSave"
    >
      <NForm
        ref="modalFormRef"
        label-placement="left"
        label-align="left"
        :label-width="80"
        :model="modalForm"
        :rules="addAPIRules"
      >
        <NFormItem label="API名称" path="path">
          <NInput v-model:value="modalForm.path" clearable placeholder="请输入API路径" />
        </NFormItem>
        <NFormItem label="请求方式" path="method">
          <NInput v-model:value="modalForm.method" clearable placeholder="请输入请求方式" />
        </NFormItem>
        <NFormItem label="API简介" path="summary">
          <NInput v-model:value="modalForm.summary" clearable placeholder="请输入API简介" />
        </NFormItem>
        <NFormItem label="Tags" path="tags">
          <NInput v-model:value="modalForm.tags" clearable placeholder="请输入Tags" />
        </NFormItem>
      </NForm>
    </CrudModal>

    <NDrawer v-model:show="docsVisible" :width="720">
      <NDrawerContent title="API文档" closable>
        <NSpace vertical size="large">
          <div class="api-doc-url">
            <span>{{ apiDocsUrl }}</span>
            <NButton size="small" type="primary" @click="handleCopyDocsUrl(apiDocsUrl)">
              复制文档地址
            </NButton>
          </div>
          <div class="api-doc-url">
            <span>{{ openApiDocsUrl }}</span>
            <NButton size="small" @click="handleCopyDocsUrl(openApiDocsUrl)">
              复制OpenAPI地址
            </NButton>
          </div>
          <div v-if="docsLoading" class="api-doc-empty">加载中...</div>
          <div v-else-if="!apiDocs.items?.length" class="api-doc-empty">暂无API文档</div>
          <div v-else class="api-doc-list">
            <div v-for="item in apiDocs.items" :key="`${item.method}-${item.path}`" class="api-doc-item">
              <div class="api-doc-main">
                <NTag size="small" :type="item.auth_required ? 'warning' : 'success'">
                  {{ item.method }}
                </NTag>
                <span class="api-doc-path">{{ item.path }}</span>
              </div>
              <div class="api-doc-meta">
                <span>{{ item.summary || '暂无简介' }}</span>
                <span>{{ item.tags?.join(' / ') }}</span>
              </div>
            </div>
          </div>
        </NSpace>
      </NDrawerContent>
    </NDrawer>
  </CommonPage>
</template>

<style scoped>
.api-doc-url {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  background: #f6f7f9;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
}

.api-doc-url span {
  min-width: 0;
  overflow: hidden;
  color: #374151;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.api-doc-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.api-doc-item {
  padding: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
}

.api-doc-main,
.api-doc-meta {
  display: flex;
  align-items: center;
  gap: 10px;
}

.api-doc-main {
  min-width: 0;
}

.api-doc-path {
  overflow-wrap: anywhere;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}

.api-doc-meta {
  justify-content: space-between;
  margin-top: 8px;
  color: #6b7280;
  font-size: 13px;
}

.api-doc-empty {
  padding: 24px 0;
  color: #6b7280;
  text-align: center;
}
</style>
