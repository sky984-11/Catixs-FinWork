<template>
  <AppPage :show-footer="false">
    <div class="product-page">
      <section v-if="mode === 'products'" class="category-panel">
        <div class="panel-head">
          <div>
            <span class="eyebrow">PRODUCT CATALOG</span>
            <h3>产品目录</h3>
          </div>
          <n-button secondary circle @click="openCategoryModal()">
            <template #icon><TheIcon icon="mdi:plus" :size="18" /></template>
          </n-button>
        </div>
        <n-tree
          block-line
          :data="options.categoryTree"
          :expanded-keys="expandedCategoryKeys"
          :selected-keys="selectedCategoryKeys"
          key-field="key"
          label-field="label"
          @update:expanded-keys="(keys) => (expandedCategoryKeys = keys)"
          @update:selected-keys="handleCategorySelect"
        />
        <div class="category-actions">
          <n-button size="small" secondary :disabled="!query.category_id" @click="editSelectedCategory">编辑分类</n-button>
          <n-popconfirm :disabled="!query.category_id" @positive-click="deleteSelectedCategory">
            <template #trigger><n-button size="small" secondary type="error" :disabled="!query.category_id">删除分类</n-button></template>
            确认删除当前分类？
          </n-popconfirm>
        </div>
      </section>

      <section class="product-panel">
        <div class="panel-head">
          <div>
            <span class="eyebrow">PRODUCT CENTER</span>
            <h2>{{ pageTitle }}</h2>
          </div>
          <n-space>
            <n-button secondary circle :loading="loading" title="刷新" @click="loadPage">
              <template #icon><TheIcon icon="mdi:refresh" :size="18" /></template>
            </n-button>
            <n-button type="primary" @click="openEditor()">
              <template #icon><TheIcon :icon="addIcon" :size="18" /></template>
              {{ addText }}
            </n-button>
          </n-space>
        </div>

        <div class="filter-row">
          <n-input v-if="showKeyword" v-model:value="query.keyword" clearable :placeholder="keywordPlaceholder" @keyup.enter="loadPage">
            <template #prefix><TheIcon icon="mdi:magnify" :size="17" /></template>
          </n-input>
          <n-select v-if="mode === 'products'" v-model:value="query.status" clearable :options="options.productStatuses" placeholder="产品状态" />
          <n-select v-if="mode === 'specs'" v-model:value="query.attr_type" clearable :options="options.attributeTypes" placeholder="属性类型" />
          <n-select v-if="mode === 'configs'" v-model:value="query.product_id" clearable filterable :options="options.products" placeholder="关联产品" />
          <n-select v-if="mode === 'pricing'" v-model:value="query.product_id" clearable filterable :options="options.products" placeholder="关联产品" />
          <n-select v-if="mode === 'pricing'" v-model:value="query.price_type" clearable :options="options.priceTypes" placeholder="价格类型" />
          <n-cascader
            v-if="mode === 'templates'"
            v-model:value="query.category_id"
            clearable
            filterable
            check-strategy="child"
            :options="options.categoryTree"
            placeholder="适用分类"
          />
          <n-button secondary @click="resetQuery">重置</n-button>
          <n-button type="primary" @click="loadPage">搜索</n-button>
        </div>

        <div class="table-wrap">
          <n-data-table
            remote
            striped
            flex-height
            :loading="loading"
            :columns="columns"
            :data="rows"
            :pagination="false"
            :row-key="(row) => row.id"
            :scroll-x="scrollX"
          >
            <template #empty><n-empty description="暂无数据" /></template>
          </n-data-table>
        </div>
        <div class="list-footer">
          <span>共 {{ pagination.itemCount }} 条</span>
          <n-pagination
            v-model:page="pagination.page"
            v-model:page-size="pagination.pageSize"
            :item-count="pagination.itemCount"
            :page-sizes="pagination.pageSizes"
            show-size-picker
            @update:page="loadPage"
            @update:page-size="handlePageSizeChange"
          />
        </div>
      </section>

      <n-modal
        v-model:show="categoryModal.show"
        preset="card"
        :title="categoryModal.form.id ? '编辑产品分类' : '新增产品分类'"
        class="product-modal product-category-modal"
        style="width: min(640px, calc(100vw - 32px))"
      >
        <n-form :model="categoryModal.form" label-placement="top" class="modal-form">
          <n-grid responsive="screen" cols="1 m:2" :x-gap="16" :y-gap="2">
            <n-form-item-gi label="分类名称" required><n-input v-model:value="categoryModal.form.name" /></n-form-item-gi>
            <n-form-item-gi label="分类编码"><n-input v-model:value="categoryModal.form.code" placeholder="留空自动生成" /></n-form-item-gi>
            <n-form-item-gi label="上级分类"><n-select v-model:value="categoryModal.form.parent_id" clearable filterable :options="topCategoryOptions" /></n-form-item-gi>
            <n-form-item-gi label="排序"><n-input-number v-model:value="categoryModal.form.order" :min="0" /></n-form-item-gi>
            <n-form-item-gi label="说明" :span="2"><n-input v-model:value="categoryModal.form.description" type="textarea" /></n-form-item-gi>
          </n-grid>
        </n-form>
        <template #footer><ModalFooter :loading="categoryModal.loading" @cancel="categoryModal.show = false" @save="saveCategory" /></template>
      </n-modal>

      <n-modal
        v-model:show="editor.show"
        preset="card"
        :title="editorTitle"
        class="product-modal"
        style="width: min(760px, calc(100vw - 32px))"
      >
        <n-form :model="editor.form" label-placement="top" class="modal-form">
          <n-grid responsive="screen" cols="1 m:2" :x-gap="16" :y-gap="2">
            <template v-if="mode === 'products'">
              <n-form-item-gi label="产品名称" required><n-input v-model:value="editor.form.name" /></n-form-item-gi>
              <n-form-item-gi label="产品编码"><n-input v-model:value="editor.form.code" placeholder="留空自动生成" /></n-form-item-gi>
              <n-form-item-gi label="产品分类">
                <n-cascader
                  v-model:value="editor.form.category_id"
                  clearable
                  filterable
                  check-strategy="child"
                  :options="options.categoryTree"
                  placeholder="请选择产品分类"
                />
              </n-form-item-gi>
              <n-form-item-gi label="产品状态"><n-select v-model:value="editor.form.status" :options="options.productStatuses" /></n-form-item-gi>
              <n-form-item-gi label="地区">
                <n-cascader
                  v-model:value="editor.form.region"
                  clearable
                  filterable
                  show-path
                  check-strategy="child"
                  :options="productRegionOptions"
                  :filter="regionCascaderFilter"
                  placeholder="从 POP 点选择国家 / 地区"
                />
              </n-form-item-gi>
              <n-form-item-gi label="计费模式"><n-select v-model:value="editor.form.billing_mode" :options="productBillingModeOptions" /></n-form-item-gi>
              <n-form-item-gi label="产品说明" :span="2"><n-input v-model:value="editor.form.description" type="textarea" /></n-form-item-gi>
            </template>

            <template v-else-if="mode === 'specs'">
              <n-form-item-gi label="属性名称" required><n-input v-model:value="editor.form.name" /></n-form-item-gi>
              <n-form-item-gi label="属性编码" required><n-input v-model:value="editor.form.code" /></n-form-item-gi>
              <n-form-item-gi label="属性类型"><n-select v-model:value="editor.form.attr_type" :options="options.attributeTypes" /></n-form-item-gi>
              <n-form-item-gi label="单位"><n-input v-model:value="editor.form.unit" /></n-form-item-gi>
              <n-form-item-gi label="必填"><n-switch v-model:value="editor.form.required" /></n-form-item-gi>
              <n-form-item-gi label="启用"><n-switch v-model:value="editor.form.status" /></n-form-item-gi>
              <n-form-item-gi label="可选值" :span="2"><n-input v-model:value="editor.form.options" type="textarea" placeholder="一行一个值，或填写 JSON" /></n-form-item-gi>
              <n-form-item-gi label="说明" :span="2"><n-input v-model:value="editor.form.description" type="textarea" /></n-form-item-gi>
            </template>

            <template v-else-if="mode === 'configs'">
              <n-form-item-gi label="关联产品" required><n-select v-model:value="editor.form.product_id" filterable :options="options.products" /></n-form-item-gi>
              <n-form-item-gi label="规格属性" required><n-select v-model:value="editor.form.attribute_id" filterable :options="options.attributes" /></n-form-item-gi>
              <n-form-item-gi label="排序"><n-input-number v-model:value="editor.form.order" :min="0" /></n-form-item-gi>
              <n-form-item-gi label="必填"><n-switch v-model:value="editor.form.required" /></n-form-item-gi>
              <n-form-item-gi label="默认值"><n-input v-model:value="editor.form.default_value" /></n-form-item-gi>
              <n-form-item-gi label="可选范围"><n-input v-model:value="editor.form.value_range" /></n-form-item-gi>
            </template>

            <template v-else-if="mode === 'pricing'">
              <n-form-item-gi label="关联产品" required><n-select v-model:value="editor.form.product_id" filterable :options="options.products" /></n-form-item-gi>
              <n-form-item-gi label="价格类型"><n-select v-model:value="editor.form.price_type" :options="options.priceTypes" /></n-form-item-gi>
              <n-form-item-gi v-if="editor.form.price_type === 'customer'" label="客户"><n-select v-model:value="editor.form.customer_id" clearable filterable :options="options.customers" /></n-form-item-gi>
              <n-form-item-gi label="计费模式"><n-select v-model:value="editor.form.billing_mode" :options="options.billingModes" /></n-form-item-gi>
              <n-form-item-gi label="计费单位"><n-select v-model:value="editor.form.billing_unit" :options="options.billingUnits" /></n-form-item-gi>
              <n-form-item-gi label="币种"><n-select v-model:value="editor.form.currency" :options="options.currencies" /></n-form-item-gi>
              <n-form-item-gi label="价格"><n-input-number v-model:value="editor.form.amount" :min="0" /></n-form-item-gi>
              <n-form-item-gi label="最低售价"><n-input-number v-model:value="editor.form.min_amount" :min="0" clearable /></n-form-item-gi>
              <n-form-item-gi label="生效日期"><n-date-picker v-model:formatted-value="editor.form.effective_date" value-format="yyyy-MM-dd" type="date" clearable /></n-form-item-gi>
              <n-form-item-gi label="失效日期"><n-date-picker v-model:formatted-value="editor.form.expiry_date" value-format="yyyy-MM-dd" type="date" clearable /></n-form-item-gi>
              <n-form-item-gi label="阶梯规则" :span="2"><n-input v-model:value="editor.form.tier_rules" type="textarea" /></n-form-item-gi>
              <n-form-item-gi label="带宽规则" :span="2"><n-input v-model:value="editor.form.bandwidth_rule" type="textarea" /></n-form-item-gi>
              <n-form-item-gi label="备注" :span="2"><n-input v-model:value="editor.form.remark" type="textarea" /></n-form-item-gi>
            </template>

            <template v-else>
              <n-form-item-gi label="模板名称" required><n-input v-model:value="editor.form.name" /></n-form-item-gi>
              <n-form-item-gi label="适用分类">
                <n-cascader
                  v-model:value="editor.form.category_id"
                  clearable
                  filterable
                  check-strategy="child"
                  :options="options.categoryTree"
                  placeholder="请选择适用分类"
                />
              </n-form-item-gi>
              <n-form-item-gi label="模板类型"><n-input v-model:value="editor.form.template_type" /></n-form-item-gi>
              <n-form-item-gi label="启用"><n-switch v-model:value="editor.form.status" /></n-form-item-gi>
              <n-form-item-gi label="模板说明" :span="2"><n-input v-model:value="editor.form.description" type="textarea" /></n-form-item-gi>
              <n-form-item-gi label="模板配置" :span="2"><n-input v-model:value="editor.form.config" type="textarea" placeholder="可填写标准规格、默认价格或创建说明" /></n-form-item-gi>
            </template>
          </n-grid>
        </n-form>
        <template #footer><ModalFooter :loading="editor.loading" @cancel="editor.show = false" @save="saveEditor" /></template>
      </n-modal>
    </div>
  </AppPage>
</template>

<script setup>
import { computed, defineComponent, h, nextTick, onMounted, reactive, ref, watch } from 'vue'
import {
  NButton,
  NCascader,
  NDataTable,
  NDatePicker,
  NEmpty,
  NForm,
  NFormItemGi,
  NGrid,
  NInput,
  NInputNumber,
  NPagination,
  NPopconfirm,
  NSelect,
  NSpace,
  NSwitch,
  NTag,
  NTree,
} from 'naive-ui'
import api from '@/api'
import TheIcon from '@/components/icon/TheIcon.vue'
import { translateCity, translateCountry, translateLocationPath } from '@/utils/location-i18n'

const props = defineProps({ mode: { type: String, default: 'products' } })

const modeMeta = {
  products: { title: '产品管理', keyword: '搜索产品名称 / 编码 / 地区', add: '新增产品', icon: 'mdi:plus-box-outline' },
  specs: { title: '规格管理', keyword: '搜索属性名称 / 编码 / 单位', add: '新增属性', icon: 'mdi:tune-variant' },
  configs: { title: '规格配置', keyword: '', add: '新增配置', icon: 'mdi:playlist-plus' },
  pricing: { title: '定价管理', keyword: '搜索产品 / 客户', add: '新增价格', icon: 'mdi:cash-plus' },
  templates: { title: '产品模板', keyword: '搜索模板名称 / 说明', add: '新增模板', icon: 'mdi:file-plus-outline' },
}

const pageTitle = computed(() => modeMeta[props.mode]?.title || '产品中心')
const addText = computed(() => modeMeta[props.mode]?.add || '新增')
const addIcon = computed(() => modeMeta[props.mode]?.icon || 'mdi:plus')
const keywordPlaceholder = computed(() => modeMeta[props.mode]?.keyword || '搜索')
const showKeyword = computed(() => props.mode !== 'configs')
const scrollX = computed(() => (props.mode === 'pricing' ? 1280 : props.mode === 'products' ? 1180 : 980))
const selectedCategoryKeys = computed(() => (query.category_id ? [query.category_id] : []))
const topCategoryOptions = computed(() => options.categories.filter((item) => !item.parent_id))
const productRegionOptions = computed(() => {
  const tree = buildPopRegionOptions()
  if (editor.form.region && !findCascaderValue(tree, editor.form.region)) {
    tree.unshift({ label: editor.form.region, value: editor.form.region })
  }
  return tree
})
const productBillingModeOptions = computed(() => {
  if (props.mode !== 'products') return options.billingModes
  const allowedValues = billingModesForCategory(editor.form.category_id)
  return options.billingModes.filter((item) => allowedValues.includes(item.value))
})

const loading = ref(false)
const rows = ref([])
const categories = ref([])
const expandedCategoryKeys = ref([])
const popRegions = ref([])
const editorInitializing = ref(false)
const pagination = reactive({ page: 1, pageSize: 20, itemCount: 0, pageSizes: [20, 50, 100] })
const query = reactive({ keyword: '', category_id: null, status: null, attr_type: null, product_id: null, price_type: null, customer_id: null })
const options = reactive({
  categoryTree: [],
  categories: [],
  products: [],
  attributes: [],
  customers: [],
  productStatuses: [],
  priceTypes: [],
  billingModes: [],
  billingUnits: [],
  attributeTypes: [],
  currencies: [],
})
const categoryModal = reactive({ show: false, loading: false, form: emptyCategory() })
const editor = reactive({ show: false, loading: false, form: emptyForm() })
const regionAliasMap = new Map([
  ['hk', '香港'],
  ['hongkong', '香港'],
  ['hong kong', '香港'],
  ['newyork', '纽约'],
  ['new york', '纽约'],
  ['losangeles', '洛杉矶'],
  ['los angeles', '洛杉矶'],
  ['london', '伦敦'],
  ['ashburn', '阿什本'],
  ['frankfurt', '法兰克福'],
  ['tokyo', '东京'],
  ['singapore', '新加坡'],
  ['taipei', '台北'],
  ['seoul', '首尔'],
])

const ModalFooter = defineComponent({
  emits: ['cancel', 'save'],
  props: { loading: Boolean },
  setup(componentProps, { emit }) {
    return () => h('div', { class: 'modal-footer' }, [
      h(NButton, { onClick: () => emit('cancel') }, () => '取消'),
      h(NButton, { type: 'primary', loading: componentProps.loading, onClick: () => emit('save') }, () => '保存'),
    ])
  },
})

function renderTag(text, type = 'default') {
  return h(NTag, { size: 'small', round: true, type }, { default: () => text || '-' })
}

function actionButtons(row) {
  return h('div', { class: 'table-actions' }, [
    h(NButton, { size: 'small', secondary: true, type: 'info', onClick: () => openEditor(row) }, { icon: () => h(TheIcon, { icon: 'mdi:pencil', size: 15 }) }),
    h(NPopconfirm, { onPositiveClick: () => deleteRow(row) }, {
      trigger: () => h(NButton, { size: 'small', secondary: true, type: 'error' }, { icon: () => h(TheIcon, { icon: 'mdi:trash-can-outline', size: 15 }) }),
      default: () => '确认删除？',
    }),
  ])
}

const productColumns = [
  { title: '产品名称', key: 'name', width: 220, ellipsis: { tooltip: true } },
  { title: '产品编码', key: 'code', width: 130 },
  { title: '产品分类', key: 'category_name', width: 150 },
  { title: '状态', key: 'status_label', width: 100, render: (row) => renderTag(row.status_label, row.status === 'active' ? 'success' : 'default') },
  { title: '地区', key: 'region', width: 130 },
  { title: '计费模式', key: 'billing_mode_label', width: 130 },
  { title: '操作', key: 'actions', width: 100, fixed: 'right', render: actionButtons },
]
const attributeColumns = [
  { title: '属性名称', key: 'name', width: 180 },
  { title: '属性编码', key: 'code', width: 150 },
  { title: '属性类型', key: 'attr_type_label', width: 120 },
  { title: '单位', key: 'unit', width: 100 },
  { title: '必填', key: 'required', width: 90, render: (row) => renderTag(row.required ? '是' : '否', row.required ? 'warning' : 'default') },
  { title: '操作', key: 'actions', width: 100, fixed: 'right', render: actionButtons },
]
const configColumns = [
  { title: '关联产品', key: 'product_name', width: 220, ellipsis: { tooltip: true } },
  { title: '属性名称', key: 'attribute_name', width: 160 },
  { title: '属性编码', key: 'attribute_code', width: 140 },
  { title: '类型', key: 'attr_type_label', width: 100 },
  { title: '默认值', key: 'default_value', width: 140 },
  { title: '可选范围', key: 'value_range', width: 180, ellipsis: { tooltip: true } },
  { title: '操作', key: 'actions', width: 100, fixed: 'right', render: actionButtons },
]
const priceColumns = [
  { title: '产品名称', key: 'product_name', width: 220, ellipsis: { tooltip: true } },
  { title: '价格类型', key: 'price_type_label', width: 120, render: (row) => renderTag(row.price_type_label, row.price_type === 'customer' ? 'warning' : 'success') },
  { title: '客户', key: 'customer_name', width: 180, ellipsis: { tooltip: true } },
  { title: '计费模式', key: 'billing_mode_label', width: 120 },
  { title: '计费单位', key: 'billing_unit_label', width: 110 },
  { title: '价格', key: 'amount', width: 120, render: (row) => `${row.currency || ''} ${row.amount ?? 0}` },
  { title: '生效日期', key: 'effective_date', width: 120 },
  { title: '失效日期', key: 'expiry_date', width: 120 },
  { title: '操作', key: 'actions', width: 100, fixed: 'right', render: actionButtons },
]
const templateColumns = [
  { title: '模板名称', key: 'name', width: 220 },
  { title: '适用分类', key: 'category_name', width: 160 },
  { title: '模板类型', key: 'template_type', width: 120 },
  { title: '说明', key: 'description', minWidth: 240, ellipsis: { tooltip: true } },
  { title: '状态', key: 'status', width: 90, render: (row) => renderTag(row.status ? '启用' : '停用', row.status ? 'success' : 'default') },
  { title: '操作', key: 'actions', width: 100, fixed: 'right', render: actionButtons },
]
const columns = computed(() => {
  if (props.mode === 'products') return productColumns
  if (props.mode === 'specs') return attributeColumns
  if (props.mode === 'configs') return configColumns
  if (props.mode === 'pricing') return priceColumns
  return templateColumns
})
const editorTitle = computed(() => `${editor.form.id ? '编辑' : '新增'}${pageTitle.value.replace('管理', '').replace('配置', '配置')}`)

function emptyCategory() {
  return { id: null, name: '', code: '', parent_id: null, order: 0, description: '', status: true }
}

function emptyForm() {
  if (props.mode === 'products') return { id: null, name: '', code: '', category_id: query.category_id, status: 'active', region: '', billing_mode: 'fixed', description: '' }
  if (props.mode === 'specs') return { id: null, name: '', code: '', attr_type: 'text', unit: '', required: false, options: '', description: '', status: true }
  if (props.mode === 'configs') return { id: null, product_id: query.product_id, attribute_id: null, order: 0, default_value: '', value_range: '', required: false }
  if (props.mode === 'pricing') return { id: null, product_id: query.product_id, price_type: query.price_type || 'standard', customer_id: null, customer_name: '', billing_mode: 'fixed', billing_unit: 'month', currency: 'USD', amount: 0, min_amount: null, tier_rules: '', bandwidth_rule: '', effective_date: null, expiry_date: null, status: 'active', remark: '' }
  return { id: null, name: '', category_id: query.category_id, template_type: 'product', description: '', config: '', status: true }
}

async function loadOptions() {
  const [res, regionRes] = await Promise.all([
    api.productCenterApi.options(),
    api.assetApi.regions({ page_size: 1000 }),
  ])
  const data = res.data || {}
  options.categoryTree = data.category_tree || []
  expandedCategoryKeys.value = getTreeKeys(options.categoryTree)
  options.categories = data.categories || []
  options.products = data.products || []
  options.attributes = data.attributes || []
  options.customers = data.customers || []
  options.productStatuses = data.product_statuses || []
  options.priceTypes = data.price_types || []
  options.billingModes = data.billing_modes || []
  options.billingUnits = data.billing_units || []
  options.attributeTypes = data.attribute_types || []
  options.currencies = data.currencies || []
  popRegions.value = regionRes.data || []
}

async function loadCategories() {
  const res = await api.productCenterApi.listCategories()
  categories.value = res.data || []
}

function pageParams(extra = {}) {
  return { page: pagination.page, page_size: pagination.pageSize, ...extra }
}

async function loadPage() {
  loading.value = true
  try {
    let res
    if (props.mode === 'products') res = await api.productCenterApi.listProducts(pageParams({ keyword: query.keyword, category_id: query.category_id || undefined, status: query.status || '' }))
    else if (props.mode === 'specs') res = await api.productCenterApi.listAttributes(pageParams({ keyword: query.keyword, attr_type: query.attr_type || '' }))
    else if (props.mode === 'configs') res = await api.productCenterApi.listSpecConfigs(pageParams({ product_id: query.product_id || undefined }))
    else if (props.mode === 'pricing') res = await api.productCenterApi.listPrices(pageParams({ keyword: query.keyword, product_id: query.product_id || undefined, price_type: query.price_type || '' }))
    else res = await api.productCenterApi.listTemplates(pageParams({ keyword: query.keyword, category_id: query.category_id || undefined }))
    rows.value = res.data || []
    pagination.itemCount = res.total || 0
  } finally {
    loading.value = false
  }
}

async function refreshAll() {
  await loadOptions()
  await loadCategories()
  await loadPage()
}

function resetQuery() {
  Object.assign(query, { keyword: '', category_id: null, status: null, attr_type: null, product_id: null, price_type: null, customer_id: null })
  pagination.page = 1
  loadPage()
}

function handlePageSizeChange(size) {
  pagination.pageSize = size
  pagination.page = 1
  loadPage()
}

function handleCategorySelect(keys) {
  query.category_id = keys?.[0] || null
  pagination.page = 1
  loadPage()
}

function getTreeKeys(nodes = []) {
  return nodes.flatMap((node) => [node.key, ...getTreeKeys(node.children || [])]).filter((key) => key !== undefined && key !== null)
}

function openCategoryModal(row = null) {
  categoryModal.form = row ? { ...row } : emptyCategory()
  categoryModal.show = true
}

function editSelectedCategory() {
  const row = categories.value.find((item) => item.id === query.category_id)
  if (row) openCategoryModal(row)
}

async function saveCategory() {
  if (!categoryModal.form.name) return window.$message?.warning('请填写分类名称')
  categoryModal.loading = true
  try {
    const payload = { ...categoryModal.form }
    if (payload.id) await api.productCenterApi.updateCategory(payload.id, payload)
    else await api.productCenterApi.createCategory(payload)
    categoryModal.show = false
    await refreshAll()
  } finally {
    categoryModal.loading = false
  }
}

async function deleteSelectedCategory() {
  if (!query.category_id) return
  await api.productCenterApi.deleteCategory(query.category_id)
  query.category_id = null
  await refreshAll()
}

function openEditor(row = null) {
  editorInitializing.value = true
  editor.form = row ? { ...emptyForm(), ...row } : emptyForm()
  if (!row) applyProductBillingDefault()
  editor.show = true
  nextTick(() => {
    editorInitializing.value = false
  })
}

function getCategory(categoryId) {
  return categories.value.find((item) => item.id === categoryId)
}

function categoryPathNames(categoryId) {
  const names = []
  let category = getCategory(categoryId)
  while (category) {
    names.unshift(category.name)
    category = getCategory(category.parent_id)
  }
  return names
}

function categoryIncludes(categoryId, names) {
  return categoryPathNames(categoryId).some((name) => names.includes(name))
}

function text(value, fallback = '-') {
  return String(value || '').trim() || fallback
}

function fieldText(value) {
  if (value == null) return ''
  if (typeof value === 'object') {
    return String(value.name || value.label || value.title || value.value || value.code || value.id || '').trim()
  }
  return String(value).trim()
}

function displayRegion(value) {
  const valueText = fieldText(value)
  if (!valueText) return ''
  return translateLocationPath(valueText) || translateCountry(valueText) || translateCity(valueText) || valueText
}

function translateRegionAlias(value) {
  const valueText = fieldText(value)
  if (!valueText) return ''
  const translated = translateCity(valueText) || translateCountry(valueText)
  const normalized = valueText
    .toLowerCase()
    .replace(/[,，]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
  return regionAliasMap.get(normalized) || regionAliasMap.get(normalized.replace(/\s+/g, '')) || translated || valueText
}

function normalizeRegion(value) {
  return String(value || '')
    .toLowerCase()
    .replace(/[\s　]+/g, '')
    .replace(/[，、;；]+/g, ',')
    .replace(/[／\\/]+/g, '/')
    .replace(/\/+/g, '/')
    .trim()
}

function canonicalRegion(value) {
  const valueText = displayRegion(value)
  if (!valueText) return ''
  const source = valueText
    .split(/[,，、;；]+/)
    .map((item) => item.trim())
    .filter(Boolean)
    .find((item) => item.includes('/')) || valueText
  const pathParts = source
    .split('/')
    .map((item) => item.trim())
    .filter(Boolean)
  return translateRegionAlias(pathParts[pathParts.length - 1] || source)
}

function regionPathParts(value) {
  const parts = displayRegion(value)
    .split(/[／\\/]+/)
    .map((item) => translateRegionAlias(item.trim()) || item.trim())
    .filter(Boolean)
  return parts.length ? parts : [canonicalRegion(value)].filter(Boolean)
}

function popRegionPathParts(item = {}) {
  const country = translateCountry(fieldText(item.country) || fieldText(item.country_name))
  const city = translateCity(fieldText(item.city) || fieldText(item.city_name))
  const regionParts = regionPathParts(fieldText(item.name) || fieldText(item.region_name))
  const values = [country, city]
  if (!city) {
    regionParts.forEach((part) => {
      const label = translateRegionAlias(part) || fieldText(part)
      const key = normalizeRegion(label)
      if (!key || values.some((value) => normalizeRegion(value) === key)) return
      values.push(label)
    })
  }
  const parts = []
  values.forEach((value) => {
    const label = translateRegionAlias(value) || fieldText(value)
    const key = normalizeRegion(label)
    if (!key || parts.some((part) => normalizeRegion(part) === key)) return
    parts.push(label)
  })
  return parts
}

function ensureRegionPath(roots, parts) {
  let children = roots
  let current = null
  const path = []
  parts.forEach((part) => {
    const label = translateRegionAlias(part) || part
    const key = normalizeRegion(label)
    if (!key) return
    path.push(label)
    const value = canonicalRegion(path.join(' / ')) || label
    let node = children.find((item) => normalizeRegion(item.label) === key || normalizeRegion(item.value) === normalizeRegion(value))
    if (!node) {
      node = {
        label,
        value,
        region: value,
        searchText: uniqueValues([path.join(' '), value, displayRegion(value)]).join(' '),
        children: [],
      }
      children.push(node)
    } else {
      node.searchText = uniqueValues([node.searchText, path.join(' '), value, displayRegion(value)]).join(' ')
      if (!node.region) node.region = value
    }
    current = node
    children = node.children
  })
  return current
}

function sortCascaderTree(nodes) {
  return nodes
    .sort((left, right) => String(left.label || '').localeCompare(String(right.label || ''), 'zh-Hans-CN'))
    .map((node) => ({
      ...node,
      children: node.children?.length ? sortCascaderTree(node.children) : undefined,
    }))
}

function buildPopRegionOptions() {
  const roots = []
  popRegions.value
    .filter((region) => region.status !== false)
    .forEach((region) => ensureRegionPath(roots, popRegionPathParts(region)))
  return sortCascaderTree(roots)
}

function findCascaderValue(nodes = [], value) {
  return nodes.some((node) => node.value === value || findCascaderValue(node.children || [], value))
}

function uniqueValues(values) {
  return [...new Set(values.map((value) => String(value || '').trim()).filter(Boolean))]
}

function normalizeSearchText(value) {
  return String(value || '')
    .toLowerCase()
    .replace(/[\s　]+/g, '')
    .replace(/[\/\\,，、;；?？_-]+/g, '')
    .trim()
}

function regionCascaderFilter(pattern, option, path = []) {
  const keyword = normalizeSearchText(pattern)
  if (!keyword) return true
  const options = Array.isArray(path) && path.length ? path : [option]
  const valueText = options
    .flatMap((item) => [item?.label, item?.value, item?.region, item?.searchText])
    .filter(Boolean)
    .join(' ')
  return normalizeSearchText(valueText).includes(keyword)
}

function billingModesForCategory(categoryId) {
  if (!categoryId) return options.billingModes.map((item) => item.value)
  if (categoryIncludes(categoryId, ['Remote Hands'])) return ['hourly']
  if (categoryIncludes(categoryId, ['IP Transit', 'DIA', 'China Route 回国带宽', 'IEPL', 'Wave'])) return ['bandwidth', 'fixed', 'hybrid']
  if (categoryIncludes(categoryId, ['IPv4', 'IPv6', 'ASN', '互联网资源'])) return ['quantity', 'fixed']
  if (categoryIncludes(categoryId, ['IX', 'Peering', 'Cloud Connect', '上云互联'])) return ['fixed', 'bandwidth']
  if (categoryIncludes(categoryId, ['物理服务器', '云主机', '计算资源'])) return ['fixed', 'usage']
  if (categoryIncludes(categoryId, ['整柜整租', '散柜机位', 'Cross Connect', '机房资源'])) return ['fixed', 'quantity']
  return options.billingModes.map((item) => item.value)
}

function applyProductBillingDefault() {
  if (props.mode !== 'products') return
  const allowedValues = billingModesForCategory(editor.form.category_id)
  if (!allowedValues.length) return
  if (!editor.form.billing_mode || !allowedValues.includes(editor.form.billing_mode)) {
    editor.form.billing_mode = allowedValues[0]
  }
}

async function saveEditor() {
  editor.loading = true
  try {
    const payload = { ...editor.form }
    if (props.mode === 'products') {
      if (!payload.name) return window.$message?.warning('请填写产品名称')
      if (payload.id) await api.productCenterApi.updateProduct(payload.id, payload)
      else await api.productCenterApi.createProduct(payload)
    } else if (props.mode === 'specs') {
      if (!payload.name || !payload.code) return window.$message?.warning('请填写属性名称和编码')
      if (payload.id) await api.productCenterApi.updateAttribute(payload.id, payload)
      else await api.productCenterApi.createAttribute(payload)
    } else if (props.mode === 'configs') {
      if (!payload.product_id || !payload.attribute_id) return window.$message?.warning('请选择产品和规格属性')
      if (payload.id) await api.productCenterApi.updateSpecConfig(payload.id, payload)
      else await api.productCenterApi.createSpecConfig(payload)
    } else if (props.mode === 'pricing') {
      if (!payload.product_id) return window.$message?.warning('请选择产品')
      if (payload.id) await api.productCenterApi.updatePrice(payload.id, payload)
      else await api.productCenterApi.createPrice(payload)
    } else {
      if (!payload.name) return window.$message?.warning('请填写模板名称')
      if (payload.id) await api.productCenterApi.updateTemplate(payload.id, payload)
      else await api.productCenterApi.createTemplate(payload)
    }
    editor.show = false
    await refreshAll()
  } finally {
    editor.loading = false
  }
}

async function deleteRow(row) {
  if (props.mode === 'products') await api.productCenterApi.deleteProduct(row.id)
  else if (props.mode === 'specs') await api.productCenterApi.deleteAttribute(row.id)
  else if (props.mode === 'configs') await api.productCenterApi.deleteSpecConfig(row.id)
  else if (props.mode === 'pricing') await api.productCenterApi.deletePrice(row.id)
  else await api.productCenterApi.deleteTemplate(row.id)
  await refreshAll()
}

watch(() => props.mode, () => {
  resetQuery()
})

watch(() => editor.form.category_id, () => {
  if (editorInitializing.value) return
  applyProductBillingDefault()
})

onMounted(refreshAll)
</script>

<style scoped>
:deep(.app-page-shell) {
  overflow: hidden;
}
.product-page {
  display: flex;
  height: 100%;
  min-height: 0;
  gap: 12px;
}
.category-panel,
.product-panel {
  display: flex;
  min-height: 0;
  flex-direction: column;
  border: 1px solid #e7edf4;
  border-radius: 8px;
  background: #fff;
}
.category-panel {
  width: 280px;
  flex-shrink: 0;
  padding: 14px;
}
.product-panel {
  flex: 1;
  padding: 18px;
}
.panel-head {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}
.panel-head h2,
.panel-head h3 {
  margin: 4px 0 0;
  color: #0f172a;
}
.panel-head h2 {
  font-size: 22px;
}
.panel-head h3 {
  font-size: 18px;
}
.eyebrow {
  color: #607089;
  font-size: 12px;
  font-weight: 700;
}
.filter-row {
  display: grid;
  flex-shrink: 0;
  grid-template-columns: minmax(240px, 1.4fr) repeat(3, minmax(150px, 1fr)) 78px 78px;
  gap: 10px;
  margin: 16px 0;
}
.table-wrap {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}
.table-wrap :deep(.n-data-table) {
  width: 100%;
  height: 100%;
}
.table-wrap :deep(.n-data-table .n-data-table-base-table) {
  min-height: 0;
}
.list-footer {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-top: 14px;
}
.category-panel :deep(.n-tree) {
  flex: 1;
  min-height: 0;
  margin-top: 14px;
  overflow: auto;
}
.category-actions,
.table-actions,
.modal-footer {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.category-actions {
  flex-shrink: 0;
  justify-content: flex-end;
  padding-top: 12px;
}
:deep(.product-modal) {
  max-height: calc(100vh - 72px);
  border-radius: 8px;
  overflow: hidden;
}
:deep(.product-modal .n-card-header) {
  padding: 18px 22px 12px;
  border-bottom: 1px solid #eef1f5;
}
:deep(.product-modal .n-card-header__main) {
  font-size: 17px;
  font-weight: 700;
}
:deep(.product-modal .n-card__content) {
  max-height: calc(100vh - 210px);
  padding: 18px 22px 6px;
  overflow: auto;
}
:deep(.product-modal .n-card__footer) {
  padding: 14px 22px 18px;
  border-top: 1px solid #eef1f5;
  background: #fff;
}
.modal-form :deep(.n-form-item) {
  margin-bottom: 12px;
}
.modal-form :deep(.n-form-item-label) {
  min-height: 24px;
  font-weight: 600;
  color: #26364f;
}
.modal-form :deep(.n-input),
.modal-form :deep(.n-input-number),
.modal-form :deep(.n-select),
.modal-form :deep(.n-date-picker) {
  width: 100%;
}
.modal-form :deep(textarea.n-input__textarea-el) {
  min-height: 76px;
}
.modal-footer {
  justify-content: flex-end;
}
@media (max-width: 900px) {
  .product-page {
    flex-direction: column;
    overflow: hidden;
  }
  .category-panel {
    width: 100%;
    max-height: 240px;
  }
  .filter-row {
    grid-template-columns: 1fr 1fr;
  }
  :deep(.product-modal) {
    width: calc(100vw - 24px);
    max-height: calc(100vh - 32px);
  }
  :deep(.product-modal .n-card__content) {
    max-height: calc(100vh - 180px);
    padding: 16px 16px 4px;
  }
  :deep(.product-modal .n-card-header),
  :deep(.product-modal .n-card__footer) {
    padding-left: 16px;
    padding-right: 16px;
  }
}
</style>
