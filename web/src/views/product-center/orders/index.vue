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
    <div v-if="editor.readonly" class="order-detail" :style="detailTheme">
      <section class="detail-summary">
        <div class="detail-eyebrow">订单概览</div>
        <h2 class="detail-title">{{ form.name || '未命名订单' }}</h2>
        <div class="detail-order-no">{{ form.order_no }}</div>
        <dl class="detail-meta">
          <div>
            <dt>关联客户</dt>
            <dd>{{ original?.customer_name || '—' }}</dd>
          </div>
          <div>
            <dt>签约主体</dt>
            <dd>{{ original?.signing_entity_name || '—' }}</dd>
          </div>
          <div>
            <dt>创建时间</dt>
            <dd>{{ original?.created_at || '—' }}</dd>
          </div>
          <div>
            <dt>更新时间</dt>
            <dd>{{ original?.updated_at || '—' }}</dd>
          </div>
        </dl>
      </section>
      <section class="detail-products">
        <div class="detail-section-heading">
          <h3>产品明细</h3>
          <span>{{ form.items.length }} 项产品</span>
        </div>
        <article v-for="(item, index) in form.items" :key="item.key" class="detail-product">
          <div class="detail-product-heading">
            <span class="detail-product-index">{{ String(index + 1).padStart(2, '0') }}</span>
            <div class="detail-product-info">
              <h4>{{ item.product_name || '未命名产品' }}</h4>
              <div class="detail-product-meta">
                <n-tag v-if="item.variant_name" size="small" :bordered="false" type="info">{{
                  item.variant_name
                }}</n-tag>
                <n-tag size="small" :bordered="false">{{ item.category_name || '未分类' }}</n-tag>
                <span>产品编号 · {{ item.product_code || '—' }}</span>
              </div>
            </div>
            <div class="detail-quantity">
              <span>数量</span><strong>× {{ item.quantity }}</strong>
            </div>
          </div>
          <div v-if="item.spec_snapshot?.length" class="detail-specs">
            <span v-for="field in item.spec_snapshot" :key="field.id"
              >{{ field.name }}：{{ specValue(field.value) }}{{ field.unit || '' }}</span
            >
          </div>
          <div v-if="item.price_version_id" class="detail-price-status">
            <n-tag
              :type="item.price_reference ? 'warning' : 'success'"
              size="small"
              :bordered="false"
            >
              {{ item.price_reference ? '公共参考价 · 尚未保存' : '订单已保存价格' }}
            </n-tag>
            <span
              >{{ item.currency }} · 每 {{ item.period_months }} 个月结算 ·
              {{ unitLabel(item.billing_unit) }}</span
            >
          </div>
          <div class="detail-prices">
            <div class="detail-price">
              <div class="detail-price-label">MRC <span>每单位月费</span></div>
              <div class="detail-price-amount">
                <small v-if="item.mrc != null">{{ item.currency }}</small
                ><strong>{{ displayMoney(item.mrc) }}</strong>
              </div>
              <div v-if="item.base_mrc != null" class="detail-price-base">
                公共价格 {{ item.currency }} {{ displayMoney(item.base_mrc) }}
              </div>
              <div class="mrc-subtotal">
                月费小计：{{ item.currency }} {{ displayMoney(mrcSubtotal(item)) }}
                <span>（单价 × {{ item.quantity }}）</span>
              </div>
            </div>
            <div class="detail-price">
              <div class="detail-price-label">NRC <span>每单位一次性费用</span></div>
              <div class="detail-price-amount">
                <small v-if="item.nrc != null">{{ item.currency }}</small
                ><strong>{{ displayMoney(item.nrc) }}</strong>
              </div>
              <div v-if="item.base_nrc != null" class="detail-price-base">
                公共价格 {{ item.currency }} {{ displayMoney(item.base_nrc) }}
              </div>
            </div>
          </div>
          <div v-if="item.price_error" class="detail-price-error">
            <n-alert type="error">{{ item.price_error }}</n-alert>
            <CButton
              show-save
              save-text="重试加载价格"
              :disabled="busy"
              :save-loading="item.price_loading"
              @save="inheritPrice(item, true)"
            />
          </div>
          <p v-else-if="!item.price_version_id" class="detail-price-note">
            {{ item.price_loading ? '正在读取公共价格…' : '暂无公共价格，订单尚未定价' }}
          </p>
          <p v-else class="detail-price-note">
            来源：公共价格 V{{ item.price_version_number
            }}<span v-if="item.price_reference"> · 仅供参考，编辑保存后形成订单价格</span>
          </p>
        </article>
        <n-empty v-if="!form.items.length" description="暂无产品明细" />
      </section>
      <section class="detail-remark">
        <div class="detail-section-heading"><h3>备注</h3></div>
        <p :class="{ 'detail-muted': !form.remark }">{{ form.remark || '暂无备注' }}</p>
      </section>
    </div>
    <n-form v-else label-placement="top" :disabled="busy || editor.readonly">
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
        <div class="items" :style="detailTheme">
          <section
            v-for="(item, index) in form.items"
            :key="item.key"
            class="item-card"
            :aria-label="`产品明细 ${index + 1}`"
          >
            <div class="item-card-heading">
              <div class="item-card-title">
                <span class="item-card-index">{{ index + 1 }}</span
                >产品明细
              </div>
              <CButton
                v-if="!editor.readonly"
                show-delete
                :disabled="busy"
                @delete="form.items.splice(index, 1)"
              />
            </div>
            <div class="item-row">
              <n-tree-select
                v-model:value="item.category_id"
                filterable
                placeholder="选择产品分类"
                :options="categoryTree"
                @update:value="clearProduct(item)"
              />
              <n-select
                v-model:value="item.product_id"
                class="item-product"
                filterable
                placeholder="选择产品（名称 / 编号）"
                :disabled="busy || editor.readonly || item.category_id === null"
                :options="productOptions(item)"
                @update:value="changeProduct(item)"
              />
              <n-select
                v-model:value="item.variant_id"
                class="item-variant"
                filterable
                :placeholder="hasNoVariants(item) ? '无规格' : '选择规格组合'"
                :options="variantOptions(item)"
                :loading="item.variant_loading"
                :disabled="busy || !item.product_id || hasNoVariants(item)"
                @update:value="changeVariant(item)"
              />
              <n-input-number
                v-model:value="item.quantity"
                class="item-quantity"
                :min="1"
                :max="1000000"
                :precision="0"
                placeholder="数量"
              />
              <div class="item-prices">
                <n-alert v-if="item.variant_error" type="error"
                  >{{ item.variant_error
                  }}<CButton
                    show-save
                    save-text="重试加载组合"
                    :disabled="busy"
                    @save="loadVariants(item)"
                /></n-alert>
                <p
                  v-else-if="
                    item.product_id && !item.variant_loading && !variantOptions(item).length
                  "
                >
                  {{
                    hasNoVariants(item)
                      ? '无规格产品，直接使用产品公共价格。'
                      : '暂无可选组合，请先启用规格组合。'
                  }}
                </p>
                <p v-if="item.spec_snapshot?.length">
                  {{
                    item.spec_snapshot
                      .map((field) => `${field.name}：${specValue(field.value)}${field.unit || ''}`)
                      .join('；')
                  }}
                </p>
                <div class="price-context">
                  <span v-if="editor.readonly && item.price_reference" class="price-reference">
                    当前公共参考价（订单尚未保存价格）
                  </span>
                  <span v-if="item.price_version_id">
                    {{ item.currency }} · 每 {{ item.period_months }} 个月结算 · 单位：{{
                      unitLabel(item.billing_unit)
                    }}
                    · 公共价格 V{{ item.price_version_number }}：MRC {{ item.base_mrc }} / NRC
                    {{ item.base_nrc }}
                  </span>
                  <span v-else-if="!item.price_error">{{
                    item.price_loading ? '正在读取公共价格…' : '暂无公共价格，订单尚未定价'
                  }}</span>
                  <CButton
                    v-if="item.product_id && (!editor.readonly || item.price_error)"
                    show-save
                    :save-text="editor.readonly ? '重试加载价格' : '继承最新公共价格'"
                    :disabled="busy"
                    :save-loading="item.price_loading"
                    @save="inheritPrice(item, editor.readonly)"
                  />
                </div>
                <n-alert v-if="item.price_error" type="error">{{ item.price_error }}</n-alert>
                <div class="price-inputs">
                  <label
                    >MRC（每单位月费）
                    <n-input
                      v-model:value="item.mrc"
                      :placeholder="editor.readonly ? '暂无价格' : '继承公共 MRC'"
                      :readonly="editor.readonly"
                      :disabled="editor.readonly ? false : busy || !item.price_version_id"
                    />
                    <div class="mrc-subtotal" aria-live="polite">
                      月费小计：{{ item.currency }} {{ displayMoney(mrcSubtotal(item)) }}
                      <span>（单价 × {{ item.quantity }}）</span>
                    </div>
                  </label>
                  <label
                    >NRC（每单位一次性费用）
                    <n-input
                      v-model:value="item.nrc"
                      :placeholder="editor.readonly ? '暂无价格' : '继承公共 NRC'"
                      :readonly="editor.readonly"
                      :disabled="editor.readonly ? false : busy || !item.price_version_id"
                    />
                  </label>
                </div>
              </div>
            </div>
          </section>
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
import { NButton, NSpace, NTag, NTooltip, useThemeVars } from 'naive-ui'
import api from '@/api'
import CButton from '@/components/public/CButton.vue'
import TheIcon from '@/components/icon/TheIcon.vue'

defineOptions({ name: '订单管理' })
const themeVars = useThemeVars()
const detailTheme = computed(() => ({
  '--detail-muted': themeVars.value.textColor3,
  '--detail-border': themeVars.value.borderColor,
  '--detail-surface': themeVars.value.actionColor,
  '--detail-accent': themeVars.value.primaryColor,
}))
function displayMoney(value) {
  if (value === null || value === undefined || value === '') return '—'
  const [integer, fraction = ''] = String(value).split('.')
  return `${integer.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}.${fraction.padEnd(2, '0')}`
}
function mrcSubtotal(item) {
  const value = item.mrc === null || item.mrc === '' ? item.base_mrc : item.mrc
  if (
    value == null ||
    !/^(?:0|[1-9]\d{0,13})(?:\.\d{1,2})?$/.test(String(value)) ||
    !Number.isInteger(item.quantity) ||
    item.quantity < 1
  )
    return null
  const [integer, fraction = ''] = String(value).split('.')
  const cents = (BigInt(integer) * 100n + BigInt(fraction.padEnd(2, '0'))) * BigInt(item.quantity)
  return `${cents / 100n}.${String(cents % 100n).padStart(2, '0')}`
}
const service = api.productCenterApi
const rows = ref([]),
  customers = ref([]),
  categories = ref([]),
  categoryNodes = ref([]),
  units = ref([]),
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
const variants = ref({})
const busy = computed(
  () =>
    saving.value ||
    deleting.value ||
    opening.value !== null ||
    form.items.some((item) => item.price_loading || item.variant_loading)
)
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
    units.value = result.data.billing_units || []
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
  return availableProducts.value.filter((item) => ids.has(item.category_id || 0))
}
function addItem() {
  form.items.push({
    key: ++itemKey,
    category_id: null,
    product_id: null,
    variant_id: null,
    variant_loading: false,
    variant_error: '',
    quantity: 1,
    ...emptyPrice(),
  })
}
function emptyPrice() {
  return {
    price_version_id: null,
    price_version_number: null,
    currency: null,
    period_months: null,
    billing_unit: null,
    base_mrc: null,
    base_nrc: null,
    mrc: null,
    nrc: null,
    price_loading: false,
    price_error: '',
    price_reference: false,
  }
}
function unitLabel(value) {
  return units.value.find((item) => item.value === value)?.label || value
}
function clearProduct(item) {
  item.product_id = null
  item.variant_id = null
  item.spec_snapshot = []
  item.variant_error = ''
  Object.assign(item, emptyPrice())
}
async function changeProduct(item) {
  Object.assign(item, emptyPrice())
  item.variant_id = null
  item.spec_snapshot = []
  await loadVariants(item)
  const choices = variantOptions(item).filter((option) => !option.disabled)
  if (choices.length === 1) {
    item.variant_id = choices[0].value
    await changeVariant(item)
  } else if (!item.variant_error && hasNoVariants(item)) {
    await changeVariant(item)
  }
}
function hasNoVariants(item) {
  return Array.isArray(variants.value[item.product_id]) && !variants.value[item.product_id].length
}
function specValue(value) {
  return Array.isArray(value)
    ? value.join(' / ')
    : typeof value === 'boolean'
    ? value
      ? '是'
      : '否'
    : value
}
function variantOptions(item) {
  return (variants.value[item.product_id] || [])
    .filter(
      (variant) =>
        variant.status === 'active' ||
        original.value?.items.some(
          (old) => old.product_id === item.product_id && old.variant_id === variant.id
        )
    )
    .map((variant) => ({
      label: `${variant.name}${variant.status === 'offline' ? '（已下架）' : ''}`,
      value: variant.id,
      disabled: form.items.some((other) => other !== item && other.variant_id === variant.id),
    }))
}
async function loadVariants(item) {
  if (!item.product_id) return
  item.variant_loading = true
  item.variant_error = ''
  try {
    variants.value[item.product_id] = (await service.listVariants(item.product_id)).data || []
  } catch (e) {
    item.variant_error = e.message || '规格组合加载失败'
  } finally {
    item.variant_loading = false
  }
}
async function changeVariant(item) {
  Object.assign(item, emptyPrice())
  const variant = (variants.value[item.product_id] || []).find((row) => row.id === item.variant_id)
  item.spec_snapshot = variant?.spec_snapshot || []
  item.variant_name = variant?.name
  item.variant_code = variant?.code
  if (item.variant_id || hasNoVariants(item)) await inheritPrice(item)
}
async function inheritPrice(item, referenceOnly = false) {
  if (item.price_loading || !item.product_id || (!item.variant_id && !hasNoVariants(item))) return
  item.price_loading = true
  item.price_error = ''
  try {
    const result = await service.getOrderPrice(item.product_id, item.variant_id)
    if (result.data) Object.assign(item, result.data, { price_reference: referenceOnly })
    else if (item.price_version_id) window.$message?.warning('暂无公共价格，保留订单原价格')
  } catch (error) {
    item.price_error = error.message || '公共价格加载失败，请重试'
  } finally {
    item.price_loading = false
  }
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
        ...emptyPrice(),
        ...item,
        category_id: item.category_id || 0,
        key: ++itemKey,
      })),
    })
    if (!data) addItem()
    if (data) {
      if (!readonly) await Promise.all(form.items.map(loadVariants))
      await Promise.all(
        form.items
          .filter((item) => !item.price_version_id)
          .map((item) => inheritPrice(item, readonly))
      )
    }
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
  if (form.items.some((item) => item.price_error))
    return window.$message?.warning('请先重试加载失败的公共价格')
  const validMoney = (value) =>
    value === null || value === '' || /^(?:0|[1-9]\d{0,13})(?:\.\d{1,2})?$/.test(value)
  if (form.items.some((item) => !validMoney(item.mrc) || !validMoney(item.nrc))) {
    return window.$message?.warning('MRC、NRC 必须是非负金额，最多两位小数')
  }
  if (
    !form.name.trim() ||
    !form.customer_id ||
    !form.items.length ||
    form.items.some(
      (item) =>
        !item.product_id ||
        (!item.variant_id && !hasNoVariants(item)) ||
        item.variant_error ||
        !Number.isInteger(item.quantity) ||
        item.quantity < 1
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
      items: form.items.map(({ product_id, variant_id, quantity, price_version_id, mrc, nrc }) => ({
        product_id,
        variant_id,
        quantity,
        price_version_id,
        mrc: mrc || null,
        nrc: nrc || null,
      })),
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
    render: (row) =>
      row.items
        .map(
          (item) =>
            `${item.product_name}${item.variant_name ? ` · ${item.variant_name}` : ''} × ${
              item.quantity
            }`
        )
        .join('；'),
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
.mrc-subtotal {
  margin-top: 8px;
  font-size: 13px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.mrc-subtotal span {
  font-weight: 400;
  opacity: 0.65;
}
.detail-specs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 18px;
  margin-top: 12px;
  font-size: 12px;
  color: var(--detail-muted);
}
.order-detail {
  max-height: 68vh;
  overflow-y: auto;
  padding-right: 8px;
  overflow-wrap: anywhere;
}
.detail-summary {
  padding: 20px;
  border-radius: 12px;
  background: var(--detail-surface);
}
.detail-eyebrow {
  color: var(--detail-muted);
  font-size: 12px;
  margin-bottom: 8px;
}
.detail-title {
  margin: 0 0 10px;
  font-size: 20px;
  font-weight: 600;
  line-height: 1.5;
}
.detail-order-no {
  color: var(--detail-muted);
  font-size: 12px;
  font-family: monospace;
}
.detail-meta {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px 24px;
  margin: 20px 0 0;
  padding-top: 18px;
  border-top: 1px solid var(--detail-border);
}
.detail-meta dt {
  color: var(--detail-muted);
  font-size: 12px;
  margin-bottom: 4px;
}
.detail-meta dd {
  margin: 0;
}
.detail-section-heading {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 24px 0 12px;
}
.detail-section-heading h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}
.detail-section-heading > span {
  font-size: 12px;
  color: var(--detail-muted);
}
.detail-product {
  border: 1px solid var(--detail-border);
  border-radius: 12px;
  padding: 18px;
  margin-bottom: 14px;
}
.detail-product-heading {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}
.detail-product-index {
  background: var(--detail-surface);
  color: var(--detail-accent);
  border-radius: 8px;
  padding: 7px 9px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.detail-product-info {
  flex: 1;
  min-width: 0;
}
.detail-product-info h4 {
  font-size: 15px;
  line-height: 1.6;
  margin: 0 0 8px;
  font-weight: 600;
}
.detail-product-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  color: var(--detail-muted);
  font-size: 12px;
}
.detail-quantity {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  flex-shrink: 0;
}
.detail-quantity span {
  color: var(--detail-muted);
  font-size: 12px;
}
.detail-quantity strong {
  font-size: 18px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.detail-price-status {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  margin-top: 18px;
}
.detail-price-status > span {
  font-size: 12px;
  color: var(--detail-muted);
}
.detail-prices {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-top: 12px;
}
.detail-price {
  padding: 16px;
  border-radius: 8px;
  background: var(--detail-surface);
  min-width: 0;
}
.detail-price-label {
  font-weight: 600;
}
.detail-price-label span {
  margin-left: 6px;
  font-size: 12px;
  font-weight: 400;
  color: var(--detail-muted);
}
.detail-price-amount {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 6px;
  margin: 10px 0 6px;
  font-variant-numeric: tabular-nums;
}
.detail-price-amount strong {
  font-size: 25px;
  font-weight: 600;
  line-height: 1.3;
}
.detail-price-amount small {
  font-size: 12px;
  color: var(--detail-muted);
}
.detail-price-base,
.detail-price-note,
.detail-muted {
  color: var(--detail-muted);
  font-size: 12px;
}
.detail-price-note {
  margin: 12px 0 0;
}
.detail-price-error {
  display: grid;
  gap: 10px;
  margin-top: 12px;
}
.detail-remark p {
  margin: 0;
  padding: 14px 16px;
  border-radius: 8px;
  background: var(--detail-surface);
  white-space: pre-wrap;
  line-height: 1.7;
}
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
.item-card {
  margin-bottom: 18px;
  padding: 16px;
  border: 1px solid var(--detail-border);
  border-radius: 12px;
}
.item-card-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin: -16px -16px 16px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--detail-border);
  border-radius: 12px 12px 0 0;
  background: var(--detail-surface);
}
.item-card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
}
.item-card-index {
  color: var(--detail-accent);
  font-variant-numeric: tabular-nums;
}
.item-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.4fr) 100px;
  gap: 12px;
}
.item-prices {
  grid-column: 1 / -1;
  padding-top: 12px;
  border-top: 1px solid var(--detail-border);
  overflow-wrap: anywhere;
}
.item-product {
  grid-column: 2 / -1;
}
.item-variant {
  grid-column: 1 / 3;
}
.item-quantity {
  grid-column: 3;
}
.price-context {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}
.price-inputs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.price-inputs label {
  min-width: 0;
}
:deep(.customer-select-option .n-base-select-option__content) {
  width: 100%;
}
@media (max-width: 600px) {
  .order-detail {
    padding-right: 0;
  }
  .detail-summary,
  .detail-product {
    padding: 14px;
  }
  .detail-meta,
  .detail-prices {
    grid-template-columns: 1fr;
  }
  .detail-product-heading {
    flex-wrap: wrap;
  }
  .detail-product-index {
    display: none;
  }
  .detail-price-amount strong {
    font-size: 22px;
  }
  .item-row,
  .price-inputs {
    grid-template-columns: minmax(0, 1fr);
  }
  .item-row > * {
    grid-column: 1 / -1;
  }
  .customer-filter {
    width: 220px;
  }
}
</style>
