<template>
  <AppPage :show-footer="false">
    <section class="contacts-panel">
      <div class="panel-head">
        <div>
          <span class="eyebrow">VENDOR CENTER</span>
          <h2>供应商联系人</h2>
        </div>
        <NSpace>
          <NButton secondary :loading="loading" @click="load">刷新</NButton>
          <NButton type="primary" @click="openEditor()">新增联系人</NButton>
        </NSpace>
      </div>
      <div class="filters">
        <NInput v-model:value="keyword" clearable placeholder="搜索供应商、编号或联系信息" />
        <NSelect
          v-model:value="vendorId"
          clearable
          filterable
          :options="vendorOptions"
          placeholder="供应商"
        />
        <NSelect v-model:value="contactRole" clearable :options="roles" placeholder="联系人角色" />
        <NButton @click="resetFilters">重置</NButton>
      </div>
      <NAlert v-if="error" type="error" class="error">{{ error }}</NAlert>
      <NDataTable
        striped
        :loading="loading"
        :columns="columns"
        :data="rows"
        :row-key="(row) => row.key"
        :scroll-x="1300"
        :scrollbar-props="{ trigger: 'none' }"
        :pagination="{ pageSize: 20, showSizePicker: true, pageSizes: [20, 50, 100] }"
      >
        <template #empty><NEmpty description="暂无供应商联系人" /></template>
      </NDataTable>
      <p class="hint">
        共 {{ rows.length }} 条联系信息，按供应商及公司、销售、账单、NOC 角色维护。
      </p>
    </section>

    <NModal
      v-model:show="visible"
      preset="card"
      :title="editing ? '编辑供应商联系人' : '新增供应商联系人'"
      class="contact-modal"
      :mask-closable="false"
      :closable="!saving"
      :close-on-esc="!saving"
    >
      <NForm ref="formRef" :model="form" :rules="rules" label-placement="top" :disabled="saving">
        <NFormItem label="供应商" path="vendor_id">
          <NSelect
            v-model:value="form.vendor_id"
            filterable
            :disabled="editing || saving"
            :options="vendorOptions"
            placeholder="请选择供应商"
            @update:value="fillContent"
          />
        </NFormItem>
        <NFormItem label="联系人角色" path="role">
          <NSelect
            v-model:value="form.role"
            :disabled="editing || saving"
            :options="roles"
            @update:value="fillContent"
          />
        </NFormItem>
        <template v-if="form.role === 'company_contact'">
          <NFormItem label="公司邮箱" path="company_email">
            <NInput
              v-model:value="form.company_email"
              :maxlength="100"
              clearable
              placeholder="请输入公司邮箱"
            />
          </NFormItem>
          <NFormItem label="公司电话" path="company_phone">
            <NInput
              v-model:value="form.company_phone"
              :maxlength="50"
              clearable
              placeholder="请输入公司电话"
            />
          </NFormItem>
        </template>
        <template v-if="form.role === 'noc_contact'">
          <NFormItem label="NOC 邮箱" path="noc_email">
            <NInput
              v-model:value="form.noc_email"
              :maxlength="100"
              clearable
              placeholder="请输入 NOC 邮箱"
            />
          </NFormItem>
          <NFormItem label="NOC 电话" path="noc_phone">
            <NInput
              v-model:value="form.noc_phone"
              :maxlength="50"
              clearable
              placeholder="请输入 NOC 电话"
            />
          </NFormItem>
        </template>
        <NFormItem v-if="form.role !== 'company_contact'" label="联系信息" path="content">
          <NInput
            v-model:value="form.content"
            type="textarea"
            :maxlength="10000"
            :autosize="{ minRows: 6, maxRows: 14 }"
            placeholder="填写姓名、邮箱、电话、服务说明或链接，多位联系人可分行填写"
          />
        </NFormItem>
        <p class="hint">与供应商档案中的对应联系信息同步；选择已有供应商和角色时会带出当前内容。</p>
      </NForm>
      <template #footer
        ><div class="footer">
          <CButton
            show-cancel
            show-save
            :disabled="saving"
            :save-loading="saving"
            @cancel="visible = false"
            @save="save"
          /></div
      ></template>
    </NModal>
    <NModal
      v-model:show="deleteVisible"
      preset="card"
      title="删除供应商联系信息"
      class="contact-modal"
      :mask-closable="false"
      :closable="!saving"
      :close-on-esc="!saving"
    >
      <p>
        确认清除「{{ deleting?.name }}」的{{
          deleting?.roleLabel
        }}信息？供应商档案中的对应联系信息也会清除。
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
import { computed, h, onMounted, reactive, ref } from 'vue'
import { NButton, NSpace, NTag } from 'naive-ui'
import AppPage from '@/components/page/AppPage.vue'
import CButton from '@/components/public/CButton.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import api from '@/api'

const vendors = ref([])
const entities = ref([])
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const keyword = ref('')
const vendorId = ref(null)
const contactRole = ref(null)
const visible = ref(false)
const editing = ref(false)
const deleteVisible = ref(false)
const deleting = ref(null)
const formRef = ref(null)
const form = reactive({
  vendor_id: null,
  role: 'sales_contact',
  content: '',
  company_email: '',
  company_phone: '',
  noc_email: '',
  noc_phone: '',
})
const roles = [
  { label: '公司联系信息', value: 'company_contact' },
  { label: '销售联系人', value: 'sales_contact' },
  { label: '账单联系人', value: 'billing_contact' },
  { label: 'NOC 联系人', value: 'noc_contact' },
]
const rules = {
  noc_email: [
    {
      validator: (_rule, value) =>
        !value?.trim() || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim()),
      message: '邮箱格式错误',
      trigger: 'blur',
    },
  ],
  vendor_id: [{ required: true, type: 'number', message: '请选择供应商', trigger: 'change' }],
  company_email: [
    {
      validator: (_rule, value) =>
        !value?.trim() || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim()),
      message: '邮箱格式错误',
      trigger: 'blur',
    },
  ],
  content: [
    {
      required: true,
      validator: (_rule, value) =>
        Boolean(
          value?.trim() ||
            (form.role === 'noc_contact' && (form.noc_email.trim() || form.noc_phone.trim()))
        ),
      message: '请填写联系信息',
      trigger: 'blur',
    },
  ],
}
const vendorOptions = computed(() =>
  vendors.value.map((vendor) => ({
    label: `${vendor.name} (${vendor.code || '-'})`,
    value: vendor.id,
  }))
)
function contactContent(vendor, role) {
  if (!vendor) return ''
  if (role === 'company_contact')
    return [vendor.company_email, vendor.company_phone].filter(Boolean).join('\n')
  if (role === 'noc_contact')
    return [
      ...new Set([vendor.noc_contact, vendor.noc_email, vendor.noc_phone].filter(Boolean)),
    ].join('\n')
  return (
    vendor[role] ||
    (role === 'noc_contact' ? [vendor.noc_email, vendor.noc_phone].filter(Boolean).join('\n') : '')
  )
}
const rows = computed(() =>
  vendors.value
    .flatMap((vendor) =>
      roles.map((role) => ({
        ...vendor,
        key: `${vendor.id}-${role.value}`,
        role: role.value,
        roleLabel: role.label,
        content: contactContent(vendor, role.value),
      }))
    )
    .filter(
      (row) =>
        row.content.trim() &&
        (vendorId.value === null || row.id === vendorId.value) &&
        (contactRole.value === null || row.role === contactRole.value) &&
        `${row.name} ${row.code} ${row.content}`
          .toLowerCase()
          .includes(keyword.value.trim().toLowerCase())
    )
)
const columns = [
  { title: '供应商编号', key: 'code', width: 130 },
  { title: '供应商名称', key: 'name', width: 240 },
  {
    title: '签约主体',
    key: 'signing_entity_id',
    width: 180,
    render: (row) => {
      const name =
        row.signing_entity_name ||
        entities.value.find((entity) => entity.id === row.signing_entity_id)?.name ||
        '-'
      return h(
        NTag,
        {
          size: 'small',
          type: name.includes('科特思') ? 'success' : name.includes('77') ? 'warning' : 'info',
        },
        () => name
      )
    },
  },
  { title: '联系人角色', key: 'roleLabel', width: 150 },
  {
    title: '联系信息',
    key: 'content',
    width: 500,
    render: (row) => h('div', { class: 'contact-content' }, row.content),
  },
  {
    title: '操作',
    key: 'actions',
    fixed: 'right',
    width: 100,
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
  column.key === 'actions' ? column : { ...column, resizable: true, minWidth: 90 }
)
async function load() {
  if (loading.value) return
  loading.value = true
  error.value = ''
  try {
    const [vendorResponse, entityResponse] = await Promise.all([
      api.getVendorList({ page: 1, page_size: 9999 }),
      api.customerCenterApi.signingEntities(),
    ])
    vendors.value = vendorResponse.data || []
    entities.value = entityResponse.data || []
  } catch {
    error.value = '加载供应商联系人失败，请点击刷新重试'
  } finally {
    loading.value = false
  }
}
function resetFilters() {
  keyword.value = ''
  vendorId.value = null
  contactRole.value = null
}
function fillContent() {
  const vendor = vendors.value.find((vendor) => vendor.id === form.vendor_id)
  form.company_email = vendor?.company_email || ''
  form.company_phone = vendor?.company_phone || ''
  form.noc_email = vendor?.noc_email || ''
  form.noc_phone = vendor?.noc_phone || ''
  form.content = vendor?.[form.role] || ''
}
function openEditor(row) {
  editing.value = Boolean(row)
  Object.assign(form, {
    vendor_id: row?.id || vendorId.value,
    role: row?.role || contactRole.value || 'sales_contact',
    content: row?.[row.role] || '',
    company_email: row?.company_email || '',
    company_phone: row?.company_phone || '',
    noc_email: row?.noc_email || '',
    noc_phone: row?.noc_phone || '',
  })
  if (!row) fillContent()
  visible.value = true
}
async function updateContact(id, role, content, companyDetails = {}) {
  const response = await api.getVendorById({ vendor_id: id })
  const payload = { id, name: response.data.name, [role]: content }
  if (role === 'company_contact') {
    delete payload.company_contact
    Object.assign(payload, {
      company_email: companyDetails.company_email?.trim() || '',
      company_phone: companyDetails.company_phone?.trim() || '',
    })
  }
  if (role === 'noc_contact')
    Object.assign(payload, {
      noc_email: companyDetails.noc_email?.trim() || '',
      noc_phone: companyDetails.noc_phone?.trim() || '',
    })
  await api.updateVendor(payload)
}
async function save() {
  if (saving.value) return
  if (form.role === 'company_contact' && !form.company_email.trim() && !form.company_phone.trim()) {
    window.$message?.error('请填写公司邮箱或电话')
    return
  }
  try {
    await formRef.value?.validate()
  } catch {
    return
  }
  saving.value = true
  try {
    await updateContact(form.vendor_id, form.role, form.content.trim(), form)
    visible.value = false
    window.$message?.success('联系信息已保存')
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
    await updateContact(deleting.value.id, deleting.value.role, '')
    deleteVisible.value = false
    window.$message?.success('联系信息已删除')
    await load()
  } catch (e) {
    window.$message?.error(e?.message || '删除失败，请重试')
  } finally {
    saving.value = false
  }
}
onMounted(load)
</script>

<style scoped>
.contacts-panel {
  padding: 24px;
  border-radius: 16px;
  background: var(--n-color, #fff);
}
.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 20px;
}
.eyebrow {
  color: #718096;
  font-size: 11px;
  letter-spacing: 2px;
}
h2 {
  margin: 4px 0 0;
  font-size: 22px;
}
.filters {
  display: grid;
  grid-template-columns: minmax(200px, 2fr) minmax(180px, 1fr) 160px auto;
  gap: 12px;
  margin-bottom: 20px;
}
.hint {
  color: #718096;
  font-size: 12px;
}
.error {
  margin-bottom: 16px;
}
.footer {
  display: flex;
  justify-content: flex-end;
}
.contact-modal {
  width: min(680px, calc(100vw - 32px));
}
:deep(.contact-content) {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  max-height: 180px;
  overflow-y: auto;
}
@media (max-width: 760px) {
  .contacts-panel {
    padding: 12px;
  }
  .filters {
    grid-template-columns: 1fr;
  }
}
</style>
