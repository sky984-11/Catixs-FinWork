<template>
  <n-card :title="mode === 'hosts' ? '监控主机' : '分类管理'">
    <template #header-extra
      ><n-space>
        <CButton
          show-save
          save-text="刷新"
          :disabled="busy || hostDialog || categoryDialog"
          @save="reload"
        />
        <CButton
          v-if="canEdit"
          show-save
          :save-text="mode === 'hosts' ? '纳管主机' : '新增分类'"
          :disabled="busy || !ready"
          @save="mode === 'hosts' ? openHost() : openCategory()"
        /> </n-space
    ></template>
    <n-alert type="info" class="gap">{{
      mode === 'hosts'
        ? '按需纳管主机及监控项。指定监控项时，仅纳入引用所选监控项的触发器告警；选择全部时包含后续新增监控项。'
        : '分类由 FinWork 独立维护。新增、重命名和删除不会修改 Zabbix 标签；被主机使用的分类须先解除关联才能删除。'
    }}</n-alert>
    <n-alert v-if="error" type="error" class="gap">{{ error }}</n-alert>
    <n-alert v-if="form.tags_warning" type="warning" class="gap">{{ form.tags_warning }}</n-alert>
    <n-input
      v-model:value="filter"
      :placeholder="mode === 'hosts' ? '搜索主机、分类' : '搜索分类名称'"
      clearable
      class="gap"
    />
    <p class="muted">
      {{
        mode === 'hosts'
          ? `已纳管 ${form.hosts.length} 台主机`
          : `共 ${form.categories.length} 个分类，${
              form.hosts.filter((h) => !h.category).length
            } 台主机未分类`
      }}
    </p>
    <n-data-table
      :columns="mode === 'hosts' ? hostColumns : categoryColumns"
      :data="visibleRows"
      :row-key="(row) => (mode === 'hosts' ? row.hostid : row.key)"
      :loading="loading"
      :scroll-x="mode === 'hosts' ? 1510 : 1110"
      :max-height="tableHeight"
      striped
      size="small"
    />
  </n-card>
  <n-modal
    v-model:show="hostDialog"
    preset="card"
    :title="editingHost ? '调整纳管范围' : '纳管主机'"
    style="width: min(1100px, calc(100vw - 24px))"
    :closable="!busy"
    :mask-closable="!busy"
    :close-on-esc="!busy"
  >
    <div class="dialog-body">
      <n-alert v-if="dialogError" type="error" class="gap">{{ dialogError }}</n-alert>
      <template v-if="!editingHost">
        <n-space class="gap" align="center">
          <n-select
            v-model:value="groupId"
            :options="groups.map((g) => ({ label: g.name, value: g.groupid }))"
            filterable
            placeholder="选择 Zabbix 主机组"
            :disabled="busy"
            style="width: 280px"
            @update:value="changeGroup"
          />
          <n-input
            v-model:value="hostKeyword"
            placeholder="组内主机名称筛选（可选）"
            :disabled="busy || !groupId"
            style="width: 300px"
            @keyup.enter="searchHosts"
          />
          <CButton
            show-save
            save-text="搜索主机"
            :disabled="busy || !groupId"
            @save="searchHosts"
          />
        </n-space>
        <n-alert v-if="hostsTruncated" type="warning" class="gap"
          >仅显示前 100 台，请按名称缩小范围。</n-alert
        >
        <n-select
          v-model:value="draft.hostid"
          :options="
            candidates.map((h) => ({
              label: h.name,
              value: h.hostid,
              disabled: form.hosts.some((saved) => saved.hostid === h.hostid),
            }))
          "
          filterable
          placeholder="选择需要纳管的主机"
          :disabled="busy || !groupId"
          @update:value="changeHost"
        />
      </template>
      <h3 v-else>{{ draft.name }}</h3>
      <h3>平台分类</h3>
      <n-select
        v-model:value="draft.category"
        :options="categoryOptions"
        clearable
        filterable
        placeholder="未分类（可稍后分配）"
        :disabled="busy"
      />
      <h3 v-if="draftFields.length">分类属性</h3>
      <n-form-item v-for="field in draftFields" :key="field.key" :label="field.label">
        <n-input
          v-model:value="draft.attributes[field.key]"
          :disabled="busy"
          maxlength="300"
          :placeholder="`填写${field.label}`"
        />
      </n-form-item>
      <h3>监控项范围</h3>
      <n-radio-group
        v-model:value="draft.scope"
        :disabled="busy || !draft.hostid"
        @update:value="scopeChanged"
        ><n-space
          ><n-radio value="selected">指定监控项</n-radio
          ><n-radio value="all">全部监控项</n-radio></n-space
        ></n-radio-group
      >
      <template v-if="draft.scope === 'selected'">
        <n-space class="gap" align="center">
          <n-input
            v-model:value="itemKeyword"
            placeholder="搜索监控项名称或键值"
            :disabled="busy || !draft.hostid"
            style="width: 350px; max-width: 100%"
            @keyup.enter="loadItems"
          />
          <CButton
            show-save
            save-text="查询监控项"
            :disabled="busy || !draft.hostid"
            @save="loadItems"
          />
        </n-space>
        <n-alert v-if="itemsTruncated" type="warning" class="gap"
          >仅显示前 500 个监控项，可搜索后继续勾选，已选项会保留。</n-alert
        >
        <p>
          已选 {{ draft.itemids.length }} 项
          <span class="muted">至少选择一项；没有关联触发器的监控项不会产生事件。</span>
        </p>
        <n-data-table
          :columns="itemColumns"
          :data="items"
          :checked-row-keys="draft.itemids"
          :row-key="(row) => row.itemid"
          :scroll-x="850"
          :max-height="300"
          :loading="searching"
          size="small"
          @update:checked-row-keys="updateItems"
        />
        <n-space class="gap"
          ><n-tag
            v-for="id in draft.itemids"
            :key="id"
            closable
            :disabled="busy"
            @close="removeItem(id)"
            >{{ itemNames[id] || `监控项 ${id}` }}</n-tag
          ></n-space
        >
      </template>
    </div>
    <template #footer
      ><n-space justify="end"
        ><CButton show-cancel :disabled="busy" @cancel="hostDialog = false" /><CButton
          show-save
          save-text="保存纳管配置"
          :save-loading="saving"
          :disabled="busy || !draft.hostid"
          @save="saveHost" /></n-space
    ></template>
  </n-modal>
  <n-modal
    v-model:show="categoryDialog"
    preset="card"
    :title="categoryDraft.key ? '编辑分类' : '新增分类'"
    style="width: min(480px, calc(100vw - 24px))"
    :closable="!busy"
    :mask-closable="!busy"
    :close-on-esc="!busy"
  >
    <n-alert v-if="dialogError" type="error" class="gap">{{ dialogError }}</n-alert>
    <n-form-item label="分类名称" required
      ><n-input
        v-model:value="categoryDraft.label"
        maxlength="40"
        show-count
        :disabled="busy"
        placeholder="例如：传输线路、网络设备、虚拟化平台"
    /></n-form-item>
    <h3>分类字段</h3>
    <p class="muted">键用于保存数据，名称用于展示。删除字段后保存会清除对应主机值。</p>
    <n-space v-for="(field, index) in categoryDraft.fields" :key="index" class="gap" :wrap="false">
      <n-input
        v-model:value="field.key"
        placeholder="键，例如 provider"
        :disabled="busy || field.locked"
        maxlength="40"
      />
      <n-input
        v-model:value="field.label"
        placeholder="名称，例如供应商"
        :disabled="busy"
        maxlength="40"
      />
      <CButton
        show-save
        save-text="移除"
        :disabled="busy"
        @save="categoryDraft.fields.splice(index, 1)"
      />
    </n-space>
    <CButton
      show-save
      save-text="添加字段"
      :disabled="busy || categoryDraft.fields.length >= 20"
      @save="categoryDraft.fields.push({ key: '', label: '' })"
    />
    <template #footer
      ><CButton
        show-save
        show-cancel
        :disabled="busy"
        :save-loading="saving"
        @save="saveCategory"
        @cancel="categoryDialog = false"
    /></template>
  </n-modal>
  <n-modal
    v-model:show="removal.show"
    preset="card"
    title="确认移除"
    style="width: min(480px, calc(100vw - 24px))"
    :closable="!busy"
    :mask-closable="!busy"
    :close-on-esc="!busy"
  >
    <p>
      {{
        removal.kind === 'host'
          ? '移除后将不再查询此主机的事件，不会删除 Zabbix 数据。'
          : '确认删除这个未关联主机的分类？'
      }}
    </p>
    <n-alert v-if="dialogError" type="error" class="gap">{{ dialogError }}</n-alert>
    <template #footer
      ><CButton
        show-save
        show-cancel
        :disabled="busy"
        :save-loading="saving"
        @save="remove"
        @cancel="removal.show = false"
    /></template>
  </n-modal>
</template>

<script setup>
import { computed, h, reactive, ref, onMounted } from 'vue'
import { useWindowSize } from '@vueuse/core'
import { NButton, NSpace, NTag, NTooltip } from 'naive-ui'
import CButton from '@/components/public/CButton.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import api from '@/api/monitor-events'
import { usePermissionStore, useUserStore } from '@/store'

const props = defineProps({ mode: { type: String, default: 'hosts' } })
const user = useUserStore(),
  permissions = usePermissionStore()
const canEdit = computed(
  () => user.isSuperUser || permissions.apis.includes('put/api/v1/monitor-events/settings')
)
const form = reactive({ revision: 0, categories: [], hosts: [] })
const loading = ref(false),
  searching = ref(false),
  saving = ref(false),
  ready = ref(false)
const busy = computed(() => loading.value || searching.value || saving.value)
const error = ref(''),
  dialogError = ref(''),
  filter = ref('')
const { height } = useWindowSize()
const tableHeight = computed(() => Math.max(240, height.value - 330))
const categoryOptions = computed(() =>
  form.categories.map((c) => ({ label: c.label, value: c.key }))
)
const categoryName = (key) => form.categories.find((c) => c.key === key)?.label || '未分类'
const visibleRows = computed(() =>
  (props.mode === 'hosts' ? form.hosts : form.categories).filter((row) =>
    (props.mode === 'hosts'
      ? `${row.name} ${categoryName(row.category)} ${Object.values(row.attributes || {}).join(' ')}`
      : row.label
    )
      .toLowerCase()
      .includes(filter.value.trim().toLowerCase())
  )
)
function action(label, icon, callback, disabled = false, danger = false) {
  return h(NTooltip, null, {
    trigger: () =>
      h(
        NButton,
        {
          size: 'small',
          circle: true,
          quaternary: true,
          type: danger ? 'error' : 'default',
          disabled: busy.value || !canEdit.value || disabled,
          'aria-label': label,
          onClick: (event) => {
            event.stopPropagation()
            if (!busy.value && canEdit.value && !disabled) callback()
          },
        },
        { icon: () => h(TheIcon, { icon, size: 17 }) }
      ),
    default: () => label,
  })
}
const businessColumns = (columns) =>
  columns.map((c) => ({ resizable: true, ellipsis: { tooltip: true }, ...c }))
function attributeCell(row) {
  const fields = form.categories.find((c) => c.key === row.category)?.fields || []
  const filled = fields.filter((field) => row.attributes?.[field.key])
  if (!filled.length) return h('span', { class: 'muted' }, fields.length ? '未填写' : '—')
  return h(
    'div',
    { class: 'host-attributes' },
    filled.map((field) =>
      h('div', { class: 'host-attribute', title: `${field.label}：${row.attributes[field.key]}` }, [
        h('span', { class: 'host-attribute-label' }, field.label),
        h('span', { class: 'host-attribute-value' }, row.attributes[field.key]),
      ])
    )
  )
}
const hostColumns = [
  ...businessColumns([
    { title: '主机名称', key: 'name', width: 500 },
    {
      title: '分类属性',
      key: 'attributes',
      width: 360,
      ellipsis: false,
      render: attributeCell,
    },
    {
      title: '平台分类',
      key: 'category',
      width: 220,
      render: (row) =>
        h(
          NTag,
          { size: 'small', bordered: false, type: row.category ? 'info' : 'default' },
          { default: () => categoryName(row.category) }
        ),
    },
    {
      title: '监控项范围',
      key: 'itemids',
      width: 300,
      render: (row) => (row.itemids == null ? '全部监控项' : `指定 ${row.itemids.length} 个监控项`),
    },
  ]),
  {
    title: '操作',
    key: 'actions',
    width: 130,
    fixed: 'right',
    render: (row) =>
      h(
        NSpace,
        { wrap: false },
        {
          default: () => [
            action('调整分类和监控项', 'mdi:pencil-outline', () => openHost(row)),
            action(
              '移除纳管',
              'mdi:delete-outline',
              () => confirmRemove('host', row.hostid),
              false,
              true
            ),
          ],
        }
      ),
  },
]
const categoryColumns = [
  ...businessColumns([
    { title: '分类名称', key: 'label', width: 240 },
    {
      title: '自定义字段',
      key: 'fields',
      width: 260,
      render: (row) => (row.fields || []).map((f) => f.label).join(' / ') || '—',
    },
    {
      title: '关联主机数',
      key: 'count',
      width: 130,
      render: (row) => form.hosts.filter((h) => h.category === row.key).length,
    },
    {
      title: '关联主机',
      key: 'hosts',
      width: 350,
      render: (row) =>
        form.hosts
          .filter((h) => h.category === row.key)
          .map((h) => h.name)
          .join(' / ') || '—',
    },
  ]),
  {
    title: '操作',
    key: 'actions',
    width: 130,
    fixed: 'right',
    render: (row) =>
      h(
        NSpace,
        { wrap: false },
        {
          default: () => [
            action('编辑分类', 'mdi:pencil-outline', () => openCategory(row)),
            action(
              form.hosts.some((h) => h.category === row.key)
                ? '请先调整关联主机的分类'
                : '删除分类',
              'mdi:delete-outline',
              () => confirmRemove('category', row.key),
              form.hosts.some((h) => h.category === row.key),
              true
            ),
          ],
        }
      ),
  },
]
const itemColumns = [
  { type: 'selection', disabled: () => busy.value },
  ...businessColumns([
    { title: '监控项', key: 'name', width: 360 },
    { title: '键值', key: 'key_', width: 340 },
    { title: '单位', key: 'units', width: 100 },
  ]),
]
const hostDialog = ref(false),
  editingHost = ref(false),
  categoryDialog = ref(false)
const groups = ref([]),
  candidates = ref([]),
  items = ref([]),
  itemNames = reactive({})
const groupId = ref(null),
  hostKeyword = ref(''),
  itemKeyword = ref('')
const hostsTruncated = ref(false),
  itemsTruncated = ref(false)
const draft = reactive({
  hostid: null,
  name: '',
  category: null,
  scope: 'selected',
  itemids: [],
  attributes: {},
})
const draftFields = computed(
  () => form.categories.find((c) => c.key === draft.category)?.fields || []
)
const categoryDraft = reactive({ key: null, label: '', fields: [] })
const removal = reactive({ show: false, kind: '', key: '' })
async function reload() {
  if (busy.value) return
  loading.value = true
  error.value = ''
  ready.value = false
  try {
    Object.assign(form, { tags_warning: '' }, (await api.settings()).data)
    ready.value = true
  } catch (e) {
    error.value = e.message || '配置加载失败，请重试'
  } finally {
    loading.value = false
  }
}
async function persist(hosts, categories) {
  if (!canEdit.value || busy.value || !ready.value) return false
  saving.value = true
  dialogError.value = ''
  error.value = ''
  try {
    const result = await api.saveSettings({
      revision: form.revision,
      categories,
      hosts: hosts.map((h) => ({
        hostid: h.hostid,
        category: h.category || null,
        itemids: h.itemids ?? null,
        attributes: h.attributes || {},
      })),
    })
    Object.assign(form, result.data)
    window.$message?.success('配置已保存')
    return true
  } catch (e) {
    dialogError.value = e.message || '保存失败，请重试'
    error.value = dialogError.value
    return false
  } finally {
    saving.value = false
  }
}
async function openHost(row) {
  if (busy.value) return
  dialogError.value = ''
  editingHost.value = !!row
  groupId.value = null
  hostKeyword.value = ''
  itemKeyword.value = ''
  candidates.value = []
  items.value = []
  hostsTruncated.value = false
  itemsTruncated.value = false
  Object.assign(draft, {
    hostid: row?.hostid || null,
    name: row?.name || '',
    category: row?.category || null,
    scope: row && row.itemids == null ? 'all' : 'selected',
    itemids: [...(row?.itemids || [])],
    attributes: { ...(row?.attributes || {}) },
  })
  hostDialog.value = true
  if (row) {
    if (draft.scope === 'selected') await loadItems()
    return
  }
  searching.value = true
  try {
    groups.value = (await api.hostGroups()).data
  } catch (e) {
    dialogError.value = e.message || '主机组加载失败，请关闭后重试'
  } finally {
    searching.value = false
  }
}
function changeGroup() {
  draft.hostid = null
  draft.itemids = []
  items.value = []
  hostKeyword.value = ''
  searchHosts()
}
async function searchHosts() {
  if (busy.value || !groupId.value) return
  searching.value = true
  dialogError.value = ''
  candidates.value = []
  try {
    const result = (await api.hosts(groupId.value, hostKeyword.value.trim())).data
    candidates.value = result.rows
    hostsTruncated.value = result.truncated
  } catch (e) {
    dialogError.value = e.message || '主机查询失败'
  } finally {
    searching.value = false
  }
}
function changeHost() {
  draft.itemids = []
  items.value = []
  itemKeyword.value = ''
  draft.name = candidates.value.find((h) => h.hostid === draft.hostid)?.name || ''
  if (draft.scope === 'selected') loadItems()
}
function scopeChanged() {
  if (draft.scope === 'selected') loadItems()
}
async function loadItems() {
  if (busy.value || !draft.hostid) return
  searching.value = true
  dialogError.value = ''
  items.value = []
  try {
    const result = (await api.hostItems(draft.hostid, itemKeyword.value.trim())).data
    items.value = result.rows
    itemsTruncated.value = result.truncated
    for (const item of items.value) itemNames[item.itemid] = item.name
  } catch (e) {
    dialogError.value = e.message || '监控项查询失败'
  } finally {
    searching.value = false
  }
}
function updateItems(keys) {
  const visible = new Set(items.value.map((i) => i.itemid))
  draft.itemids = [...new Set([...draft.itemids.filter((id) => !visible.has(id)), ...keys])]
}
function removeItem(id) {
  if (!busy.value) draft.itemids = draft.itemids.filter((value) => value !== id)
}
async function saveHost() {
  if (!draft.hostid || busy.value) return
  if (draft.scope === 'selected' && !draft.itemids.length) {
    dialogError.value = '请至少选择一个监控项'
    return
  }
  if (!editingHost.value && form.hosts.length >= 1000) {
    dialogError.value = '最多纳管 1000 台主机'
    return
  }
  const host = {
    hostid: draft.hostid,
    category: draft.category,
    attributes: Object.fromEntries(
      draftFields.value.map((f) => [f.key, draft.attributes[f.key] || ''])
    ),
    itemids: draft.scope === 'all' ? null : [...draft.itemids],
  }
  const hosts = editingHost.value
    ? form.hosts.map((h) => (h.hostid === draft.hostid ? host : h))
    : [...form.hosts, host]
  if (await persist(hosts, form.categories)) hostDialog.value = false
}
function openCategory(row) {
  dialogError.value = ''
  Object.assign(categoryDraft, {
    key: row?.key || null,
    label: row?.label || '',
    fields: (row?.fields || []).map((f) => ({ ...f, locked: true })),
  })
  categoryDialog.value = true
}
async function saveCategory() {
  const label = categoryDraft.label.trim()
  if (!label) {
    dialogError.value = '请输入分类名称'
    return
  }
  if (form.categories.some((c) => c.key !== categoryDraft.key && c.label === label)) {
    dialogError.value = '分类名称已存在'
    return
  }
  const category = {
    fields: categoryDraft.fields.map((f) => ({ key: f.key.trim(), label: f.label.trim() })),
    key:
      categoryDraft.key ||
      `cat_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 12)}`,
    label,
  }
  const categories = categoryDraft.key
    ? form.categories.map((c) => (c.key === category.key ? category : c))
    : [...form.categories, category]
  if (await persist(form.hosts, categories)) categoryDialog.value = false
}
function confirmRemove(kind, key) {
  dialogError.value = ''
  Object.assign(removal, { show: true, kind, key })
}
async function remove() {
  const hosts =
    removal.kind === 'host' ? form.hosts.filter((h) => h.hostid !== removal.key) : form.hosts
  const categories =
    removal.kind === 'category'
      ? form.categories.filter((c) => c.key !== removal.key)
      : form.categories
  if (await persist(hosts, categories)) removal.show = false
}
onMounted(reload)
</script>
<style scoped>
.gap {
  margin: 12px 0;
}
.muted {
  opacity: 0.7;
  font-size: 12px;
}
.dialog-body {
  max-height: 68vh;
  overflow: auto;
  padding-right: 8px;
}
:deep(.host-attributes) {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 4px 0;
}
:deep(.host-attribute) {
  display: inline-flex;
  align-items: baseline;
  gap: 8px;
  max-width: 100%;
  min-width: 0;
  padding: 3px 8px;
  border: 1px solid rgba(128, 128, 128, 0.14);
  border-radius: 5px;
  background: rgba(128, 128, 128, 0.05);
  font-size: 12px;
  line-height: 20px;
}
:deep(.host-attribute-label) {
  flex-shrink: 0;
  opacity: 0.65;
}
:deep(.host-attribute-value) {
  min-width: 0;
  overflow-wrap: anywhere;
  white-space: normal;
  font-weight: 500;
}
h3 {
  margin: 18px 0 10px;
  font-size: 14px;
}
</style>
