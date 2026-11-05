<template>
  <n-modal
    :show="true"
    preset="card"
    title="规格组合"
    style="width: min(1000px, calc(100vw - 24px))"
    :closable="!blocked"
    :mask-closable="!blocked"
    :close-on-esc="!blocked"
    @update:show="close"
  >
    <div class="variant-heading">
      <h3>{{ product.name }}</h3>
      <p>有规格的产品按组合维护公共价格；无规格的产品可直接配置价格。</p>
    </div>
    <n-space>
      <CButton show-save save-text="新增组合" :disabled="blocked || loading" @save="edit()" />
      <CButton
        v-if="!loading && !error && !rows.length"
        show-save
        save-text="直接配置价格（无规格）"
        :disabled="blocked"
        @save="productPriceOpen = true"
      />
    </n-space>
    <n-alert v-if="error" type="error" class="variant-gap"
      >{{ error }}<CButton show-save save-text="重试" :disabled="busy" @save="load"
    /></n-alert>
    <n-data-table
      class="variant-gap"
      :columns="columns"
      :data="rows"
      :loading="loading"
      :scroll-x="790"
      :max-height="420"
      :row-key="(row) => row.id"
    >
      <template #empty><n-empty description="暂无规格组合，无规格产品可直接配置价格" /></template>
    </n-data-table>
  </n-modal>
  <n-modal
    v-model:show="editor.show"
    preset="card"
    :title="form.id ? '编辑规格组合' : '新增规格组合'"
    style="width: min(700px, calc(100vw - 24px))"
    :closable="!busy"
    :mask-closable="!busy"
    :close-on-esc="!busy"
  >
    <n-form label-placement="top" :disabled="busy">
      <div class="variant-grid">
        <n-form-item label="组合名称" required
          ><n-input
            v-model:value="form.name"
            :maxlength="160"
            placeholder="例如 32核 / 128GB / 2TB"
        /></n-form-item>
        <n-form-item label="状态"
          ><n-select v-model:value="form.status" :options="statuses"
        /></n-form-item>
      </div>
      <n-alert v-if="fieldError" type="error"
        >{{ fieldError }}<CButton show-save save-text="重试" :disabled="busy" @save="loadFields"
      /></n-alert>
      <n-form-item label="规格属性">
        <div class="variant-attribute-picker">
          <div class="variant-category-hint">
            按产品分类过滤：{{ product.category_name || '当前产品所属分类' }}
          </div>
          <n-select
            :value="selectedFieldIds"
            filterable
            multiple
            :options="attributeOptions"
            :loading="fieldsLoading"
            :disabled="busy || !!fieldError"
            placeholder="从规格属性中选择需要的参数"
            @update:value="selectFields"
          />
          <p>必填属性默认选中，其余属性按需选择；选中后在下方填写参数值。</p>
        </div>
      </n-form-item>
      <n-spin :show="fieldsLoading">
        <div class="variant-grid variant-fields">
          <n-form-item
            v-for="field in selectedFields"
            :key="field.id"
            :label="field.unit ? `${field.name}（${field.unit}）` : field.name"
            :required="field.required"
          >
            <n-input-number
              v-if="field.attr_type === 'number'"
              v-model:value="form.spec_values[field.id]"
              clearable
            />
            <n-select
              v-else-if="['select', 'multi_select'].includes(field.attr_type)"
              v-model:value="form.spec_values[field.id]"
              :multiple="field.attr_type === 'multi_select'"
              :options="field.select_options"
              filterable
              clearable
            />
            <n-switch
              v-else-if="field.attr_type === 'switch'"
              v-model:value="form.spec_values[field.id]"
            />
            <n-date-picker
              v-else-if="field.attr_type === 'date'"
              v-model:formatted-value="form.spec_values[field.id]"
              type="date"
              value-format="yyyy-MM-dd"
              clearable
            />
            <n-input
              v-else
              v-model:value="form.spec_values[field.id]"
              :maxlength="2000"
              clearable
            />
          </n-form-item>
        </div>
      </n-spin>
      <n-alert v-if="legacyFields.length" type="info" class="variant-gap">
        以下历史参数已停用或不再属于当前分类，原值仍保留：
        {{
          legacyFields
            .map(
              (field) =>
                `${field.name}：${
                  Array.isArray(field.value) ? field.value.join(' / ') : field.value
                }`
            )
            .join('；')
        }}
      </n-alert>
      <n-empty
        v-if="!fieldsLoading && !fieldError && fields.length && !selectedFields.length"
        description="请先选择规格属性"
      />
      <n-empty
        v-if="!fieldsLoading && !fieldError && !fields.length"
        description="该分类暂无规格属性，可先在规格属性中配置"
      />
    </n-form>
    <template #footer
      ><CButton
        show-save
        show-cancel
        :disabled="busy"
        :save-loading="saving"
        @cancel="editor.show = false"
        @save="save"
    /></template>
  </n-modal>
  <n-modal
    v-model:show="deletion.show"
    preset="card"
    title="删除规格组合"
    style="width: min(460px, calc(100vw - 24px))"
    :closable="!busy"
    :mask-closable="!busy"
    :close-on-esc="!busy"
  >
    确认删除“{{ deletion.row?.name }}”？已关联价格或订单的组合请改为下架。
    <template #footer
      ><CButton
        show-cancel
        show-delete
        :disabled="busy"
        :delete-loading="saving"
        @cancel="deletion.show = false"
        @delete="remove"
    /></template>
  </n-modal>
  <ProductPriceVersions
    v-if="priceVariant || productPriceOpen"
    :product="product"
    :variant="priceVariant"
    :units="units"
    @close="closePrices"
  />
</template>

<script setup>
import { computed, h, onMounted, reactive, ref } from 'vue'
import { NButton, NSpace, NTag, NTooltip } from 'naive-ui'
import api from '@/api'
import CButton from '@/components/public/CButton.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import ProductPriceVersions from './ProductPriceVersions.vue'

const props = defineProps({
  product: { type: Object, required: true },
  units: { type: Array, default: () => [] },
})
const emit = defineEmits(['close'])
const service = api.productCenterApi
const rows = ref([]),
  loading = ref(false),
  saving = ref(false),
  error = ref('')
const fields = ref([]),
  fieldsLoading = ref(false),
  fieldError = ref(''),
  priceVariant = ref(null)
const editor = reactive({ show: false }),
  deletion = reactive({ show: false, row: null })
const form = reactive({ spec_values: {} })
const selectedFieldIds = ref([])
const productPriceOpen = ref(false)
function closePrices() {
  priceVariant.value = null
  productPriceOpen.value = false
}
const attributeOptions = computed(() =>
  fields.value.map((field) => ({
    value: field.id,
    label: `${field.name}${field.unit ? `（${field.unit}）` : ''}${
      field.required ? ' · 必填' : ''
    }`,
    disabled: field.required,
  }))
)
const selectedFields = computed(() =>
  fields.value.filter((field) => selectedFieldIds.value.includes(field.id))
)
const legacyFields = computed(() =>
  (form.spec_snapshot || []).filter(
    (field) => !fields.value.some((current) => current.id === field.id)
  )
)
function selectFields(ids) {
  selectedFieldIds.value = [
    ...new Set([
      ...ids,
      ...fields.value.filter((field) => field.required).map((field) => field.id),
    ]),
  ]
  for (const field of fields.value) {
    if (!selectedFieldIds.value.includes(field.id)) delete form.spec_values[field.id]
    else if (field.attr_type === 'switch' && form.spec_values[field.id] === undefined)
      form.spec_values[field.id] = false
  }
}
const busy = computed(() => saving.value || fieldsLoading.value)
const blocked = computed(
  () => busy.value || editor.show || deletion.show || !!priceVariant.value || productPriceOpen.value
)
const statuses = [
  { label: '在售', value: 'active' },
  { label: '下架', value: 'offline' },
]
function close(show) {
  if (!show && !blocked.value) emit('close')
}
async function load() {
  loading.value = true
  error.value = ''
  try {
    rows.value = (await service.listVariants(props.product.id)).data || []
  } catch (e) {
    error.value = e.message || '组合加载失败'
    rows.value = []
  } finally {
    loading.value = false
  }
}
async function loadFields() {
  fieldsLoading.value = true
  fieldError.value = ''
  try {
    fields.value = props.product.category_id
      ? (await service.productSpecFields(props.product.category_id)).data || []
      : []
    selectedFieldIds.value = fields.value
      .filter((field) => field.required || Object.hasOwn(form.spec_values, field.id))
      .map((field) => field.id)
    if (!form.id) selectFields(selectedFieldIds.value)
  } catch (e) {
    fieldError.value = e.message || '参数加载失败'
  } finally {
    fieldsLoading.value = false
  }
}
async function edit(row) {
  if (blocked.value) return
  Object.assign(
    form,
    row
      ? { ...row, spec_values: { ...row.spec_values } }
      : { id: null, name: '', status: 'active', spec_values: {}, spec_snapshot: [] }
  )
  fields.value = []
  selectedFieldIds.value = []
  editor.show = true
  await loadFields()
}
async function save() {
  if (busy.value || fieldError.value) return
  if (!form.name.trim()) return window.$message?.warning('请填写组合名称')
  saving.value = true
  try {
    const data = {
      name: form.name.trim(),
      status: form.status,
      spec_values: form.spec_values,
    }
    if (form.id) await service.updateVariant(props.product.id, form.id, data)
    else await service.createVariant(props.product.id, data)
    editor.show = false
    window.$message?.success('规格组合已保存')
    await load()
  } catch {
    /* 保留表单以便重试 */
  } finally {
    saving.value = false
  }
}
async function remove() {
  if (busy.value) return
  saving.value = true
  try {
    await service.deleteVariant(props.product.id, deletion.row.id)
    deletion.show = false
    await load()
  } catch {
    /* 保留确认弹窗以便重试 */
  } finally {
    saving.value = false
  }
}
function action(label, icon, callback, type = 'default') {
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
          disabled: blocked.value || loading.value,
          onClick: (event) => {
            event.stopPropagation()
            if (!blocked.value) callback()
          },
        },
        { icon: () => h(TheIcon, { icon, size: 17 }) }
      ),
    default: () => label,
  })
}
const columns = [
  { title: '组合名称', key: 'name', width: 190, resizable: true, ellipsis: { tooltip: true } },
  {
    title: '参数',
    key: 'spec_snapshot',
    width: 330,
    resizable: true,
    ellipsis: { tooltip: true },
    render: (row) =>
      (row.spec_snapshot || [])
        .map(
          (field) =>
            `${field.name}: ${
              Array.isArray(field.value)
                ? field.value.join(' / ')
                : typeof field.value === 'boolean'
                ? field.value
                  ? '是'
                  : '否'
                : field.value
            }${field.unit || ''}`
        )
        .join('；') || '—',
  },
  {
    title: '状态',
    key: 'status',
    width: 100,
    resizable: true,
    render: (row) =>
      h(
        NTag,
        { size: 'small', type: row.status === 'active' ? 'success' : 'default' },
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
        { wrap: false, size: 4 },
        {
          default: () => [
            action('编辑', 'mdi:pencil-outline', () => edit(row)),
            action(
              '价格方案',
              'mdi:currency-usd',
              () => {
                priceVariant.value = row
              },
              'primary'
            ),
            action(
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
onMounted(load)
</script>

<style scoped>
.variant-attribute-picker {
  width: 100%;
}
.variant-category-hint {
  margin-bottom: 8px;
  font-size: 12px;
}
.variant-attribute-picker p {
  margin: 8px 0 0;
  opacity: 0.65;
  font-size: 12px;
}
.variant-heading h3 {
  margin: 0 0 8px;
  overflow-wrap: anywhere;
}
.variant-heading p {
  opacity: 0.7;
  margin-bottom: 18px;
}
.variant-gap {
  margin-top: 16px;
}
.variant-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 18px;
}
.variant-fields {
  max-height: 46vh;
  overflow-y: auto;
}
.variant-grid :deep(.n-input-number),
.variant-grid :deep(.n-date-picker) {
  width: 100%;
}
@media (max-width: 600px) {
  .variant-grid {
    grid-template-columns: 1fr;
  }
}
</style>
