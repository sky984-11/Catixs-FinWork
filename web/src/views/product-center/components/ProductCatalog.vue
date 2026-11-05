<template>
  <AppPage :show-footer="false" class="product-catalog-page">
    <div class="product-layout">
      <n-card title="产品分类" class="category-panel">
        <template #header-extra>
          <n-tooltip>
            <template #trigger>
              <n-button
                size="small"
                circle
                quaternary
                type="primary"
                aria-label="新增分类"
                :disabled="busy"
                @click.stop="editCategory()"
              >
                <template #icon><TheIcon icon="mdi:plus" :size="17" /></template>
              </n-button>
            </template>
            新增分类
          </n-tooltip>
        </template>
        <n-button
          class="all-products"
          :class="{ 'is-selected': !query.category_id }"
          quaternary
          :disabled="busy"
          @click="selectCategory([])"
        >
          <template #icon><TheIcon icon="mdi:view-grid-outline" :size="17" /></template>
          全部产品
        </n-button>
        <div class="category-tree cus-scroll-y">
          <n-tree
            block-line
            default-expand-all
            :data="categoryTree"
            :selected-keys="selectedKeys"
            :render-prefix="renderCategoryPrefix"
            :render-label="renderCategoryLabel"
            :disabled="busy"
            @update:selected-keys="selectCategory"
          />
          <n-empty v-if="!categoryTree.length && !optionsLoading" description="暂无分类" />
        </div>
        <div class="category-actions">
          <span class="category-selection" :title="selectedCategory?.name">{{
            selectedCategory?.name || '选择分类后操作'
          }}</span>
          <n-space :wrap="false" :size="4">
            <n-tooltip>
              <template #trigger>
                <n-button
                  size="small"
                  circle
                  quaternary
                  aria-label="编辑分类"
                  :disabled="!selectedCategory || busy"
                  @click.stop="editCategory(selectedCategory)"
                >
                  <template #icon><TheIcon icon="mdi:pencil-outline" :size="17" /></template>
                </n-button>
              </template>
              编辑分类
            </n-tooltip>
            <n-tooltip>
              <template #trigger>
                <n-button
                  size="small"
                  circle
                  quaternary
                  type="error"
                  aria-label="删除分类"
                  :disabled="!selectedCategory || busy"
                  @click.stop="confirmDelete(selectedCategory, 'category')"
                >
                  <template #icon><TheIcon icon="mdi:trash-can-outline" :size="17" /></template>
                </n-button>
              </template>
              删除分类
            </n-tooltip>
          </n-space>
        </div>
      </n-card>
      <n-card title="产品管理" class="product-panel">
        <template #header-extra
          ><n-button type="primary" :disabled="busy || optionsLoading" @click="editProduct()"
            >新增产品</n-button
          ></template
        >
        <n-space class="filters" align="center">
          <n-input
            v-model:value="query.keyword"
            clearable
            placeholder="搜索产品编号 / 产品名称"
            @keyup.enter="search"
          />
          <n-select
            v-model:value="query.status"
            clearable
            :options="statuses"
            placeholder="状态"
            style="width: 130px"
          />
          <n-button :disabled="busy" @click="search">查询</n-button>
          <n-button v-if="optionError" :loading="optionsLoading" @click="loadOptions"
            >重试加载选项</n-button
          >
        </n-space>
        <n-alert v-if="error || optionError" type="error" class="filters">{{
          error || optionError
        }}</n-alert>
        <n-data-table
          remote
          striped
          :columns="columns"
          :data="rows"
          :loading="loading"
          :row-key="(row) => row.id"
          :scroll-x="1160"
          :pagination="false"
        />
        <n-pagination
          v-model:page="page"
          v-model:page-size="pageSize"
          :item-count="total"
          :page-sizes="[20, 50, 100]"
          show-size-picker
          class="pagination"
          @update:page="loadProducts"
          @update:page-size="search"
        />
      </n-card>
    </div>
    <n-modal
      v-model:show="editor.show"
      preset="card"
      :title="editor.form.id ? '编辑产品' : '新增产品'"
      class="product-editor"
      style="width: min(680px, calc(100vw - 32px))"
      :mask-closable="!saving"
      :close-on-esc="!saving"
      :closable="!saving"
    >
      <template #header>
        <div class="product-editor-heading">
          <span class="product-editor-icon"><TheIcon icon="mdi:cube-outline" :size="23" /></span>
          <div>
            <h3>{{ editor.form.id ? '编辑产品' : '新增产品' }}</h3>
            <p>维护产品公共信息，在规格组合中配置参数；无规格产品可直接配置价格</p>
          </div>
        </div>
      </template>
      <div class="cus-scroll-y product-editor-body">
        <n-form label-placement="top" :disabled="saving" class="product-edit-form">
          <section class="product-form-section">
            <div class="product-section-heading">
              <TheIcon icon="mdi:information-outline" :size="17" /><span>基本信息</span>
            </div>
            <div class="product-field-grid">
              <n-form-item label="产品编号" required
                ><n-input
                  v-model:value="editor.form.code"
                  placeholder="请输入产品编号"
                  :maxlength="80"
              /></n-form-item>
              <n-form-item label="产品名称" required
                ><n-input v-model:value="editor.form.name" :maxlength="160"
              /></n-form-item>
              <n-form-item label="分类" required
                ><n-tree-select
                  v-model:value="editor.form.category_id"
                  :options="categoryTree"
                  filterable
              /></n-form-item>
              <n-form-item label="计费单位" required
                ><n-select v-model:value="editor.form.billing_unit" :options="units" filterable tag
              /></n-form-item>
              <n-form-item label="最短合同期（月）" required
                ><n-input-number
                  v-model:value="editor.form.min_contract_months"
                  :min="1"
                  :max="1200"
                  :precision="0"
              /></n-form-item>
              <n-form-item label="状态"
                ><n-select v-model:value="editor.form.status" :options="statuses"
              /></n-form-item>
            </div>
          </section>
        </n-form>
      </div>
      <template #footer>
        <div class="product-editor-footer">
          <CButton
            :show-cancel="true"
            :show-save="true"
            :disabled="saving"
            :save-loading="saving"
            @cancel="editor.show = false"
            @save="saveProduct"
          /></div
      ></template>
    </n-modal>
    <n-modal
      v-model:show="categoryEditor.show"
      preset="card"
      :title="categoryEditor.form.id ? '编辑分类' : '新增分类'"
      class="product-editor"
      style="width: min(560px, calc(100vw - 32px))"
      :mask-closable="!saving"
      :close-on-esc="!saving"
      :closable="!saving"
    >
      <n-form label-placement="top" :disabled="saving">
        <n-form-item label="分类名称" required
          ><n-input v-model:value="categoryEditor.form.name" :maxlength="120"
        /></n-form-item>
        <n-form-item label="分类编码"
          ><n-input v-model:value="categoryEditor.form.code" placeholder="留空自动生成"
        /></n-form-item>
        <n-form-item label="上级分类"
          ><n-tree-select
            v-model:value="categoryEditor.form.parent_id"
            :options="parentTree"
            clearable
        /></n-form-item>
        <n-form-item label="排序"
          ><n-input-number v-model:value="categoryEditor.form.order" :min="0" :precision="0"
        /></n-form-item>
      </n-form>
      <template #footer
        ><CButton
          :show-cancel="true"
          :show-save="true"
          :disabled="saving"
          :save-loading="saving"
          @cancel="categoryEditor.show = false"
          @save="saveCategory"
      /></template>
    </n-modal>
    <n-modal
      v-model:show="deletion.show"
      preset="card"
      title="确认删除"
      class="product-editor"
      style="width: min(560px, calc(100vw - 32px))"
      :mask-closable="!saving"
      :close-on-esc="!saving"
      :closable="!saving"
    >
      确认删除“{{ deletion.row?.name }}”？存在关联数据或价格版本历史时不可删除。
      <template #footer
        ><CButton
          :show-cancel="true"
          :show-delete="true"
          :disabled="saving"
          :delete-loading="saving"
          @cancel="deletion.show = false"
          @delete="remove"
      /></template>
    </n-modal>
    <n-modal
      v-model:show="cloning.show"
      preset="card"
      title="克隆产品"
      style="width: min(560px, calc(100vw - 32px))"
      :closable="!saving"
      :mask-closable="!saving"
      :close-on-esc="!saving"
    >
      <p class="clone-source">源产品：{{ cloning.source?.name }}</p>
      <n-form label-placement="top" :disabled="saving">
        <n-form-item label="新产品名称" required
          ><n-input v-model:value="cloning.form.name" :maxlength="160"
        /></n-form-item>
        <n-form-item label="新产品编号" required
          ><n-input v-model:value="cloning.form.code" :maxlength="80"
        /></n-form-item>
        <n-form-item label="同时复制公共价格版本"
          ><n-switch v-model:value="cloning.form.copy_prices"
        /></n-form-item>
      </n-form>
      <n-alert type="info" :show-icon="false"
        >复制产品信息及全部规格组合，不复制订单等业务关联。若需要修改组合参数，可关闭价格复制，调整后再定价。</n-alert
      >
      <template #footer
        ><CButton
          show-cancel
          show-save
          save-text="确认克隆"
          :disabled="saving"
          :save-loading="saving"
          @cancel="cloning.show = false"
          @save="cloneProduct"
      /></template>
    </n-modal>
    <ProductVariants
      v-if="variantProduct"
      :product="variantProduct"
      :units="units"
      @close="closePricing"
    />
    <ProductPriceVersions
      v-if="priceProduct"
      :product="priceProduct"
      :units="units"
      @close="closePricing"
    />
  </AppPage>
</template>

<script setup>
import { computed, h, onMounted, reactive, ref } from 'vue'
import { NButton, NSpace, NTag, NTooltip } from 'naive-ui'
import api from '@/api'
import TheIcon from '@/components/icon/TheIcon.vue'
import CButton from '@/components/public/CButton.vue'
import ProductVariants from './ProductVariants.vue'
import ProductPriceVersions from './ProductPriceVersions.vue'

const service = api.productCenterApi
const rows = ref([]),
  categories = ref([]),
  options = ref({})
const loading = ref(false),
  optionsLoading = ref(true),
  saving = ref(false),
  rowSaving = ref(null)
const error = ref(''),
  optionError = ref(''),
  page = ref(1),
  pageSize = ref(20),
  total = ref(0)
const query = reactive({ keyword: '', category_id: null, status: null })
const editor = reactive({ show: false, form: {} })
const categoryEditor = reactive({ show: false, form: {} })
const deletion = reactive({ show: false, row: null, kind: 'product' })
const cloning = reactive({
  show: false,
  source: null,
  form: { name: '', code: '', copy_prices: true },
})
const variantProduct = ref(null)
const priceProduct = ref(null)
function closePricing() {
  variantProduct.value = null
  priceProduct.value = null
  loadProducts()
}
const busy = computed(() => saving.value || rowSaving.value !== null)
const statuses = [
  { label: '在售', value: 'active' },
  { label: '下架', value: 'offline' },
]
const units = computed(() => options.value.billing_units || [{ label: '月', value: 'month' }])
const selectedKeys = computed(() => (query.category_id ? [query.category_id] : []))
const selectedCategory = computed(() =>
  categories.value.find((row) => row.id === query.category_id)
)
function renderCategoryPrefix({ option }) {
  return h(TheIcon, {
    icon: option.children?.length ? 'mdi:folder-outline' : 'mdi:cube-outline',
    size: 15,
    class: 'category-node-icon',
  })
}
function renderCategoryLabel({ option }) {
  return h(
    NTooltip,
    { placement: 'right', delay: 400 },
    {
      trigger: () => h('span', { class: 'category-node-label' }, option.label),
      default: () => option.label,
    }
  )
}
function buildTree(parentId = null, excluded = null, visited = new Set()) {
  return categories.value
    .filter((row) => row.parent_id === parentId && row.id !== excluded && !visited.has(row.id))
    .map((row) => {
      const children = buildTree(row.id, excluded, new Set([...visited, row.id]))
      return {
        label: row.name,
        key: row.id,
        value: row.id,
        ...(children.length ? { children } : {}),
      }
    })
}
const categoryTree = computed(() => buildTree())
const parentTree = computed(() => buildTree(null, categoryEditor.form.id))
function selectCategory(keys) {
  query.category_id = keys[0] || null
  search()
}
function search() {
  page.value = 1
  loadProducts()
}
let requestId = 0
async function loadProducts() {
  const current = ++requestId
  loading.value = true
  error.value = ''
  try {
    const result = await service.listProducts({
      ...query,
      status: query.status || '',
      page: page.value,
      page_size: pageSize.value,
    })
    if (current !== requestId) return
    rows.value = result.data
    total.value = result.total
  } catch (e) {
    if (current === requestId) {
      error.value = e.message || '产品加载失败，请重试'
      rows.value = []
      total.value = 0
    }
  } finally {
    if (current === requestId) loading.value = false
  }
}
async function loadOptions() {
  optionsLoading.value = true
  optionError.value = ''
  try {
    const categoryResult = await service.listCategories()
    const optionResult = await service.options()
    categories.value = categoryResult.data
    options.value = optionResult.data
  } catch (e) {
    optionError.value = e.message || '分类选项加载失败'
  } finally {
    optionsLoading.value = false
  }
}
function editProduct(row) {
  editor.form = row
    ? { ...row, spec_values: { ...(row.spec_values || {}) } }
    : {
        code: '',
        name: '',
        category_id: query.category_id,
        billing_unit: 'month',
        min_contract_months: 1,
        status: 'active',
        spec_values: {},
      }
  editor.show = true
}
function openClone(row) {
  if (busy.value) return
  cloning.source = row
  cloning.form = {
    name: `${row.name.slice(0, 155)} - 副本`,
    code: `${(row.code || '').slice(0, 75)}-COPY`,
    copy_prices: true,
  }
  cloning.show = true
}
async function cloneProduct() {
  if (busy.value) return
  const data = { ...cloning.form, name: cloning.form.name.trim(), code: cloning.form.code.trim() }
  if (!data.name || !data.code) return window.$message?.warning('请填写新产品名称和编号')
  saving.value = true
  rowSaving.value = cloning.source.id
  try {
    await service.cloneProduct(cloning.source.id, data)
    cloning.show = false
    window.$message?.success('产品已克隆')
    await loadProducts()
  } catch {
    /* 保留表单以便修改编号或重试 */
  } finally {
    saving.value = false
    rowSaving.value = null
  }
}
async function saveProduct() {
  if (busy.value) return
  const form = { ...editor.form, code: editor.form.code?.trim(), name: editor.form.name?.trim() }
  form.parameterized = true
  delete form.spec_values
  if (!form.code) return window.$message?.warning('请填写产品编号')
  if (!form.name || !form.category_id || !form.billing_unit || !form.min_contract_months)
    return window.$message?.warning('请完整填写产品必填项')
  saving.value = true
  try {
    if (form.id) await service.updateProduct(form.id, form)
    else await service.createProduct(form)
    editor.show = false
    window.$message?.success('产品已保存')
    await loadProducts()
  } catch {
    /* 请求封装展示错误，保留表单以便重试 */
  } finally {
    saving.value = false
  }
}
function editCategory(row) {
  categoryEditor.form = row
    ? { ...row }
    : { name: '', code: '', parent_id: query.category_id, order: 0 }
  categoryEditor.show = true
}
async function saveCategory() {
  if (busy.value) return
  const form = { ...categoryEditor.form, name: categoryEditor.form.name?.trim() }
  if (!form.name) return window.$message?.warning('请填写分类名称')
  saving.value = true
  try {
    if (form.id) await service.updateCategory(form.id, form)
    else await service.createCategory(form)
    categoryEditor.show = false
    await loadOptions()
    await loadProducts()
  } catch {
    /* 保留表单以便重试 */
  } finally {
    saving.value = false
  }
}
function confirmDelete(row, kind) {
  if (row) Object.assign(deletion, { show: true, row, kind })
}
async function remove() {
  if (busy.value) return
  saving.value = true
  try {
    if (deletion.kind === 'category') {
      await service.deleteCategory(deletion.row.id)
      query.category_id = null
      await loadOptions()
    } else await service.deleteProduct(deletion.row.id)
    deletion.show = false
    if (rows.value.length === 1 && page.value > 1) page.value--
    await loadProducts()
  } catch {
    /* 删除失败保留确认框 */
  } finally {
    saving.value = false
  }
}
function actionButton(row, label, icon, type, handler) {
  return h(NTooltip, null, {
    trigger: () =>
      h(
        NButton,
        {
          size: 'small',
          circle: true,
          quaternary: true,
          type,
          'aria-label': label,
          disabled: busy.value,
          loading: rowSaving.value === row.id,
          onClick: (event) => {
            event.stopPropagation()
            if (!busy.value) handler()
          },
        },
        { icon: () => h(TheIcon, { icon, size: 17 }) }
      ),
    default: () => label,
  })
}
const columns = computed(() =>
  [
    { title: '产品编号', key: 'code', width: 150 },
    { title: '产品名称', key: 'name', width: 220, ellipsis: { tooltip: true } },
    {
      title: '分类',
      key: 'category_id',
      width: 220,
      render: (row) =>
        h(
          NTag,
          { size: 'small', bordered: false },
          {
            default: () =>
              row.category_name ||
              categories.value.find((item) => item.id === row.category_id)?.name ||
              '未分类',
          }
        ),
    },
    {
      title: '计费单位',
      key: 'billing_unit',
      width: 120,
      render: (row) =>
        units.value.find((unit) => unit.value === row.billing_unit)?.label || row.billing_unit,
    },
    { title: '最短合同期（月）', key: 'min_contract_months', width: 160 },
    {
      title: '状态',
      key: 'status',
      width: 110,
      render: (row) =>
        h(
          NTag,
          { type: row.status === 'active' ? 'success' : 'default', size: 'small' },
          { default: () => (row.status === 'active' ? '在售' : '下架') }
        ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 180,
      fixed: 'right',
      render: (row) =>
        h(
          NSpace,
          { wrap: false, size: 6 },
          {
            default: () => [
              actionButton(row, '编辑', 'mdi:pencil-outline', 'info', () => editProduct(row)),
              actionButton(row, '克隆', 'mdi:content-copy', 'default', () => openClone(row)),
              actionButton(row, '删除', 'mdi:delete-outline', 'error', () =>
                confirmDelete(row, 'product')
              ),
              row.direct_pricing
                ? actionButton(row, '价格', 'mdi:currency-usd', 'primary', () => {
                    priceProduct.value = row
                  })
                : actionButton(row, '规格组合', 'mdi:tune-variant', 'primary', () => {
                    variantProduct.value = row
                  }),
            ],
          }
        ),
    },
  ].map((column) => ({ ...column, resizable: column.key !== 'actions' }))
)
onMounted(async () => {
  await loadOptions()
  await loadProducts()
})
</script>

<style scoped>
.clone-source {
  overflow-wrap: anywhere;
  margin: 0 0 18px;
}
.product-catalog-page {
  min-height: 0;
  overflow: hidden;
}
.product-layout {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  grid-template-rows: minmax(0, 1fr);
  flex: 1;
  min-height: 0;
  gap: 16px;
}
.product-panel,
.category-panel {
  min-width: 0;
  min-height: 0;
}
.product-panel {
  overflow: auto;
}
.category-panel :deep(.n-card__content) {
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 0 14px 12px;
}
.category-panel :deep(.n-card-header) {
  padding: 18px 18px 14px;
}
.category-panel :deep(.n-card-header__main) {
  font-size: 16px;
  font-weight: 600;
}
.category-panel :deep(.n-card-header),
.category-panel :deep(.n-card__content > .n-button),
.category-panel .category-actions {
  flex-shrink: 0;
}
.category-tree {
  flex: 1;
  min-height: 0;
  overflow: auto;
  scrollbar-gutter: stable;
  padding: 4px 0;
}
.all-products {
  justify-content: flex-start;
  margin-bottom: 8px;
  border-radius: 6px;
}
.all-products.is-selected {
  color: var(--primary-color);
  background: color-mix(in srgb, var(--primary-color) 10%, transparent);
}
.category-tree :deep(.n-tree-node) {
  min-height: 34px;
  align-items: center;
  margin: 2px 0;
  border-radius: 6px;
}
.category-tree :deep(.n-tree-node-content) {
  min-width: 0;
  overflow: hidden;
}
.category-tree :deep(.n-tree-node-content__text),
.category-tree :deep(.category-node-label) {
  display: block;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.category-tree :deep(.n-tree-node--selected .n-tree-node-content) {
  font-weight: 600;
}
.category-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding-top: 12px;
  margin-top: 8px;
  border-top: 1px solid var(--n-border-color);
}
.category-selection {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  color: var(--n-text-color);
  opacity: 0.65;
}
.filters {
  margin: 16px 0;
}
.pagination {
  margin-top: 20px;
  justify-content: flex-end;
}
/* Keep styles on the editor content so they also apply inside the teleported modal. */
.product-editor-heading {
  display: flex;
  align-items: center;
  gap: 12px;
}
.product-editor-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  border-radius: 12px;
  color: var(--primary-color);
  background: color-mix(in srgb, var(--primary-color) 10%, transparent);
}
.product-editor-heading h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}
.product-editor-heading p {
  margin: 4px 0 0;
  font-size: 12px;
  font-weight: 400;
  opacity: 0.55;
}
.product-editor-body {
  max-height: min(66dvh, calc(100dvh - 210px));
  overflow-y: auto;
  padding-right: 6px;
  scrollbar-gutter: stable;
}
.product-form-section {
  padding: 16px 16px 0;
  border: 1px solid color-mix(in srgb, currentColor 9%, transparent);
  border-radius: 10px;
  background: color-mix(in srgb, currentColor 2%, transparent);
}
.product-form-section + .product-form-section {
  margin-top: 14px;
}
.product-section-heading {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  font-size: 14px;
  font-weight: 600;
}
.product-section-heading > :first-child {
  color: var(--primary-color);
}
.product-section-heading small {
  margin-left: auto;
  font-size: 12px;
  font-weight: 400;
  opacity: 0.5;
}
.product-field-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  column-gap: 18px;
}
.product-field-grid :deep(.n-form-item) {
  min-width: 0;
}
.product-field-grid :deep(.n-input-number) {
  width: 100%;
}
.product-spec-placeholder,
.product-spec-empty {
  grid-column: 1 / -1;
  padding: 12px 0 28px;
}
.product-spec-placeholder {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 10px;
  opacity: 0.65;
}
.product-editor-footer {
  display: flex;
  justify-content: flex-end;
  padding-top: 14px;
  border-top: 1px solid color-mix(in srgb, currentColor 9%, transparent);
}
@media (max-width: 600px) {
  .product-field-grid {
    grid-template-columns: minmax(0, 1fr);
  }
  .product-form-section {
    padding: 12px 12px 0;
  }
}
@media (max-width: 800px) {
  .product-catalog-page {
    overflow: auto;
  }
  .product-layout {
    grid-template-columns: minmax(0, 1fr);
    grid-template-rows: auto auto;
    flex: none;
  }
  .category-panel {
    height: min(420px, 50dvh);
  }
  .product-panel {
    overflow: visible;
  }
}
</style>
