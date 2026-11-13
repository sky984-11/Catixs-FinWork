<template>
  <div class="cost-library" :class="{ 'cost-library--page': !product }">
    <template v-if="product">
      <n-alert type="info" class="gap"
        >选择成本资源后关联当前版本。成本更新不会自动覆盖已关联版本，也不会修改销售价格、规格或订单。</n-alert
      >
      <h3>{{ product.name }} · 已关联成本</h3>
      <n-data-table :columns="linkColumns" :data="links" :loading="linksLoading" :scroll-x="940" />
      <h3>选择成本资源</h3>
    </template>
    <div v-else class="toolbar">
      <div>
        <h2>资源成本库</h2>
        <p>维护采购成本与历史版本，供产品关联使用。空白表示未报价，0 表示免费。</p>
      </div>
      <n-space>
        <CButton
          v-if="can('post', '')"
          show-save
          save-text="新增成本"
          :disabled="busy || !ready"
          @save="edit()"
        />
        <CButton
          v-if="can('post', '/import/commit') && can('post', '/import/preview')"
          show-save
          save-text="导入 CSV"
          :disabled="busy || !ready"
          @save="openImport"
        />
      </n-space>
    </div>
    <n-alert v-if="optionError" type="error" class="gap"
      >{{ optionError }}<CButton show-save save-text="重新加载选项" :disabled="busy" @save="init"
    /></n-alert>
    <n-tabs v-model:value="category" type="line" @update:value="search">
      <n-tab v-for="(item, key) in meta.categories" :key="key" :name="key" :disabled="busy">{{
        categoryLabels[key] || item.label
      }}</n-tab>
    </n-tabs>
    <div class="filters">
      <n-input
        v-model:value="keyword"
        clearable
        placeholder="搜索站点、服务、供应商"
        :disabled="busy"
        @keyup.enter="search"
      />
      <n-select
        v-model:value="vendorId"
        :options="vendorOptions"
        clearable
        filterable
        placeholder="供应商"
        :disabled="busy"
        @update:value="search"
      />
      <n-select
        v-if="!product"
        v-model:value="enabled"
        :options="[
          { label: '启用', value: 'enabled' },
          { label: '停用', value: 'disabled' },
        ]"
        clearable
        placeholder="全部状态"
        :disabled="busy"
        @update:value="search"
      />
      <CButton show-save save-text="查询 / 刷新" :disabled="busy || !ready" @save="search" />
    </div>
    <n-alert v-if="error" type="error" class="gap">{{ error }}</n-alert>
    <n-data-table
      class="cost-table"
      :flex-height="!product"
      size="small"
      :bordered="false"
      :columns="columns"
      :data="rows"
      :loading="loading"
      :scroll-x="scrollWidth"
      :row-key="(row) => row.id"
    />
    <div class="list-footer">
      <span class="result-count"
        >共 {{ total }} 条资源<span class="quote-hint"> · 空白为未报价，0 为免费</span></span
      >
      <n-pagination
        v-model:page="page"
        :page-size="20"
        :item-count="total"
        class="pagination"
        :disabled="busy"
        :page-slot="5"
        @update:page="load"
      />
    </div>

    <n-modal
      v-model:show="editor.show"
      preset="card"
      :title="editor.id ? '编辑成本（保存新版本）' : '新增成本'"
      style="width: min(920px, calc(100vw - 24px))"
      :closable="!busy"
      :mask-closable="!busy"
      :close-on-esc="!busy"
    >
      <n-form label-placement="top" :disabled="busy">
        <div class="form-grid">
          <n-form-item label="启用"><n-switch v-model:value="editor.form.enabled" /></n-form-item>
          <n-form-item
            v-for="key in editFields"
            :key="key"
            :label="fieldLabel(key)"
            :class="{ wide: ['note', 'site_address'].includes(key) }"
            :required="
              (key === 'currency' &&
                ['nrc', 'mrc', 'price_per_mbps', 'burst_price'].some(
                  (field) => editor.form[field] != null && editor.form[field] !== ''
                )) ||
              (category === 'xc' ? key === 'dc_name' : ['service', 'site_a'].includes(key)) ||
              (category === 'ptp' && key === 'site_b')
            "
          >
            <n-select
              v-if="meta.fields[key].type === 'vendor'"
              v-model:value="editor.form[key]"
              :options="editVendorOptions"
              filterable
              clearable
              placeholder="可选；无来源时留空"
            />
            <n-select
              v-else-if="meta.fields[key].type === 'select'"
              v-model:value="editor.form[key]"
              :options="
                meta.fields[key].options.map((value) => ({ label: valueLabel(key, value), value }))
              "
              clearable
            />
            <n-date-picker
              v-else-if="meta.fields[key].type === 'date'"
              v-model:formatted-value="editor.form[key]"
              value-format="yyyy-MM-dd"
              type="date"
              clearable
            />
            <n-input-number
              v-else-if="meta.fields[key].type === 'integer'"
              v-model:value="editor.form[key]"
              :min="1"
              :max="1200"
              :precision="0"
              clearable
            />
            <n-input
              v-else
              v-model:value="editor.form[key]"
              :type="key === 'note' ? 'textarea' : 'text'"
              :maxlength="key === 'note' ? 4000 : 500"
              :placeholder="
                meta.fields[key].type === 'money'
                  ? '未报价留空；免费填 0'
                  : key === 'mrc_unit'
                  ? '例如：月、kVA、机柜、U'
                  : '请输入'
              "
            />
          </n-form-item>
        </div>
      </n-form>
      <n-alert v-if="saveError" type="error">{{ saveError }}</n-alert>
      <template #footer
        ><CButton
          show-save
          show-cancel
          :disabled="busy"
          :save-loading="busy"
          @cancel="editor.show = false"
          @save="save"
      /></template>
    </n-modal>

    <n-modal
      v-model:show="history.show"
      preset="card"
      title="成本版本历史"
      style="width: min(1200px, calc(100vw - 24px))"
    >
      <n-data-table :columns="historyColumns" :data="history.rows" :scroll-x="scrollWidth" />
      <template #footer
        ><CButton show-cancel cancel-text="关闭" @cancel="history.show = false"
      /></template>
    </n-modal>

    <n-modal
      v-model:show="importer.show"
      preset="card"
      :title="`导入 ${meta.categories[category]?.label || ''}`"
      style="width: min(1100px, calc(100vw - 24px))"
      :closable="!busy"
      :mask-closable="!busy"
      :close-on-esc="!busy"
    >
      <p>
        使用当前分类模板，移除原表顶部说明行。UTF-8 CSV，每次最多 500 行、2
        MiB；供应商填写已有名称或 ID。币种与税率保持原值，不换汇、不自动加价。
      </p>
      <n-space class="gap">
        <CButton show-save save-text="下载模板" :disabled="busy" @save="downloadTemplate" />
        <CButton show-save save-text="选择 CSV" :disabled="busy" @save="fileInput.click()" />
        <input ref="fileInput" type="file" accept=".csv,text/csv" hidden @change="readCsv" />
      </n-space>
      <n-input
        v-model:value="importer.text"
        type="textarea"
        placeholder="也可直接粘贴 CSV 内容"
        :rows="6"
        :maxlength="2097152"
        :disabled="busy"
        @update:value="clearImportPreview"
      />
      <n-alert v-if="importer.error" type="error" class="gap">{{ importer.error }}</n-alert>
      <n-alert v-for="(item, index) in importer.errors" :key="index" type="error" class="gap"
        >{{ item.row ? `第 ${item.row} 行：` : '' }}{{ item.message }}</n-alert
      >
      <template v-if="importer.rows.length">
        <p>预检 {{ importer.rows.length }} 条；所有校验通过后才能确认导入。重复导入会拒绝。</p>
        <n-data-table
          :columns="businessColumns"
          :data="importer.rows"
          :scroll-x="scrollWidth"
          :max-height="300"
        />
      </template>
      <template #footer
        ><n-space justify="end">
          <CButton show-cancel :disabled="busy" @cancel="importer.show = false" />
          <CButton
            show-save
            save-text="校验并预览"
            :disabled="busy || !importer.text.trim()"
            :save-loading="busy"
            @save="previewImport"
          />
          <CButton
            show-save
            save-text="确认导入"
            :disabled="busy || !importer.rows.length || !!importer.errors.length"
            @save="commitImport"
          /> </n-space
      ></template>
    </n-modal>

    <n-modal
      v-model:show="confirmation.show"
      preset="card"
      title="确认操作"
      style="width: min(460px, calc(100vw - 24px))"
      :closable="!busy"
      :mask-closable="!busy"
      :close-on-esc="!busy"
    >
      <p>{{ confirmation.message }}</p>
      <template #footer
        ><CButton
          show-save
          show-cancel
          :disabled="busy"
          :save-loading="busy"
          @cancel="confirmation.show = false"
          @save="confirm"
      /></template>
    </n-modal>
  </div>
</template>

<script setup>
import { computed, h, onMounted, reactive, ref, watch } from 'vue'
import { NButton, NSpace, NTooltip } from 'naive-ui'
import CButton from '@/components/public/CButton.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import service from '@/api/resource-costs'
import { usePermissionStore, useUserStore } from '@/store'

const props = defineProps({ product: { type: Object, default: null } })
const categoryLabels = {
  ipt_dia: 'IPT / DIA（数据中心）',
  ptp: '点对点（PtP）',
  retail: '商业楼宇',
  xc: '交叉连接（XC）',
  colo: '机柜托管（Colo）',
}
const fieldLabels = {
  service_resource: '资源类型',
  service: '服务类型',
  vendor_id: '供应商',
  bandwidth: '带宽',
  burst: '突发带宽',
  site_a: 'A 端站点',
  site_b: 'B 端站点',
  protection: '线路保护',
  xc_cabling: '交叉连接 / 布线',
  contract_months: '合同期限（月）',
  currency: '币种',
  nrc: '一次性成本（NRC）',
  mrc: '月度成本（MRC）',
  mrc_unit: '月费计价单位',
  price_per_mbps: '每 Mbps 月费',
  burst_price: '每 Mbps 突发单价',
  dc_name: '数据中心名称',
  site_address: '站点地址',
  tax_rate: '税率（%）',
  note: '备注',
}
const valueLabels = {
  service_resource: { Onnet: '本网', Offnet: '外网', NA: '不适用' },
  protection: {
    Protected: '有保护',
    Unprotected: '无保护',
    Diverse: '多路由',
    NA: '不适用',
    No: '无保护',
  },
  xc_cabling: { Yes: '是', No: '否', NA: '不适用' },
}
function fieldLabel(key) {
  return fieldLabels[key] || meta.fields[key]?.label || key
}
function valueLabel(key, value) {
  return valueLabels[key]?.[value] || value
}
const emit = defineEmits(['busy'])
const user = useUserStore(),
  permissions = usePermissionStore()
function can(method, path) {
  return user.isSuperUser || permissions.apis.includes(`${method}/api/v1/resource-costs${path}`)
}
const meta = reactive({ categories: {}, fields: {}, vendors: [] })
const ready = ref(false),
  optionError = ref(''),
  error = ref(''),
  saveError = ref('')
const busy = ref(false),
  loading = ref(false),
  linksLoading = ref(false)
watch(busy, (value) => emit('busy', value))
const category = ref('ipt_dia'),
  keyword = ref(''),
  vendorId = ref(null),
  enabled = ref('enabled')
const page = ref(1),
  total = ref(0),
  rows = ref([]),
  links = ref([])
const editor = reactive({ show: false, id: null, form: {} })
const history = reactive({ show: false, rows: [] })
const importer = reactive({ show: false, text: '', rows: [], errors: [], error: '' })
const fileInput = ref(null)
const confirmation = reactive({ show: false, message: '', callback: null })
const vendorOptions = computed(() =>
  meta.vendors.map((row) => ({ label: row.name || row.legal_name, value: row.id }))
)
const editVendorOptions = computed(() =>
  meta.vendors
    .filter((row) => row.status || row.id === editor.form.vendor_id)
    .map((row) => ({
      label: `${row.name || row.legal_name}${row.status ? '' : '（已停用）'}`,
      value: row.id,
      disabled: !row.status,
    }))
)
const editFields = computed(() => meta.categories[category.value]?.fields || [])
function display(row, key) {
  if (key === 'vendor_id')
    return row.vendor_name || meta.vendors.find((v) => v.id === row.vendor_id)?.name || '—'
  return row[key] == null || row[key] === '' ? '—' : String(valueLabel(key, row[key]))
}
const businessColumns = computed(() =>
  [
    ...editFields.value.map((key) => ({
      title: fieldLabel(key),
      key,
      width: ['site_a', 'site_b', 'site_address', 'note'].includes(key) ? 260 : 140,
      render: (row) => display(row, key),
    })),
    { title: '版本', key: 'revision', width: 80 },
    { title: '状态', key: 'enabled', width: 80, render: (row) => (row.enabled ? '启用' : '停用') },
  ].map((col) => ({ ...col, resizable: true, ellipsis: { tooltip: true } }))
)
function action(label, icon, callback, type = 'default', disabled = false) {
  return h(NTooltip, null, {
    trigger: () =>
      h(
        NButton,
        {
          size: 'small',
          circle: true,
          quaternary: true,
          type,
          disabled: busy.value || disabled,
          loading: busy.value,
          'aria-label': label,
          onClick: (event) => {
            event.stopPropagation()
            if (!busy.value && !disabled) callback()
          },
        },
        { icon: () => h(TheIcon, { icon, size: 17 }) }
      ),
    default: () => label,
  })
}
const columns = computed(() => [
  ...businessColumns.value,
  {
    title: '操作',
    key: 'actions',
    width: productMode.value ? 80 : 100,
    fixed: 'right',
    render: (row) =>
      h(
        NSpace,
        { wrap: false, size: 4 },
        {
          default: () =>
            props.product
              ? [
                  can('post', '/products/{product_id}/links')
                    ? action(
                        '关联此版本',
                        'mdi:link-plus',
                        () => askLink(row),
                        'primary',
                        links.value.some((l) => l.version_id === row.version_id)
                      )
                    : null,
                ]
              : [
                  can('put', '/{resource_id}')
                    ? action('编辑', 'mdi:pencil-outline', () => edit(row))
                    : null,
                  can('get', '/{resource_id}/versions')
                    ? action('历史版本', 'mdi:history', () => openHistory(row))
                    : null,
                ],
        }
      ),
  },
])
const productMode = computed(() => !!props.product)
const scrollWidth = computed(
  () => businessColumns.value.reduce((sum, col) => sum + col.width, 0) + 100
)
const historyColumns = computed(() => businessColumns.value)
const linkColumns = [
  { title: '资源', key: 'title', width: 280 },
  { title: '币种', key: 'currency', width: 80 },
  { title: '一次性成本', key: 'nrc', width: 120, render: (row) => display(row, 'nrc') },
  { title: '月度成本', key: 'mrc', width: 120, render: (row) => display(row, 'mrc') },
  { title: '计价单位', key: 'mrc_unit', width: 100 },
  {
    title: '关联 / 最新版本',
    key: 'revision',
    width: 160,
    render: (row) => `V${row.revision} / V${row.latest_revision}`,
  },
].map((col) => ({ ...col, resizable: true, ellipsis: { tooltip: true } }))
linkColumns.push({
  title: '操作',
  key: 'actions',
  width: 80,
  fixed: 'right',
  render: (row) =>
    h(
      NSpace,
      { wrap: false },
      {
        default: () =>
          can('delete', '/products/{product_id}/links/{link_id}')
            ? action(
                '解除关联',
                'mdi:link-off',
                () =>
                  ask('解除关联后保留成本历史，销售价格和订单不受影响。', async () => {
                    await service.unlink(props.product.id, row.link_id)
                    await loadLinks()
                  }),
                'error'
              )
            : null,
      }
    ),
})
let requestId = 0
async function load() {
  const id = ++requestId
  loading.value = true
  error.value = ''
  try {
    const result = await service.list({
      category: category.value,
      keyword: keyword.value,
      vendor_id: vendorId.value || undefined,
      enabled: props.product
        ? true
        : enabled.value === 'enabled'
        ? true
        : enabled.value === 'disabled'
        ? false
        : undefined,
      page: page.value,
      page_size: 20,
    })
    if (id === requestId) {
      rows.value = result.data || []
      total.value = result.total
    }
  } catch (e) {
    if (id === requestId) {
      rows.value = []
      error.value = e.message || '成本加载失败，请重试'
    }
  } finally {
    if (id === requestId) loading.value = false
  }
}
function search() {
  page.value = 1
  load()
}
async function loadLinks() {
  if (!props.product) return
  linksLoading.value = true
  try {
    links.value = (await service.links(props.product.id)).data || []
  } finally {
    linksLoading.value = false
  }
}
async function init() {
  optionError.value = ''
  ready.value = false
  try {
    Object.assign(meta, (await service.options()).data)
    ready.value = true
    if (props.product) {
      const name = `${props.product.name} ${props.product.category_name || ''}`.toLowerCase()
      category.value = /\bxc\b/.test(name)
        ? 'xc'
        : /colo/.test(name)
        ? 'colo'
        : /ptp/.test(name)
        ? 'ptp'
        : /retail/.test(name)
        ? 'retail'
        : 'ipt_dia'
    }
    await Promise.all([load(), loadLinks()])
  } catch (e) {
    optionError.value = e.message || '选项加载失败'
  }
}
function edit(row) {
  editor.id = row?.id || null
  saveError.value = ''
  editor.form = {
    category: category.value,
    code: row?.code || '',
    enabled: row?.enabled ?? true,
    expected_revision: row?.revision || null,
    effective_date: row?.effective_date ?? null,
    expiry_date: row?.expiry_date ?? null,
  }
  for (const key of editFields.value) editor.form[key] = row?.[key] ?? null
  editor.show = true
}
async function save() {
  if (busy.value) return
  busy.value = true
  saveError.value = ''
  try {
    const data = { ...editor.form }
    for (const key of Object.keys(data)) if (data[key] === '') data[key] = null
    if (editor.id) await service.update(editor.id, data)
    else await service.create(data)
    editor.show = false
    await load()
    window.$message?.success('成本已保存')
  } catch (e) {
    saveError.value = e.message || '保存失败，请检查字段'
  } finally {
    busy.value = false
  }
}
async function openHistory(row) {
  busy.value = true
  try {
    history.rows = (await service.versions(row.id)).data || []
    history.show = true
  } catch (e) {
    error.value = e.message || '历史版本加载失败'
  } finally {
    busy.value = false
  }
}
function ask(message, callback) {
  Object.assign(confirmation, { show: true, message, callback })
}
function askLink(row) {
  ask(
    `将 ${row.title || row.dc_name || row.service || '此资源'} 的 V${
      row.revision
    } 版本关联到产品？已有同资源关联将更新为此版本。`,
    async () => {
      await service.link(props.product.id, row.version_id)
      await loadLinks()
    }
  )
}
async function confirm() {
  if (busy.value) return
  busy.value = true
  try {
    await confirmation.callback()
    confirmation.show = false
    window.$message?.success('操作成功')
  } catch (e) {
    error.value = e.message || '操作失败，请重试'
  } finally {
    busy.value = false
  }
}
function openImport() {
  Object.assign(importer, { show: true, text: '', rows: [], errors: [], error: '' })
}
function clearImportPreview() {
  importer.rows = []
  importer.errors = []
  importer.error = ''
}
function downloadTemplate() {
  const text =
    editFields.value
      .map((key) => meta.fields[key].label)
      .map((label) => `"${label.replaceAll('"', '""')}"`)
      .join(',') + '\r\n'
  const url = URL.createObjectURL(new Blob(['\ufeff', text], { type: 'text/csv;charset=utf-8' }))
  const link = document.createElement('a')
  link.href = url
  link.download = `resource-cost-${category.value}.csv`
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
async function readCsv(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  clearImportPreview()
  if (!file.size || file.size > 2 * 1024 * 1024) {
    importer.error = '请选择非空且不超过 2 MiB 的 CSV'
    return
  }
  busy.value = true
  try {
    importer.text = await file.text()
    if (importer.text.includes('\ufffd')) throw new Error('编码无法识别，请将文件另存为 UTF-8 CSV')
  } catch (e) {
    importer.error = e.message || '文件读取失败'
    importer.text = ''
  } finally {
    busy.value = false
  }
}
async function previewImport() {
  if (busy.value) return
  busy.value = true
  clearImportPreview()
  try {
    const result = (
      await service.previewImport({ category: category.value, csv_text: importer.text })
    ).data
    importer.rows = result.rows
    importer.errors = result.errors
  } catch (e) {
    importer.error = e.message || '校验失败'
  } finally {
    busy.value = false
  }
}
async function commitImport() {
  if (busy.value || !importer.rows.length || importer.errors.length) return
  busy.value = true
  try {
    await service.import({ rows: importer.rows })
    importer.show = false
    await load()
    window.$message?.success('导入成功')
  } catch (e) {
    importer.error = e.message || '导入失败，本次未写入数据'
  } finally {
    busy.value = false
  }
}
onMounted(init)
</script>

<style scoped>
.cost-library {
  min-width: 0;
}
.cost-library--page {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
  padding: 20px;
  border: 1px solid #e7edf4;
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 2px 8px rgb(24 40 64 / 3%);
}
.cost-library--page > :not(.cost-table) {
  flex-shrink: 0;
}
.cost-library--page .cost-table {
  flex: 1;
  min-height: 0;
}
.cost-table {
  border: 1px solid #e7edf4;
  border-radius: 8px;
  overflow: hidden;
}
.toolbar h2 {
  margin: 0;
  font-size: 22px;
  font-weight: 650;
  letter-spacing: 0.3px;
}
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}
.toolbar p {
  margin: 6px 0 16px;
  color: #7b8798;
  font-size: 13px;
}
.gap {
  margin: 12px 0;
}
.filters {
  display: flex;
  gap: 12px;
  margin: 14px 0;
  padding: 12px;
  border-radius: 8px;
  background: #f7f9fc;
  flex-wrap: wrap;
}
.filters > .n-input,
.filters > .n-select {
  width: 220px;
  max-width: 100%;
}
.list-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding-top: 14px;
}
.result-count {
  color: #66758a;
  font-size: 13px;
}
.pagination {
  margin-left: auto;
}
:global(html.dark) .cost-library--page {
  background: #181c24;
  border-color: #303744;
}
:global(html.dark) .filters {
  background: #202631;
}
:global(html.dark) .cost-table {
  border-color: #303744;
}
.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 20px;
}
.wide {
  grid-column: 1/-1;
}
@media (max-width: 600px) {
  .cost-library--page {
    padding: 12px;
  }
  .toolbar {
    gap: 8px;
  }
  .toolbar p,
  .quote-hint {
    display: none;
  }
  .filters {
    gap: 8px;
    padding: 8px;
  }
  .form-grid {
    grid-template-columns: 1fr;
  }
  .filters > .n-input,
  .filters > .n-select {
    width: calc(50% - 4px);
  }
}
</style>
