<template>
  <AppPage :show-footer="false">
    <div class="dhcp-page">
      <section class="dhcp-panel">
        <div class="panel-head">
          <div>
            <span class="eyebrow">OPS CENTER</span>
            <h2>DHCP 池</h2>
          </div>
          <n-button type="primary" round @click="openEditor()">
            <template #icon><TheIcon icon="mdi:plus" :size="17" /></template>
            新增 DHCP 池
          </n-button>
        </div>

        <div class="filter-row">
          <n-input v-model:value="filters.keyword" clearable placeholder="搜索地区 / 机房 / VLAN / IP" @keyup.enter="loadPools" />
          <n-button secondary round @click="resetFilters">
            <template #icon><TheIcon icon="mdi:refresh" :size="16" /></template>
            重置
          </n-button>
          <n-button type="primary" round @click="loadPools">
            <template #icon><TheIcon icon="mdi:magnify" :size="16" /></template>
            搜索
          </n-button>
        </div>

        <div class="dhcp-table-wrap">
          <n-data-table
            :loading="loading"
            :columns="columns"
            :data="rows"
            :pagination="pagination"
            :scroll-x="1040"
            flex-height
            striped
          />
        </div>
      </section>

      <n-modal
        v-model:show="editor.show"
        preset="card"
        :title="editor.form.id ? '编辑 DHCP 池' : '新增 DHCP 池'"
        class="dhcp-editor-modal"
        :style="{ width: '720px', maxWidth: 'calc(100vw - 32px)' }"
      >
        <n-form label-placement="top" class="dhcp-form">
          <n-grid :cols="2" :x-gap="16">
            <n-gi>
              <n-form-item label="池名称" required>
                <n-input v-model:value="editor.form.name" placeholder="例如 HK VLAN199" />
              </n-form-item>
            </n-gi>
            <n-gi>
              <n-form-item label="地区 / 机房" required>
                <n-cascader
                  v-model:value="editor.form.location_key"
                  :options="locationCascaderOptions"
                  :filter="locationCascaderFilter"
                  clearable
                  filterable
                  show-path
                  check-strategy="child"
                  placeholder="选择地区 / 机房"
                  @update:value="handleLocationChange"
                />
              </n-form-item>
            </n-gi>
            <n-gi>
              <n-form-item label="VLAN" required>
                <n-input-number v-model:value="editor.form.vlan" :min="1" :max="4094" />
              </n-form-item>
            </n-gi>
            <n-gi>
              <n-form-item label="网关" required>
                <n-input v-model:value="editor.form.gateway" placeholder="45.67.201.249/29" />
              </n-form-item>
            </n-gi>
            <n-gi>
              <n-form-item label="CIDR" required>
                <n-input v-model:value="editor.form.cidr" placeholder="45.67.201.248/29" />
              </n-form-item>
            </n-gi>
            <n-gi>
              <n-form-item label="DNS">
                <n-input v-model:value="editor.form.dns" placeholder="8.8.8.8" />
              </n-form-item>
            </n-gi>
            <n-gi>
              <n-form-item label="开始 IP" required>
                <n-input v-model:value="editor.form.start_ip" placeholder="45.67.201.250" />
              </n-form-item>
            </n-gi>
            <n-gi>
              <n-form-item label="结束 IP" required>
                <n-input v-model:value="editor.form.end_ip" placeholder="45.67.201.254" />
              </n-form-item>
            </n-gi>
            <n-gi>
              <n-form-item label="启用">
                <n-switch v-model:value="editor.form.status" />
              </n-form-item>
            </n-gi>
            <n-gi :span="2">
              <n-form-item label="备注">
                <n-input v-model:value="editor.form.remark" type="textarea" placeholder="内部备注" />
              </n-form-item>
            </n-gi>
          </n-grid>
        </n-form>
        <template #footer>
          <div class="modal-footer">
            <span>云主机创建和价格管理会按地区选择启用状态的 DHCP 池。</span>
            <n-space :size="10">
              <CButton show-cancel @cancel="editor.show = false" />
              <CButton show-save :save-loading="editor.loading" @save="savePool" />
            </n-space>
          </div>
        </template>
      </n-modal>
    </div>
  </AppPage>
</template>

<script setup>
import { computed, h, onMounted, reactive, ref } from 'vue'
import { NButton, NPopconfirm, NTag, useMessage } from 'naive-ui'
import api from '@/api'
import CButton from '@/components/public/CButton.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import { translateCity, translateCountry, translateLocationPath } from '@/utils/location-i18n'

const message = useMessage()
const loading = ref(false)
const rows = ref([])
const bindingOptions = reactive({ regions: [], locations: [] })
const filters = reactive({ keyword: '' })
const editor = reactive({ show: false, loading: false, form: emptyForm() })

const pagination = reactive({
  page: 1,
  pageSize: 20,
  itemCount: 0,
  showSizePicker: true,
  pageSizes: [20, 50, 100],
  onChange: (page) => {
    pagination.page = page
    loadPools()
  },
  onUpdatePageSize: (pageSize) => {
    pagination.pageSize = pageSize
    pagination.page = 1
    loadPools()
  },
})

const columns = [
  { title: '地区 / 机房', key: 'region_name', width: 210, render: (row) => placeText(row) },
  { title: '池名称', key: 'name', width: 170 },
  { title: 'VLAN', key: 'vlan', width: 90 },
  { title: '地址池', key: 'range', width: 250, render: (row) => `${row.start_ip || '-'} - ${row.end_ip || '-'}` },
  { title: '网关', key: 'gateway', width: 170 },
  { title: '剩余', key: 'available_count', width: 120, render: (row) => `${row.available_count || 0} / ${row.total_count || 0}` },
  { title: '下一个 IP', key: 'next_ip', width: 150, render: (row) => row.next_ip || '-' },
  {
    title: '状态',
    key: 'status',
    width: 100,
    render: (row) => h(NTag, { size: 'small', round: true, type: row.status ? 'success' : 'default' }, { default: () => (row.status ? '启用' : '停用') }),
  },
  {
    title: '操作',
    key: 'actions',
    width: 130,
    fixed: 'right',
    render: (row) => h('div', { class: 'table-actions' }, [
      h(NButton, { size: 'small', secondary: true, type: 'info', onClick: () => openEditor(row) }, { icon: () => h(TheIcon, { icon: 'mdi:pencil', size: 15 }) }),
      h(NPopconfirm, { onPositiveClick: () => deletePool(row) }, {
        trigger: () => h(NButton, { size: 'small', secondary: true, type: 'error' }, { icon: () => h(TheIcon, { icon: 'mdi:trash-can-outline', size: 15 }) }),
        default: () => '确认删除该 DHCP 池？',
      }),
    ]),
  },
]

const locationCascaderOptions = computed(() => {
  const roots = []
  const regionMap = new Map(bindingOptions.regions.map((region) => [Number(region.value), region]))
  bindingOptions.locations.forEach((location) => {
    const region = regionMap.get(Number(location.region_id))
    const locationName = textValue(location.name || location.label)
    if (!region || !locationName) return
    const regionText = displayRegion(region.label || [region.country, region.city].filter(Boolean).join(' / ') || region.name)
    const parent = ensureCascaderPath(roots, regionPathParts(regionText), 'region')
    const value = locationKey(location.value)
    if (parent.children.some((item) => item.value === value)) return
    parent.children.push({
      label: locationName,
      value,
      region_id: location.region_id,
      location_id: location.value,
      searchText: uniqueValues([regionText, locationName, location.label, region.name, region.code, region.country, region.city]).join(' '),
    })
  })
  return sortTree(roots)
})

function emptyForm() {
  return {
    id: null,
    name: '',
    region_code: '',
    region_id: null,
    location_id: null,
    location_key: null,
    vlan: 199,
    gateway: '',
    cidr: '',
    start_ip: '',
    end_ip: '',
    dns: '8.8.8.8',
    status: true,
    remark: '',
  }
}

function placeText(row) {
  return [row.region_name || row.region_code || '', row.location_name || ''].filter(Boolean).join(' / ') || '-'
}

async function loadBindingOptions() {
  const res = await api.virtualMachineApi.nodeBindingOptions()
  bindingOptions.regions = res.data?.regions || []
  bindingOptions.locations = res.data?.locations || []
}

async function loadPools() {
  loading.value = true
  try {
    const res = await api.virtualMachineApi.dhcpPools({
      keyword: filters.keyword,
      page: pagination.page,
      page_size: pagination.pageSize,
    })
    const list = Array.isArray(res?.data) ? res.data : Array.isArray(res?.data?.items) ? res.data.items : []
    rows.value = list
    pagination.itemCount = Number(res?.total ?? res?.data?.total ?? list.length)
  } catch (error) {
    rows.value = []
    pagination.itemCount = 0
    message.error(error.message || '读取 DHCP 池失败')
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  filters.keyword = ''
  pagination.page = 1
  loadPools()
}

function openEditor(row = null) {
  editor.form = row ? { ...emptyForm(), ...row, location_key: row.location_id ? locationKey(row.location_id) : null } : emptyForm()
  editor.show = true
}

async function savePool() {
  const payload = { ...editor.form }
  if (!payload.name || (!payload.region_id && !payload.region_code) || !payload.vlan || !payload.gateway || !payload.cidr || !payload.start_ip || !payload.end_ip) {
    message.warning('请填写池名称、地区/机房、VLAN、网关、CIDR 和 IP 段')
    return
  }
  editor.loading = true
  try {
    if (payload.id) await api.virtualMachineApi.updateDhcpPool(payload.id, payload)
    else await api.virtualMachineApi.createDhcpPool(payload)
    editor.show = false
    message.success('DHCP 池已保存')
    await loadPools()
  } finally {
    editor.loading = false
  }
}

async function deletePool(row) {
  try {
    const res = await api.virtualMachineApi.deleteDhcpPool(row.id)
    message.success(res?.msg || 'DHCP 池已删除')
    await loadPools()
  } catch (error) {
    message.error(error.message || '删除 DHCP 池失败')
  }
}

function handleLocationChange(value, option) {
  const locationId = parseLocationKey(value)
  const location = bindingOptions.locations.find((item) => Number(item.value) === Number(locationId))
  const regionId = option?.region_id || location?.region_id || null
  const region = bindingOptions.regions.find((item) => Number(item.value) === Number(regionId))
  editor.form.location_id = location?.value || null
  editor.form.region_id = regionId
  editor.form.region_code = region?.code || region?.name || [region?.country, region?.city].filter(Boolean).join(' / ') || ''
}

function textValue(value) {
  if (value == null) return ''
  if (typeof value === 'object') return String(value.name || value.label || value.value || value.code || value.id || '').trim()
  return String(value).trim()
}

function displayRegion(value) {
  const text = textValue(value)
  if (!text) return ''
  return translateLocationPath(text) || translateCountry(text) || translateCity(text) || text
}

function regionPathParts(value) {
  const text = displayRegion(value)
  return text.split(/[\/,，、;；\\]+/).map((item) => item.trim()).filter(Boolean)
}

function ensureCascaderPath(roots, parts, prefix) {
  let children = roots
  let current = null
  const path = []
  parts.forEach((part) => {
    path.push(part)
    const value = `${prefix}:${path.join('/')}`
    let node = children.find((item) => item.value === value)
    if (!node) {
      node = { label: part, value, searchText: path.join(' '), children: [] }
      children.push(node)
    }
    current = node
    children = node.children
  })
  return current || { children: roots }
}

function sortTree(nodes) {
  return nodes
    .sort((left, right) => String(left.label || '').localeCompare(String(right.label || ''), 'zh-Hans-CN'))
    .map((node) => ({ ...node, children: node.children?.length ? sortTree(node.children) : undefined }))
}

function normalizeSearch(value) {
  return String(value || '').toLowerCase().replace(/[\s　]+/g, '').replace(/[\/,，、;；_-]+/g, '').trim()
}

function locationCascaderFilter(pattern, option, path = []) {
  const keyword = normalizeSearch(pattern)
  if (!keyword) return true
  const options = Array.isArray(path) && path.length ? path : [option]
  const text = options.flatMap((item) => [item?.label, item?.value, item?.searchText]).filter(Boolean).join(' ')
  return normalizeSearch(text).includes(keyword)
}

function uniqueValues(values) {
  return [...new Set(values.map((value) => String(value || '').trim()).filter(Boolean))]
}

function locationKey(value) {
  return value ? `location:${value}` : null
}

function parseLocationKey(value) {
  const text = String(value || '')
  if (!text.startsWith('location:')) return null
  const id = Number(text.split(':')[1])
  return Number.isFinite(id) ? id : null
}

onMounted(async () => {
  await loadPools()
  try {
    await loadBindingOptions()
  } catch (error) {
    // The editor's location options must not prevent the DHCP pool list from loading.
    console.warn('读取 DHCP 池位置选项失败', error)
  }
})
</script>

<style scoped>
.dhcp-page {
  height: 100%;
  min-height: 0;
}

.dhcp-panel {
  display: flex;
  height: calc(100vh - 150px);
  min-height: 0;
  flex-direction: column;
  gap: 16px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  padding: 18px;
}

.panel-head,
.filter-row,
.modal-footer,
.table-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.dhcp-panel :deep(.table-actions) {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  white-space: nowrap;
}

.dhcp-panel :deep(.table-actions > * + *) {
  margin-left: 10px;
}

.panel-head,
.modal-footer {
  justify-content: space-between;
}

.eyebrow {
  color: #58708f;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
}

h2 {
  margin: 6px 0 0;
  color: #0f172a;
  font-size: 22px;
}

.filter-row {
  display: grid;
  grid-template-columns: minmax(260px, 1fr) auto auto;
}

.dhcp-table-wrap {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.dhcp-table-wrap :deep(.n-data-table) {
  width: 100%;
  height: 100%;
}

.dhcp-table-wrap :deep(.n-data-table .n-data-table-base-table) {
  min-height: 0;
}

.dhcp-form :deep(.n-input),
.dhcp-form :deep(.n-input-number),
.dhcp-form :deep(.n-cascader) {
  width: 100%;
}

.dhcp-editor-modal :deep(.n-card-header),
.dhcp-editor-modal :deep(.n-card__footer) {
  border-color: #eef2f7;
}

.dhcp-editor-modal :deep(.n-card__footer .n-space) {
  gap: 10px !important;
}

.modal-footer span {
  color: #64748b;
  font-size: 12px;
}

@media (max-width: 768px) {
  .dhcp-panel {
    height: auto;
    min-height: calc(100vh - 120px);
    padding: 12px;
  }

  .filter-row {
    grid-template-columns: 1fr;
  }

  .panel-head,
  .modal-footer {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
