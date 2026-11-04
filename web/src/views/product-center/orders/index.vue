<template>
  <n-card title="订单管理">
    <n-space class="toolbar" :wrap="true">
      <n-input
        v-model:value="keyword"
        clearable
        placeholder="订单号、订单名称、客户"
        @keyup.enter="search"
      />
      <n-select
        v-model:value="customerId"
        class="customer-filter"
        clearable
        filterable
        placeholder="筛选客户"
        :options="customers"
        :render-label="renderCustomer"
        @update:value="search"
      />
      <n-button :disabled="busy" @click="search">查询</n-button>
      <n-button
        type="primary"
        :disabled="busy || optionsLoading || !!optionsError"
        @click="openEditor()"
        >新增订单</n-button
      >
    </n-space>
    <n-alert v-if="loadError || optionsError" type="error" class="toolbar">
      {{ loadError || optionsError }}
      <n-button text :disabled="busy" @click="reload">重试</n-button>
    </n-alert>
    <n-data-table
      :columns="columns"
      :data="rows"
      :loading="loading"
      :scroll-x="1260"
      :row-key="(row) => row.id"
    >
      <template #empty><n-empty description="暂无订单" /></template>
    </n-data-table>
    <n-pagination
      v-model:page="page"
      :page-size="20"
      :item-count="total"
      :disabled="busy || loading"
      class="pagination"
      @update:page="load"
    />
  </n-card>
  <n-modal
    v-model:show="editor.show"
    preset="card"
    :title="editor.readonly ? '订单详情' : form.id ? '编辑订单' : '新增订单'"
    style="width: min(850px, calc(100vw - 24px))"
    :closable="!busy"
    :mask-closable="!busy"
    :close-on-esc="!busy"
  >
    <n-form label-placement="top" :disabled="busy || editor.readonly">
      <n-form-item v-if="form.order_no" label="订单号"
        ><n-input :value="form.order_no" disabled
      /></n-form-item>
      <n-form-item label="订单名称" required
        ><n-input v-model:value="form.name" :maxlength="160"
      /></n-form-item>
      <n-form-item label="客户" required>
        <n-select
          v-model:value="form.customer_id"
          filterable
          :options="editorCustomers"
          :render-label="renderCustomer"
        />
      </n-form-item>
      <n-form-item label="产品明细" required>
        <div class="items">
          <div v-for="(item, index) in form.items" :key="item.key" class="item-row">
            <n-tree-select
              v-model:value="item.category_id"
              filterable
              placeholder="选择产品分类"
              :options="categoryTree"
              @update:value="item.product_id = null"
            />
            <n-select
              v-model:value="item.product_id"
              filterable
              placeholder="选择产品（名称 / SKU）"
              :disabled="busy || editor.readonly || item.category_id === null"
              :options="productOptions(item)"
            />
            <n-input-number
              v-model:value="item.quantity"
              :min="1"
              :max="1000000"
              :precision="0"
              placeholder="数量"
            />
            <CButton
              v-if="!editor.readonly"
              show-delete
              :disabled="busy"
              @delete="form.items.splice(index, 1)"
            />
          </div>
          <CButton
            v-if="!editor.readonly"
            show-save
            save-text="添加产品"
            :disabled="busy || form.items.length >= 200"
            @save="addItem"
          />
        </div>
      </n-form-item>
      <n-form-item label="备注"
        ><n-input v-model:value="form.remark" type="textarea" :maxlength="5000"
      /></n-form-item>
    </n-form>
    <template #footer>
      <CButton
        show-cancel
        :show-save="!editor.readonly"
        :cancel-text="editor.readonly ? '关闭' : '取消'"
        :disabled="busy"
        :save-loading="saving"
        @cancel="editor.show = false"
        @save="save"
      />
    </template>
  </n-modal>
  <n-modal
    v-model:show="deletion.show"
    preset="card"
    title="删除订单"
    style="width: min(460px, calc(100vw - 24px))"
    :closable="!busy"
    :mask-closable="!busy"
    :close-on-esc="!busy"
  >
    确认删除订单“{{ deletion.row?.name }}”及其产品明细？删除后无法恢复。
    <template #footer>
      <CButton
        show-cancel
        show-delete
        :disabled="busy"
        :delete-loading="deleting"
        @cancel="deletion.show = false"
        @delete="remove"
      />
    </template>
  </n-modal>
</template>

<script setup>
import { computed, h, onMounted, reactive, ref } from 'vue'
import { NButton, NSpace, NTag, NTooltip } from 'naive-ui'
import api from '@/api'
import CButton from '@/components/public/CButton.vue'
import TheIcon from '@/components/icon/TheIcon.vue'

defineOptions({ name: '订单管理' })
const service = api.productCenterApi
const rows = ref([]),
  customers = ref([]),
  categories = ref([]),
  categoryNodes = ref([]),
  products = ref([])
const loading = ref(false),
  optionsLoading = ref(false),
  saving = ref(false),
  deleting = ref(false),
  opening = ref(null)
const loadError = ref(''),
  optionsError = ref(''),
  keyword = ref(''),
  customerId = ref(null)
const page = ref(1),
  total = ref(0)
const editor = reactive({ show: false, readonly: false })
const deletion = reactive({ show: false, row: null })
const form = reactive({ items: [] })
const original = ref(null)
const busy = computed(() => saving.value || deleting.value || opening.value !== null)
let itemKey = 0
let requestId = 0

async function load() {
  const current = ++requestId
  loading.value = true
  loadError.value = ''
  try {
    const result = await service.listOrders({
      page: page.value,
      page_size: 20,
      keyword: keyword.value,
      customer_id: customerId.value || undefined,
    })
    if (current === requestId) {
      rows.value = result.data
      total.value = result.total
    }
  } catch (error) {
    if (current === requestId) {
      rows.value = []
      total.value = 0
      loadError.value = error.message || '订单加载失败'
    }
  } finally {
    if (current === requestId) loading.value = false
  }
}
function search() {
  page.value = 1
  load()
}
async function loadOptions() {
  optionsLoading.value = true
  optionsError.value = ''
  try {
    const result = await service.options()
    customers.value = result.data.customers || []
    categories.value = result.data.categories || []
    categoryNodes.value = result.data.category_tree || []
    products.value = (result.data.products || []).map((item) => ({
      ...item,
      label: `${item.label} · ${item.code || '-'}`,
    }))
  } catch (error) {
    optionsError.value = error.message || '客户和产品选项加载失败'
  } finally {
    optionsLoading.value = false
  }
}
async function reload() {
  await Promise.all([load(), loadOptions()])
}
const editorCustomers = computed(() => {
  const options = [...customers.value]
  if (original.value && !options.some((item) => item.value === original.value.customer_id)) {
    options.push({
      value: original.value.customer_id,
      label: original.value.customer_name,
      signing_entity_name: original.value.signing_entity_name,
    })
  }
  return options
})
const availableProducts = computed(() => {
  const options = [...products.value]
  for (const item of original.value?.items || []) {
    if (!options.some((option) => option.value === item.product_id)) {
      options.push({
        value: item.product_id,
        label: `${item.product_name} · ${item.product_code || '-'}（已下架）`,
        category_id: item.category_id,
        category_name: item.category_name,
      })
    }
  }
  return options
})
const categoryTree = computed(() => {
  const options = [...categoryNodes.value]
  const keys = new Set()
  function collectKeys(nodes) {
    for (const node of nodes) {
      keys.add(node.key)
      if (node.children) collectKeys(node.children)
    }
  }
  collectKeys(options)
  for (const product of availableProducts.value) {
    const value = product.category_id || 0
    if (!keys.has(value)) {
      options.push({ key: value, value, label: product.category_name || '未分类' })
      keys.add(value)
    }
  }
  return options
})
function productOptions(line) {
  if (line.category_id === null) return []
  const ids = new Set([line.category_id])
  // Selecting a parent category also includes products in its descendants.
  let previousSize
  do {
    previousSize = ids.size
    for (const category of categories.value) {
      if (ids.has(category.parent_id)) ids.add(category.value)
    }
  } while (ids.size !== previousSize)
  return availableProducts.value
    .filter((item) => ids.has(item.category_id || 0))
    .map((item) => ({
      ...item,
      disabled:
        item.value !== line.product_id &&
        form.items.some((other) => other.product_id === item.value),
    }))
}
function addItem() {
  form.items.push({ key: ++itemKey, category_id: null, product_id: null, quantity: 1 })
}
async function openEditor(row = null, readonly = false) {
  if (busy.value) return
  opening.value = row?.id || 0
  try {
    const data = row ? (await service.getOrder(row.id)).data : null
    original.value = data
    Object.assign(form, {
      id: data?.id || null,
      order_no: data?.order_no || '',
      name: data?.name || '',
      customer_id: data?.customer_id || null,
      remark: data?.remark || '',
      items: (data?.items || []).map((item) => ({
        ...item,
        category_id: item.category_id || 0,
        key: ++itemKey,
      })),
    })
    if (!data) addItem()
    editor.readonly = readonly
    editor.show = true
  } catch {
    /* 请求封装显示错误 */
  } finally {
    opening.value = null
  }
}
async function save() {
  if (busy.value) return
  if (
    !form.name.trim() ||
    !form.customer_id ||
    !form.items.length ||
    form.items.some(
      (item) => !item.product_id || !Number.isInteger(item.quantity) || item.quantity < 1
    )
  ) {
    return window.$message?.warning('请填写订单名称、客户和至少一条有效产品明细')
  }
  saving.value = true
  try {
    const payload = {
      name: form.name.trim(),
      customer_id: form.customer_id,
      remark: form.remark,
      items: form.items.map(({ product_id, quantity }) => ({ product_id, quantity })),
    }
    if (form.id) await service.updateOrder(form.id, payload)
    else await service.createOrder(payload)
    editor.show = false
    window.$message?.success('订单已保存')
    await load()
  } catch {
    /* 保留表单以便重试 */
  } finally {
    saving.value = false
  }
}
async function remove() {
  if (busy.value) return
  deleting.value = true
  try {
    await service.deleteOrder(deletion.row.id)
    deletion.show = false
    if (rows.value.length === 1 && page.value > 1) page.value -= 1
    window.$message?.success('订单已删除')
    await load()
  } catch {
    /* 保留确认弹窗以便重试 */
  } finally {
    deleting.value = false
  }
}
function renderCustomer(option) {
  const entity = String(option.signing_entity_name || '').toLowerCase()
  const tag = entity.includes('科特思')
    ? ['科', 'success']
    : entity.includes('77')
    ? ['7', 'warning']
    : entity.includes('catixs')
    ? ['C', 'info']
    : null
  return h(
    'span',
    {
      style:
        'display:flex;align-items:center;justify-content:space-between;gap:12px;width:100%;min-width:0',
    },
    [
      h(
        'span',
        { style: 'overflow:hidden;text-overflow:ellipsis;white-space:nowrap' },
        option.label
      ),
      tag
        ? h(
            NTag,
            { size: 'small', round: true, type: tag[1], style: 'flex-shrink:0' },
            { default: () => tag[0] }
          )
        : null,
    ]
  )
}
function action(row, label, icon, callback, type = 'default') {
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
          disabled:
            busy.value ||
            loading.value ||
            editor.show ||
            deletion.show ||
            (label === '编辑' && (optionsLoading.value || !!optionsError.value)),
          loading:
            (opening.value === row.id && label !== '删除') ||
            (deleting.value && deletion.row?.id === row.id && label === '删除'),
          onClick: (event) => {
            event.stopPropagation()
            callback()
          },
        },
        { icon: () => h(TheIcon, { icon, size: 17 }) }
      ),
    default: () => label,
  })
}
const columns = [
  { title: '订单号', key: 'order_no', width: 330, resizable: true },
  { title: '订单名称', key: 'name', width: 180, resizable: true, ellipsis: { tooltip: true } },
  { title: '客户', key: 'customer_name', width: 180, resizable: true },
  {
    title: '产品明细',
    key: 'items',
    width: 260,
    resizable: true,
    ellipsis: { tooltip: true },
    render: (row) => row.items.map((item) => `${item.product_name} × ${item.quantity}`).join('；'),
  },
  { title: '创建时间', key: 'created_at', width: 180, resizable: true },
  {
    title: '操作',
    key: 'actions',
    width: 130,
    fixed: 'right',
    render: (row) =>
      h(
        NSpace,
        { wrap: false, size: 4 },
        {
          default: () => [
            action(row, '查看', 'mdi:eye-outline', () => openEditor(row, true)),
            action(row, '编辑', 'mdi:pencil-outline', () => openEditor(row)),
            action(
              row,
              '删除',
              'mdi:trash-can-outline',
              () => {
                deletion.row = row
                deletion.show = true
              },
              'error'
            ),
          ],
        }
      ),
  },
]
onMounted(reload)
</script>

<style scoped>
.toolbar {
  margin-bottom: 16px;
}
.customer-filter {
  width: 260px;
}
.pagination {
  margin-top: 16px;
  justify-content: flex-end;
}
.items {
  width: 100%;
}
.item-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.4fr) 100px auto;
  gap: 12px;
  margin-bottom: 12px;
}
:deep(.customer-select-option .n-base-select-option__content) {
  width: 100%;
}
@media (max-width: 600px) {
  .item-row {
    grid-template-columns: minmax(0, 1fr) 100px;
  }
  .item-row > :first-child,
  .item-row > :nth-child(2) {
    grid-column: 1 / -1;
  }
  .customer-filter {
    width: 220px;
  }
}
</style>
