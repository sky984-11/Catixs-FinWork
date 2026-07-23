<template>
  <AppPage :show-footer="false">
    <div class="ipam-page">
      <section class="ipam-toolbar">
        <div class="toolbar-filters">
          <n-input
            v-model:value="filters.search"
            clearable
            placeholder="搜索 IP / 前缀"
            @clear="handleFilterChange"
            @keydown.enter="handleFilterChange"
            @update:value="handleSearchInput"
          >
            <template #prefix>
              <TheIcon icon="mdi:magnify" :size="17" />
            </template>
          </n-input>
          <n-select
            v-model:value="filters.supplier"
            clearable
            filterable
            placeholder="供应商"
            :options="filterOptions.suppliers"
            @update:value="handleFilterChange"
          />
          <n-select
            v-model:value="filters.customer"
            clearable
            filterable
            placeholder="客户"
            :options="filterOptions.customers"
            @update:value="handleFilterChange"
          />
          <n-select
            v-model:value="filters.region"
            clearable
            filterable
            placeholder="地区"
            :options="filterOptions.regions"
            @update:value="handleFilterChange"
          />
        </div>
        <div class="toolbar-actions">
          <n-button type="primary" round @click="openCreateModal">
            <template #icon>
              <TheIcon icon="mdi:plus" :size="17" />
            </template>
            新增
          </n-button>
          <n-button type="primary" round :loading="syncLoading" @click="syncPveIps">
            <template #icon>
              <TheIcon icon="mdi:sync" :size="17" />
            </template>
            提交同步
          </n-button>
        </div>
      </section>

      <section class="tree-table-panel">
        <n-data-table
          class="prefix-table"
          size="small"
          :loading="loading"
          :columns="prefixColumns"
          :data="prefixTreeData"
          :pagination="prefixPagination"
          remote
          flex-height
          :row-key="prefixRowKey"
          :bordered="false"
          striped
        />
      </section>

      <n-modal
        v-model:show="showIpModal"
        preset="card"
        :title="selectedPrefix?.prefix || 'IP Addresses'"
        class="ip-detail-modal"
        :bordered="false"
      >
        <template v-if="selectedPrefix">
          <div class="detail-head">
            <div>
              <span class="eyebrow">IP Addresses</span>
              <h3>{{ selectedPrefix.prefix }}</h3>
              <p>{{ prefixSubtitle(selectedPrefix) }}</p>
            </div>
            <div class="detail-meter">
              <n-progress
                type="circle"
                :percentage="Math.min(selectedPrefix.utilization || 0, 100)"
                :status="progressStatus(selectedPrefix.utilization)"
              />
              <span>{{ formatNumber(selectedPrefix.used) }} / {{ formatNumber(selectedPrefix.usable) }}</span>
            </div>
          </div>

          <n-data-table
            class="ip-table"
            size="small"
            :loading="ipLoading"
            :columns="ipColumns"
            :data="ipRows"
            :pagination="ipPagination"
            remote
            max-height="calc(100vh - 360px)"
            :row-key="(row) => row.id || row.address"
            striped
          >
            <template #empty>
              <n-empty description="暂无 IP 地址或可用段" />
            </template>
          </n-data-table>
        </template>
      </n-modal>

      <n-modal
        v-model:show="ipEditModal.show"
        preset="card"
        title="编辑 IP"
        class="ip-edit-modal"
        :bordered="false"
      >
        <n-form label-placement="left" label-width="88" :model="ipEditModal.form">
          <n-form-item label="IP 地址">
            <n-input v-model:value="ipEditModal.form.address" placeholder="例如 2.59.61.14/32" />
          </n-form-item>
          <n-form-item label="状态">
            <n-select v-model:value="ipEditModal.form.status" :options="ipStatusOptions" />
          </n-form-item>
          <n-form-item label="DNS 名称">
            <n-input v-model:value="ipEditModal.form.dns_name" placeholder="DNS 名称" />
          </n-form-item>
          <n-form-item label="说明">
            <n-input
              v-model:value="ipEditModal.form.description"
              type="textarea"
              placeholder="说明"
              :autosize="{ minRows: 3, maxRows: 6 }"
            />
          </n-form-item>
        </n-form>
        <template #footer>
          <div class="modal-actions">
            <n-button round @click="ipEditModal.show = false">取消</n-button>
            <n-button type="primary" round :loading="ipEditModal.saving" @click="saveIpAddress">保存</n-button>
          </div>
        </template>
      </n-modal>

      <n-modal
        v-model:show="prefixEditModal.show"
        preset="card"
        title="编辑前缀"
        class="ip-edit-modal"
        :bordered="false"
      >
        <n-form label-placement="left" label-width="88" :model="prefixEditModal.form">
          <n-form-item label="IP 前缀">
            <n-input v-model:value="prefixEditModal.form.prefix" placeholder="例如 2.59.61.0/24" />
          </n-form-item>
          <n-form-item label="状态">
            <n-select v-model:value="prefixEditModal.form.status" :options="prefixStatusOptions" />
          </n-form-item>
          <n-form-item label="供应商">
            <n-select
              v-model:value="prefixEditModal.form.supplier"
              clearable
              filterable
              placeholder="Owner"
              :options="prefixFieldOptions.suppliers"
            />
          </n-form-item>
          <n-form-item label="客户">
            <n-select
              v-model:value="prefixEditModal.form.customer_id"
              clearable
              filterable
              placeholder="租户"
              :options="prefixFieldOptions.tenants"
            />
          </n-form-item>
          <n-form-item label="角色">
            <n-select
              v-model:value="prefixEditModal.form.role_id"
              clearable
              filterable
              placeholder="角色"
              :options="prefixFieldOptions.roles"
            />
          </n-form-item>
          <n-form-item label="地区">
            <div class="scope-selects">
              <n-select
                v-model:value="prefixEditModal.form.scope_type"
                placeholder="作用域类型"
                :options="prefixFieldOptions.scopeTypes"
              />
              <n-select
                v-model:value="prefixEditModal.form.scope_id"
                clearable
                filterable
                placeholder="站点"
                :options="prefixFieldOptions.sites"
              />
            </div>
          </n-form-item>
          <n-form-item label="VLAN">
            <n-select
              v-model:value="prefixEditModal.form.vlan_id"
              clearable
              filterable
              placeholder="VLAN"
              :options="prefixFieldOptions.vlans"
            />
          </n-form-item>
          <n-form-item label="说明">
            <n-input
              v-model:value="prefixEditModal.form.description"
              type="textarea"
              placeholder="说明"
              :autosize="{ minRows: 3, maxRows: 6 }"
            />
          </n-form-item>
        </n-form>
        <template #footer>
          <div class="modal-actions">
            <n-button round @click="prefixEditModal.show = false">取消</n-button>
            <n-button type="primary" round :loading="prefixEditModal.saving" @click="savePrefix">保存</n-button>
          </div>
        </template>
      </n-modal>

      <n-modal
        v-model:show="createModal.show"
        preset="card"
        title="新增"
        class="ip-edit-modal"
        :bordered="false"
      >
        <n-form label-placement="left" label-width="88" :model="createModal.form">
          <n-form-item label="类型">
            <n-radio-group v-model:value="createModal.type">
              <n-radio-button value="ip">IP 地址</n-radio-button>
              <n-radio-button value="prefix">前缀</n-radio-button>
            </n-radio-group>
          </n-form-item>
          <n-form-item v-if="createModal.type === 'ip'" label="IP 地址">
            <n-input v-model:value="createModal.form.address" placeholder="例如 2.59.61.14/32" />
          </n-form-item>
          <n-form-item v-else label="IP 前缀">
            <n-input v-model:value="createModal.form.prefix" placeholder="例如 2.59.61.0/24" />
          </n-form-item>
          <n-form-item label="状态">
            <n-select
              v-model:value="createModal.form.status"
              :options="createModal.type === 'ip' ? ipStatusOptions : prefixStatusOptions"
            />
          </n-form-item>
          <n-form-item v-if="createModal.type === 'ip'" label="DNS 名称">
            <n-input v-model:value="createModal.form.dns_name" placeholder="DNS 名称" />
          </n-form-item>
          <template v-else>
            <n-form-item label="供应商">
              <n-select
                v-model:value="createModal.form.supplier"
                clearable
                filterable
                placeholder="Owner"
                :options="prefixFieldOptions.suppliers"
              />
            </n-form-item>
            <n-form-item label="客户">
              <n-select
                v-model:value="createModal.form.customer_id"
                clearable
                filterable
                placeholder="租户"
                :options="prefixFieldOptions.tenants"
              />
            </n-form-item>
            <n-form-item label="角色">
              <n-select
                v-model:value="createModal.form.role_id"
                clearable
                filterable
                placeholder="角色"
                :options="prefixFieldOptions.roles"
              />
            </n-form-item>
            <n-form-item label="地区">
              <div class="scope-selects">
                <n-select
                  v-model:value="createModal.form.scope_type"
                  placeholder="作用域类型"
                  :options="prefixFieldOptions.scopeTypes"
                />
                <n-select
                  v-model:value="createModal.form.scope_id"
                  clearable
                  filterable
                  placeholder="站点"
                  :options="prefixFieldOptions.sites"
                />
              </div>
            </n-form-item>
            <n-form-item label="VLAN">
              <n-select
                v-model:value="createModal.form.vlan_id"
                clearable
                filterable
                placeholder="VLAN"
                :options="prefixFieldOptions.vlans"
              />
            </n-form-item>
          </template>
          <n-form-item label="说明">
            <n-input
              v-model:value="createModal.form.description"
              type="textarea"
              placeholder="说明"
              :autosize="{ minRows: 3, maxRows: 6 }"
            />
          </n-form-item>
        </n-form>
        <template #footer>
          <div class="modal-actions">
            <n-button round @click="createModal.show = false">取消</n-button>
            <n-button type="primary" round :loading="createModal.saving" @click="saveCreate">保存</n-button>
          </div>
        </template>
      </n-modal>
    </div>
  </AppPage>
</template>

<script setup>
import { computed, h, onMounted, reactive, ref } from 'vue'
import { NButton, NPopconfirm, NProgress, NSpace, NTag, useMessage } from 'naive-ui'
import api from '@/api'
import TheIcon from '@/components/icon/TheIcon.vue'

defineOptions({ name: 'OpsIpam' })

const message = useMessage()
const loading = ref(false)
const ipLoading = ref(false)
const syncLoading = ref(false)
const prefixes = ref([])
const ipRows = ref([])
const selectedPrefix = ref(null)
const showIpModal = ref(false)
const ipEditModal = reactive({
  show: false,
  saving: false,
  row: null,
  form: {
    address: '',
    status: 'active',
    dns_name: '',
    description: '',
  },
})
const prefixEditModal = reactive({
  show: false,
  saving: false,
  row: null,
  form: {
    prefix: '',
    status: 'active',
    supplier: '',
    customer_id: null,
    role_id: null,
    scope_type: 'dcim.site',
    scope_id: null,
    vlan_id: null,
    description: '',
  },
})
const createModal = reactive({
  show: false,
  saving: false,
  type: 'ip',
  form: {
    address: '',
    prefix: '',
    status: 'active',
    dns_name: '',
    supplier: '',
    customer_id: null,
    role_id: null,
    scope_type: 'dcim.site',
    scope_id: null,
    vlan_id: null,
    description: '',
  },
})
const summary = reactive({
  prefix_count: 0,
  ip_count: 0,
  used: 0,
  usable: 0,
  available: 0,
  utilization: 0,
  customer_count: 0,
  supplier_count: 0,
})

const filters = reactive({
  search: '',
  region: null,
  customer: null,
  supplier: null,
})

const filterOptions = reactive({
  regions: [],
  customers: [],
  suppliers: [],
})
const prefixFieldOptions = reactive({
  loaded: false,
  loading: false,
  suppliers: [],
  tenants: [],
  roles: [],
  vlans: [],
  scopeTypes: [{ label: 'DCIM > 站点', value: 'dcim.site' }],
  sites: [],
})


const ipStatusOptions = [
  { label: '已用', value: 'active' },
  { label: '预留', value: 'reserved' },
  { label: '废弃', value: 'deprecated' },
  { label: 'DHCP', value: 'dhcp' },
  { label: 'SLAAC', value: 'slaac' },
]

const prefixStatusOptions = [
  { label: '启用', value: 'active' },
  { label: '预留', value: 'reserved' },
  { label: '废弃', value: 'deprecated' },
  { label: '容器', value: 'container' },
]

const prefixPagination = reactive({
  page: 1,
  pageSize: 20,
  itemCount: 0,
  showSizePicker: true,
  pageSizes: [20, 50, 100],
  onUpdatePage: (page) => {
    prefixPagination.page = page
    fetchOverview()
  },
  onUpdatePageSize: (pageSize) => {
    prefixPagination.pageSize = pageSize
    prefixPagination.page = 1
    fetchOverview()
  },
})

const ipPagination = reactive({
  page: 1,
  pageSize: 20,
  itemCount: 0,
  showSizePicker: true,
  pageSizes: [20, 50, 100],
  onUpdatePage: (page) => {
    ipPagination.page = page
    fetchPrefixIps()
  },
  onUpdatePageSize: (pageSize) => {
    ipPagination.pageSize = pageSize
    ipPagination.page = 1
    fetchPrefixIps()
  },
})

const prefixTreeData = computed(() => buildPrefixTree(prefixes.value))
let searchTimer = null

const prefixColumns = [
  {
    title: 'IP 前缀',
    key: 'prefix',
    resizable: true,
    width: 260,
    minWidth: 240,
    render(row) {
      return h(
        'button',
        {
          class: 'prefix-link',
          onClick: (event) => {
            event.stopPropagation()
            selectPrefix(row)
          },
        },
        [
          h(NTag, { size: 'tiny', round: true, type: prefixTypeTag(row).type }, { default: () => prefixTypeTag(row).text }),
          h('span', row.prefix || '-'),
        ]
      )
    },
  },
  {
    title: '状态',
    key: 'status',
    resizable: true,
    width: 90,
    minWidth: 82,
    render(row) {
      return h(NTag, { size: 'small', round: true, type: statusTagType(row.status) }, {
        default: () => mapPrefixStatus(row),
      })
    },
  },
  {
    title: '子网',
    key: 'child_prefix_count',
    resizable: true,
    width: 60,
    minWidth: 52,
    render(row) {
      return Number(row.child_prefix_count || 0)
    },
  },
  {
    title: '角色',
    key: 'role',
    resizable: true,
    width: 96,
    minWidth: 84,
    ellipsis: { tooltip: true },
    render(row) {
      return row.role || '—'
    },
  },
  {
    title: '利用率',
    key: 'utilization',
    resizable: true,
    width: 150,
    minWidth: 130,
    render(row) {
      return h('div', { class: 'usage-cell' }, [
        h(NProgress, {
          type: 'line',
          percentage: Math.min(Number(row.utilization || 0), 100),
          height: 18,
          borderRadius: 4,
          fillBorderRadius: 4,
          showIndicator: false,
          status: progressStatus(row.utilization),
        }),
        h('span', formatPercent(row.utilization)),
      ])
    },
  },
  {
    title: '供应商',
    key: 'supplier',
    resizable: true,
    width: 130,
    minWidth: 110,
    ellipsis: { tooltip: true },
    render(row) {
      return row.supplier || row.owner || '未知'
    },
  },
  {
    title: '客户',
    key: 'customer',
    resizable: true,
    width: 120,
    minWidth: 100,
    ellipsis: { tooltip: true },
    render(row) {
      return row.customer || '—'
    },
  },
  {
    title: '地区',
    key: 'region',
    resizable: true,
    width: 90,
    minWidth: 72,
    ellipsis: { tooltip: true },
    render(row) {
      return row.region || row.scope || row.site || '—'
    },
  },
  {
    title: 'VLAN',
    key: 'vlan',
    resizable: true,
    width: 90,
    minWidth: 72,
    ellipsis: { tooltip: true },
    render(row) {
      return row.vlan || '—'
    },
  },
  {
    title: '描述',
    key: 'description',
    resizable: true,
    width: 320,
    minWidth: 260,
    ellipsis: { tooltip: true },
    render(row) {
      return row.description || '—'
    },
  },
  {
    title: '操作',
    key: 'actions',
    width: 120,
    fixed: 'right',
    render(row) {
      if (!Number.isFinite(Number(row.id))) return ''
      return h(NSpace, { size: 8 }, {
        default: () => [
          h(
            NButton,
            {
              text: true,
              size: 'small',
              type: 'primary',
              onClick: () => openPrefixEditModal(row),
            },
            { default: () => '编辑' }
          ),
          h(
            NPopconfirm,
            {
              onPositiveClick: () => deletePrefix(row),
            },
            {
              trigger: () => h(
                NButton,
                { text: true, size: 'small', type: 'error' },
                { default: () => '删除' }
              ),
              default: () => `确认删除 ${row.prefix || '该前缀'}？`,
            }
          ),
        ],
      })
    },
  },
]

const ipColumns = [
  {
    title: 'IP 地址',
    key: 'address',
    width: 170,
    render(row) {
      if (row.entry_type === 'available') {
        return h(NTag, { size: 'small', round: true, type: 'success' }, { default: () => row.address })
      }
      return row.address || '—'
    },
  },
  {
    title: '角色',
    key: 'role',
    width: 96,
    minWidth: 84,
    ellipsis: { tooltip: true },
    render(row) {
      return row.role || '—'
    },
  },
  {
    title: '客户',
    key: 'customer',
    minWidth: 160,
    render(row) {
      return h(NTag, { size: 'small', round: true, type: row.customer === '未归属' ? 'warning' : 'success' }, {
        default: () => row.customer || '未归属',
      })
    },
  },
  {
    title: '状态',
    key: 'status',
    width: 110,
    render(row) {
      return h(NTag, { size: 'small', round: true, type: statusTagType(row.status) }, {
        default: () => row.status_label || mapIpStatus(row.status),
      })
    },
  },
  { title: '说明', key: 'description', minWidth: 220, ellipsis: { tooltip: true } },
  {
    title: '操作',
    key: 'actions',
    width: 120,
    fixed: 'right',
    render(row) {
      if (row.entry_type === 'available' || !Number.isFinite(Number(row.id))) return ''
      return h(NSpace, { size: 8 }, {
        default: () => [
          h(
            NButton,
            {
              text: true,
              size: 'small',
              type: 'primary',
              onClick: () => openIpEditModal(row),
            },
            { default: () => '编辑' }
          ),
          h(
            NPopconfirm,
            {
              onPositiveClick: () => deleteIpAddress(row),
            },
            {
              trigger: () => h(
                NButton,
                { text: true, size: 'small', type: 'error' },
                { default: () => '删除' }
              ),
              default: () => `确认删除 ${row.address || '该 IP'}？`,
            }
          ),
        ],
      })
    },
  },
]

function prefixRowKey(row) {
  return row.id || row.prefix
}

function statusTagType(status) {
  if (status === 'active') return 'success'
  if (status === 'available') return 'success'
  if (status === 'reserved') return 'warning'
  if (status === 'deprecated') return 'error'
  if (status === 'container') return 'info'
  return 'default'
}

function mapIpStatus(status) {
  return {
    available: '可用',
    active: '已用',
    reserved: '预留/空闲',
    deprecated: '废弃',
    dhcp: 'DHCP',
    slaac: 'SLAAC',
  }[String(status || '').toLowerCase()] || status || '未知'
}

function mapPrefixStatus(prefix) {
  return prefix?.status_label || {
    active: '启用',
    reserved: '预留',
    deprecated: '废弃',
    container: '容器',
  }[String(prefix?.status || '').toLowerCase()] || prefix?.status || '未知'
}

function prefixTypeTag(row) {
  if (row.children?.length) return { text: '父级', type: 'info' }
  if (row.parent_prefix) return { text: '子级', type: 'success' }
  return { text: '前缀', type: 'default' }
}

function prefixSortValue(prefix) {
  const value = String(prefix?.prefix || '')
  const [address = '', mask = '0'] = value.split('/')
  const versionWeight = value.includes(':') ? 6 : 4
  const addressParts = address.split('.')
  const addressWeight = addressParts.length === 4 && addressParts.every((part) => /^\d+$/.test(part))
    ? addressParts.reduce((total, part) => total * 256 + Number(part || 0), 0)
    : Number.MAX_SAFE_INTEGER
  return [versionWeight, addressWeight, Number(mask || 0), value]
}

function comparePrefixes(left, right) {
  const leftValue = prefixSortValue(left)
  const rightValue = prefixSortValue(right)
  for (let index = 0; index < leftValue.length; index += 1) {
    if (leftValue[index] < rightValue[index]) return -1
    if (leftValue[index] > rightValue[index]) return 1
  }
  return 0
}

function buildPrefixTree(items) {
  const clones = new Map()
  const roots = []

  items.forEach((item) => {
    if (!item?.prefix) return
    clones.set(item.prefix, { ...item, children: [] })
  })

  clones.forEach((item) => {
    const parent = item.parent_prefix
    if (parent && parent !== item.prefix && clones.has(parent)) {
      clones.get(parent).children.push(item)
    } else {
      roots.push(item)
    }
  })

  const sortTree = (nodes) => {
    nodes.sort(comparePrefixes)
    nodes.forEach((node) => {
      sortTree(node.children)
      if (!node.children.length) delete node.children
    })
  }
  sortTree(roots)
  return roots
}

function progressStatus(value) {
  const current = Number(value || 0)
  if (current >= 90) return 'error'
  if (current >= 70) return 'warning'
  return 'success'
}

function formatPercent(value) {
  return `${Number(value || 0).toFixed(1)}%`
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString()
}

function prefixSubtitle(prefix) {
  const supplier = prefix.supplier && prefix.supplier !== '未指定' ? `供应商: ${prefix.supplier}` : ''
  const parent = prefix.parent_prefix ? `父前缀: ${prefix.parent_prefix}` : ''
  const region = prefix.region || prefix.scope || prefix.site
  return [supplier, parent, region, prefix.role, prefix.vlan, prefix.vrf].filter(Boolean).join(' / ') || '未分类'
}

function selectPrefix(prefix) {
  selectedPrefix.value = prefix
  ipRows.value = []
  ipPagination.page = 1
  ipPagination.itemCount = 0
  showIpModal.value = true
  fetchPrefixIps()
}

function optionValueByLabel(options, label) {
  if (!label) return null
  const option = (options || []).find((item) => item.label === label || String(item.value) === String(label))
  return option ? option.value : null
}

function ensureStringOption(options, value) {
  if (!value || (options || []).some((item) => item.value === value)) return
  options.push({ label: value, value })
}

async function loadPrefixFieldOptions() {
  if (prefixFieldOptions.loaded || prefixFieldOptions.loading) return
  prefixFieldOptions.loading = true
  try {
    const res = await api.netboxApi.prefixOptions()
    const data = res.data || {}
    prefixFieldOptions.suppliers = data.suppliers || []
    prefixFieldOptions.tenants = data.tenants || []
    prefixFieldOptions.roles = data.roles || []
    prefixFieldOptions.vlans = data.vlans || []
    prefixFieldOptions.scopeTypes = data.scope_types || [{ label: 'DCIM > 站点', value: 'dcim.site' }]
    prefixFieldOptions.sites = data.sites || []
    prefixFieldOptions.loaded = true
  } catch (error) {
    message.error(error.message || '加载 NetBox 下拉选项失败')
  } finally {
    prefixFieldOptions.loading = false
  }
}

async function openCreateModal() {
  await loadPrefixFieldOptions()
  createModal.type = 'ip'
  createModal.form.address = ''
  createModal.form.prefix = selectedPrefix.value?.prefix || ''
  createModal.form.status = 'active'
  createModal.form.dns_name = ''
  createModal.form.supplier = ''
  createModal.form.customer_id = null
  createModal.form.role_id = null
  createModal.form.scope_type = 'dcim.site'
  createModal.form.scope_id = null
  createModal.form.vlan_id = null
  createModal.form.description = ''
  createModal.show = true
}

async function saveCreate() {
  createModal.saving = true
  try {
    if (createModal.type === 'ip') {
      if (!String(createModal.form.address || '').trim()) {
        message.warning('请填写 IP 地址')
        return
      }
      const res = await api.netboxApi.createIpAddress({
        address: createModal.form.address.trim(),
        status: createModal.form.status,
        dns_name: createModal.form.dns_name?.trim() || '',
        description: createModal.form.description || '',
      })
      message.success(res.msg || 'IP 已新增')
    } else {
      if (!String(createModal.form.prefix || '').trim()) {
        message.warning('请填写 IP 前缀')
        return
      }
      const res = await api.netboxApi.createPrefix({
        prefix: createModal.form.prefix.trim(),
        status: createModal.form.status,
        supplier: createModal.form.supplier || '',
        customer_id: createModal.form.customer_id,
        role_id: createModal.form.role_id,
        scope_type: createModal.form.scope_type,
        scope_id: createModal.form.scope_id,
        vlan_id: createModal.form.vlan_id,
        description: createModal.form.description || '',
      })
      message.success(res.msg || '前缀已新增')
    }
    createModal.show = false
    await fetchOverview()
    if (selectedPrefix.value && showIpModal.value) {
      await fetchPrefixIps()
    }
  } catch (error) {
    message.error(error.message || '新增失败')
  } finally {
    createModal.saving = false
  }
}

async function openPrefixEditModal(row) {
  await loadPrefixFieldOptions()
  ensureStringOption(prefixFieldOptions.suppliers, row.supplier === '未指定' ? '' : row.supplier || '')
  prefixEditModal.row = row
  prefixEditModal.form.prefix = row.prefix || ''
  prefixEditModal.form.status = row.status || 'active'
  prefixEditModal.form.supplier = row.supplier === '未指定' ? '' : row.supplier || ''
  prefixEditModal.form.customer_id = row.tenant_id || optionValueByLabel(prefixFieldOptions.tenants, row.customer)
  prefixEditModal.form.role_id = row.role_id || optionValueByLabel(prefixFieldOptions.roles, row.role)
  prefixEditModal.form.scope_type = row.scope_type || 'dcim.site'
  prefixEditModal.form.scope_id = row.scope_id || optionValueByLabel(prefixFieldOptions.sites, row.region || row.scope || row.site)
  prefixEditModal.form.vlan_id = row.vlan_id || optionValueByLabel(prefixFieldOptions.vlans, row.vlan)
  prefixEditModal.form.description = row.description || ''
  prefixEditModal.show = true
}

async function savePrefix() {
  const id = Number(prefixEditModal.row?.id)
  if (!Number.isFinite(id)) return
  if (!String(prefixEditModal.form.prefix || '').trim()) {
    message.warning('请填写 IP 前缀')
    return
  }
  prefixEditModal.saving = true
  try {
    const res = await api.netboxApi.updatePrefix(id, {
      prefix: prefixEditModal.form.prefix.trim(),
      status: prefixEditModal.form.status,
      supplier: prefixEditModal.form.supplier || '',
      customer_id: prefixEditModal.form.customer_id,
      role_id: prefixEditModal.form.role_id,
      scope_type: prefixEditModal.form.scope_type,
      scope_id: prefixEditModal.form.scope_id,
      vlan_id: prefixEditModal.form.vlan_id,
      description: prefixEditModal.form.description || '',
    })
    message.success(res.msg || '前缀已更新')
    prefixEditModal.show = false
    await fetchOverview()
  } catch (error) {
    message.error(error.message || '更新前缀失败')
  } finally {
    prefixEditModal.saving = false
  }
}

async function deletePrefix(row) {
  const id = Number(row?.id)
  if (!Number.isFinite(id)) return
  try {
    const res = await api.netboxApi.deletePrefix(id)
    message.success(res.msg || '前缀已删除')
    if (selectedPrefix.value?.id === row.id) {
      selectedPrefix.value = null
      showIpModal.value = false
      ipRows.value = []
      ipPagination.itemCount = 0
    }
    await fetchOverview()
  } catch (error) {
    message.error(error.message || '删除前缀失败')
  }
}

function openIpEditModal(row) {
  ipEditModal.row = row
  ipEditModal.form.address = row.address || ''
  ipEditModal.form.status = row.status || 'active'
  ipEditModal.form.dns_name = row.dns_name || ''
  ipEditModal.form.description = row.description || ''
  ipEditModal.show = true
}

async function saveIpAddress() {
  const id = Number(ipEditModal.row?.id)
  if (!Number.isFinite(id)) return
  if (!String(ipEditModal.form.address || '').trim()) {
    message.warning('请填写 IP 地址')
    return
  }
  ipEditModal.saving = true
  try {
    const res = await api.netboxApi.updateIpAddress(id, {
      address: ipEditModal.form.address.trim(),
      status: ipEditModal.form.status,
      dns_name: ipEditModal.form.dns_name?.trim() || '',
      description: ipEditModal.form.description || '',
    })
    message.success(res.msg || 'IP 已更新')
    ipEditModal.show = false
    await fetchPrefixIps()
  } catch (error) {
    message.error(error.message || '更新 IP 失败')
  } finally {
    ipEditModal.saving = false
  }
}

async function deleteIpAddress(row) {
  const id = Number(row?.id)
  if (!Number.isFinite(id)) return
  try {
    const res = await api.netboxApi.deleteIpAddress(id)
    message.success(res.msg || 'IP 已删除')
    await fetchPrefixIps()
  } catch (error) {
    message.error(error.message || '删除 IP 失败')
  }
}

function handleFilterChange() {
  if (searchTimer) {
    clearTimeout(searchTimer)
    searchTimer = null
  }
  prefixPagination.page = 1
  fetchOverview()
}

function handleSearchInput() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    handleFilterChange()
  }, 400)
}

async function fetchPrefixIps() {
  if (!selectedPrefix.value?.prefix) return
  ipLoading.value = true
  try {
    const res = await api.netboxApi.prefixIps({
      prefix: selectedPrefix.value.prefix,
      prefix_id: Number.isFinite(Number(selectedPrefix.value.id)) ? selectedPrefix.value.id : undefined,
      page: ipPagination.page,
      page_size: ipPagination.pageSize,
    })
    ipRows.value = res.data?.items || []
    ipPagination.itemCount = Number(res.data?.total || 0)
  } catch (error) {
    message.error(error.message || '璇诲彇 NetBox IP 鏁版嵁澶辫触')
  } finally {
    ipLoading.value = false
  }
}

async function fetchOverview() {
  loading.value = true
  try {
    const res = await api.netboxApi.ipamOverview({
      search: filters.search?.trim() || undefined,
      region: filters.region || undefined,
      customer: filters.customer || undefined,
      supplier: filters.supplier || undefined,
      page: prefixPagination.page,
      page_size: prefixPagination.pageSize,
    })
    Object.assign(summary, res.data?.summary || {})
    prefixes.value = res.data?.prefixes || []
    prefixPagination.itemCount = Number(res.data?.total || prefixes.value.length)
    const currentPrefix = selectedPrefix.value?.prefix
    selectedPrefix.value = currentPrefix ? prefixes.value.find((item) => item.prefix === currentPrefix) || null : null
    if (selectedPrefix.value && showIpModal.value) {
      ipPagination.page = 1
      fetchPrefixIps()
    } else if (!selectedPrefix.value) {
      showIpModal.value = false
      ipRows.value = []
      ipPagination.itemCount = 0
    }
  } catch (error) {
    message.error(error.message || '读取 NetBox IPAM 数据失败')
  } finally {
    loading.value = false
  }
}

async function fetchFilterOptions() {
  try {
    const res = await api.netboxApi.ipamFilterOptions()
    Object.assign(filterOptions, res.data || { regions: [], customers: [], suppliers: [] })
  } catch (error) {
    message.error(error.message || '加载 IPAM 过滤选项失败')
  }
}

async function syncPveIps() {
  syncLoading.value = true
  try {
    const res = await api.netboxApi.syncPveIps()
    message.success(res.msg || 'PVE IP 同步任务已提交')
  } catch (error) {
    message.error(error.message || '提交 PVE IP 同步任务失败')
  } finally {
    syncLoading.value = false
  }
}

onMounted(() => {
  fetchOverview()
  fetchFilterOptions()
})
</script>

<style scoped>
.ipam-page {
  box-sizing: border-box;
  display: flex;
  height: calc(100vh - 92px);
  min-height: 0;
  flex-direction: column;
  padding: 12px;
  overflow: hidden;
  background: #f4f7fb;
}

.ipam-toolbar,
.tree-table-panel {
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 12px 30px rgba(15, 23, 42, 0.04);
}

.ipam-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
}

.detail-head h3 {
  margin: 0;
  color: #0f172a;
  letter-spacing: 0;
}

.eyebrow {
  color: #64748b;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}

.toolbar-filters {
  display: grid;
  width: 100%;
  flex: 1;
  grid-template-columns: minmax(220px, 1.25fr) repeat(3, minmax(160px, 1fr));
  gap: 8px;
}

.toolbar-actions {
  display: flex;
  flex-shrink: 0;
  gap: 8px;
  justify-content: flex-end;
}

.tree-table-panel {
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  margin-top: 8px;
  padding: 12px;
}

.prefix-table {
  min-height: 0;
  flex: 1;
}

.detail-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}

.detail-head p {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 12px;
}

.prefix-link {
  display: inline-flex;
  max-width: 100%;
  align-items: center;
  gap: 8px;
  border: 0;
  background: transparent;
  color: #0369a1;
  cursor: pointer;
  font: inherit;
  font-weight: 700;
  padding: 0;
}

.prefix-link span:last-child {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.usage-cell {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 48px;
  align-items: center;
  gap: 8px;
}

.usage-cell span {
  color: #334155;
  font-size: 12px;
  text-align: right;
}

.detail-meter {
  display: grid;
  justify-items: center;
  gap: 6px;
  min-width: 120px;
  color: #475569;
}

html.dark .ipam-page {
  background: #0f172a;
}

html.dark .ipam-toolbar,
html.dark .tree-table-panel {
  border-color: rgba(148, 163, 184, 0.22);
  background: rgba(17, 24, 39, 0.92);
  box-shadow: none;
}

html.dark .detail-head h3 {
  color: #e5e7eb;
}

html.dark .prefix-link {
  color: #7dd3fc;
}

:deep(.ip-detail-modal) {
  width: min(1080px, calc(100vw - 48px));
}

:deep(.ip-edit-modal) {
  width: min(680px, calc(100vw - 48px));
}

:deep(.ip-detail-modal .n-card__content) {
  max-height: calc(100vh - 150px);
  overflow: auto;
}

:deep(.ip-detail-modal .ip-table) {
  min-height: 260px;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.scope-selects {
  display: grid;
  grid-template-columns: minmax(180px, 0.45fr) minmax(220px, 0.55fr);
  gap: 8px;
  width: 100%;
}

@media (max-width: 1180px) {
  .toolbar-filters {
    grid-template-columns: repeat(2, minmax(180px, 1fr));
  }
}

@media (max-width: 760px) {
  .ipam-toolbar,
  .detail-head {
    align-items: stretch;
    flex-direction: column;
  }

  .toolbar-filters {
    grid-template-columns: 1fr;
  }

  .toolbar-actions {
    justify-content: stretch;
  }

  .toolbar-actions :deep(.n-button) {
    width: 100%;
  }
}
</style>
