<template>
  <n-modal
    :show="show"
    preset="card"
    title="分类与监控范围"
    style="width: min(1100px, calc(100vw - 24px))"
    :closable="!working"
    :mask-closable="!working"
    :close-on-esc="!working"
    @update:show="emit('update:show', $event)"
  >
    <n-spin :show="loading">
      <div class="settings-body">
        <n-alert type="info"
          >仅已选主机会进入仪表盘。以下修改保存后生效，移除主机不会删除 Zabbix 数据。</n-alert
        >
        <n-alert v-if="error" type="error" class="gap">{{ error }}</n-alert>

        <h3>分类标签</h3>
        <n-select
          v-model:value="form.category_tag"
          :options="tagOptions"
          filterable
          :disabled="working"
          placeholder="选择 Zabbix 主机标签名"
        />
        <p class="muted">
          分类来自该标签的值，在 Zabbix
          中维护。先选择主机组可发现更多标签；缺少该标签或值为空的主机归入未分类。
        </p>
        <n-alert v-if="form.tags_warning" type="warning" class="gap">{{
          form.tags_warning
        }}</n-alert>
        <h3>从 Zabbix 选择主机</h3>
        <n-space class="gap" align="center">
          <n-select
            v-model:value="groupId"
            :options="groupOptions"
            placeholder="① 选择 Zabbix 主机组"
            filterable
            clearable
            :disabled="working"
            style="width: 260px"
            @update:value="groupChanged"
          />
          <n-input
            v-model:value="keyword"
            placeholder="② 组内主机名称筛选（可选）"
            clearable
            :disabled="working || !groupId"
            style="width: 320px; max-width: 100%"
            @keyup.enter="search"
          />
          <CButton
            show-save
            save-text="搜索主机"
            :save-loading="searching"
            :disabled="working || !groupId"
            @save="search"
          />
        </n-space>
        <CButton
          v-if="searchError && !groups.length"
          show-save
          save-text="重新加载主机组"
          :disabled="working"
          @save="loadGroups"
        />
        <n-alert v-if="searchError" type="error" class="gap">{{ searchError }}</n-alert>
        <n-alert v-if="truncated" type="warning" class="gap"
          >匹配超过 100 台，仅展示前 100 台，请缩小搜索范围。</n-alert
        >
        <n-data-table
          v-model:checked-row-keys="checked"
          :columns="candidateColumns"
          :data="candidates"
          :row-key="(row) => row.hostid"
          :max-height="260"
          :scroll-x="720"
          :loading="searching"
          size="small"
        >
          <template #empty
            ><n-empty
              :description="
                searched ? '当前主机组内没有匹配的主机' : '先选择主机组，再勾选需要监控的主机'
              "
          /></template>
        </n-data-table>
        <n-space align="center" class="gap">
          <CButton
            show-save
            :save-text="`添加选中主机（${checked.length}）`"
            :disabled="working || !checked.length"
            @save="addHosts"
          />
        </n-space>
        <h3>已选主机（{{ form.hosts.length }} / 1000）</h3>
        <n-data-table
          :columns="selectedColumns"
          :data="form.hosts"
          :row-key="(row) => row.hostid"
          :max-height="300"
          :scroll-x="740"
          size="small"
        />
        <p class="muted">
          主机停用、删除或 Zabbix
          权限变化后，仪表盘会提示无法读取。清空主机并保存后，事件读取将停止。
        </p>
      </div>
    </n-spin>
    <template #footer
      ><n-space justify="end">
        <CButton show-cancel :disabled="working" @cancel="emit('update:show', false)" />
        <CButton
          show-save
          save-text="保存配置"
          :save-loading="saving"
          :disabled="working || !ready"
          @save="save"
        /> </n-space
    ></template>
  </n-modal>
  <n-modal
    v-model:show="removal.show"
    preset="card"
    title="确认移除"
    style="width: min(440px, calc(100vw - 24px))"
  >
    <p>从当前配置移除此主机？保存配置后生效。</p>
    <template #footer
      ><CButton show-save show-cancel @save="remove" @cancel="removal.show = false"
    /></template>
  </n-modal>
</template>

<script setup>
import { computed, h, reactive, ref, watch } from 'vue'
import { NButton, NSpace, NTooltip } from 'naive-ui'
import CButton from '@/components/public/CButton.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import api from '@/api/monitor-events'

const props = defineProps({ show: Boolean })
const emit = defineEmits(['update:show', 'saved'])
const form = reactive({ revision: 0, category_tag: 'business_category', hosts: [] })
const loading = ref(false),
  saving = ref(false),
  searching = ref(false),
  ready = ref(false),
  error = ref(''),
  searchError = ref('')
const keyword = ref(''),
  candidates = ref([]),
  checked = ref([]),
  searched = ref(false),
  truncated = ref(false)
const groupId = ref(null),
  groups = ref([])
const groupOptions = computed(() =>
  groups.value.map((group) => ({ label: group.name, value: group.groupid }))
)
const removal = reactive({ show: false, kind: '', key: '' })
const working = computed(() => loading.value || saving.value || searching.value)
const tagOptions = computed(() =>
  [
    ...new Set(
      [
        form.category_tag,
        ...[...form.hosts, ...candidates.value].flatMap((h) => (h.tags || []).map((t) => t.tag)),
      ].filter(Boolean)
    ),
  ]
    .sort()
    .map((value) => ({ label: value, value }))
)
function hostCategory(row) {
  return (
    [
      ...new Set(
        (row.tags || [])
          .filter((t) => t.tag === form.category_tag && t.value?.trim())
          .map((t) => t.value.trim())
      ),
    ].join(' / ') || '未分类'
  )
}
function actionButton(label, icon, callback, disabled = false) {
  return h(NTooltip, null, {
    trigger: () =>
      h(
        NButton,
        {
          size: 'small',
          circle: true,
          quaternary: true,
          type: 'error',
          disabled: working.value || disabled,
          'aria-label': label,
          onClick: (event) => {
            event.stopPropagation()
            if (!working.value && !disabled) callback()
          },
        },
        { icon: () => h(TheIcon, { icon, size: 17 }) }
      ),
    default: () => (disabled ? '请先重新分配该分类的主机' : label),
  })
}
const candidateColumns = [
  {
    type: 'selection',
    disabled: (row) => working.value || form.hosts.some((h) => h.hostid === row.hostid),
  },
  ...[
    { title: '主机名称', key: 'name', width: 250 },
    {
      title: 'IP / 地址',
      key: 'addresses',
      width: 220,
      render: (row) => row.addresses.join(' / ') || '—',
    },
    { title: '标签分类', key: 'category', width: 200, render: hostCategory },
  ].map((c) => ({ ...c, resizable: true, ellipsis: { tooltip: true } })),
]
const selectedColumns = [
  { title: '主机名称', key: 'name', width: 280, resizable: true, ellipsis: { tooltip: true } },
  { title: 'Zabbix ID', key: 'hostid', width: 140, resizable: true },
  {
    title: '所属分类',
    key: 'category',
    width: 240,
    resizable: true,
    render: hostCategory,
  },
  {
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
            actionButton('移除主机', 'mdi:delete-outline', () => confirmRemove('host', row.hostid)),
        }
      ),
  },
]
watch(
  () => props.show,
  async (value) => {
    if (!value) return
    loading.value = true
    ready.value = false
    error.value = ''
    searchError.value = ''
    candidates.value = []
    checked.value = []
    searched.value = false
    keyword.value = ''
    groupId.value = null
    groups.value = []
    truncated.value = false
    try {
      const result = await api.settings()
      form.tags_warning = ''
      Object.assign(form, result.data)
      ready.value = true
      await loadGroups()
    } catch (e) {
      error.value = e.message || '配置读取失败，请关闭后重新打开'
    } finally {
      loading.value = false
    }
  }
)
function confirmRemove(kind, key) {
  Object.assign(removal, { show: true, kind, key })
}
function remove() {
  form.hosts = form.hosts.filter((h) => h.hostid !== removal.key)
  removal.show = false
}
async function search() {
  if (working.value || !groupId.value) return
  searching.value = true
  searchError.value = ''
  checked.value = []
  candidates.value = []
  truncated.value = false
  try {
    const result = await api.hosts(groupId.value, keyword.value.trim())
    candidates.value = result.data.rows
    truncated.value = result.data.truncated
    searched.value = true
  } catch (e) {
    searchError.value = e.message || '主机搜索失败'
  } finally {
    searching.value = false
  }
}
async function loadGroups() {
  searching.value = true
  searchError.value = ''
  try {
    groups.value = (await api.hostGroups()).data || []
  } catch (e) {
    searchError.value = e.message || '主机组加载失败，请重试'
  } finally {
    searching.value = false
  }
}
function groupChanged() {
  keyword.value = ''
  candidates.value = []
  checked.value = []
  searched.value = false
  truncated.value = false
  if (groupId.value) search()
}
function addHosts() {
  const selected = candidates.value.filter(
    (h) => checked.value.includes(h.hostid) && !form.hosts.some((s) => s.hostid === h.hostid)
  )
  if (form.hosts.length + selected.length > 1000) {
    error.value = '最多选择 1000 台主机'
    return
  }
  form.hosts.push(...selected.map((h) => ({ hostid: h.hostid, name: h.name, tags: h.tags || [] })))
  checked.value = []
}
async function save() {
  if (working.value) return
  saving.value = true
  error.value = ''
  try {
    const data = {
      revision: form.revision,
      category_tag: form.category_tag,
      hosts: form.hosts.map((h) => ({ hostid: h.hostid })),
    }
    if (!data.category_tag?.trim()) throw new Error('请选择分类标签')
    await api.saveSettings(data)
    window.$message?.success('分类与监控范围已保存')
    emit('update:show', false)
    emit('saved')
  } catch (e) {
    error.value = e.message || '保存失败'
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.settings-body {
  max-height: 70vh;
  overflow: auto;
  padding-right: 8px;
}
.gap {
  margin: 12px 0;
}
.category-list {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 12px;
}
.category-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.muted {
  font-size: 12px;
  color: #7d899a;
}
h3 {
  margin: 18px 0 10px;
}
@media (max-width: 700px) {
  .category-list {
    grid-template-columns: 1fr;
  }
}
</style>
