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
            <n-button v-if="mode !== 'price-history'" type="primary" @click="openEditor()">
              <template #icon><TheIcon :icon="addIcon" :size="18" /></template>
              {{ addText }}
            </n-button>
          </n-space>
        </div>

        <div class="filter-row">
          <div class="filter-controls">
          <n-input v-if="showKeyword" v-model:value="query.keyword" clearable :placeholder="keywordPlaceholder" @keyup.enter="loadPage">
            <template #prefix><TheIcon icon="mdi:magnify" :size="17" /></template>
          </n-input>
          <n-cascader
            v-if="mode === 'products'"
            v-model:value="query.category_id"
            clearable
            filterable
            :show-path="false"
            check-strategy="child"
            :options="options.categoryTree"
            placeholder="产品分类"
          />
          <n-select v-if="mode === 'products'" v-model:value="query.status" clearable :options="options.productStatuses" placeholder="产品状态" />
          <n-cascader
            v-if="mode === 'products'"
            v-model:value="query.region"
            clearable
            filterable
            show-path
            check-strategy="child"
            :options="productRegionOptions"
            :filter="regionCascaderFilter"
            placeholder="地区"
          />
          <n-select v-if="mode === 'specs'" v-model:value="query.attr_type" clearable :options="options.attributeTypes" placeholder="属性类型" />
          <n-cascader
            v-if="mode === 'specs'"
            v-model:value="query.category_id"
            clearable
            filterable
            :show-path="false"
            check-strategy="child"
            :options="options.categoryTree"
            placeholder="适用分类"
          />
          <n-select v-if="mode === 'configs'" v-model:value="query.product_id" clearable filterable :options="options.products" placeholder="关联产品" />
          <n-cascader v-if="mode === 'pricing'" v-model:value="query.category_id" clearable filterable :show-path="false" check-strategy="child" :options="options.categoryTree" placeholder="产品目录" />
          <n-select v-if="mode === 'pricing'" v-model:value="query.customer_id" clearable filterable :show-checkmark="false" :options="options.customers" :render-label="renderCustomerOption" placeholder="客户" />
          <n-select v-if="mode === 'price-history'" v-model:value="query.product_id" clearable filterable :options="options.products" placeholder="关联产品" />
          <n-select v-if="mode === 'price-history'" v-model:value="query.customer_id" clearable filterable :show-checkmark="false" :options="options.customers" :render-label="renderCustomerOption" placeholder="客户" />
          <n-cascader
            v-if="mode === 'templates'"
            v-model:value="query.category_id"
            clearable
            filterable
            check-strategy="child"
            :options="options.categoryTree"
            placeholder="适用分类"
          />
          </div>
          <div class="filter-actions">
            <n-button class="filter-action-button" secondary @click="resetQuery">
              <template #icon><TheIcon icon="mdi:reload" :size="16" /></template>
              重置
            </n-button>
            <n-button class="filter-action-button" type="primary" @click="loadPage">
              <template #icon><TheIcon icon="mdi:magnify" :size="16" /></template>
              搜索
            </n-button>
          </div>
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
            @update:sorter="handleSorterChange"
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
              <n-form-item-gi label="产品编码"><n-input v-model:value="editor.form.code" :disabled="Boolean(editor.form.id)" placeholder="留空自动生成" /></n-form-item-gi>
              <n-form-item-gi label="产品分类" required>
                <n-cascader
                  v-model:value="editor.form.category_id"
                  clearable
                  filterable
                  check-strategy="child"
                  :options="options.categoryTree"
                  :disabled="Boolean(editor.form.id)"
                  placeholder="请选择产品分类"
                />
              </n-form-item-gi>
              <n-form-item-gi label="产品状态"><n-select v-model:value="editor.form.status" :options="options.productStatuses" /></n-form-item-gi>
              <n-form-item-gi label="地区" required>
                <n-cascader
                  v-model:value="editor.form.region"
                  clearable
                  filterable
                  show-path
                  check-strategy="child"
                  :options="productRegionOptions"
                  :disabled="Boolean(editor.form.id)"
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
              <n-form-item-gi label="属性类型"><n-select v-model:value="editor.form.attr_type" :options="options.attributeTypes" /></n-form-item-gi>
              <n-form-item-gi label="单位"><n-input v-model:value="editor.form.unit" /></n-form-item-gi>
              <n-form-item-gi label="必填"><n-switch v-model:value="editor.form.required" /></n-form-item-gi>
              <n-form-item-gi label="启用"><n-switch v-model:value="editor.form.status" /></n-form-item-gi>
              <n-form-item-gi label="可选值" :span="2"><n-input v-model:value="editor.form.options" type="textarea" placeholder="一行一个值，或填写 JSON" /></n-form-item-gi>
              <n-form-item-gi label="说明" :span="2"><n-input v-model:value="editor.form.description" type="textarea" /></n-form-item-gi>
            </template>

            <template v-else-if="mode === 'configs'">
              <n-form-item-gi label="关联产品" required :span="2">
                <n-select v-model:value="editor.form.product_id" filterable :options="options.products" @update:value="handleConfigProductChange" />
              </n-form-item-gi>
              <n-form-item-gi label="规格属性集合" required :span="2">
                <div class="spec-config-lines">
                  <div v-for="(line, index) in editor.form.configs" :key="line.key" class="spec-config-line">
                    <div class="spec-config-line-head">
                      <strong>属性 {{ index + 1 }}</strong>
                      <n-button quaternary circle type="error" :disabled="editor.form.configs.length <= 1" @click="removeConfigLine(index)">
                        <template #icon><TheIcon icon="mdi:trash-can-outline" size="16" /></template>
                      </n-button>
                    </div>
                    <div class="spec-config-line-grid">
                      <n-select
                        v-model:value="line.attribute_id"
                        filterable
                        :disabled="!editor.form.product_id"
                        :options="configAttributeOptions"
                        :placeholder="editor.form.product_id ? '请选择规格属性' : '请先选择关联产品'"
                        @update:value="normalizeConfigLineValues(line, true)"
                      />
                      <n-input-number v-if="configLineAttrType(line) === 'number'" v-model:value="line.default_value" clearable :placeholder="configLineValuePlaceholder(line)" />
                      <n-select v-else-if="configLineAttrType(line) === 'select'" v-model:value="line.default_value" clearable filterable :options="configLineAttrOptions(line)" :placeholder="configLineValuePlaceholder(line)" />
                      <n-select v-else-if="configLineAttrType(line) === 'multi_select'" v-model:value="line.default_value" multiple clearable filterable :options="configLineAttrOptions(line)" :placeholder="configLineValuePlaceholder(line)" />
                      <n-switch v-else-if="configLineAttrType(line) === 'switch'" v-model:value="line.default_value" />
                      <n-date-picker v-else-if="configLineAttrType(line) === 'date'" v-model:formatted-value="line.default_value" value-format="yyyy-MM-dd" type="date" clearable :placeholder="configLineValuePlaceholder(line)" />
                      <n-input v-else v-model:value="line.default_value" :placeholder="configLineValuePlaceholder(line)" />
                      <div class="spec-config-required"><span>必填</span><n-switch v-model:value="line.required" /></div>
                    </div>
                  </div>
                  <n-button secondary type="info" :disabled="!editor.form.product_id" @click="addConfigLine">
                    <template #icon><TheIcon icon="mdi:plus" size="16" /></template>
                    添加属性
                  </n-button>
                </div>
              </n-form-item-gi>
            </template>

            <template v-else-if="mode === 'pricing'">
              <n-form-item-gi v-if="!isInheritedCloudPriceEdit" label="关联产品" required :span="2"><n-select v-model:value="editor.form.product_id" filterable :options="options.products" @update:value="handlePricingProductChange" /></n-form-item-gi>
              <n-form-item-gi v-if="isPricingCloudProduct && !isInheritedCloudPriceEdit" label="关联云主机" required :span="2"><n-select v-model:value="editor.form.cloud_vm_key" filterable :multiple="!editor.form.id" :loading="cloudVmLoading" :options="cloudVmOptions" placeholder="请选择当前产品地区的云主机" @update:value="handleCloudVmChange" /></n-form-item-gi>
              <n-form-item-gi v-else-if="isPricingPhysicalServerProduct && !isInheritedCloudPriceEdit" label="关联物理服务器" required :span="2"><n-select v-model:value="editor.form.physical_device_key" filterable :loading="physicalDeviceLoading" :options="physicalDeviceOptions" placeholder="请选择当前产品地区使用中的物理服务器" @update:value="handlePhysicalDeviceChange" /></n-form-item-gi>
              <n-form-item-gi v-else-if="!isInheritedCloudPriceEdit" label="关联规格配置" required :span="2"><n-select v-model:value="editor.form.spec_config_key" filterable :options="pricingSpecConfigOptions" @update:value="handlePricingSpecConfigChange" /></n-form-item-gi>
              <n-form-item-gi v-if="!isInheritedCloudPriceEdit" label="客户" required><n-select v-model:value="editor.form.customer_id" clearable filterable :show-checkmark="false" :disabled="(isPricingCloudProduct || isPricingPhysicalServerProduct) && Boolean(editor.form.customer_id)" :options="options.customers" :render-label="renderCustomerOption" @update:value="handlePricingCustomerChange" /></n-form-item-gi>
              <n-form-item-gi v-if="!isInheritedCloudPriceEdit" label="计费单位"><n-select v-model:value="editor.form.billing_unit" :options="options.billingUnits" /></n-form-item-gi>
              <n-form-item-gi label="价格">
                <n-input-group class="price-amount-field">
                  <n-input-number v-model:value="editor.form.amount" :min="0" />
                  <n-select v-model:value="editor.form.currency" class="price-currency-select" :options="options.currencies" />
                </n-input-group>
              </n-form-item-gi>
              <template v-if="!isInheritedCloudPriceEdit">
                <n-form-item-gi label="生效日期"><n-date-picker v-model:formatted-value="editor.form.effective_date" value-format="yyyy-MM-dd" type="date" clearable /></n-form-item-gi>
              </template>
              <n-form-item-gi label="失效日期"><n-date-picker v-model:formatted-value="editor.form.expiry_date" value-format="yyyy-MM-dd" type="date" clearable /></n-form-item-gi>
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
      <n-modal v-model:show="notificationModal.show" preset="card" title="飞书通知" class="price-notification-modal" :style="{ width: '560px', maxWidth: 'calc(100vw - 24px)' }" :bordered="false">
        <n-form :model="notificationModal.form" label-placement="top" class="modal-form"><n-grid :cols="2" :x-gap="16">
          <n-form-item-gi label="启用通知" :span="2"><n-switch v-model:value="notificationModal.form.notify_enabled"><template #checked>启用</template><template #unchecked>关闭</template></n-switch></n-form-item-gi>
          <template v-if="notificationModal.form.notify_enabled">
            <n-form-item-gi label="通知人" :span="2"><n-select v-model:value="notificationModal.form.notify_user_ids" multiple filterable :options="options.notifyUsers" placeholder="选择飞书通知接收人" /></n-form-item-gi>
            <n-form-item-gi label="提醒方式"><n-select v-model:value="notificationModal.form.notify_schedule" :options="notifyScheduleOptions" /></n-form-item-gi>
            <n-form-item-gi v-if="notificationModal.form.notify_schedule === 'once'" label="通知时间"><n-date-picker v-model:formatted-value="notificationModal.form.notify_at" value-format="yyyy-MM-dd HH:mm:ss" type="datetime" clearable /></n-form-item-gi>
            <template v-else>
              <n-form-item-gi label="每月执行日"><n-input-number v-model:value="notificationModal.form.notify_day" :min="1" :max="31" /></n-form-item-gi>
              <n-form-item-gi label="执行时间"><n-time-picker v-model:formatted-value="notificationModal.form.notify_time" value-format="HH:mm:ss" clearable /></n-form-item-gi>
            </template>
          </template>
        </n-grid></n-form>
        <template #footer><ModalFooter :loading="notificationModal.loading" @cancel="notificationModal.show = false" @save="saveNotification" /></template>
      </n-modal>
      <n-modal v-model:show="credentialModal.show" preset="card" title="云主机创建完成" class="vm-credential-modal" :bordered="false">
        <p class="vm-credential-note">请立即复制并妥善保存初始登录信息，关闭后无法再次查看密码。</p>
        <div class="vm-credential-list">
          <div class="vm-credential-row"><span>虚拟机名称</span><code>{{ credentialModal.data.vm_name }}</code></div>
          <div class="vm-credential-row"><span>初始密码</span><code>{{ credentialModal.data.password }}</code></div>
          <div class="vm-credential-row"><span>IP 地址</span><code>{{ credentialModal.data.ip || '-' }}</code></div>
          <div class="vm-credential-row"><span>所在 PVE</span><code>{{ credentialModal.data.remote || '-' }}</code></div>
        </div>
        <template #footer><CButton show-cancel show-save cancel-text="关闭" save-text="复制全部" @cancel="credentialModal.show = false" @save="copyVmCredentials" /></template>
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
  NInputGroup,
  NInputNumber,
  NPagination,
  NPopconfirm,
  NSelect,
  NSpace,
  NSwitch,
  NTag,
  NTree,
  NTooltip,
} from 'naive-ui'
import api from '@/api'
import TheIcon from '@/components/icon/TheIcon.vue'
import CButton from '@/components/public/CButton.vue'
import { translateCity, translateCountry, translateLocationPath } from '@/utils/location-i18n'

const props = defineProps({ mode: { type: String, default: 'products' } })

const modeMeta = {
  products: { title: '产品管理', keyword: '搜索产品名称 / 编码 / 地区', add: '新增产品', icon: 'mdi:plus-box-outline' },
  specs: { title: '规格管理', keyword: '搜索属性名称 / 编码 / 单位', add: '新增属性', icon: 'mdi:tune-variant' },
  configs: { title: '规格配置', keyword: '', add: '新增配置', icon: 'mdi:playlist-plus' },
  pricing: { title: '价格管理', keyword: '搜索产品 / 客户', add: '新增价格', icon: 'mdi:cash-plus' },
  'price-history': { title: '客户历史价格', keyword: '搜索产品 / 客户', add: '', icon: 'mdi:history' },
  templates: { title: '产品模板', keyword: '搜索模板名称 / 说明', add: '新增模板', icon: 'mdi:file-plus-outline' },
}

const pageTitle = computed(() => modeMeta[props.mode]?.title || '产品中心')
const addText = computed(() => modeMeta[props.mode]?.add || '新增')
const addIcon = computed(() => modeMeta[props.mode]?.icon || 'mdi:plus')
const keywordPlaceholder = computed(() => modeMeta[props.mode]?.keyword || '搜索')
const showKeyword = computed(() => !['configs', 'products', 'specs', 'pricing', 'price-history'].includes(props.mode))
const scrollX = computed(() => {
  if (['pricing', 'price-history'].includes(props.mode)) return 1280
  if (props.mode === 'products') return 1180
  if (props.mode === 'specs') return 1280
  if (props.mode === 'configs') return 1420
  return 980
})
const selectedCategoryKeys = computed(() => (query.category_id ? [query.category_id] : []))
const topCategoryOptions = computed(() => options.categories.filter((item) => !item.parent_id))
const productRegionOptions = computed(() => {
  return buildPopRegionOptions()
})
const productBillingModeOptions = computed(() => {
  if (props.mode !== 'products') return options.billingModes
  const allowedValues = billingModesForCategory(editor.form.category_id)
  return options.billingModes.filter((item) => allowedValues.includes(item.value))
})
const configAttributeOptions = computed(() => {
  if (props.mode !== 'configs') return options.attributes
  const allowedCategoryIds = specAttributeCategoryIdsForProduct(editor.form.product_id)
  if (!allowedCategoryIds.length) return []
  const rows = options.attributes.filter((item) => attributeCategoryIds(item).some((id) => allowedCategoryIds.includes(id)))
  if (editor.form.attribute_id && !rows.some((item) => item.value === editor.form.attribute_id)) {
    const current = options.attributes.find((item) => item.value === editor.form.attribute_id)
    if (current) rows.unshift(current)
  }
  return rows
})
const selectedConfigAttribute = computed(() => {
  if (props.mode !== 'configs' || !editor.form.attribute_id) return null
  return options.attributes.find((item) => String(item.value) === String(editor.form.attribute_id)) || null
})
const selectedConfigAttrType = computed(() => selectedConfigAttribute.value?.attr_type || 'text')
const selectedConfigAttrOptions = computed(() => parseAttributeOptions(selectedConfigAttribute.value?.options))
const configValuePlaceholder = computed(() => {
  if (!selectedConfigAttribute.value) return '请先选择规格属性'
  if (selectedConfigAttrType.value === 'number') return `请输入数字${selectedConfigAttribute.value.unit ? `，单位 ${selectedConfigAttribute.value.unit}` : ''}`
  if (['select', 'multi_select'].includes(selectedConfigAttrType.value)) return selectedConfigAttrOptions.value.length ? '请选择默认值' : '请先在规格属性中维护可选值'
  if (selectedConfigAttrType.value === 'date') return '请选择日期'
  if (selectedConfigAttrType.value === 'resource_ref') return '请输入资源引用'
  return '请输入默认值'
})
const configRangePlaceholder = computed(() => {
  if (selectedConfigAttrType.value === 'number') return '例如：1-100，或填写允许的数字范围'
  if (selectedConfigAttrType.value === 'date') return '例如：2026-01-01 至 2026-12-31'
  if (selectedConfigAttrType.value === 'switch') return '开关类型通常无需填写'
  return '不限制则留空'
})

const loading = ref(false)
const rows = ref([])
const categories = ref([])
const expandedCategoryKeys = ref([])
const popRegions = ref([])
const editorInitializing = ref(false)
const dhcpLoading = ref(false)
const cloudVmLoading = ref(false)
const cloudVmOptions = ref([])
const physicalDeviceLoading = ref(false)
const physicalDeviceOptions = ref([])
const pagination = reactive({ page: 1, pageSize: 20, itemCount: 0, pageSizes: [20, 50, 100] })
const configSortState = reactive({ columnKey: 'product_category_sort', order: 'ascend' })
const pricingSortState = reactive({ columnKey: 'id', order: 'descend' })
const query = reactive({ keyword: '', category_id: null, status: null, region: null, attr_type: null, product_id: null, spec_config_key: null, price_type: null, customer_id: null })
const options = reactive({
  categoryTree: [],
  categories: [],
  products: [],
  specConfigs: [],
  attributes: [],
  customers: [],
  productStatuses: [],
  priceTypes: [],
  billingModes: [],
  billingUnits: [],
  attributeTypes: [],
  currencies: [],
  notifyUsers: [],
  dhcpPools: [],
})
const categoryModal = reactive({ show: false, loading: false, form: emptyCategory() })
const editor = reactive({ show: false, loading: false, inheriting: false, form: emptyForm() })
const credentialModal = reactive({ show: false, data: { vm_name: '', password: '', ip: '', remote: '' } })
const notificationModal = reactive({ show: false, loading: false, form: { id: null, notify_enabled: false, notify_user_ids: [], notify_schedule: 'once', notify_at: null, notify_day: 1, notify_time: '09:00:00' } })
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
    return () =>
      h('div', { class: 'modal-footer' }, [
        h(CButton, {
          showCancel: true,
          showSave: true,
          saveLoading: componentProps.loading,
          onCancel: () => emit('cancel'),
          onSave: () => emit('save'),
        }),
      ])
  },
})

function renderTag(text, type = 'default') {
  return h(NTag, { size: 'small', round: true, type }, { default: () => text || '-' })
}

function renderCustomerOption(option) {
  const signingEntity = String(option?.signing_entity_name || '')
  const normalized = signingEntity.toLowerCase()
  const tag = signingEntity.includes('科特思')
    ? { text: '科', type: 'success' }
    : normalized.includes('77')
      ? { text: '7', type: 'warning' }
      : normalized.includes('catixs')
        ? { text: 'C', type: 'info' }
        : null
  if (!tag) return option.label
  return h('span', {
    style: {
      display: 'grid',
      gridTemplateColumns: 'minmax(0, 1fr) auto',
      alignItems: 'center',
      width: '100%',
      minWidth: 0,
      flex: '1 1 auto',
      columnGap: '12px',
    },
  }, [
    h('span', { style: 'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;' }, option.label),
    h(NTag, { size: 'small', round: true, type: tag.type }, { default: () => tag.text }),
  ])
}

function renderCategoryTag(text, type = 'default') {
  return h(
    'span',
    { style: { display: 'inline-flex', margin: '3px 10px 3px 0' } },
    [h(NTag, { size: 'small', round: true, type }, { default: () => text || '-' })]
  )
}

const categoryTagTypes = ['info', 'success', 'warning', 'error', 'primary', 'default']

function categoryTagType(name) {
  const text = String(name || '')
  let hash = 0
  for (let index = 0; index < text.length; index += 1) hash += text.charCodeAt(index)
  return categoryTagTypes[hash % categoryTagTypes.length]
}

function renderCategoryTags(row) {
  const names = Array.isArray(row.category_names) && row.category_names.length
    ? row.category_names
    : String(row.category_name || '')
        .split(/[、,，]/)
        .map((item) => item.trim())
        .filter(Boolean)
  if (!names.length) return '-'
  return h('div', { class: 'category-tags' }, names.map((name) => renderCategoryTag(name, categoryTagType(name))))
}

function renderSpecConfigAttributes(row) {
  const attrs = Array.isArray(row.attributes) ? row.attributes : []
  if (!attrs.length) return row.attribute_summary || '-'
  return h(
    'div',
    { class: 'config-attribute-tags' },
    attrs.map((item) => {
      const value = item.value || '-'
      const unit = item.unit && value !== '-' && !String(value).endsWith(item.unit) ? ` ${item.unit}` : ''
      return h(
        'span',
        { class: 'config-attribute-tag', style: { marginRight: '8px', marginBottom: '6px' } },
        [
          h(
            NTag,
            { size: 'small', round: true, type: categoryTagType(item.code || item.name) },
            { default: () => `${item.name || item.code}: ${value}${unit}` }
          ),
        ]
      )
    })
  )
}

function actionIconButton(icon, label, type, onClick) {
  return h('span', { class: 'table-action-item' }, [
    h(NTooltip, { placement: 'top' }, {
      trigger: () => h(NButton, { size: 'tiny', secondary: true, round: true, type, onClick }, { icon: () => h(TheIcon, { icon, size: 14 }) }),
      default: () => label,
    }),
  ])
}

function deleteActionButton(row) {
  const product = getProduct(row.product_id)
  const isCloudProduct = isCategoryMatch(product?.category_id, ['云主机'])
    || options.specConfigs.some((item) => item.product_id === product?.value && item.source_type === 'cloud_vm')
  const shutsDownVm = props.mode === 'pricing' && isCloudProduct && Boolean(row.cloud_vm_remote && row.cloud_vm_vmid)
  const releasesPhysicalServer = props.mode === 'pricing' && Boolean(row.physical_device_id)
  return h('span', { class: 'table-action-item' }, [
    h(NPopconfirm, { onPositiveClick: () => deleteRow(row) }, {
      trigger: () => h(NTooltip, { placement: 'top' }, {
        trigger: () => h(NButton, { size: 'tiny', secondary: true, round: true, type: 'error' }, { icon: () => h(TheIcon, { icon: props.mode === 'pricing' ? 'mdi:archive-arrow-down-outline' : 'mdi:trash-can-outline', size: 14 }) }),
        default: () => props.mode === 'pricing' ? '下架' : '删除',
      }),
      default: () => (
        shutsDownVm
          ? '删除价格将关闭关联虚拟机，确认继续？'
          : releasesPhysicalServer
            ? '删除价格将把关联物理服务器标记为空闲，确认继续？'
            : '确认删除？'
      ),
    }),
  ])
}

function actionButtons(row) {
  return h('div', { class: 'table-actions' }, [
    actionIconButton('mdi:pencil', '编辑', 'info', () => openEditor(row)),
    deleteActionButton(row),
  ])
}

function priceActionButtons(row) {
  const buttons = [actionIconButton('mdi:pencil', '编辑', 'info', () => openEditor(row))]
  if (row.price_type === 'customer') buttons.push(actionIconButton('mdi:bell-outline', '飞书通知', 'primary', () => openNotification(row)))
  if (row.price_type === 'standard') {
    buttons.push(actionIconButton('mdi:content-copy', '继承', 'primary', () => inheritPrice(row)))
  }
  buttons.push(deleteActionButton(row))
  return h('div', { class: 'table-actions pricing-table-actions' }, buttons)
}

function priceHistoryActionButtons(row) {
  return h('div', { class: 'table-actions pricing-table-actions' }, [deleteActionButton(row)])
}

function configActionButtons(row) {
  if (row.auto_sync) return null
  return actionButtons(row)
}

function configSortProps(key) {
  return {
    sorter: true,
    sortOrder: props.mode === 'configs' && configSortState.columnKey === key ? configSortState.order : false,
  }
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
  { title: '属性名称', key: 'name', width: 130 },
  { title: '属性编码', key: 'code', width: 140 },
  { title: '适用分类', key: 'category_name', width: 680, render: renderCategoryTags },
  { title: '属性类型', key: 'attr_type_label', width: 90 },
  { title: '单位', key: 'unit', width: 70 },
  { title: '必填', key: 'required', width: 70, render: (row) => renderTag(row.required ? '是' : '否', row.required ? 'warning' : 'default') },
  { title: '操作', key: 'actions', width: 100, fixed: 'right', render: actionButtons },
]
const configColumns = computed(() => [
  { title: '关联产品', key: 'product_name', width: 220, ellipsis: { tooltip: true }, ...configSortProps('product_name') },
  { title: '规格名称', key: 'spec_name', width: 300, ellipsis: { tooltip: true }, ...configSortProps('spec_name') },
  { title: '规格属性', key: 'attribute_summary', minWidth: 620, render: renderSpecConfigAttributes, ...configSortProps('attribute_summary') },
  { title: '来源', key: 'source_label', width: 150, render: (row) => renderTag(row.source_label, row.auto_sync ? 'success' : 'default'), ...configSortProps('source_label') },
  { title: '操作', key: 'actions', width: 100, fixed: 'right', render: configActionButtons },
])
const priceColumns = [
  { title: '产品名称', key: 'product_name', width: 220, ellipsis: { tooltip: true } },
  { title: '规格配置', key: 'spec_config_display', width: 340, ellipsis: { tooltip: true } },
  { title: '价格类型', key: 'price_type_label', width: 120, render: (row) => renderTag(row.price_type_label, row.price_type === 'customer' ? 'warning' : 'success') },
  { title: '客户', key: 'customer_display_name', width: 180, ellipsis: { tooltip: true } },
  { title: '计费单位', key: 'billing_unit_label', width: 110 },
  { title: '价格', key: 'amount', width: 120, render: (row) => `${row.currency || ''} ${row.amount ?? 0}` },
  { title: '生效日期', key: 'effective_date', width: 120 },
  { title: '失效日期', key: 'expiry_date', width: 120 },
  { title: '操作', key: 'actions', width: 150, fixed: 'right', render: priceActionButtons },
]
const priceHistoryColumns = [
  ...priceColumns.filter((item) => item.key !== 'actions'),
  { title: '下架日期', key: 'off_shelf_at', width: 180 },
  { title: '操作', key: 'actions', width: 100, fixed: 'right', render: priceHistoryActionButtons },
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
  if (props.mode === 'configs') return configColumns.value
  if (props.mode === 'pricing') {
    return priceColumns.map((column) => ({
      ...column,
      resizable: column.key !== 'actions',
      sorter: column.key === 'actions' ? false : true,
      sortOrder: pricingSortState.columnKey === column.key ? pricingSortState.order : false,
    }))
  }
  if (props.mode === 'price-history') return priceHistoryColumns
  return templateColumns
})
const editorTitle = computed(() => `${editor.form.id ? '编辑' : '新增'}${pageTitle.value.replace('管理', '').replace('配置', '配置')}`)
const pricingProduct = computed(() => getProduct(editor.form.product_id))
const isPricingCloudProduct = computed(() => (
  isCategoryMatch(pricingProduct.value?.category_id, ['云主机'])
  || options.specConfigs.some((item) => item.product_id === pricingProduct.value?.value && item.source_type === 'cloud_vm')
))
const isPricingPhysicalServerProduct = computed(() => (
  isCategoryMatch(pricingProduct.value?.category_id, ['物理服务器'])
  || options.specConfigs.some((item) => item.product_id === pricingProduct.value?.value && item.source_type === 'physical_server')
))
const isInheritedCloudPriceEdit = computed(() => props.mode === 'pricing' && Boolean(editor.form.id) && Boolean(editor.form.inherited_from_price_id) && isPricingCloudProduct.value)
const selectedDhcpPool = computed(() => options.dhcpPools.find((item) => String(item.value) === String(editor.form.dhcp_pool_id)))
const pricingSpecConfigOptions = computed(() => {
  const productId = editor.form.product_id
  if (!productId) return []
  return options.specConfigs.filter((item) => String(item.product_id) === String(productId))
})

const cloudOsOptions = [
  {
    label: 'Debian',
    value: 'debian',
    children: [
      { label: '13 (trixie)', value: 'debian:13' },
      { label: '12 (Bookworm)', value: 'debian:12' },
      { label: '11 (Bullseye)', value: 'debian:11' },
    ],
  },
  {
    label: 'Ubuntu',
    value: 'ubuntu',
    children: [
      { label: '25.04 LTS', value: 'ubuntu:25.04' },
      { label: '24.04 LTS', value: 'ubuntu:24.04' },
      { label: '22.04 LTS', value: 'ubuntu:22.04' },
      { label: '20.04 LTS', value: 'ubuntu:20.04' },
    ],
  },
  {
    label: 'CentOS',
    value: 'centos',
    children: [{ label: '7.9', value: 'centos:7.9' }],
  },
]
const notifyScheduleOptions = [{ label: '一次性提醒', value: 'once' }, { label: '每月定时提醒', value: 'monthly' }]

function todayText() {
  const now = new Date()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${now.getFullYear()}-${month}-${day}`
}

function emptyCloudSpecValues() {
  return { cpu_core: 2, mem_total: 2, disk_total: 20 }
}

function emptyCategory() {
  return { id: null, name: '', code: '', parent_id: null, order: 0, description: '', status: true }
}

function emptyForm() {
  if (props.mode === 'products') return { id: null, name: '', code: '', category_id: query.category_id, status: 'active', region: '', billing_mode: 'fixed', description: '' }
  if (props.mode === 'specs') return { id: null, name: '', code: '', category_id: query.category_id, category_ids: query.category_id ? [query.category_id] : [], attr_type: 'text', unit: '', required: false, options: '', description: '', status: true }
  if (props.mode === 'configs') return { id: null, product_id: query.product_id, configs: [emptyConfigLine()] }
  if (props.mode === 'pricing') return { id: null, product_id: null, spec_config_key: query.spec_config_key, spec_config_name: '', cloud_vm_key: [], cloud_vm_remote: '', cloud_vm_vmid: null, cloud_vm_name: '', physical_device_key: null, physical_device_id: null, physical_device_name: '', physical_device_node: '', price_type: 'customer', customer_id: null, customer_name: '', billing_mode: 'fixed', billing_unit: 'month', currency: 'USD', amount: 0, effective_date: todayText(), expiry_date: null, notify_enabled: false, notify_user_ids: [], notify_schedule: 'once', notify_at: null, status: 'active', remark: '' }
  return { id: null, name: '', category_id: query.category_id, template_type: 'product', description: '', config: '', status: true }
}

function emptyConfigLine() {
  return { key: `${Date.now()}-${Math.random()}`, attribute_id: null, order: 0, default_value: '', value_range: '', required: false }
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
  options.specConfigs = data.spec_configs || []
  options.attributes = data.attributes || []
  options.customers = data.customers || []
  options.productStatuses = data.product_statuses || []
  options.priceTypes = data.price_types || []
  options.billingModes = data.billing_modes || []
  options.billingUnits = data.billing_units || []
  options.attributeTypes = data.attribute_types || []
  options.currencies = data.currencies || []
  options.notifyUsers = data.notify_users || []
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
    if (props.mode === 'products') res = await api.productCenterApi.listProducts(pageParams({ category_id: query.category_id || undefined, status: query.status || '', region: query.region || '' }))
    else if (props.mode === 'specs') res = await api.productCenterApi.listAttributes(pageParams({ keyword: query.keyword, attr_type: query.attr_type || '', category_id: query.category_id || undefined }))
    else if (props.mode === 'configs') res = await api.productCenterApi.listSpecConfigs(pageParams({
      product_id: query.product_id || undefined,
      sort_field: configSortState.columnKey || 'product_category_sort',
      sort_order: configSortState.order || 'ascend',
    }))
    else if (props.mode === 'pricing') res = await api.productCenterApi.listPrices(pageParams({ category_id: query.category_id || undefined, customer_id: query.customer_id || undefined, sort_field: pricingSortState.columnKey, sort_order: pricingSortState.order }))
    else if (props.mode === 'price-history') res = await api.productCenterApi.listPriceHistory(pageParams({ product_id: query.product_id || undefined, customer_id: query.customer_id || undefined }))
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
  Object.assign(query, { keyword: '', category_id: null, status: null, region: null, attr_type: null, product_id: null, spec_config_key: null, price_type: null, customer_id: null })
  pagination.page = 1
  loadPage()
}

function handlePageSizeChange(size) {
  pagination.pageSize = size
  pagination.page = 1
  loadPage()
}

function handleSorterChange(sorter) {
  if (!['configs', 'pricing'].includes(props.mode)) return
  const activeSorter = Array.isArray(sorter) ? sorter.find((item) => item.order) : sorter
  const state = props.mode === 'pricing' ? pricingSortState : configSortState
  const defaultKey = props.mode === 'pricing' ? 'id' : 'product_category_sort'
  const defaultOrder = props.mode === 'pricing' ? 'descend' : 'ascend'
  if (!activeSorter?.order) {
    state.columnKey = defaultKey
    state.order = defaultOrder
  } else {
    state.columnKey = activeSorter.columnKey || activeSorter.key || defaultKey
    state.order = activeSorter.order
  }
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
  editor.inheriting = false
  editor.form = row ? { ...emptyForm(), ...row } : emptyForm()
  if (props.mode === 'specs') {
    editor.form.category_ids = attributeCategoryIds(editor.form)
    editor.form.category_id = editor.form.category_ids[0] || null
  }
  if (props.mode === 'configs') {
    if (row) {
      editor.form = specConfigGroupToForm(row)
    }
    ;(editor.form.configs || []).forEach((line) => normalizeConfigLineValues(line))
  }
  if (props.mode === 'pricing') {
    editor.form.spec_values = pricingSpecValuesFromKey(editor.form.spec_config_key)
    if (row?.dhcp_lease) {
      editor.form.dhcp_pool_id = row.dhcp_lease.pool_id
      editor.form.os_type = row.dhcp_lease.os_type || editor.form.os_type || 'debian'
      editor.form.os_version = row.dhcp_lease.os_version || editor.form.os_version || '12'
      editor.form.os_key = `${editor.form.os_type}:${editor.form.os_version}`
      editor.form.spec_values = {
        cpu_core: row.dhcp_lease.cpu_cores || editor.form.spec_values.cpu_core || 2,
        mem_total: row.dhcp_lease.memory_gb || editor.form.spec_values.mem_total || 2,
        disk_total: row.dhcp_lease.disk_gb || editor.form.spec_values.disk_total || 20,
      }
    }
    editor.form.price_type = 'customer'
    if (row?.cloud_vm_remote && row?.cloud_vm_vmid) editor.form.cloud_vm_key = [row.cloud_vm_remote, row.cloud_vm_vmid].join(':')
    if (row?.physical_device_id) editor.form.physical_device_key = [row.physical_device_id, row.physical_device_node || ''].join(':')
    loadCloudVmOptions()
    loadPhysicalDeviceOptions()
  }
  if (!row) applyProductBillingDefault()
  editor.show = true
  nextTick(() => {
    editorInitializing.value = false
  })
}

function inheritPrice(row) {
  editorInitializing.value = true
  editor.inheriting = true
  editor.form = {
    ...emptyForm(),
    ...row,
    id: null,
    inherited_from_price_id: row.id,
    price_type: 'customer',
    customer_id: null,
    customer_name: '',
  }
  editor.form.billing_mode = getProduct(editor.form.product_id)?.billing_mode || editor.form.billing_mode || 'fixed'
  if (row.cloud_vm_remote && row.cloud_vm_vmid) editor.form.cloud_vm_key = [row.cloud_vm_remote, row.cloud_vm_vmid].join(':')
  loadCloudVmOptions()
  loadPhysicalDeviceOptions()
  editor.show = true
  nextTick(() => {
    editorInitializing.value = false
  })
}

function openNotification(row) {
  const notifyAt = row.notify_at ? new Date(String(row.notify_at).replace(' ', 'T')) : null
  notificationModal.form = {
    id: row.id,
    notify_enabled: Boolean(row.notify_enabled),
    notify_user_ids: Array.isArray(row.notify_user_ids) ? row.notify_user_ids : [],
    notify_schedule: row.notify_schedule || 'once',
    notify_at: row.notify_at || null,
    notify_day: notifyAt?.getDate?.() || 1,
    notify_time: notifyAt ? String(notifyAt.getHours()).padStart(2, '0') + ':' + String(notifyAt.getMinutes()).padStart(2, '0') + ':00' : '09:00:00',
  }
  notificationModal.show = true
}

async function saveNotification() {
  const form = notificationModal.form
  if (form.notify_enabled && !form.notify_user_ids.length) return window.$message?.warning('请选择通知人')
  if (form.notify_enabled && form.notify_schedule === 'once' && !form.notify_at) return window.$message?.warning('请选择通知时间')
  if (form.notify_enabled && form.notify_schedule === 'monthly' && (!form.notify_day || !form.notify_time)) return window.$message?.warning('请填写每月执行日和执行时间')
  notificationModal.loading = true
  try {
    await api.productCenterApi.updatePriceNotification(form.id, { ...form })
    notificationModal.show = false
    await loadPage()
  } finally {
    notificationModal.loading = false
  }
}

function specConfigGroupToForm(row = {}) {
  const attrs = Array.isArray(row.attributes) ? row.attributes : []
  return {
    id: row.id,
    product_id: row.product_id,
    source_key: row.source_key,
    config_ids: row.config_ids || [],
    configs: attrs.length
      ? attrs.map((item, index) => ({
          key: `${item.id || index}-${Date.now()}`,
          attribute_id: item.attribute_id,
          order: item.order ?? index,
          default_value: item.default_value ?? item.value ?? '',
          value_range: item.value_range ?? '',
          required: Boolean(item.required),
        }))
      : [emptyConfigLine()],
  }
}

function getCategory(categoryId) {
  return [...categories.value, ...options.categories].find((item) => String(item.id || item.value) === String(categoryId))
}

function getProduct(productId) {
  return options.products.find((item) => String(item.value) === String(productId))
}

function categoryPathNames(categoryId) {
  const names = []
  let category = getCategory(categoryId)
  while (category) {
    names.unshift(category.name || category.label)
    category = getCategory(category.parent_id)
  }
  return names
}

function categoryPathIds(categoryId) {
  const ids = []
  let category = getCategory(categoryId)
  while (category) {
    const id = Number(category.id || category.value)
    if (id) ids.unshift(id)
    category = getCategory(category.parent_id)
  }
  return ids
}

function categoryIncludes(categoryId, names) {
  return categoryPathNames(categoryId).some((name) => names.includes(name))
}

function isCategoryMatch(categoryId, names) {
  if (!categoryId) return false
  return categoryIncludes(categoryId, names)
}

function specAttributeCategoryIdsForProduct(productId) {
  const product = getProduct(productId)
  if (!product?.category_id) return []
  return categoryPathIds(product.category_id)
}

function attributeCategoryIds(attribute = {}) {
  const values = Array.isArray(attribute.category_ids) && attribute.category_ids.length ? attribute.category_ids : [attribute.category_id]
  return values.map((item) => Number(item)).filter(Boolean)
}

function parseAttributeOptions(raw) {
  const textValue = String(raw || '').trim()
  if (!textValue) return []
  let values = []
  try {
    const parsed = JSON.parse(textValue)
    if (Array.isArray(parsed)) values = parsed
    else if (parsed && typeof parsed === 'object') values = Object.entries(parsed).map(([value, label]) => ({ label, value }))
  } catch {
    values = textValue.split(/[\n,，]/).map((item) => item.trim()).filter(Boolean)
  }
  return values
    .map((item) => {
      if (item && typeof item === 'object') {
        const value = item.value ?? item.id ?? item.code ?? item.label ?? item.name
        const label = item.label ?? item.name ?? item.title ?? value
        return value == null ? null : { label: String(label), value: String(value) }
      }
      return item == null ? null : { label: String(item), value: String(item) }
    })
    .filter(Boolean)
}

function parseMultiValue(value) {
  if (Array.isArray(value)) return value.map((item) => String(item)).filter(Boolean)
  const textValue = String(value || '').trim()
  if (!textValue) return []
  try {
    const parsed = JSON.parse(textValue)
    if (Array.isArray(parsed)) return parsed.map((item) => String(item)).filter(Boolean)
  } catch {
    // fall through to delimiter parsing
  }
  return textValue.split(/[\n,，]/).map((item) => item.trim()).filter(Boolean)
}

function configLineAttribute(line = {}) {
  if (!line.attribute_id) return null
  return options.attributes.find((item) => String(item.value) === String(line.attribute_id)) || null
}

function configLineAttrType(line = {}) {
  return configLineAttribute(line)?.attr_type || 'text'
}

function configLineAttrOptions(line = {}) {
  return parseAttributeOptions(configLineAttribute(line)?.options)
}

function configLineValuePlaceholder(line = {}) {
  const attribute = configLineAttribute(line)
  const type = configLineAttrType(line)
  const attrOptions = configLineAttrOptions(line)
  if (!attribute) return '请先选择规格属性'
  if (type === 'number') return `请输入数字${attribute.unit ? `，单位 ${attribute.unit}` : ''}`
  if (['select', 'multi_select'].includes(type)) return attrOptions.length ? '请选择默认值' : '请先在规格属性中维护可选值'
  if (type === 'date') return '请选择日期'
  if (type === 'resource_ref') return '请输入资源引用'
  return '请输入默认值'
}

function configLineRangePlaceholder(line = {}) {
  const type = configLineAttrType(line)
  if (type === 'number') return '例如：1-100，或填写允许的数字范围'
  if (type === 'date') return '例如：2026-01-01 至 2026-12-31'
  if (type === 'switch') return '开关类型通常无需填写'
  return '不限制则留空'
}

function normalizeConfigLineValues(line, reset = false) {
  const type = configLineAttrType(line)
  if (reset) {
    line.default_value = type === 'switch' ? false : type === 'number' ? null : type === 'multi_select' ? [] : ''
    line.value_range = ['select', 'multi_select'].includes(type) ? [] : ''
    return
  }
  if (type === 'multi_select') {
    line.default_value = parseMultiValue(line.default_value)
    line.value_range = parseMultiValue(line.value_range)
  } else if (type === 'select') {
    line.default_value = Array.isArray(line.default_value) ? line.default_value[0] || null : line.default_value || null
    line.value_range = parseMultiValue(line.value_range)
  } else if (type === 'switch') {
    line.default_value = line.default_value === true || ['true', '1', 'yes', '是'].includes(String(line.default_value).toLowerCase())
    line.value_range = Array.isArray(line.value_range) ? line.value_range.join(', ') : line.value_range || ''
  } else if (type === 'number') {
    const numberValue = Number(line.default_value)
    line.default_value = Number.isFinite(numberValue) ? numberValue : null
    line.value_range = Array.isArray(line.value_range) ? line.value_range.join(', ') : line.value_range || ''
  } else {
    line.default_value = Array.isArray(line.default_value) ? line.default_value.join(', ') : line.default_value || ''
    line.value_range = Array.isArray(line.value_range) ? line.value_range.join(', ') : line.value_range || ''
  }
}

function addConfigLine() {
  editor.form.configs.push(emptyConfigLine())
}

function removeConfigLine(index) {
  if (editor.form.configs.length <= 1) return
  editor.form.configs.splice(index, 1)
}

function handleConfigProductChange() {
  editor.form.configs = [emptyConfigLine()]
}

function handlePricingProductChange(value) {
  const product = getProduct(value)
  editor.form.spec_config_key = null
  editor.form.spec_config_name = ''
  editor.form.billing_mode = product?.billing_mode || 'fixed'
  editor.form.cloud_vm_key = []
  editor.form.cloud_vm_remote = ''
  editor.form.cloud_vm_vmid = null
  editor.form.cloud_vm_name = ''
  editor.form.physical_device_key = null
  editor.form.physical_device_id = null
  editor.form.physical_device_name = ''
  editor.form.physical_device_node = ''
  editor.form.customer_id = null
  editor.form.customer_name = ''
  loadCloudVmOptions()
  loadPhysicalDeviceOptions()
}

function handlePricingOsChange(value) {
  const [osType, osVersion] = String(value || '').split(':')
  editor.form.os_type = osType || ''
  editor.form.os_version = osVersion || ''
}

async function loadPricingDhcpPools() {
  if (props.mode !== 'pricing') return
  const product = getProduct(editor.form.product_id)
  if (!product || !isCategoryMatch(product.category_id, ['云主机'])) {
    options.dhcpPools = []
    editor.form.dhcp_pool_id = null
    return
  }
  dhcpLoading.value = true
  try {
    const res = await api.virtualMachineApi.dhcpPoolOptions({ region: product.region || product.label || '' })
    options.dhcpPools = res.data || []
    if (!editor.form.dhcp_pool_id && options.dhcpPools.length) {
      editor.form.dhcp_pool_id = options.dhcpPools[0].value
    }
  } finally {
    dhcpLoading.value = false
  }
}

function pricingSpecValuesFromKey(specConfigKey) {
  const specConfig = getSpecConfigOption(specConfigKey)
  const values = emptyCloudSpecValues()
  const cloudPriceMatch = /^cloud-price:(\d+):(\d+):(\d+)$/.exec(String(specConfigKey || ''))
  if (cloudPriceMatch) {
    return {
      cpu_core: Number(cloudPriceMatch[1]),
      mem_total: Number(cloudPriceMatch[2]),
      disk_total: Number(cloudPriceMatch[3]),
    }
  }
  ;(specConfig?.attributes || []).forEach((item) => {
    if (['cpu_core', 'mem_total', 'disk_total'].includes(item.code)) {
      const numberValue = Number(item.value ?? item.default_value)
      values[item.code] = Number.isFinite(numberValue) ? numberValue : null
    }
  })
  return values
}

function getSpecConfigOption(specConfigKey) {
  return options.specConfigs.find((item) => String(item.value) === String(specConfigKey))
}

function handlePricingSpecConfigChange(value) {
  const specConfig = getSpecConfigOption(value)
  editor.form.product_id = specConfig?.product_id || null
  editor.form.spec_config_name = specConfig?.spec_name || ''
  editor.form.spec_values = pricingSpecValuesFromKey(value)
  if (specConfig?.billing_mode) editor.form.billing_mode = specConfig.billing_mode
}

function handlePricingTypeChange(value) {
  if (value !== 'customer') {
    editor.form.customer_id = null
    editor.form.customer_name = ''
  }
}

function handlePricingCustomerChange(value) {
  if (value) editor.form.price_type = 'customer'
}

async function loadCloudVmOptions() {
  if (props.mode !== 'pricing' || !isPricingCloudProduct.value || !editor.form.product_id) {
    cloudVmOptions.value = []
    return
  }
  cloudVmLoading.value = true
  try {
    const res = await api.productCenterApi.priceCloudVmOptions(editor.form.product_id)
    cloudVmOptions.value = res.data || []
  } finally {
    cloudVmLoading.value = false
  }
}

function handleCloudVmChange(value) {
  const selectedKeys = Array.isArray(value) ? value : [value]
  const selected = cloudVmOptions.value.find((item) => item.value === selectedKeys[0])
  editor.form.cloud_vm_remote = selected?.remote || ''
  editor.form.cloud_vm_vmid = selected?.vmid || null
  editor.form.cloud_vm_name = selected?.name || ''
  editor.form.customer_id = selected?.customer_id || null
  editor.form.customer_name = selected?.customer_name || ''
}

async function loadPhysicalDeviceOptions() {
  if (props.mode !== 'pricing' || !isPricingPhysicalServerProduct.value || !editor.form.product_id) {
    physicalDeviceOptions.value = []
    return
  }
  physicalDeviceLoading.value = true
  try {
    const res = await api.productCenterApi.pricePhysicalDeviceOptions(editor.form.product_id)
    physicalDeviceOptions.value = res.data || []
  } finally {
    physicalDeviceLoading.value = false
  }
}

function handlePhysicalDeviceChange(value) {
  const selected = physicalDeviceOptions.value.find((item) => item.value === value)
  editor.form.physical_device_id = selected?.id || null
  editor.form.physical_device_name = selected?.name || ''
  editor.form.physical_device_node = selected?.node_name || ''
  editor.form.customer_id = selected?.customer_id || null
  editor.form.customer_name = selected?.customer_name || ''
}

function normalizeConfigEditorValues(reset = false) {
  if (props.mode !== 'configs') return
  const type = selectedConfigAttrType.value
  if (reset) {
    editor.form.default_value = type === 'switch' ? false : type === 'number' ? null : type === 'multi_select' ? [] : ''
    editor.form.value_range = ['select', 'multi_select'].includes(type) ? [] : ''
    return
  }
  if (type === 'multi_select') {
    editor.form.default_value = parseMultiValue(editor.form.default_value)
    editor.form.value_range = parseMultiValue(editor.form.value_range)
  }
  else if (type === 'select') {
    editor.form.default_value = Array.isArray(editor.form.default_value) ? editor.form.default_value[0] || null : editor.form.default_value || null
    editor.form.value_range = parseMultiValue(editor.form.value_range)
  } else if (type === 'switch') {
    editor.form.default_value = editor.form.default_value === true || ['true', '1', 'yes', '是'].includes(String(editor.form.default_value).toLowerCase())
    editor.form.value_range = Array.isArray(editor.form.value_range) ? editor.form.value_range.join(', ') : editor.form.value_range || ''
  } else if (type === 'number') {
    const numberValue = Number(editor.form.default_value)
    editor.form.default_value = Number.isFinite(numberValue) ? numberValue : null
    editor.form.value_range = Array.isArray(editor.form.value_range) ? editor.form.value_range.join(', ') : editor.form.value_range || ''
  } else {
    editor.form.default_value = Array.isArray(editor.form.default_value) ? editor.form.default_value.join(', ') : editor.form.default_value || ''
    editor.form.value_range = Array.isArray(editor.form.value_range) ? editor.form.value_range.join(', ') : editor.form.value_range || ''
  }
}

function serializeConfigValue(value) {
  if (Array.isArray(value)) return value.length ? JSON.stringify(value) : null
  if (typeof value === 'boolean') return String(value)
  if (value == null || value === '') return null
  return String(value)
}

function ensureConfigAttributeFitsProduct() {
  if (props.mode !== 'configs' || !editor.form.product_id || !editor.form.attribute_id) return
  const allowedCategoryIds = specAttributeCategoryIdsForProduct(editor.form.product_id)
  const selected = options.attributes.find((item) => item.value === editor.form.attribute_id)
  if (selected && allowedCategoryIds.length && !attributeCategoryIds(selected).some((id) => allowedCategoryIds.includes(id))) {
    editor.form.attribute_id = null
  }
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
  return fieldText(value)
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
  const countryNodes = new Map()
  popRegions.value
    .filter((region) => region.status !== false)
    .forEach((region) => {
      const rawValue = fieldText(region.name) || [fieldText(region.country), fieldText(region.city)].filter(Boolean).join(' / ')
      if (!rawValue) return
      const countryLabel = regionCountryLabel(region)
      const cityLabel = regionCityLabel(region)
      const countryKey = normalizeSearchText(countryLabel || rawValue)
      if (!countryKey) return
      if (!countryNodes.has(countryKey)) {
        countryNodes.set(countryKey, {
          label: countryLabel || rawValue,
          value: `country:${countryKey}`,
          region: '',
          searchText: uniqueValues([countryLabel, region.country, rawValue]).join(' '),
          children: [],
        })
      }
      const parent = countryNodes.get(countryKey)
      parent.searchText = uniqueValues([parent.searchText, rawValue, region.code, region.country]).join(' ')
      parent.children.push({
        label: cityLabel || rawValue,
        value: rawValue,
        region: rawValue,
        searchText: uniqueValues([
          countryLabel,
          cityLabel,
          rawValue,
          region.code,
          region.country,
          region.city,
          translateLocationPath(rawValue),
        ]).join(' '),
      })
    })
  return [...countryNodes.values()]
    .map((node) => ({
      ...node,
      children: node.children
        .sort((left, right) => String(left.label || '').localeCompare(String(right.label || ''), 'zh-Hans-CN'))
        .map((child) => ({ ...child, children: undefined })),
    }))
    .sort((left, right) => String(left.label || '').localeCompare(String(right.label || ''), 'zh-Hans-CN'))
}

function regionNameParts(region = {}) {
  const nameParts = fieldText(region.name)
    .split('/')
    .map((item) => item.trim())
    .filter(Boolean)
  return {
    country: fieldText(region.country) || nameParts[0] || '',
    city: fieldText(region.city) || nameParts.slice(1).join(' / ') || '',
  }
}

function regionCountryLabel(region = {}) {
  const { country } = regionNameParts(region)
  return translateCountry(country) || translateLocationPath(country) || country
}

function regionCityLabel(region = {}) {
  const { city } = regionNameParts(region)
  if (!city) return translateLocationPath(fieldText(region.name)) || fieldText(region.name)
  return translateLocationPath(city) || translateCity(city) || city
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
      if (!payload.category_id) return window.$message?.warning('请选择产品分类')
      if (!payload.region) return window.$message?.warning('请选择地区')
      if (payload.id) await api.productCenterApi.updateProduct(payload.id, payload)
      else await api.productCenterApi.createProduct(payload)
    } else if (props.mode === 'specs') {
      payload.category_ids = attributeCategoryIds(payload)
      payload.category_id = payload.category_ids[0] || null
      if (!payload.name || !payload.code || !payload.category_ids.length) return window.$message?.warning('请填写属性名称、编码和适用分类')
      if (payload.id) await api.productCenterApi.updateAttribute(payload.id, payload)
      else await api.productCenterApi.createAttribute(payload)
    } else if (props.mode === 'configs') {
      const configLines = (payload.configs || []).filter((line) => line.attribute_id)
      if (!payload.product_id || !configLines.length) return window.$message?.warning('请选择产品并至少添加一个规格属性')
      const ids = configLines.map((line) => line.attribute_id)
      if (new Set(ids).size !== ids.length) return window.$message?.warning('同一个规格中不能重复选择相同属性')
      payload.configs = configLines.map((line, index) => {
        normalizeConfigLineValues(line)
        return {
          attribute_id: line.attribute_id,
          order: index,
          default_value: serializeConfigValue(line.default_value),
          value_range: '',
          required: Boolean(line.required),
        }
      })
      if (payload.source_key || payload.config_ids?.length) await api.productCenterApi.updateSpecConfigGroup(payload)
      else await api.productCenterApi.createSpecConfig(payload)
    } else if (props.mode === 'pricing') {
      if (!payload.product_id) return window.$message?.warning('请选择产品')
      const isCloudProduct = isPricingCloudProduct.value
      const isPhysicalServerProduct = isPricingPhysicalServerProduct.value
      if (isCloudProduct) {
        payload.spec_config_key = null
        payload.spec_config_name = ''
        const cloudVmKeys = Array.isArray(payload.cloud_vm_key) ? payload.cloud_vm_key : [payload.cloud_vm_key]
        if (!cloudVmKeys.filter(Boolean).length) return window.$message?.warning('请选择当前产品地区的云主机')
        if (!payload.id) payload.cloud_vm_keys = cloudVmKeys
      } else if (isPhysicalServerProduct) {
        payload.spec_config_key = null
        payload.spec_config_name = ''
        if (!payload.physical_device_id) return window.$message?.warning('请选择当前产品地区使用中的物理服务器')
      } else if (!payload.spec_config_key) {
        return window.$message?.warning('请选择规格配置')
      }
      payload.price_type = 'customer'
      if (!payload.customer_id) {
        return window.$message?.warning('请选择客户')
      }
      const specConfig = getSpecConfigOption(payload.spec_config_key)
      if (specConfig) {
        payload.product_id = specConfig.product_id
        payload.spec_config_name = specConfig.spec_name
        payload.billing_mode = specConfig.billing_mode || payload.billing_mode
      }
      delete payload.min_amount
      delete payload.tier_rules
      delete payload.bandwidth_rule
      const res = payload.id
        ? await api.productCenterApi.updatePrice(payload.id, payload)
        : await api.productCenterApi.createPrice(payload)
      if (res?.code && res.code !== 200) {
        window.$message?.warning(res.msg || '价格保存失败')
        return
      }
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

async function copyVmCredentials() {
  const data = credentialModal.data
  const text = `虚拟机名称: ${data.vm_name}\n初始密码: ${data.password}\nIP 地址: ${data.ip || '-'}\n所在 PVE: ${data.remote || '-'}`
  try {
    await navigator.clipboard.writeText(text)
    window.$message?.success('登录信息已复制')
  } catch {
    window.$message?.error('复制失败，请手动复制')
  }
}

async function deleteRow(row) {
  if (props.mode === 'products') await api.productCenterApi.deleteProduct(row.id)
  else if (props.mode === 'specs') await api.productCenterApi.deleteAttribute(row.id)
  else if (props.mode === 'configs') {
    if (row.auto_sync) return
    await api.productCenterApi.deleteSpecConfigGroup({ product_id: row.product_id, source_key: row.source_key, config_ids: row.config_ids || [] })
  }
  else if (props.mode === 'pricing') await api.productCenterApi.deletePrice(row.id)
  else if (props.mode === 'price-history') await api.productCenterApi.deletePriceHistory(row.id)
  else await api.productCenterApi.deleteTemplate(row.id)
  window.$message?.success('删除成功')
  await refreshAll()
}

watch(() => props.mode, () => {
  resetQuery()
})

watch(() => editor.form.category_id, () => {
  if (editorInitializing.value) return
  applyProductBillingDefault()
})

watch(() => editor.form.product_id, () => {
  if (editorInitializing.value) return
  ensureConfigAttributeFitsProduct()
})

watch(() => editor.form.attribute_id, () => {
  if (editorInitializing.value || props.mode !== 'configs') return
  normalizeConfigEditorValues(true)
})

onMounted(refreshAll)
</script>

<style scoped>
:global(.n-base-select-option.customer-select-option .n-base-select-option__content) {
  display: flex;
  width: 100%;
}

:global(.n-base-select-option.customer-select-option .n-base-select-option__content > span) {
  flex: 1 1 auto;
  min-width: 0;
}

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
  display: flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin: 16px 0;
}
.filter-controls {
  display: grid;
  flex: 1;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px;
  min-width: 0;
  max-width: 760px;
}
.filter-actions {
  display: inline-flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
}
.filter-action-button {
  min-width: 92px;
  height: 34px;
  font-weight: 600;
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
.modal-footer {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.table-actions {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  white-space: nowrap;
}
.table-action-item {
  display: inline-flex;
}
.pricing-table-actions {
  gap: 10px;
}
:deep(.pricing-table-actions) {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  white-space: nowrap;
}

.category-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 8px;
  padding: 3px 0;
}
.config-attribute-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 5px 0;
}
.config-attribute-tag {
  display: inline-flex;
  max-width: 100%;
  margin-right: 8px;
  margin-bottom: 6px;
}
.spec-config-lines {
  display: flex;
  width: 100%;
  flex-direction: column;
  gap: 12px;
}
.spec-config-line {
  padding: 14px;
  border: 1px solid #e7edf4;
  border-radius: 8px;
  background: #f8fafc;
}
.spec-config-line-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  color: #26364f;
}
.spec-config-line-grid {
  display: grid;
  grid-template-columns: minmax(240px, 1.2fr) minmax(220px, 1fr) 120px;
  gap: 10px 12px;
  align-items: center;
}
.spec-config-line-grid > * {
  min-width: 0;
}
.spec-config-required {
  display: inline-flex;
  align-items: center;
  justify-content: flex-start;
  gap: 8px;
  min-width: 0;
  white-space: nowrap;
  color: #607089;
}
.spec-config-required :deep(.n-switch) {
  flex-shrink: 0;
}
@media (max-width: 1280px) {
  .spec-config-line-grid {
    grid-template-columns: 1fr;
  }
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
.price-amount-field {
  width: 100%;
}
.cloud-price-specs {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  width: 100%;
  gap: 12px;
}
.cloud-price-spec-item {
  display: block;
  min-width: 0;
  padding: 10px;
  border: 1px solid #e4e9f1;
  border-radius: 8px;
  background: #f8fafc;
}
.cloud-price-spec-item > span {
  display: block;
  margin-bottom: 6px;
  color: #64748b;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}
.cloud-price-spec-item :deep(.n-input-number .n-input) {
  background: #fff;
}
.dhcp-price-field {
  width: 100%;
}
.dhcp-pool-hint {
  margin-top: 8px;
  color: #64748b;
  font-size: 12px;
  line-height: 1.6;
}
.cloud-create-hint {
  width: 100%;
  padding: 9px 12px;
  border: 1px solid #d9e8ff;
  border-radius: 8px;
  background: #f4f8ff;
  color: #53709b;
  font-size: 12px;
  line-height: 1.6;
}
.vm-credential-note {
  margin: 0 0 14px;
  color: #9a6700;
  font-size: 13px;
}
.vm-credential-list {
  overflow: hidden;
  border: 1px solid #e4e9f1;
  border-radius: 8px;
}
.vm-credential-row {
  display: grid;
  grid-template-columns: 108px minmax(0, 1fr);
  min-height: 42px;
  border-bottom: 1px solid #e4e9f1;
}
.vm-credential-row:last-child {
  border-bottom: 0;
}
.vm-credential-row > span {
  display: flex;
  align-items: center;
  padding: 0 12px;
  background: #f8fafc;
  color: #64748b;
  font-size: 12px;
}
.vm-credential-row code {
  display: flex;
  align-items: center;
  overflow-wrap: anywhere;
  padding: 8px 12px;
  color: #1e293b;
  font-size: 13px;
}
.price-amount-field :deep(.n-input-number) {
  flex: 1;
}
.price-currency-select {
  width: 96px !important;
  flex: 0 0 96px;
}
.price-amount-field :deep(.n-input-number .n-input) {
  border-top-right-radius: 0;
  border-bottom-right-radius: 0;
}
.price-currency-select :deep(.n-base-selection) {
  border-top-left-radius: 0;
  border-bottom-left-radius: 0;
}
.modal-footer {
  width: 100%;
  justify-content: flex-end;
}


:deep(.price-notification-modal) {
  width: 560px;
  max-width: calc(100vw - 24px);
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
    align-items: stretch;
    flex-direction: column;
  }
  .filter-controls {
    max-width: none;
    grid-template-columns: 1fr;
  }
  .filter-actions {
    justify-content: flex-end;
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
  .price-amount-field {
    display: flex;
  }
  .cloud-price-specs {
    grid-template-columns: 1fr;
  }
  .price-currency-select {
    width: 84px !important;
    flex-basis: 84px;
  }
}
</style>
