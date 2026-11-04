<template>
  <AppPage :show-footer="false" class="product-catalog-page">
    <div class="product-layout">
      <n-card title="产品分类" class="category-panel">
        <template #header-extra
          ><n-button size="small" :disabled="busy" @click="editCategory()"
            >新增分类</n-button
          ></template
        >
        <n-button text :disabled="busy" @click="selectCategory([])">全部产品</n-button>
        <div class="category-tree cus-scroll-y">
          <n-tree
            block-line
            default-expand-all
            :data="categoryTree"
            :selected-keys="selectedKeys"
            :disabled="busy"
            @update:selected-keys="selectCategory"
          />
          <n-empty v-if="!categoryTree.length && !optionsLoading" description="暂无分类" />
        </div>
        <n-space class="filters">
          <n-button
            size="small"
            :disabled="!selectedCategory || busy"
            @click="editCategory(selectedCategory)"
            >编辑分类</n-button
          >
          <n-button
            size="small"
            type="error"
            secondary
            :disabled="!selectedCategory || busy"
            @click="confirmDelete(selectedCategory, 'category')"
            >删除分类</n-button
          >
        </n-space>
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
            placeholder="搜索 SKU / 产品名称"
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
          :scroll-x="1130"
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
      style="width: min(560px, calc(100vw - 32px))"
      :mask-closable="!saving"
      :close-on-esc="!saving"
      :closable="!saving"
    >
      <n-form label-placement="top" :disabled="saving">
        <n-form-item label="SKU"
          ><n-input
            v-model:value="editor.form.code"
            placeholder="留空按分类编码自动生成，如 NET.TRANSIT-001"
            :disabled="Boolean(editor.form.id)"
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
      </n-form>
      <template #footer
        ><CButton
          :show-cancel="true"
          :show-save="true"
          :disabled="saving"
          :save-loading="saving"
          @cancel="editor.show = false"
          @save="saveProduct"
      /></template>
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
    <ProductPriceVersions
      v-if="priceProduct"
      :product="priceProduct"
      :customers="options.customers || []"
      :units="units"
      @close="priceProduct = null"
    />
  </AppPage>
</template>

<script setup>
import { computed, h, onMounted, reactive, ref } from 'vue'
import { NButton, NSelect, NSpace, NTag, NTooltip } from 'naive-ui'
import api from '@/api'
import TheIcon from '@/components/icon/TheIcon.vue'
import CButton from '@/components/public/CButton.vue'
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
const priceProduct = ref(null)
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
    optionError.value = e.message || '分类与客户选项加载失败'
  } finally {
    optionsLoading.value = false
  }
}
function editProduct(row) {
  editor.form = row
    ? { ...row }
    : {
        code: '',
        name: '',
        category_id: query.category_id,
        billing_unit: 'month',
        min_contract_months: 1,
        status: 'active',
      }
  editor.show = true
}
async function saveProduct() {
  if (busy.value) return
  const form = { ...editor.form, name: editor.form.name?.trim() }
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
async function changeCategory(row, categoryId) {
  if (busy.value || categoryId === row.category_id) return
  rowSaving.value = row.id
  try {
    await service.updateProduct(row.id, { ...row, category_id: categoryId })
    await loadProducts()
  } catch {
    /* 失败时保留原分类 */
  } finally {
    rowSaving.value = null
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
    { title: 'SKU', key: 'code', width: 150 },
    { title: '产品名称', key: 'name', width: 220, ellipsis: { tooltip: true } },
    {
      title: '分类',
      key: 'category_id',
      width: 220,
      render: (row) =>
        h('div', { onClick: (e) => e.stopPropagation() }, [
          h(NSelect, {
            value: row.category_id,
            options: categories.value.map((item) => ({ label: item.name, value: item.id })),
            filterable: true,
            disabled: busy.value || optionsLoading.value,
            loading: rowSaving.value === row.id,
            'onUpdate:value': (value) => changeCategory(row, value),
          }),
        ]),
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
      width: 150,
      fixed: 'right',
      render: (row) =>
        h(
          NSpace,
          { wrap: false, size: 6 },
          {
            default: () => [
              actionButton(row, '编辑', 'mdi:pencil-outline', 'info', () => editProduct(row)),
              actionButton(row, '删除', 'mdi:delete-outline', 'error', () =>
                confirmDelete(row, 'product')
              ),
              actionButton(row, '价格方案', 'mdi:currency-usd', 'primary', () => {
                priceProduct.value = row
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
}
.category-panel :deep(.n-card-header),
.category-panel :deep(.n-card__content > .n-button),
.category-panel .filters {
  flex-shrink: 0;
}
.category-tree {
  flex: 1;
  min-height: 0;
  overflow: auto;
  scrollbar-gutter: stable;
}
.filters {
  margin: 16px 0;
}
.pagination {
  margin-top: 20px;
  justify-content: flex-end;
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
