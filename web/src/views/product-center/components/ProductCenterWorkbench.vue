<template>
  <AppPage :show-footer="false">
    <section class="product-panel">
      <div class="panel-head">
        <h2>{{ isSpecs ? '规格属性' : '产品模板' }}</h2>
        <n-button type="primary" :disabled="busy" @click="openEditor()">{{
          isSpecs ? '新增属性' : '新增模板'
        }}</n-button>
      </div>
      <div class="filter-row">
        <n-input
          v-model:value="query.keyword"
          clearable
          placeholder="搜索名称 / 编码"
          @keyup.enter="search"
        />
        <n-select
          v-if="isSpecs"
          v-model:value="query.attr_type"
          clearable
          :options="options.attributeTypes"
          placeholder="属性类型"
        />
        <n-cascader
          v-model:value="query.category_id"
          clearable
          filterable
          :show-path="false"
          check-strategy="child"
          :options="options.categoryTree"
          placeholder="适用分类"
        />
        <n-button secondary @click="resetQuery">重置</n-button
        ><n-button type="primary" @click="search">搜索</n-button>
      </div>
      <n-data-table
        :loading="loading"
        :columns="columns"
        :data="rows"
        :row-key="(row) => row.id"
        :scroll-x="scrollX"
        :pagination="false"
        ><template #empty><n-empty description="暂无数据" /></template
      ></n-data-table>
      <div class="list-footer">
        <span>共 {{ pagination.itemCount }} 条</span
        ><n-pagination
          v-model:page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :item-count="pagination.itemCount"
          :page-sizes="[10, 20, 50, 100]"
          show-size-picker
          @update:page="loadPage"
          @update:page-size="search"
        />
      </div>
      <n-modal
        v-model:show="editor.show"
        preset="card"
        :title="editor.form.id ? '编辑' : '新增'"
        :closable="!busy"
        :mask-closable="!busy"
        :close-on-esc="!busy"
        style="width: min(760px, calc(100vw - 32px))"
      >
        <n-form :model="editor.form" label-placement="top" :disabled="busy"
          ><n-grid responsive="screen" cols="1 m:2" :x-gap="16" :y-gap="2">
            <template v-if="mode === 'specs'">
              <n-form-item-gi label="属性名称" required
                ><n-input v-model:value="editor.form.name"
              /></n-form-item-gi>
              <n-form-item-gi label="属性编码" required
                ><n-input v-model:value="editor.form.code"
              /></n-form-item-gi>
              <n-form-item-gi label="适用分类" required>
                <n-cascader
                  v-model:value="editor.form.category_ids"
                  filterable
                  multiple
                  :show-path="false"
                  check-strategy="child"
                  :options="options.categoryTree"
                  placeholder="请选择适用分类"
                />
              </n-form-item-gi>
              <n-form-item-gi label="属性类型"
                ><n-select v-model:value="editor.form.attr_type" :options="options.attributeTypes"
              /></n-form-item-gi>
              <n-form-item-gi label="单位"
                ><n-input v-model:value="editor.form.unit"
              /></n-form-item-gi>
              <n-form-item-gi label="必填"
                ><n-switch v-model:value="editor.form.required"
              /></n-form-item-gi>
              <n-form-item-gi label="启用"
                ><n-switch v-model:value="editor.form.status"
              /></n-form-item-gi>
              <n-form-item-gi label="可选值" :span="2"
                ><n-input
                  v-model:value="editor.form.options"
                  type="textarea"
                  placeholder="一行一个值，或填写 JSON"
              /></n-form-item-gi>
              <n-form-item-gi label="说明" :span="2"
                ><n-input v-model:value="editor.form.description" type="textarea"
              /></n-form-item-gi>
            </template>

            <template v-else>
              <n-form-item-gi label="模板名称" required
                ><n-input v-model:value="editor.form.name"
              /></n-form-item-gi>
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
              <n-form-item-gi label="模板类型"
                ><n-input v-model:value="editor.form.template_type"
              /></n-form-item-gi>
              <n-form-item-gi label="启用"
                ><n-switch v-model:value="editor.form.status"
              /></n-form-item-gi>
              <n-form-item-gi label="模板说明" :span="2"
                ><n-input v-model:value="editor.form.description" type="textarea"
              /></n-form-item-gi>
              <n-form-item-gi label="模板配置" :span="2"
                ><n-input
                  v-model:value="editor.form.config"
                  type="textarea"
                  placeholder="可填写标准规格、默认价格或创建说明"
              /></n-form-item-gi>
            </template> </n-grid
        ></n-form>
        <template #footer
          ><CButton
            show-cancel
            show-save
            :disabled="busy"
            :save-loading="editor.loading"
            @cancel="editor.show = false"
            @save="saveEditor"
        /></template>
      </n-modal>
    </section>
  </AppPage>
</template>
<script setup>
import { computed, h, onMounted, reactive, ref } from 'vue'
import { NButton, NPopconfirm, NSpace, NTag, NTooltip } from 'naive-ui'
import api from '@/api'
import TheIcon from '@/components/icon/TheIcon.vue'
import CButton from '@/components/public/CButton.vue'
const props = defineProps({ mode: { type: String, default: 'specs' } })
const isSpecs = computed(() => props.mode === 'specs')
const options = reactive({ categoryTree: [], attributeTypes: [] })
const query = reactive({ keyword: '', attr_type: null, category_id: null })
const pagination = reactive({ page: 1, pageSize: 20, itemCount: 0 })
const rows = ref([])
const loading = ref(false)
const deletingId = ref(null)
const editor = reactive({ show: false, loading: false, form: {} })
const busy = computed(() => editor.loading || deletingId.value !== null)
function actionButton(label, icon, row, remove = false) {
  const button = () =>
    h(NTooltip, null, {
      trigger: () =>
        h(
          NButton,
          {
            size: 'small',
            circle: true,
            quaternary: true,
            'aria-label': label,
            type: remove ? 'error' : 'default',
            disabled: busy.value,
            loading: remove && deletingId.value === row.id,
            onClick: (event) => {
              event.stopPropagation()
              if (!remove) openEditor(row)
            },
          },
          { icon: () => h(TheIcon, { icon, size: 17 }) }
        ),
      default: () => label,
    })
  return remove
    ? h(
        NPopconfirm,
        { disabled: busy.value, onPositiveClick: () => deleteRow(row) },
        {
          trigger: button,
          default: () => '确认删除？',
        }
      )
    : button()
}
const columns = computed(() => {
  const business = isSpecs.value
    ? [
        { title: '属性名称', key: 'name', width: 150 },
        { title: '属性编码', key: 'code', width: 150 },
        {
          title: '适用分类',
          key: 'category_name',
          width: 680,
          render: (row) =>
            h(
              NSpace,
              { size: 4 },
              {
                default: () =>
                  (row.category_names || [row.category_name])
                    .filter(Boolean)
                    .map((name) =>
                      h(NTag, { size: 'small', bordered: false }, { default: () => name })
                    ),
              }
            ),
        },
        { title: '属性类型', key: 'attr_type_label', width: 110 },
        { title: '单位', key: 'unit', width: 80 },
        {
          title: '必填',
          key: 'required',
          width: 80,
          render: (row) => (row.required ? '是' : '否'),
        },
      ]
    : [
        { title: '模板名称', key: 'name', width: 220 },
        { title: '适用分类', key: 'category_name', width: 180 },
        { title: '模板类型', key: 'template_type', width: 130 },
        { title: '说明', key: 'description', width: 300 },
        {
          title: '状态',
          key: 'status',
          width: 90,
          render: (row) => (row.status ? '启用' : '停用'),
        },
      ]
  return [
    ...business.map((column) => ({ ...column, resizable: true })),
    {
      title: '操作',
      key: 'actions',
      width: 100,
      fixed: 'right',
      resizable: false,
      render: (row) =>
        h(
          NSpace,
          { size: 4, wrap: false, onClick: (event) => event.stopPropagation() },
          {
            default: () => [
              actionButton('编辑', 'mdi:pencil-outline', row),
              actionButton('删除', 'mdi:trash-can-outline', row, true),
            ],
          }
        ),
    },
  ]
})
const scrollX = computed(() => columns.value.reduce((sum, column) => sum + column.width, 0))
async function loadPage() {
  loading.value = true
  try {
    const fetch = isSpecs.value
      ? api.productCenterApi.listAttributes
      : api.productCenterApi.listTemplates
    const response = await fetch({
      ...query,
      page: pagination.page,
      page_size: pagination.pageSize,
    })
    rows.value = response.data || []
    pagination.itemCount = response.total || 0
  } catch {
    window.$message?.error('列表加载失败，请重试')
  } finally {
    loading.value = false
  }
}
function search() {
  pagination.page = 1
  return loadPage()
}
function resetQuery() {
  Object.assign(query, { keyword: '', attr_type: null, category_id: null })
  return search()
}
function openEditor(row) {
  if (busy.value) return
  editor.form = row
    ? {
        ...row,
        category_ids: [...(row.category_ids || (row.category_id ? [row.category_id] : []))],
      }
    : {
        name: '',
        code: '',
        category_ids: [],
        category_id: null,
        attr_type: 'text',
        unit: '',
        required: false,
        status: true,
        options: '',
        description: '',
        template_type: 'product',
        config: '',
      }
  editor.show = true
}
async function saveEditor() {
  if (busy.value) return
  const payload = { ...editor.form }
  if (!payload.name || (isSpecs.value && (!payload.code || !payload.category_ids.length))) {
    return window.$message?.warning(
      isSpecs.value ? '请填写属性名称、编码和适用分类' : '请填写模板名称'
    )
  }
  if (isSpecs.value) payload.category_id = payload.category_ids[0]
  editor.loading = true
  try {
    const create = isSpecs.value
      ? api.productCenterApi.createAttribute
      : api.productCenterApi.createTemplate
    const update = isSpecs.value
      ? api.productCenterApi.updateAttribute
      : api.productCenterApi.updateTemplate
    if (payload.id) await update(payload.id, payload)
    else await create(payload)
    editor.show = false
    window.$message?.success('保存成功')
    await loadPage()
  } catch {
    window.$message?.error('保存失败，请重试')
  } finally {
    editor.loading = false
  }
}
async function deleteRow(row) {
  if (busy.value) return
  deletingId.value = row.id
  try {
    const remove = isSpecs.value
      ? api.productCenterApi.deleteAttribute
      : api.productCenterApi.deleteTemplate
    await remove(row.id)
    if (rows.value.length === 1 && pagination.page > 1) pagination.page -= 1
    window.$message?.success('删除成功')
    await loadPage()
  } catch {
    window.$message?.error('删除失败，请重试')
  } finally {
    deletingId.value = null
  }
}
onMounted(async () => {
  try {
    const response = await api.productCenterApi.options()
    options.categoryTree = response.data?.category_tree || []
    options.attributeTypes = response.data?.attribute_types || []
  } catch {
    window.$message?.error('选项加载失败，请刷新重试')
  }
  await loadPage()
})
</script>
<style scoped>
.product-panel {
  padding: 18px;
  background: #fff;
  border: 1px solid #e7edf4;
  border-radius: 8px;
  min-width: 0;
}
.panel-head,
.list-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
h2 {
  margin: 4px 0;
  font-size: 22px;
}
.filter-row {
  display: flex;
  gap: 10px;
  margin: 16px 0;
}
.filter-row > .n-input,
.filter-row > .n-select,
.filter-row > .n-cascader {
  flex: 1;
  min-width: 140px;
}
.list-footer {
  margin-top: 16px;
}
@media (max-width: 768px) {
  .filter-row {
    flex-wrap: wrap;
  }
}
</style>
