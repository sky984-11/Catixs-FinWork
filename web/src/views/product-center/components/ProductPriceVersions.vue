<template>
  <n-modal
    :show="true"
    preset="card"
    title="价格方案"
    class="price-panel"
    :style="panelStyle"
    :mask-closable="!busy && !creating && !deletion.show"
    :close-on-esc="!busy && !creating && !deletion.show"
    :closable="!busy && !creating && !deletion.show"
    @update:show="close"
  >
    <section class="price-product">
      <div class="price-product-icon"><TheIcon icon="mdi:cube-outline" :size="24" /></div>
      <div class="price-product-info">
        <h3>{{ product.name }}</h3>
        <span v-if="product.code" class="price-sku">SKU · {{ product.code }}</span>
      </div>
    </section>
    <div class="price-toolbar">
      <div class="price-section-title">
        价格版本 <span>共 {{ total }} 个版本</span>
      </div>
      <CButton
        :show-save="true"
        save-text="新增价格版本"
        :disabled="busy || creating || deletion.show"
        @save="openCreate"
      />
    </div>
    <p class="price-hint">
      <TheIcon icon="mdi:information-outline" :size="16" />新增版本保留历史价格；删除后无法恢复。
    </p>
    <n-alert v-if="loadError" type="error" class="price-toolbar">
      {{ loadError }}
      <CButton :show-save="true" save-text="重试" :disabled="busy" @save="load" />
    </n-alert>
    <n-data-table
      :columns="columns"
      :data="rows"
      :loading="loading"
      :scroll-x="710"
      :max-height="400"
      :row-key="(row) => row.id"
    >
      <template #empty><n-empty description="暂无价格方案" /></template>
    </n-data-table>
    <div class="price-pagination">
      <span>金额按每计费单位展示</span>
      <n-pagination
        v-model:page="page"
        :disabled="busy || creating || deletion.show || loading"
        :page-size="20"
        :item-count="total"
        @update:page="load"
      />
    </div>
  </n-modal>
  <n-modal
    v-model:show="creating"
    preset="card"
    title="新增价格版本"
    class="price-editor"
    style="width: min(540px, calc(100vw - 32px))"
    :mask-closable="!saving"
    :close-on-esc="!saving"
    :closable="!saving"
  >
    <n-form label-placement="top" :disabled="busy">
      <n-form-item label="币种" required
        ><n-select v-model:value="form.currency" :options="currencies"
      /></n-form-item>
      <n-form-item label="月费 MRC" required
        ><n-input-number
          v-model:value="form.mrc"
          :min="0"
          :max="99999999999999.99"
          :precision="2"
          placeholder="每计费单位月费"
      /></n-form-item>
      <n-form-item label="一次性开通费 NRC"
        ><n-input-number v-model:value="form.nrc" :min="0" :max="99999999999999.99" :precision="2"
      /></n-form-item>
      <n-form-item label="计费周期" required
        ><n-select v-model:value="form.period_months" :options="periods"
      /></n-form-item>
    </n-form>
    <n-alert :show-icon="false" type="info">
      MRC 为每计费单位月费，周期不会改变 MRC 的含义。
    </n-alert>
    <template #footer
      ><CButton
        :show-cancel="true"
        :show-save="true"
        save-text="创建版本"
        :disabled="busy"
        :save-loading="saving"
        @cancel="creating = false"
        @save="save"
    /></template>
  </n-modal>
  <n-modal
    v-model:show="deletion.show"
    preset="card"
    title="删除价格方案"
    style="width: min(460px, calc(100vw - 32px))"
    :closable="!deleting"
    :mask-closable="!deleting"
    :close-on-esc="!deleting"
  >
    确认删除 V{{ deletion.row?.version }}？删除后无法恢复。
    <template #footer>
      <CButton
        show-cancel
        show-delete
        :disabled="deleting"
        :delete-loading="deleting"
        @cancel="deletion.show = false"
        @delete="deleteVersion"
      />
    </template>
  </n-modal>
</template>

<script setup>
import { computed, h, onMounted, reactive, ref } from 'vue'
import { NButton, NSpace, NTag, NTooltip, useThemeVars } from 'naive-ui'
import TheIcon from '@/components/icon/TheIcon.vue'
import api from '@/api'
import CButton from '@/components/public/CButton.vue'

const props = defineProps({
  product: { type: Object, required: true },
  units: { type: Array, default: () => [] },
})
const emit = defineEmits(['close'])
const themeVars = useThemeVars()
const panelStyle = computed(() => ({
  width: 'min(900px, calc(100vw - 32px))',
  '--price-muted': themeVars.value.textColor3,
  '--price-surface': themeVars.value.actionColor,
  '--price-accent': themeVars.value.primaryColor,
}))
const rows = ref([]),
  loading = ref(false),
  saving = ref(false),
  creating = ref(false)
const page = ref(1),
  total = ref(0),
  loadError = ref('')
const form = reactive({})
const deleting = ref(false)
const deletion = reactive({ show: false, row: null })
const busy = computed(() => saving.value || deleting.value)
const currencies = ['CNY', 'USD', 'EUR', 'JPY', 'HKD'].map((value) => ({ label: value, value }))
const periods = [1, 3, 6, 12, 24, 36].map((value) => ({ label: `${value} 个月`, value }))
function close(show) {
  if (!show && !busy.value && !creating.value && !deletion.show) emit('close')
}
let requestId = 0
async function load() {
  const current = ++requestId
  loading.value = true
  loadError.value = ''
  try {
    const result = await api.productCenterApi.listPriceVersions(props.product.id, {
      page: page.value,
      page_size: 20,
    })
    if (current === requestId) {
      rows.value = result.data
      total.value = result.total
    }
  } catch (e) {
    if (current === requestId) {
      rows.value = []
      total.value = 0
      loadError.value = e.message || '价格历史加载失败'
    }
  } finally {
    if (current === requestId) loading.value = false
  }
}
function openCreate() {
  if (busy.value || deletion.show) return
  Object.assign(form, {
    currency: 'CNY',
    mrc: null,
    nrc: 0,
    period_months: 1,
  })
  creating.value = true
}
async function save() {
  if (busy.value) return
  if (form.mrc === null || form.nrc === null) return window.$message?.warning('请填写费用')
  saving.value = true
  try {
    await api.productCenterApi.createPriceVersion(props.product.id, {
      ...form,
      mrc: String(form.mrc),
      nrc: String(form.nrc),
    })
    creating.value = false
    page.value = 1
    window.$message?.success('价格版本已创建，历史版本保留')
    await load()
  } catch {
    /* 请求封装展示错误，保留表单以便重试 */
  } finally {
    saving.value = false
  }
}
async function deleteVersion() {
  if (busy.value || !deletion.row) return
  deleting.value = true
  try {
    await api.productCenterApi.deletePriceVersion(props.product.id, deletion.row.id)
    deletion.show = false
    deletion.row = null
    if (rows.value.length === 1 && page.value > 1) page.value -= 1
    window.$message?.success('价格版本已删除')
    await load()
  } catch {
    // Keep the confirmation available for retry; the request wrapper displays the error.
  } finally {
    deleting.value = false
  }
}
function deleteAction(row) {
  return h(
    NSpace,
    { wrap: false },
    {
      default: () =>
        h(NTooltip, null, {
          trigger: () =>
            h(
              NButton,
              {
                size: 'small',
                circle: true,
                quaternary: true,
                type: 'error',
                'aria-label': '删除',
                disabled: busy.value || creating.value || deletion.show || loading.value,
                loading: deleting.value && deletion.row?.id === row.id,
                onClick: (event) => {
                  event.stopPropagation()
                  if (busy.value || creating.value || deletion.show || loading.value) return
                  deletion.row = row
                  deletion.show = true
                },
              },
              { icon: () => h(TheIcon, { icon: 'mdi:trash-can-outline', size: 17 }) }
            ),
          default: () => '删除',
        }),
    }
  )
}
const columns = computed(() =>
  [
    {
      title: '版本',
      key: 'version',
      width: 80,
      render: (row) =>
        h(
          NTag,
          { size: 'small', bordered: false, type: 'info' },
          { default: () => `V${row.version}` }
        ),
    },
    { title: '币种', key: 'currency', width: 80 },
    {
      title: '月费 MRC',
      key: 'mrc',
      width: 130,
      align: 'right',
      render: (row) => h('span', { class: 'price-amount' }, row.mrc),
    },
    {
      title: '开通费 NRC',
      key: 'nrc',
      width: 130,
      align: 'right',
      render: (row) => h('span', { class: 'price-amount' }, row.nrc),
    },
    {
      title: '计费单位',
      key: 'billing_unit',
      width: 100,
      render: (row) =>
        props.units.find((unit) => unit.value === row.billing_unit)?.label || row.billing_unit,
    },
    { title: '周期（月）', key: 'period_months', width: 110 },
    { title: '操作', key: 'actions', width: 80, fixed: 'right', render: deleteAction },
  ].map((column) => ({ ...column, resizable: column.key !== 'actions' }))
)
onMounted(load)
</script>

<style scoped>
.price-product {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 18px;
  border-radius: 10px;
  background: var(--price-surface);
  margin-bottom: 22px;
}
.price-product-icon {
  display: flex;
  color: var(--price-accent);
  padding-top: 3px;
}
.price-product-info {
  min-width: 0;
}
.price-product-info h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  line-height: 1.65;
  overflow-wrap: anywhere;
}
.price-sku {
  display: block;
  margin-top: 6px;
  color: var(--price-muted);
  font-size: 12px;
  overflow-wrap: anywhere;
}
.price-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 12px;
}
.price-section-title {
  font-size: 15px;
  font-weight: 600;
}
.price-section-title span {
  margin-left: 8px;
  font-size: 12px;
  font-weight: 400;
  color: var(--price-muted);
}
.price-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0 0 14px;
  color: var(--price-muted);
  font-size: 12px;
}
.price-hint :deep(svg) {
  flex-shrink: 0;
}
:deep(.price-amount) {
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.price-pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 16px;
}
.price-pagination > span {
  color: var(--price-muted);
  font-size: 12px;
}
@media (max-width: 600px) {
  .price-product {
    padding: 14px;
    gap: 10px;
  }
  .price-product-info h3 {
    font-size: 14px;
  }
}
.price-editor :deep(.n-input-number),
.price-editor :deep(.n-date-picker) {
  width: 100%;
}
</style>
