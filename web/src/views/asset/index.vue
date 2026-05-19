<template>
  <AppPage :show-footer="false">
    <div class="asset-page">
      <section class="asset-layout">
        <aside class="asset-sidebar">
          <div class="panel-head">
            <div>
              <span class="eyebrow">Location</span>
              <h2>区域结构</h2>
            </div>
            <n-dropdown trigger="click" :options="createOptions" @select="handleCreateSelect">
              <n-button secondary circle>
                <template #icon>
                  <TheIcon icon="mdi:plus" :size="18" />
                </template>
              </n-button>
            </n-dropdown>
          </div>

          <n-empty v-if="!treeData.length && !loading.tree" description="暂无区域数据" />
          <n-tree
            v-else
            block-line
            block-node
            :data="treeData"
            :loading="loading.tree"
            :selected-keys="selectedKeys"
            key-field="id"
            label-field="label"
            children-field="children"
            @update:selected-keys="handleTreeSelect"
          />
        </aside>

        <main class="asset-main">
          <section class="summary-band">
            <article>
              <span>区域</span>
              <strong>{{ regionOptions.length }}</strong>
            </article>
            <article>
              <span>位置</span>
              <strong>{{ locationOptions.length }}</strong>
            </article>
            <article>
              <span>机柜</span>
              <strong>{{ cabinetOptions.length }}</strong>
            </article>
            <article>
              <span>{{ isInventoryView ? '当前库存项' : '当前设备' }}</span>
              <strong>{{ pagination.itemCount }}</strong>
            </article>
          </section>

          <section class="filter-panel">
            <n-input
              v-model:value="filters.keyword"
              clearable
              :placeholder="isInventoryView ? '分类 / 子类 / 备注' : '资产编号 / 名称 / SN / IP'"
              @keyup.enter="loadCurrentList"
            >
              <template #prefix>
                <TheIcon icon="mdi:magnify" :size="18" />
              </template>
            </n-input>
            <n-select
              v-if="isInventoryView"
              v-model:value="filters.inventoryType"
              clearable
              placeholder="库存分类"
              :options="inventoryTypeOptions"
              @update:value="handleInventoryFilterTypeChange"
            />
            <n-select
              v-if="isInventoryView"
              v-model:value="filters.inventorySubtype"
              clearable
              placeholder="库存子类"
              :options="filterInventorySubtypeOptions"
            />
            <n-select
              v-else
              v-model:value="filters.deviceType"
              clearable
              placeholder="设备类型"
              :options="deviceTypeOptions"
            />
            <n-select
              v-if="!isInventoryView"
              v-model:value="filters.deviceStatus"
              clearable
              placeholder="设备状态"
              :options="deviceStatusOptions"
            />
            <n-button secondary @click="resetFilters">重置</n-button>
            <n-button type="primary" @click="loadCurrentList">搜索</n-button>
          </section>

          <section class="content-panel">
            <div class="panel-head">
              <div>
                <span class="eyebrow">{{ selectedLabel }}</span>
                <h2>{{ isInventoryView ? '库存列表' : '设备列表' }}</h2>
              </div>
              <div class="toolbar-actions">
                <n-button v-if="isInventoryView" secondary @click="categoryModal.show = true">
                  <template #icon>
                    <TheIcon icon="mdi:shape-plus-outline" :size="18" />
                  </template>
                  分类维护
                </n-button>
                <n-button secondary @click="openContextModal">
                  <template #icon>
                    <TheIcon :icon="contextIcon" :size="18" />
                  </template>
                  {{ contextActionText }}
                </n-button>
                <n-button type="primary" @click="openPrimaryModal()">
                  <template #icon>
                    <TheIcon
                      :icon="isInventoryView ? 'mdi:package-variant-plus' : 'mdi:server-plus'"
                      :size="18"
                    />
                  </template>
                  {{ isInventoryView ? '新增库存' : '新增设备' }}
                </n-button>
              </div>
            </div>

            <n-data-table
              remote
              :loading="loading.list"
              :columns="isInventoryView ? inventoryColumns : deviceColumns"
              :data="isInventoryView ? inventoryItems : devices"
              :pagination="pagination"
              :row-key="(row) => row.id"
              @update:page="handlePageChange"
              @update:page-size="handlePageSizeChange"
            />
          </section>
        </main>
      </section>

      <n-modal
        v-model:show="inventoryModal.show"
        preset="card"
        :title="inventoryModal.form.id ? '编辑库存' : '新增库存'"
        class="asset-modal"
      >
        <n-form
          ref="inventoryFormRef"
          :model="inventoryModal.form"
          :rules="inventoryRules"
          label-placement="left"
          label-width="90"
        >
          <n-grid :cols="2" :x-gap="16">
            <n-form-item-gi label="库存位置" path="location_id">
              <n-select
                v-model:value="inventoryModal.form.location_id"
                filterable
                :options="inventoryLocationOptions"
              />
            </n-form-item-gi>
            <n-form-item-gi label="分类" path="type">
              <n-select
                v-model:value="inventoryModal.form.type"
                filterable
                tag
                :options="inventoryTypeOptions"
                @update:value="handleInventoryTypeChange"
              />
            </n-form-item-gi>
            <n-form-item-gi label="子类">
              <n-select
                v-model:value="inventoryModal.form.subtype"
                clearable
                filterable
                tag
                :options="modalInventorySubtypeOptions"
              />
            </n-form-item-gi>
            <n-form-item-gi label="数量" path="quantity">
              <n-input-number v-model:value="inventoryModal.form.quantity" :min="0" />
            </n-form-item-gi>
            <n-form-item-gi :span="2" label="扩展属性">
              <div class="attribute-editor">
                <div
                  v-for="(attr, index) in inventoryModal.form.attributeList"
                  :key="index"
                  class="attribute-row"
                >
                  <n-input v-model:value="attr.key" placeholder="属性名，如规格型号" />
                  <n-input v-model:value="attr.value" placeholder="属性值" />
                  <n-button secondary circle @click="removeInventoryAttribute(index)">
                    <template #icon>
                      <TheIcon icon="mdi:minus" :size="16" />
                    </template>
                  </n-button>
                </div>
                <n-button secondary @click="addInventoryAttribute">
                  <template #icon>
                    <TheIcon icon="mdi:plus" :size="16" />
                  </template>
                  添加属性
                </n-button>
              </div>
            </n-form-item-gi>
            <n-form-item-gi :span="2" label="备注">
              <n-input v-model:value="inventoryModal.form.remark" type="textarea" />
            </n-form-item-gi>
          </n-grid>
        </n-form>
        <template #footer>
          <div class="modal-footer">
            <n-button @click="inventoryModal.show = false">取消</n-button>
            <n-button type="primary" :loading="inventoryModal.submitting" @click="submitInventory"
              >保存</n-button
            >
          </div>
        </template>
      </n-modal>

      <n-modal
        v-model:show="deviceModal.show"
        preset="card"
        :title="deviceModal.form.id ? '编辑设备' : '新增设备'"
        class="asset-modal"
      >
        <n-form
          ref="deviceFormRef"
          :model="deviceModal.form"
          :rules="deviceRules"
          label-placement="left"
          label-width="90"
        >
          <n-grid :cols="2" :x-gap="16">
            <n-form-item-gi label="所属机柜" path="cabinet_id">
              <n-select
                v-model:value="deviceModal.form.cabinet_id"
                filterable
                :options="cabinetOptions"
              />
            </n-form-item-gi>
            <n-form-item-gi label="资产编号" path="asset_no">
              <n-input v-model:value="deviceModal.form.asset_no" />
            </n-form-item-gi>
            <n-form-item-gi label="设备名称" path="name">
              <n-input v-model:value="deviceModal.form.name" />
            </n-form-item-gi>
            <n-form-item-gi label="设备类型">
              <n-select v-model:value="deviceModal.form.type" :options="deviceTypeOptions" />
            </n-form-item-gi>
            <n-form-item-gi label="品牌">
              <n-input v-model:value="deviceModal.form.brand" />
            </n-form-item-gi>
            <n-form-item-gi label="型号">
              <n-input v-model:value="deviceModal.form.model" />
            </n-form-item-gi>
            <n-form-item-gi label="序列号">
              <n-input v-model:value="deviceModal.form.serial_no" />
            </n-form-item-gi>
            <n-form-item-gi label="状态">
              <n-select v-model:value="deviceModal.form.status" :options="deviceStatusOptions" />
            </n-form-item-gi>
            <n-form-item-gi label="起始U位">
              <n-input-number v-model:value="deviceModal.form.u_position" clearable :min="1" />
            </n-form-item-gi>
            <n-form-item-gi label="占用U数">
              <n-input-number v-model:value="deviceModal.form.u_height" :min="1" />
            </n-form-item-gi>
            <n-form-item-gi label="管理IP">
              <n-input v-model:value="deviceModal.form.mgmt_ip" />
            </n-form-item-gi>
            <n-form-item-gi label="业务IP">
              <n-input v-model:value="deviceModal.form.business_ip" />
            </n-form-item-gi>
            <n-form-item-gi :span="2" label="备注">
              <n-input v-model:value="deviceModal.form.remark" type="textarea" />
            </n-form-item-gi>
          </n-grid>
        </n-form>
        <template #footer>
          <div class="modal-footer">
            <n-button @click="deviceModal.show = false">取消</n-button>
            <n-button type="primary" :loading="deviceModal.submitting" @click="submitDevice"
              >保存</n-button
            >
          </div>
        </template>
      </n-modal>

      <n-modal
        v-model:show="simpleModal.show"
        preset="card"
        :title="simpleModal.title"
        class="simple-modal"
      >
        <n-form
          ref="simpleFormRef"
          :model="simpleModal.form"
          :rules="simpleRules"
          label-placement="left"
          label-width="80"
        >
          <template v-if="simpleModal.kind === 'region'">
            <n-form-item label="区域名称" path="name">
              <n-input v-model:value="simpleModal.form.name" />
            </n-form-item>
            <n-form-item label="区域编码" path="code">
              <n-input v-model:value="simpleModal.form.code" />
            </n-form-item>
          </template>
          <template v-if="simpleModal.kind === 'location'">
            <n-form-item label="所属区域" path="region_id">
              <n-select v-model:value="simpleModal.form.region_id" :options="regionOptions" />
            </n-form-item>
            <n-form-item label="位置名称" path="name">
              <n-input v-model:value="simpleModal.form.name" />
            </n-form-item>
            <n-form-item label="位置类型">
              <n-radio-group v-model:value="simpleModal.form.type">
                <n-radio-button :value="0">库存</n-radio-button>
                <n-radio-button :value="1">机房</n-radio-button>
              </n-radio-group>
            </n-form-item>
            <n-form-item label="地址">
              <n-input v-model:value="simpleModal.form.address" />
            </n-form-item>
          </template>
          <template v-if="simpleModal.kind === 'cabinet'">
            <n-form-item label="所属位置" path="location_id">
              <n-select
                v-model:value="simpleModal.form.location_id"
                filterable
                :options="locationOptions"
              />
            </n-form-item>
            <n-form-item label="机柜名称" path="name">
              <n-input v-model:value="simpleModal.form.name" />
            </n-form-item>
            <n-form-item label="机柜编码">
              <n-input v-model:value="simpleModal.form.code" />
            </n-form-item>
            <n-form-item label="容量U数">
              <n-input-number v-model:value="simpleModal.form.capacity_u" :min="1" />
            </n-form-item>
          </template>
          <n-form-item label="备注">
            <n-input v-model:value="simpleModal.form.remark" type="textarea" />
          </n-form-item>
          <n-form-item label="启用">
            <n-switch v-model:value="simpleModal.form.status" />
          </n-form-item>
        </n-form>
        <template #footer>
          <div class="modal-footer">
            <n-button v-if="simpleModal.form.id" type="error" ghost @click="deleteSimple"
              >删除</n-button
            >
            <span></span>
            <n-button @click="simpleModal.show = false">取消</n-button>
            <n-button type="primary" :loading="simpleModal.submitting" @click="submitSimple"
              >保存</n-button
            >
          </div>
        </template>
      </n-modal>

      <n-modal
        v-model:show="categoryModal.show"
        preset="card"
        title="分类维护"
        class="simple-modal"
      >
        <div class="category-editor">
          <div class="category-add">
            <n-input v-model:value="categoryModal.categoryName" placeholder="新增分类" />
            <n-button type="primary" @click="addInventoryCategory">添加</n-button>
          </div>
          <div
            v-for="category in inventoryCategoryTree"
            :key="category.value"
            class="category-block"
          >
            <div class="category-title">
              <strong>{{ category.label }}</strong>
              <n-button text type="error" @click="deleteInventoryCategory(category.value)"
                >删除</n-button
              >
            </div>
            <div class="subcategory-list">
              <n-tag
                v-for="child in category.children"
                :key="child"
                closable
                @close="deleteInventorySubtype(category.value, child)"
              >
                {{ child }}
              </n-tag>
            </div>
            <div class="category-add">
              <n-input
                v-model:value="categoryModal.subtypeDrafts[category.value]"
                placeholder="新增子类"
              />
              <n-button secondary @click="addInventorySubtype(category.value)">添加子类</n-button>
            </div>
          </div>
        </div>
      </n-modal>
    </div>
  </AppPage>
</template>

<script setup>
import { computed, h, onMounted, reactive, ref } from 'vue'
import api from '@/api'
import TheIcon from '@/components/icon/TheIcon.vue'

defineOptions({ name: 'AssetManagement' })

const treeData = ref([])
const selectedNode = ref(null)
const selectedKeys = ref([])
const devices = ref([])
const inventoryItems = ref([])
const regions = ref([])
const locations = ref([])
const cabinets = ref([])
const deviceFormRef = ref(null)
const inventoryFormRef = ref(null)
const simpleFormRef = ref(null)

const loading = reactive({ tree: false, list: false })
const filters = reactive({
  keyword: '',
  deviceType: null,
  deviceStatus: null,
  inventoryType: '',
  inventorySubtype: '',
})
const pagination = reactive({
  page: 1,
  pageSize: 10,
  itemCount: 0,
  showSizePicker: true,
  pageSizes: [10, 20, 50],
})

const deviceModal = reactive({ show: false, submitting: false, form: createEmptyDevice() })
const inventoryModal = reactive({ show: false, submitting: false, form: createEmptyInventory() })
const simpleModal = reactive({
  show: false,
  submitting: false,
  kind: 'region',
  title: '',
  form: {},
})
const categoryModal = reactive({
  show: false,
  categoryName: '',
  subtypeDrafts: {},
})

const deviceTypeOptions = [
  { label: '服务器', value: 0 },
  { label: '交换机', value: 1 },
  { label: '路由器', value: 2 },
  { label: '防火墙', value: 3 },
  { label: 'PDU', value: 4 },
  { label: '配件', value: 5 },
  { label: '其他', value: 99 },
]

const deviceStatusOptions = [
  { label: '库存', value: 0 },
  { label: '上架运行', value: 1 },
  { label: '维护中', value: 2 },
  { label: '故障', value: 3 },
  { label: '下架', value: 4 },
  { label: '报废', value: 5 },
]

const createOptions = [
  { label: '新增区域', key: 'region' },
  { label: '新增位置', key: 'location' },
  { label: '新增机柜', key: 'cabinet' },
]

const INVENTORY_CATEGORY_STORAGE_KEY = 'asset_inventory_category_tree'

const defaultInventoryCategoryTree = [
  { label: '光模块', value: '光模块', children: ['100G', '40G', '25G', '10G', '1G'] },
  { label: '光纤', value: '光纤', children: ['单模', '多模', 'MPO'] },
  { label: '网线', value: '网线', children: [] },
  { label: '电源线', value: '电源线', children: [] },
  { label: '调试线', value: '调试线', children: [] },
  { label: 'DAC', value: 'DAC', children: [] },
  { label: 'AOC', value: 'AOC', children: [] },
  {
    label: '服务器配件',
    value: '服务器配件',
    children: ['CPU', '内存', '硬盘', '网卡', '导轨', '背板'],
  },
  { label: '工具', value: '工具', children: ['螺丝刀', '扎带', '标签机', '手套'] },
]

const inventoryCategoryTree = ref(loadInventoryCategoryTree())
const inventoryTypeOptions = computed(() =>
  inventoryCategoryTree.value.map(({ label, value }) => ({ label, value }))
)

const deviceRules = {
  cabinet_id: {
    required: true,
    type: 'number',
    message: '请选择机柜',
    trigger: ['change', 'blur'],
  },
  asset_no: { required: true, message: '请输入资产编号', trigger: ['input', 'blur'] },
  name: { required: true, message: '请输入设备名称', trigger: ['input', 'blur'] },
}

const inventoryRules = {
  location_id: {
    required: true,
    type: 'number',
    message: '请选择库存位置',
    trigger: ['change', 'blur'],
  },
  type: { required: true, message: '请输入类型', trigger: ['input', 'blur'] },
  quantity: { required: true, type: 'number', message: '请输入数量', trigger: ['change', 'blur'] },
}

const simpleRules = {
  name: { required: true, message: '请输入名称', trigger: ['input', 'blur'] },
  code: { required: true, message: '请输入编码', trigger: ['input', 'blur'] },
  region_id: { required: true, type: 'number', message: '请选择区域', trigger: ['change', 'blur'] },
  location_id: {
    required: true,
    type: 'number',
    message: '请选择位置',
    trigger: ['change', 'blur'],
  },
}

const selectedLabel = computed(() => selectedNode.value?.label || '全部资产')
const selectedLocation = computed(() => {
  if (selectedNode.value?.type === 'location')
    return locations.value.find((item) => item.id === selectedNode.value.raw_id)
  if (selectedNode.value?.type === 'cabinet') {
    const cabinet = cabinets.value.find((item) => item.id === selectedNode.value.raw_id)
    return locations.value.find((item) => item.id === cabinet?.location_id)
  }
  return null
})
const isInventoryView = computed(() => selectedLocation.value?.type === 0)

const regionOptions = computed(() =>
  regions.value.map((item) => ({ label: `${item.name} (${item.code})`, value: item.id }))
)
const locationOptions = computed(() =>
  locations.value.map((item) => {
    const region = regions.value.find((region) => region.id === item.region_id)
    return {
      label: `${region?.name || '-'} / ${item.type === 0 ? '库存' : '机房'} / ${item.name}`,
      value: item.id,
    }
  })
)
const inventoryLocationOptions = computed(() =>
  locations.value
    .filter((item) => item.type === 0)
    .map((item) => {
      const region = regions.value.find((region) => region.id === item.region_id)
      return { label: `${region?.name || '-'} / ${item.name}`, value: item.id }
    })
)

const filterInventorySubtypeOptions = computed(() =>
  getInventorySubtypeOptions(filters.inventoryType)
)

const modalInventorySubtypeOptions = computed(() =>
  getInventorySubtypeOptions(inventoryModal.form.type)
)

const cabinetOptions = computed(() =>
  cabinets.value.map((item) => {
    const location = locations.value.find((location) => location.id === item.location_id)
    return { label: `${location?.name || '-'} / ${item.name}`, value: item.id }
  })
)
const contextActionText = computed(() => {
  if (!selectedNode.value) return '新增区域'
  if (selectedNode.value.type === 'region') return '编辑区域'
  if (selectedNode.value.type === 'location') return '编辑位置'
  return '编辑机柜'
})
const contextIcon = computed(() => {
  if (!selectedNode.value) return 'mdi:map-marker-plus-outline'
  if (selectedNode.value.type === 'region') return 'mdi:map-marker-radius-outline'
  if (selectedNode.value.type === 'location') return 'mdi:warehouse'
  return 'mdi:server-network'
})

const inventoryColumns = computed(() => [
  { title: '分类', key: 'type', width: 120 },
  { title: '子类', key: 'subtype', width: 120 },
  {
    title: '数量',
    key: 'quantity',
    width: 110,
  },
  {
    title: '扩展属性',
    key: 'attributes',
    minWidth: 260,
    render(row) {
      return formatAttributes(row.attributes)
    },
  },
  {
    title: '操作',
    key: 'actions',
    width: 150,
    render(row) {
      return h('div', { class: 'table-actions' }, [
        h('button', { class: 'link-button', onClick: () => openInventoryModal(row) }, '编辑'),
        h('button', { class: 'danger-button', onClick: () => deleteInventory(row) }, '删除'),
      ])
    },
  },
])

const deviceColumns = computed(() => [
  { title: '资产编号', key: 'asset_no', width: 150 },
  { title: '设备名称', key: 'name', minWidth: 160 },
  { title: '类型', key: 'type', width: 100, render: (row) => getDeviceType(row.type) },
  { title: '状态', key: 'status', width: 110, render: (row) => getDeviceStatus(row.status) },
  { title: '区域', key: 'region_name', width: 120 },
  { title: '位置', key: 'location_name', width: 140 },
  { title: '机柜', key: 'cabinet_name', width: 120 },
  { title: 'SN', key: 'serial_no', minWidth: 140 },
  { title: '管理IP', key: 'mgmt_ip', width: 130 },
  {
    title: '操作',
    key: 'actions',
    width: 150,
    render(row) {
      return h('div', { class: 'table-actions' }, [
        h('button', { class: 'link-button', onClick: () => openDeviceModal(row) }, '编辑'),
        h('button', { class: 'danger-button', onClick: () => deleteDevice(row) }, '删除'),
      ])
    },
  },
])

function createEmptyDevice() {
  return {
    cabinet_id: null,
    asset_no: '',
    name: '',
    type: 0,
    brand: '',
    model: '',
    serial_no: '',
    u_position: null,
    u_height: 1,
    status: 0,
    mgmt_ip: '',
    business_ip: '',
    owner: '',
    purchase_date: null,
    warranty_expire: null,
    remark: '',
  }
}

function createEmptyInventory() {
  return {
    location_id: null,
    type: '',
    subtype: '',
    quantity: 1,
    attributes: {},
    attributeList: [],
    remark: '',
    status: true,
  }
}

async function refreshAll() {
  await Promise.all([loadMeta(), loadTree()])
  await loadCurrentList()
}

async function loadMeta() {
  const [regionRes, locationRes, cabinetRes] = await Promise.all([
    api.assetApi.regions({ page_size: 1000 }),
    api.assetApi.locations({ page_size: 1000 }),
    api.assetApi.cabinets({ page_size: 1000 }),
  ])
  regions.value = regionRes.data || []
  locations.value = locationRes.data || []
  cabinets.value = cabinetRes.data || []
}

async function loadTree() {
  loading.tree = true
  try {
    const res = await api.assetApi.tree()
    treeData.value = res.data || []
  } finally {
    loading.tree = false
  }
}

async function loadCurrentList() {
  if (isInventoryView.value) {
    await loadInventory()
  } else {
    await loadDevices()
  }
}

async function loadDevices() {
  loading.list = true
  try {
    const res = await api.assetApi.devices({
      page: pagination.page,
      page_size: pagination.pageSize,
      keyword: filters.keyword || undefined,
      type: filters.deviceType ?? undefined,
      status: filters.deviceStatus ?? undefined,
      ...getSelectedParams(),
    })
    devices.value = res.data || []
    pagination.itemCount = res.total || 0
  } finally {
    loading.list = false
  }
}

async function loadInventory() {
  loading.list = true
  try {
    const res = await api.assetApi.inventory({
      page: pagination.page,
      page_size: pagination.pageSize,
      keyword: filters.keyword || undefined,
      type: filters.inventoryType || undefined,
      subtype: filters.inventorySubtype || undefined,
      ...getSelectedParams(),
    })
    inventoryItems.value = res.data || []
    pagination.itemCount = res.total || 0
  } finally {
    loading.list = false
  }
}

function getSelectedParams() {
  if (!selectedNode.value) return {}
  if (isInventoryView.value && selectedNode.value.type === 'cabinet') {
    return { location_id: selectedLocation.value?.id }
  }
  const keyMap = { region: 'region_id', location: 'location_id', cabinet: 'cabinet_id' }
  return { [keyMap[selectedNode.value.type]]: selectedNode.value.raw_id }
}

function handleTreeSelect(keys, options) {
  selectedKeys.value = keys
  selectedNode.value = options?.[0] || null
  pagination.page = 1
  loadCurrentList()
}

function handlePageChange(page) {
  pagination.page = page
  loadCurrentList()
}

function handlePageSizeChange(pageSize) {
  pagination.pageSize = pageSize
  pagination.page = 1
  loadCurrentList()
}

function resetFilters() {
  filters.keyword = ''
  filters.deviceType = null
  filters.deviceStatus = null
  filters.inventoryType = ''
  filters.inventorySubtype = ''
  pagination.page = 1
  loadCurrentList()
}

function openPrimaryModal(row = null) {
  if (isInventoryView.value) openInventoryModal(row)
  else openDeviceModal(row)
}

function handleCreateSelect(kind) {
  openSimpleModal(kind)
}

function openContextModal() {
  if (!selectedNode.value) openSimpleModal('region')
  else openSimpleModal(selectedNode.value.type, selectedNode.value)
}

function openSimpleModal(kind, node = null) {
  simpleModal.kind = kind
  simpleModal.title = `${node ? '编辑' : '新增'}${kindName(kind)}`
  simpleModal.form = createSimpleForm(kind, node)
  simpleModal.show = true
}

function createSimpleForm(kind, node) {
  if (kind === 'region') {
    const row = node ? regions.value.find((item) => item.id === node.raw_id) : null
    return {
      id: row?.id,
      name: row?.name || '',
      code: row?.code || '',
      remark: row?.remark || '',
      status: row?.status ?? true,
    }
  }
  if (kind === 'location') {
    const row = node ? locations.value.find((item) => item.id === node.raw_id) : null
    return {
      id: row?.id,
      region_id: row?.region_id || selectedRegionId(),
      name: row?.name || '',
      type: row?.type ?? 1,
      address: row?.address || '',
      remark: row?.remark || '',
      status: row?.status ?? true,
    }
  }
  const row = node ? cabinets.value.find((item) => item.id === node.raw_id) : null
  return {
    id: row?.id,
    location_id: row?.location_id || selectedLocationId(),
    name: row?.name || '',
    code: row?.code || '',
    capacity_u: row?.capacity_u || 42,
    row: row?.row || '',
    column: row?.column || '',
    remark: row?.remark || '',
    status: row?.status ?? true,
  }
}

function selectedRegionId() {
  if (selectedNode.value?.type === 'region') return selectedNode.value.raw_id
  return selectedLocation.value?.region_id || regionOptions.value[0]?.value || null
}

function selectedLocationId() {
  if (selectedNode.value?.type === 'location') return selectedNode.value.raw_id
  if (selectedNode.value?.type === 'cabinet')
    return cabinets.value.find((item) => item.id === selectedNode.value.raw_id)?.location_id
  return locationOptions.value[0]?.value || null
}

async function submitSimple() {
  await simpleFormRef.value?.validate()
  simpleModal.submitting = true
  try {
    const map = {
      region: [api.assetApi.createRegion, api.assetApi.updateRegion],
      location: [api.assetApi.createLocation, api.assetApi.updateLocation],
      cabinet: [api.assetApi.createCabinet, api.assetApi.updateCabinet],
    }
    const [createFn, updateFn] = map[simpleModal.kind]
    await (simpleModal.form.id ? updateFn(simpleModal.form) : createFn(simpleModal.form))
    window.$message?.success('保存成功')
    simpleModal.show = false
    await refreshAll()
  } finally {
    simpleModal.submitting = false
  }
}

async function deleteSimple() {
  const id = simpleModal.form.id
  if (!id) return
  const map = {
    region: [api.assetApi.deleteRegion, 'region_id'],
    location: [api.assetApi.deleteLocation, 'location_id'],
    cabinet: [api.assetApi.deleteCabinet, 'cabinet_id'],
  }
  const [deleteFn, key] = map[simpleModal.kind]
  await deleteFn({ [key]: id })
  window.$message?.success('删除成功')
  simpleModal.show = false
  selectedKeys.value = []
  selectedNode.value = null
  await refreshAll()
}

function openInventoryModal(row = null) {
  inventoryModal.form = row
    ? {
        ...createEmptyInventory(),
        ...row,
        attributeList: attributesToList(row.attributes),
      }
    : {
        ...createEmptyInventory(),
        location_id:
          selectedLocation.value?.type === 0
            ? selectedLocation.value.id
            : inventoryLocationOptions.value[0]?.value || null,
      }
  inventoryModal.show = true
}

async function submitInventory() {
  await inventoryFormRef.value?.validate()
  inventoryModal.submitting = true
  try {
    const submit = inventoryModal.form.id
      ? api.assetApi.updateInventory
      : api.assetApi.createInventory
    const payload = {
      ...inventoryModal.form,
      attributes: attributeListToObject(inventoryModal.form.attributeList),
    }
    delete payload.attributeList
    await submit(payload)
    window.$message?.success('保存成功')
    inventoryModal.show = false
    await loadInventory()
  } finally {
    inventoryModal.submitting = false
  }
}

async function deleteInventory(row) {
  await api.assetApi.deleteInventory({ inventory_id: row.id })
  window.$message?.success('删除成功')
  loadInventory()
}

function addInventoryAttribute() {
  inventoryModal.form.attributeList.push({ key: '', value: '' })
}

function cloneInventoryCategoryTree(tree = defaultInventoryCategoryTree) {
  return tree.map((item) => ({
    label: item.label,
    value: item.value,
    children: [...(item.children || [])],
  }))
}

function normalizeInventoryCategoryTree(value) {
  if (!Array.isArray(value)) return cloneInventoryCategoryTree()
  const result = []
  value.forEach((item) => {
    const label = String(item?.label || item?.value || '').trim()
    const itemValue = String(item?.value || label).trim()
    if (!label || !itemValue || result.some((category) => category.value === itemValue)) return
    const children = Array.isArray(item.children)
      ? [...new Set(item.children.map((child) => String(child || '').trim()).filter(Boolean))]
      : []
    result.push({ label, value: itemValue, children })
  })
  return result.length ? result : cloneInventoryCategoryTree()
}

function loadInventoryCategoryTree() {
  try {
    const raw = localStorage.getItem(INVENTORY_CATEGORY_STORAGE_KEY)
    return raw ? normalizeInventoryCategoryTree(JSON.parse(raw)) : cloneInventoryCategoryTree()
  } catch {
    return cloneInventoryCategoryTree()
  }
}

function saveInventoryCategoryTree() {
  localStorage.setItem(INVENTORY_CATEGORY_STORAGE_KEY, JSON.stringify(inventoryCategoryTree.value))
}

function addInventoryCategory() {
  const name = categoryModal.categoryName.trim()
  if (!name) return
  if (inventoryCategoryTree.value.some((item) => item.value === name)) {
    window.$message?.warning('分类已存在')
    return
  }
  inventoryCategoryTree.value.push({ label: name, value: name, children: [] })
  categoryModal.categoryName = ''
  saveInventoryCategoryTree()
  window.$message?.success('分类已添加')
}

function deleteInventoryCategory(value) {
  inventoryCategoryTree.value = inventoryCategoryTree.value.filter((item) => item.value !== value)
  if (filters.inventoryType === value) {
    filters.inventoryType = ''
    filters.inventorySubtype = ''
  }
  if (inventoryModal.form.type === value) {
    inventoryModal.form.type = ''
    inventoryModal.form.subtype = ''
  }
  delete categoryModal.subtypeDrafts[value]
  saveInventoryCategoryTree()
  window.$message?.success('分类已删除')
}

function addInventorySubtype(parentValue) {
  const subtype = String(categoryModal.subtypeDrafts[parentValue] || '').trim()
  if (!subtype) return
  const category = inventoryCategoryTree.value.find((item) => item.value === parentValue)
  if (!category) return
  if (category.children.includes(subtype)) {
    window.$message?.warning('子类已存在')
    return
  }
  category.children.push(subtype)
  categoryModal.subtypeDrafts[parentValue] = ''
  saveInventoryCategoryTree()
  window.$message?.success('子类已添加')
}

function deleteInventorySubtype(parentValue, subtype) {
  const category = inventoryCategoryTree.value.find((item) => item.value === parentValue)
  if (!category) return
  category.children = category.children.filter((item) => item !== subtype)
  if (filters.inventoryType === parentValue && filters.inventorySubtype === subtype) {
    filters.inventorySubtype = ''
  }
  if (inventoryModal.form.type === parentValue && inventoryModal.form.subtype === subtype) {
    inventoryModal.form.subtype = ''
  }
  saveInventoryCategoryTree()
  window.$message?.success('子类已删除')
}

function getInventorySubtypeOptions(type) {
  const category = inventoryCategoryTree.value.find((item) => item.value === type)
  return (category?.children || []).map((item) => ({ label: item, value: item }))
}

function handleInventoryTypeChange() {
  const validValues = getInventorySubtypeOptions(inventoryModal.form.type).map((item) => item.value)
  if (inventoryModal.form.subtype && !validValues.includes(inventoryModal.form.subtype)) {
    inventoryModal.form.subtype = ''
  }
}

function handleInventoryFilterTypeChange() {
  const validValues = getInventorySubtypeOptions(filters.inventoryType).map((item) => item.value)
  if (filters.inventorySubtype && !validValues.includes(filters.inventorySubtype)) {
    filters.inventorySubtype = ''
  }
}

function removeInventoryAttribute(index) {
  inventoryModal.form.attributeList.splice(index, 1)
}

function attributesToList(attributes) {
  if (!attributes || typeof attributes !== 'object') return []
  return Object.entries(attributes).map(([key, value]) => ({ key, value: String(value ?? '') }))
}

function attributeListToObject(list) {
  return (list || []).reduce((result, item) => {
    const key = String(item.key || '').trim()
    if (key) result[key] = item.value
    return result
  }, {})
}

function formatAttributes(attributes) {
  const list = attributesToList(attributes)
  if (!list.length) return '-'
  return list.map((item) => `${item.key}: ${item.value}`).join(' / ')
}

function openDeviceModal(row = null) {
  deviceModal.form = row
    ? { ...createEmptyDevice(), ...row }
    : {
        ...createEmptyDevice(),
        cabinet_id:
          selectedNode.value?.type === 'cabinet' && !isInventoryView.value
            ? selectedNode.value.raw_id
            : cabinetOptions.value[0]?.value || null,
      }
  deviceModal.show = true
}

async function submitDevice() {
  await deviceFormRef.value?.validate()
  deviceModal.submitting = true
  try {
    const submit = deviceModal.form.id ? api.assetApi.updateDevice : api.assetApi.createDevice
    await submit(deviceModal.form)
    window.$message?.success('保存成功')
    deviceModal.show = false
    await loadDevices()
  } finally {
    deviceModal.submitting = false
  }
}

async function deleteDevice(row) {
  await api.assetApi.deleteDevice({ device_id: row.id })
  window.$message?.success('删除成功')
  loadDevices()
}

function kindName(kind) {
  return { region: '区域', location: '位置', cabinet: '机柜' }[kind]
}

function getDeviceType(value) {
  return deviceTypeOptions.find((item) => item.value === Number(value))?.label || '其他'
}

function getDeviceStatus(value) {
  return deviceStatusOptions.find((item) => item.value === Number(value))?.label || '未知'
}

onMounted(refreshAll)
</script>

<style scoped>
.asset-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
}

.asset-sidebar,
.content-panel {
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 12px 30px rgba(15, 23, 42, 0.06);
}

.panel-head h2 {
  margin: 4px 0 0;
  color: #0f172a;
  font-size: 22px;
  line-height: 1.2;
}

.panel-head h2 {
  font-size: 18px;
}

.eyebrow {
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}

.toolbar-actions,
.table-actions,
.modal-footer {
  display: flex;
  align-items: center;
  gap: 10px;
}

.asset-layout {
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr);
  gap: 16px;
  min-height: 620px;
}

.asset-sidebar,
.content-panel {
  padding: 16px;
}

.asset-main {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 16px;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.summary-band {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.summary-band article {
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 8px;
  background: #fff;
  padding: 14px 16px;
}

.summary-band span {
  display: block;
  color: #64748b;
  font-size: 13px;
}

.summary-band strong {
  display: block;
  margin-top: 6px;
  color: #0f172a;
  font-size: 24px;
}

.filter-panel {
  display: grid;
  grid-template-columns: minmax(240px, 1fr) 180px 160px auto auto;
  gap: 10px;
}

.link-button,
.danger-button {
  border: 0;
  background: transparent;
  color: #2563eb;
  cursor: pointer;
  font: inherit;
}

.danger-button {
  color: #dc2626;
}

.attribute-editor {
  display: flex;
  width: 100%;
  flex-direction: column;
  gap: 8px;
}

.attribute-row {
  display: grid;
  grid-template-columns: minmax(120px, 1fr) minmax(160px, 1.4fr) 34px;
  gap: 8px;
}

.asset-modal {
  width: min(880px, 92vw);
}

.simple-modal {
  width: min(520px, 92vw);
}

.category-editor {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.category-add {
  display: flex;
  align-items: center;
  gap: 8px;
}

.category-block {
  display: flex;
  flex-direction: column;
  gap: 10px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 8px;
  padding: 12px;
}

.category-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.subcategory-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  min-height: 24px;
}

.modal-footer {
  justify-content: flex-end;
}

.modal-footer span {
  flex: 1;
}

@media (max-width: 960px) {
  .asset-layout,
  .summary-band,
  .filter-panel {
    grid-template-columns: 1fr;
  }

  .panel-head {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
