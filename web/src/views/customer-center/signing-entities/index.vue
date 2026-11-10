<template>
  <AppPage>
    <div class="entity-page">
      <div class="toolbar">
        <div>
          <h2>主体管理</h2>
          <p>维护客户签约主体及账单展示资料。停用后不再出现在新建业务的主体选项中。</p>
        </div>
        <CButton
          v-if="can('post')"
          show-save
          save-text="新增主体"
          :disabled="busy"
          @save="edit()"
        />
      </div>
      <div class="filters">
        <n-input v-model:value="keyword" clearable placeholder="搜索名称、编号" />
        <CButton show-save save-text="刷新" :disabled="busy" @save="load" />
      </div>
      <n-alert v-if="error" type="error">{{ error }}</n-alert>
      <n-data-table
        :columns="columns"
        :data="filtered"
        :loading="loading"
        :scroll-x="1390"
        :row-key="(row) => row.id"
      />
    </div>
    <n-modal
      v-model:show="modal.show"
      preset="card"
      :title="modal.id ? '编辑主体' : '新增主体'"
      style="width: min(760px, calc(100vw - 24px))"
      :closable="!saving"
      :mask-closable="!saving"
      :close-on-esc="!saving"
    >
      <n-form ref="formRef" :model="form" :rules="rules" label-placement="top" :disabled="saving">
        <div class="form-grid">
          <n-form-item
            v-for="field in fields"
            :key="field.key"
            :label="field.label"
            :path="field.key"
            :class="{ wide: field.wide }"
          >
            <n-input
              v-model:value="form[field.key]"
              :maxlength="field.max"
              :type="field.key === 'remark' ? 'textarea' : 'text'"
              :placeholder="field.placeholder || `请输入${field.label}`"
            />
          </n-form-item>
          <n-form-item label="启用"><n-switch v-model:value="form.status" /></n-form-item>
          <div v-if="safeLogo" class="logo-preview">
            <img
              :key="safeLogo"
              :src="safeLogo"
              alt="主体 Logo 预览"
              @error="logoFailed = true"
            /><span v-if="logoFailed">Logo 无法加载，请检查地址</span>
          </div>
        </div>
        <p class="hint">
          Logo 可填写站内路径（如 /logos/catixs.png、/logos/77-telecom.png）或 HTTPS
          图片地址。账单按关联主体显示 Logo。
        </p>
      </n-form>
      <template #footer
        ><CButton
          show-save
          show-cancel
          :save-loading="saving"
          :disabled="saving"
          @save="save"
          @cancel="modal.show = false"
      /></template>
    </n-modal>
  </AppPage>
</template>

<script setup>
import { computed, h, onMounted, reactive, ref, watch } from 'vue'
import { NButton, NImage, NSpace, NTag, NTooltip } from 'naive-ui'
import api from '@/api'
import CButton from '@/components/public/CButton.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import { usePermissionStore, useUserStore } from '@/store'

const user = useUserStore()
const permissions = usePermissionStore()
const service = api.customerCenterApi
const rows = ref([])
const keyword = ref('')
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const busy = computed(() => loading.value || saving.value)
const modal = reactive({ show: false, id: null })
const form = reactive({})
const formRef = ref(null)
const logoFailed = ref(false)
const failedLogos = ref(new Set())
const fields = [
  { key: 'name', label: '主体名称', max: 120 },
  { key: 'legal_name', label: '主体全称', max: 200 },
  { key: 'code', label: '主体编号', max: 50 },
  { key: 'country', label: '国家 / 地区', max: 80 },
  { key: 'address', label: '注册地址', max: 255, wide: true },
  { key: 'tax_no', label: '税号', max: 80 },
  { key: 'registration_no', label: '注册号', max: 80 },
  { key: 'logo_url', label: 'Logo 地址', max: 255, wide: true },
  { key: 'remark', label: '备注', max: 500, wide: true },
]
const rules = { name: { required: true, message: '请输入主体名称', trigger: ['input', 'blur'] } }
const safeLogo = computed(() => {
  const value = form.logo_url?.trim()
  return value && /^(https?:\/\/|\/(?!\/))/.test(value) && !value.includes('\\') ? value : ''
})
watch(safeLogo, () => {
  logoFailed.value = false
})
const filtered = computed(() =>
  rows.value.filter((row) =>
    `${row.name} ${row.legal_name || ''} ${row.code || ''}`
      .toLowerCase()
      .includes(keyword.value.trim().toLowerCase())
  )
)
function can(method) {
  const path = `/api/v1/customer-center/signing-entities${method === 'put' ? '/{entity_id}' : ''}`
  return user.isSuperUser || permissions.apis.includes(`${method}/${path}`)
}
async function load() {
  failedLogos.value.clear()
  loading.value = true
  error.value = ''
  try {
    rows.value = (await service.signingEntities({ include_inactive: true })).data || []
  } catch (e) {
    error.value = e.message || '主体加载失败，请重试'
  } finally {
    loading.value = false
  }
}
function edit(row) {
  modal.id = row?.id || null
  for (const field of fields) form[field.key] = row?.[field.key] || ''
  form.status = row?.status ?? true
  logoFailed.value = false
  modal.show = true
}
async function save() {
  if (saving.value) return
  form.name = form.name.trim()
  try {
    await formRef.value.validate()
  } catch {
    return
  }
  saving.value = true
  try {
    const payload = { ...form }
    if (modal.id) await service.updateSigningEntity(modal.id, payload)
    else await service.createSigningEntity(payload)
    modal.show = false
    window.$message?.success('主体已保存')
    await load()
  } catch {
    /* 请求封装展示错误，保留表单以便重试。 */
  } finally {
    saving.value = false
  }
}
const columns = [
  { title: '主体名称', key: 'name', width: 190 },
  { title: '主体全称', key: 'legal_name', width: 220 },
  { title: '编号', key: 'code', width: 150 },
  { title: '国家 / 地区', key: 'country', width: 140 },
  { title: '注册地址', key: 'address', width: 300 },
  {
    title: '状态',
    key: 'status',
    width: 100,
    render: (row) =>
      h(
        NTag,
        { type: row.status ? 'success' : 'default' },
        { default: () => (row.status ? '启用' : '停用') }
      ),
  },
  {
    title: 'Logo',
    key: 'logo_url',
    width: 210,
    render: (row) => {
      if (!row.logo_url) return '—'
      if (failedLogos.value.has(row.logo_url)) return '加载失败'
      return h(
        'div',
        { onClick: (event) => event.stopPropagation() },
        h(NImage, {
          key: row.logo_url,
          src: row.logo_url,
          alt: `${row.name} Logo`,
          width: 140,
          height: 44,
          objectFit: 'contain',
          imgProps: { style: { background: '#fff', padding: '4px', borderRadius: '4px' } },
          onError: () => failedLogos.value.add(row.logo_url),
        })
      )
    },
  },
].map((col) => ({
  ...col,
  resizable: true,
  ellipsis: col.key === 'logo_url' ? false : { tooltip: true },
}))
columns.push({
  title: '操作',
  key: 'actions',
  width: 80,
  fixed: 'right',
  render: (row) =>
    h(
      NSpace,
      { wrap: false },
      {
        default: () =>
          can('put')
            ? h(NTooltip, null, {
                trigger: () =>
                  h(
                    NButton,
                    {
                      size: 'small',
                      circle: true,
                      quaternary: true,
                      disabled: busy.value,
                      'aria-label': '编辑',
                      onClick: (event) => {
                        event.stopPropagation()
                        edit(row)
                      },
                    },
                    { icon: () => h(TheIcon, { icon: 'mdi:pencil-outline', size: 17 }) }
                  ),
                default: () => '编辑',
              })
            : null,
      }
    ),
})
onMounted(load)
</script>

<style scoped>
.entity-page {
  padding: 16px;
}
.toolbar {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  flex-wrap: wrap;
}
.toolbar p,
.hint {
  color: #888;
}
.filters {
  display: flex;
  gap: 12px;
  margin: 16px 0;
  max-width: 500px;
}
.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 20px;
}
.wide {
  grid-column: 1 / -1;
}
.logo-preview img {
  max-width: 180px;
  max-height: 70px;
  object-fit: contain;
}
@media (max-width: 600px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
