<template>
  <n-modal
    :show="true"
    preset="card"
    :title="`${product.name} · 价格方案`"
    class="price-panel"
    :mask-closable="!busy && !creating && !deletion.show"
    :close-on-esc="!busy && !creating && !deletion.show"
    :closable="!busy && !creating && !deletion.show"
    @update:show="close"
  >
    <n-space align="center" class="price-toolbar">
      <CButton :show-save="true" save-text="新增价格版本" :disabled="busy" @save="openCreate" />
      <span>新增版本不覆盖原价，删除版本后无法恢复</span>
    </n-space>
    <n-select
      v-model:value="customerFilter"
      :disabled="busy || deletion.show"
      clearable
      filterable
      :show-checkmark="false"
      :options="filterOptions"
      :render-label="renderCustomerOption"
      :to="false"
      placeholder="全部客户及通用价格"
      class="customer-filter"
      @update:value="search"
    />
    <n-alert v-if="loadError" type="error" class="price-toolbar">
      {{ loadError }}
      <CButton :show-save="true" save-text="重试" :disabled="busy" @save="load" />
    </n-alert>
    <n-data-table
      :columns="columns"
      :data="rows"
      :loading="loading"
      :scroll-x="1370"
      :row-key="(row) => row.id"
    >
      <template #empty><n-empty description="暂无价格方案" /></template>
    </n-data-table>
    <n-pagination
      v-model:page="page"
      :disabled="busy || deletion.show"
      :page-size="20"
      :item-count="total"
      class="pagination"
      @update:page="load"
    />
    <template #footer
      ><CButton
        :show-cancel="true"
        cancel-text="关闭"
        :disabled="busy || creating || deletion.show"
        @cancel="close(false)"
    /></template>
  </n-modal>
  <n-modal
    v-model:show="creating"
    preset="card"
    title="新增价格版本"
    class="price-editor"
    :mask-closable="!saving"
    :close-on-esc="!saving"
    :closable="!saving"
  >
    <n-form label-placement="top" :disabled="busy">
      <n-form-item label="关联客户">
        <n-select
          v-model:value="form.customer_id"
          clearable
          filterable
          :show-checkmark="false"
          :options="customers"
          :render-label="renderCustomerOption"
          :to="false"
          placeholder="通用价格（未指定客户）"
        />
      </n-form-item>
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
      <n-form-item label="生效日（含）" required
        ><n-date-picker
          v-model:formatted-value="form.effective_date"
          value-format="yyyy-MM-dd"
          type="date"
          clearable
      /></n-form-item>
      <n-form-item label="失效日（不含）" required
        ><n-date-picker
          v-model:formatted-value="form.expiry_date"
          value-format="yyyy-MM-dd"
          type="date"
          clearable
      /></n-form-item>
    </n-form>
    <n-alert :show-icon="false" type="info">
      同一客户、币种和计费周期的有效期不能重叠。MRC 为每计费单位月费，周期不会改变 MRC
      的含义。客户留空表示通用价格。
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
    确认删除 V{{ deletion.row?.version }}（{{
      deletion.row?.customer_name || '通用价格'
    }}）？删除后无法恢复。
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
import { NButton, NSpace, NTag, NTooltip } from 'naive-ui'
import TheIcon from '@/components/icon/TheIcon.vue'
import api from '@/api'
import CButton from '@/components/public/CButton.vue'

const props = defineProps({
  product: { type: Object, required: true },
  customers: { type: Array, default: () => [] },
  units: { type: Array, default: () => [] },
})
const emit = defineEmits(['close'])
const rows = ref([]),
  loading = ref(false),
  saving = ref(false),
  creating = ref(false)
const customerFilter = ref(null),
  page = ref(1),
  total = ref(0),
  loadError = ref('')
const form = reactive({})
const deleting = ref(false)
const deletion = reactive({ show: false, row: null })
const busy = computed(() => saving.value || deleting.value)
const currencies = ['CNY', 'USD', 'EUR', 'JPY', 'HKD'].map((value) => ({ label: value, value }))
const periods = [1, 3, 6, 12, 24, 36].map((value) => ({ label: `${value} 个月`, value }))
const filterOptions = computed(() => [{ label: '通用价格', value: 0 }, ...props.customers])
function renderCustomerOption(option) {
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
        'display:flex;align-items:center;justify-content:space-between;width:100%;flex:1;gap:12px;min-width:0',
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
            { size: 'small', type: tag[1], style: 'flex-shrink:0' },
            { default: () => tag[0] }
          )
        : null,
    ]
  )
}
function close(show) {
  if (!show && !busy.value && !creating.value && !deletion.show) emit('close')
}
function search() {
  page.value = 1
  load()
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
      customer_id: customerFilter.value,
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
    customer_id: customerFilter.value || null,
    currency: 'CNY',
    mrc: null,
    nrc: 0,
    period_months: 1,
    effective_date: null,
    expiry_date: null,
  })
  creating.value = true
}
async function save() {
  if (busy.value) return
  if (form.mrc === null || form.nrc === null || !form.effective_date || !form.expiry_date)
    return window.$message?.warning('请填写费用和有效期')
  if (form.expiry_date <= form.effective_date)
    return window.$message?.warning('失效日必须晚于生效日')
  saving.value = true
  try {
    await api.productCenterApi.createPriceVersion(props.product.id, {
      ...form,
      mrc: String(form.mrc),
      nrc: String(form.nrc),
    })
    customerFilter.value = form.customer_id || 0
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
    { title: '版本', key: 'version', width: 80, render: (row) => `V${row.version}` },
    {
      title: '客户',
      key: 'customer_name',
      width: 200,
      render: (row) => row.customer_name || '通用价格',
      ellipsis: { tooltip: true },
    },
    { title: '币种', key: 'currency', width: 80 },
    { title: '月费 MRC', key: 'mrc', width: 130 },
    { title: '开通费 NRC', key: 'nrc', width: 130 },
    {
      title: '计费单位',
      key: 'billing_unit',
      width: 100,
      render: (row) =>
        props.units.find((unit) => unit.value === row.billing_unit)?.label || row.billing_unit,
    },
    { title: '周期（月）', key: 'period_months', width: 110 },
    { title: '生效日（含）', key: 'effective_date', width: 140 },
    { title: '失效日（不含）', key: 'expiry_date', width: 140 },
    {
      title: '状态',
      key: 'status',
      width: 100,
      render: (row) =>
        h(
          NTag,
          { size: 'small', type: row.status === 'active' ? 'success' : 'default' },
          {
            default: () =>
              ({ active: '生效中', scheduled: '未生效', expired: '已失效' }[row.status]),
          }
        ),
    },
    { title: '操作', key: 'actions', width: 80, fixed: 'right', render: deleteAction },
  ].map((column) => ({ ...column, resizable: column.key !== 'actions' }))
)
onMounted(load)
</script>

<style scoped>
.price-panel {
  width: min(1300px, calc(100vw - 32px));
}
.price-editor {
  width: min(540px, calc(100vw - 32px));
}
.price-toolbar {
  margin-bottom: 16px;
}
.customer-filter {
  max-width: 360px;
  margin-bottom: 16px;
}
.pagination {
  margin-top: 16px;
  justify-content: flex-end;
}
.price-editor :deep(.n-input-number),
.price-editor :deep(.n-date-picker) {
  width: 100%;
}
.price-panel :deep(.n-base-select-option__content),
.price-editor :deep(.n-base-select-option__content) {
  display: flex;
  width: 100%;
}
</style>
