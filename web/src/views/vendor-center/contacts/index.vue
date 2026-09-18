<template>
  <AppPage :show-footer="false">
    <div class="contacts-page">
      <section class="contacts-panel">
        <div class="panel-head">
          <div>
            <span class="eyebrow">VENDOR CENTER</span>
            <h2>供应商联系人</h2>
          </div>
          <NSpace>
            <NButton secondary circle :loading="loading" title="刷新" @click="load"
              ><template #icon><TheIcon icon="mdi:refresh" :size="18" /></template
            ></NButton>
            <NButton type="primary" @click="openEditor()"
              ><template #icon
                ><TheIcon icon="mdi:card-account-phone-outline" :size="18" /></template
              >新增联系人</NButton
            >
          </NSpace>
        </div>
        <div class="filters">
          <NInput
            v-model:value="query.keyword"
            clearable
            placeholder="搜索联系人 / 邮箱 / 电话"
            @keyup.enter="search"
          />
          <NSelect
            v-model:value="query.vendor_id"
            clearable
            filterable
            :options="vendorOptions"
            placeholder="所属供应商"
          />
          <NSelect v-model:value="query.role" clearable :options="roles" placeholder="联系人角色" />
          <NButton secondary @click="resetFilters">重置</NButton
          ><NButton type="primary" @click="search">搜索</NButton>
        </div>
        <NAlert v-if="error" type="error" class="error">{{ error }}</NAlert>
        <div class="table-wrap">
          <NDataTable
            striped
            flex-height
            :loading="loading"
            :columns="columns"
            :data="pageRows"
            :row-key="(row) => row.id"
            :scroll-x="scrollX"
            :scrollbar-props="{ trigger: 'none' }"
            :pagination="false"
          >
            <template #empty><NEmpty description="暂无供应商联系人" /></template>
          </NDataTable>
        </div>
        <div class="pagination">
          <span>共 {{ rows.length }} 条</span>
          <NPagination
            v-model:page="page"
            v-model:page-size="pageSize"
            :item-count="rows.length"
            :page-sizes="[20, 50, 100]"
            show-size-picker
            @update:page-size="page = 1"
          />
        </div>
      </section>
    </div>
    <ContactEditorModal
      v-model:show="visible"
      :form="form"
      :loading="saving"
      :owners="vendorOptions"
      :roles="roles"
      :types="types"
      owner-label="所属供应商"
      owner-field="vendor_ids"
      role-field="roles"
      @save="save"
    />
    <NModal
      v-model:show="deleteVisible"
      preset="card"
      title="删除供应商联系人"
      style="width: min(480px, calc(100vw - 32px))"
      :mask-closable="false"
      :closable="!saving"
      :close-on-esc="!saving"
    >
      <p>
        确认删除「{{ deleting?.name || deleting?.email }}」？此联系人与「{{
          deleting?.vendor_name
        }}」的关联将一并删除。
      </p>
      <template #footer
        ><div class="footer">
          <CButton
            show-cancel
            show-delete
            :disabled="saving"
            :delete-loading="saving"
            @cancel="deleteVisible = false"
            @delete="remove"
          /></div
      ></template>
    </NModal>
  </AppPage>
</template>

<script setup>
import { computed, h, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { NButton, NSpace, NTag } from 'naive-ui'
import AppPage from '@/components/page/AppPage.vue'
import CButton from '@/components/public/CButton.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import ContactEditorModal from '@/components/business/ContactEditorModal.vue'
import api from '@/api'

const route = useRoute()
const vendors = ref([])
const contacts = ref([])
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const query = reactive({ keyword: '', vendor_id: null, role: null })
const applied = reactive({ ...query })
const page = ref(1)
const pageSize = ref(20)
const visible = ref(false)
const deleteVisible = ref(false)
const deleting = ref(null)
const emptyForm = () => ({
  id: null,
  vendor_ids: [],
  contact_type: 'person',
  roles: ['business'],
  name: '',
  email: '',
  phone: '',
  address: '',
  remark: '',
})
const form = reactive(emptyForm())
const roles = [
  { label: '商务联系人', value: 'business' },
  { label: '采购联系人', value: 'procurement' },
  { label: '技术联系人', value: 'technical' },
  { label: '财务联系人', value: 'finance' },
  { label: '运维联系人', value: 'ops' },
  { label: '紧急联系人', value: 'emergency' },
]
const types = [
  { label: '个人', value: 'person' },
  { label: '组邮箱', value: 'group' },
]
const vendorOptions = computed(() =>
  vendors.value.map((vendor) => ({ label: vendor.name, value: vendor.id }))
)
const rows = computed(() =>
  contacts.value.filter(
    (row) =>
      (!applied.vendor_id || row.vendor_ids.includes(applied.vendor_id)) &&
      (!applied.role || row.roles.includes(applied.role)) &&
      [row.name, row.email, row.phone, row.vendor_name, row.remark]
        .join(' ')
        .toLowerCase()
        .includes(applied.keyword.trim().toLowerCase())
  )
)
const pageRows = computed(() =>
  rows.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value)
)
const columns = [
  {
    title: '联系人',
    key: 'name',
    width: 150,
    fixed: 'left',
    ellipsis: { tooltip: true },
    render: (row) => row.name || row.email,
  },
  {
    title: '类型',
    key: 'contact_type',
    width: 100,
    render: (row) =>
      h(
        NTag,
        { size: 'small', round: true, type: row.contact_type === 'group' ? 'warning' : 'default' },
        () => (row.contact_type === 'group' ? '组邮箱' : '个人联系人')
      ),
  },
  { title: '所属供应商', key: 'vendor_name', width: 220, ellipsis: { tooltip: true } },
  {
    title: '角色',
    key: 'roles',
    width: 160,
    render: (row) =>
      h(NSpace, { size: 4 }, () =>
        row.roles.map((role) =>
          h(
            NTag,
            {
              size: 'small',
              round: true,
              type:
                { business: 'info', finance: 'warning', noc: 'success', emergency: 'error' }[
                  role
                ] || 'default',
            },
            () => roles.find((item) => item.value === role)?.label || role
          )
        )
      ),
  },
  {
    title: '邮箱',
    key: 'email',
    width: 190,
    ellipsis: { tooltip: true },
    render: (row) => row.email || '-',
  },
  {
    title: '电话',
    key: 'phone',
    width: 140,
    ellipsis: { tooltip: true },
    render: (row) => row.phone || '-',
  },
  {
    title: '操作',
    key: 'actions',
    fixed: 'right',
    width: 92,
    render: (row) =>
      h(NSpace, { size: 6, wrap: false }, () => [
        h(
          NButton,
          {
            circle: true,
            secondary: true,
            size: 'small',
            type: 'info',
            title: '编辑',
            onClick: () => openEditor(row),
          },
          { icon: () => h(TheIcon, { icon: 'mdi:pencil', size: 15 }) }
        ),
        h(
          NButton,
          {
            circle: true,
            secondary: true,
            size: 'small',
            type: 'error',
            title: '删除',
            onClick: () => {
              deleting.value = row
              deleteVisible.value = true
            },
          },
          { icon: () => h(TheIcon, { icon: 'mdi:trash-can-outline', size: 15 }) }
        ),
      ]),
  },
].map((column) =>
  column.key === 'actions' ? column : { ...column, resizable: true, minWidth: 80 }
)
const scrollX = columns.reduce((sum, column) => sum + column.width, 0)
async function load() {
  if (loading.value) return
  loading.value = true
  error.value = ''
  try {
    const [vendorResponse, contactResponse] = await Promise.all([
      api.getVendorList({ page: 1, page_size: 9999 }),
      api.vendorContactApi.list(),
    ])
    vendors.value = vendorResponse.data || []
    contacts.value = contactResponse.data || []
    page.value = Math.min(page.value, Math.max(1, Math.ceil(rows.value.length / pageSize.value)))
  } catch {
    error.value = '加载供应商联系人失败，请点击刷新重试'
  } finally {
    loading.value = false
  }
}
function search() {
  Object.assign(applied, query)
  page.value = 1
}
function resetFilters() {
  Object.assign(query, { keyword: '', vendor_id: null, role: null })
  search()
}
function openEditor(row) {
  Object.assign(
    form,
    emptyForm(),
    row
      ? {
          id: row.id,
          vendor_ids: [...row.vendor_ids],
          contact_type: row.contact_type,
          roles: [...row.roles],
          name: row.name,
          email: row.email,
          phone: row.phone,
          address: row.address,
          remark: row.remark,
        }
      : {
          vendor_ids: query.vendor_id ? [query.vendor_id] : [],
          roles: query.role ? [query.role] : ['business'],
        }
  )
  visible.value = true
}
async function save() {
  if (saving.value) return
  saving.value = true
  try {
    const { id, ...payload } = form
    if (id) await api.vendorContactApi.update({ ...payload, id })
    else await api.vendorContactApi.create(payload)
    visible.value = false
    window.$message?.success('联系人已保存')
    await load()
  } catch (e) {
    window.$message?.error(e?.message || '保存失败，请重试')
  } finally {
    saving.value = false
  }
}
async function remove() {
  if (saving.value || !deleting.value) return
  saving.value = true
  try {
    await api.vendorContactApi.delete(deleting.value.id)
    deleteVisible.value = false
    window.$message?.success('联系人已删除')
    await load()
  } catch (e) {
    window.$message?.error(e?.message || '删除失败，请重试')
  } finally {
    saving.value = false
  }
}
watch(
  () => route.query.vendor_id,
  (value) => {
    query.vendor_id = Number(value) || null
    search()
  },
  { immediate: true }
)
onMounted(load)
</script>

<style scoped>
:deep(.app-page-shell) {
  overflow: hidden;
}
.contacts-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}
.contacts-panel {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
  padding: 18px;
  border: 1px solid #e7edf4;
  border-radius: 8px;
  background: #fff;
}
.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 16px;
}
.eyebrow {
  color: #607089;
  font-size: 12px;
  font-weight: 700;
}
h2 {
  margin: 4px 0 0;
  color: #0f172a;
  font-size: 22px;
}
.filters {
  display: grid;
  grid-template-columns: minmax(180px, 1fr) minmax(180px, 1fr) minmax(150px, 1fr) 78px 78px;
  gap: 10px;
  margin: 16px 0;
}
.table-wrap {
  display: flex;
  flex: 1;
  min-height: 260px;
  overflow: hidden;
}
.table-wrap :deep(.n-data-table) {
  width: 100%;
  height: 100%;
}
.pagination {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-top: 14px;
}
.error {
  margin-bottom: 16px;
}
.footer {
  display: flex;
  justify-content: flex-end;
}
@media (max-width: 1000px) {
  .filters {
    grid-template-columns: 1fr 1fr;
  }
}
@media (max-width: 720px) {
  .contacts-panel {
    padding: 12px;
  }
  .pagination {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
