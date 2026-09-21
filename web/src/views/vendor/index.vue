<template>
  <div class="vendor-page">
    <VendorTable
      :vendors="vendorList"
      :companies="contractCompanyList"
      :loading="loading"
      :error="loadError"
      :pagination="pagination"
      @query-change="handleQueryChange"
      @page-change="handlePageChange"
      @page-size-change="handlePageSizeChange"
      @select="handleSelect"
      @add="openAdd"
      @edit="openEdit"
      @delete="handleDelete"
      @refresh="fetchVendors"
    />
    <NDrawer v-model:show="detailVisible" :width="'min(1100px, 100vw)'">
      <NDrawerContent title="供应商详情" closable>
        <VendorDetail
          :vendor="currentVendor"
          :edit-loading="editLoading"
          :delete-loading="deleteLoading"
          @edit="openEdit"
          @delete="handleDelete"
        />
      </NDrawerContent>
    </NDrawer>

    <NModal
      :show="modalVisible"
      preset="card"
      :title="modalTitle"
      class="vendor-modal"
      style="width: min(760px, calc(100vw - 32px))"
      :mask-closable="false"
      :closable="!modalLoading && !attachmentBusy"
      :close-on-esc="!modalLoading && !attachmentBusy"
      @update:show="handleModalVisibility"
    >
      <div class="vendor-modal__intro">
        <span class="vendor-modal__icon"
          ><TheIcon icon="mdi:office-building-outline" :size="24"
        /></span>
        <div>
          <strong>{{ modalForm.id ? '维护供应商档案' : '创建供应商档案' }}</strong>
          <p>统一维护供应商主体、签约归属、所属地区和内部备注。</p>
        </div>
      </div>
      <NForm
        ref="modalFormRef"
        label-placement="top"
        class="vendor-form"
        :model="modalForm"
        :rules="modalRules"
        :disabled="modalLoading || attachmentBusy"
      >
        <section class="form-section">
          <div class="form-section__head">
            <span>基本信息</span><small>供应商识别与主体资料</small>
          </div>
          <div class="form-grid">
            <NFormItem label="供应商简称" path="name" required>
              <NInput
                v-model:value="modalForm.name"
                :maxlength="100"
                clearable
                placeholder="请输入供应商简称"
              />
            </NFormItem>
            <NFormItem label="供应商全称" path="legal_name">
              <NInput
                v-model:value="modalForm.legal_name"
                :maxlength="200"
                clearable
                placeholder="请输入工商或证件主体名称"
              />
            </NFormItem>
            <NFormItem label="联系地址" path="address" class="form-grid__full">
              <NInput
                v-model:value="modalForm.address"
                :maxlength="255"
                clearable
                placeholder="请输入供应商联系地址"
              />
            </NFormItem>
          </div>
        </section>
        <section class="form-section">
          <div class="form-section__head">
            <span>供应商属性</span><small>签约归属与所属地区</small>
          </div>
          <NAlert v-if="legacyEntityUnmatched" type="warning" class="mb-12">
            原签约主体未能唯一匹配客户管理，请重新选择签约主体后保存。
          </NAlert>
          <div class="form-grid">
            <NFormItem label="签约主体" path="signing_entity_id" required>
              <NSelect
                v-model:value="modalForm.signing_entity_id"
                clearable
                filterable
                :options="contractCompanyOptions"
                :loading="entitiesLoading"
                placeholder="请选择签约主体"
                @update:value="handleSigningEntityChange"
              />
            </NFormItem>
            <NFormItem label="供应商编号" path="code">
              <NInput
                v-model:value="modalForm.code"
                :maxlength="50"
                clearable
                placeholder="选择签约主体后自动生成，可手动修改"
                ><template v-if="codeLoading" #suffix><NSpin :size="16" /></template
              ></NInput>
            </NFormItem>
            <NFormItem label="所属地区" path="country">
              <NCascader
                v-model:value="modalForm.country"
                clearable
                filterable
                check-strategy="child"
                :options="vendorRegionOptions"
                :filter="customerRegionFilter"
                :disabled="regionsLoading"
                :placeholder="regionsLoading ? '正在加载所属地区' : '请选择所属地区'"
              />
            </NFormItem>
            <NFormItem label="启用状态" path="status">
              <NSwitch v-model:value="modalForm.status" />
            </NFormItem>
          </div>
        </section>
        <section class="form-section">
          <div class="form-section__head"><span>备注</span><small>内部说明与补充资料</small></div>
          <NFormItem label="备注" path="remark">
            <NInput
              v-model:value="modalForm.remark"
              :maxlength="500"
              placeholder="内部备注、风险提示、历史沟通记录等"
              type="textarea"
              :autosize="{ minRows: 2, maxRows: 4 }"
            />
          </NFormItem>
        </section>
        <section class="form-section">
          <div class="form-section__head"><span>附件</span><small>供应商证明与相关文档</small></div>
          <NFormItem label="附件">
            <VendorAttachments
              v-model="attachments"
              :vendor-id="modalForm.id"
              :disabled="modalLoading"
              @busy="attachmentBusy = $event"
            />
          </NFormItem>
        </section>
      </NForm>
      <template #footer>
        <div class="modal-footer">
          <CButton
            show-cancel
            show-save
            :disabled="modalLoading || attachmentBusy || codeLoading"
            :save-loading="modalLoading"
            @cancel="cancelModal"
            @save="handleSave"
          />
        </div>
      </template>
    </NModal>
  </div>
</template>

<script setup>
import VendorTable from './components/VendorTable.vue'
import VendorAttachments from './components/VendorAttachments.vue'
import CButton from '@/components/public/CButton.vue'
import VendorDetail from './components/VendorDetail.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import api from '@/api'
import { buildCustomerRegionOptions, customerRegionFilter } from '@/utils/customer-region'

const vendorList = ref([])
const pagination = reactive({ page: 1, pageSize: 20, itemCount: 0, pageSizes: [20, 50, 100] })
const vendorQuery = reactive({ keyword: '', signing_entity_id: null, status: null })
let vendorRequestId = 0

function handleQueryChange(query) {
  Object.assign(vendorQuery, query)
  pagination.page = 1
  fetchVendors()
}

function handlePageChange(page) {
  pagination.page = page
  fetchVendors()
}

function handlePageSizeChange(size) {
  pagination.pageSize = size
  pagination.page = 1
  fetchVendors()
}
const attachments = ref([])
const attachmentBusy = ref(false)
const loading = ref(false)
const loadError = ref('')
const detailVisible = ref(false)
const contractCompanyList = ref([])
const currentVendor = ref(null)
const activeId = ref(null)
const legacyEntityUnmatched = ref(false)
const savedEntity = ref(null)
const codeLoading = ref(false)
const entitiesLoading = ref(false)
const networkRegions = ref([])
const regionsLoading = ref(false)
let codeRequestId = 0

const contractCompanyOptions = computed(() => {
  const options = (contractCompanyList.value || []).map((c) => ({
    label: c.name,
    value: c.id,
  }))
  if (savedEntity.value?.id && !options.some((option) => option.value === savedEntity.value.id)) {
    options.push({
      label: `${savedEntity.value.name}（已停用）`,
      value: savedEntity.value.id,
      disabled: true,
    })
  }
  return options
})

const modalVisible = ref(false)
const modalLoading = ref(false)
const editLoading = ref(false)
const deleteLoading = ref(false)
const modalAction = ref('add') // add | edit
const modalTitle = ref('新增供应商')
const modalFormRef = ref(null)
const modalForm = reactive({
  id: null,
  name: '',
  legal_name: '',
  code: '',
  country: '',
  address: '',
  signing_entity_id: null,
  remark: '',
  status: true,
})

const vendorRegionOptions = computed(() =>
  buildCustomerRegionOptions(networkRegions.value, modalForm.country)
)

async function fetchRegions() {
  if (regionsLoading.value) return
  regionsLoading.value = true
  try {
    const response = await api.assetApi.regions({ page: 1, page_size: 1000, status: true })
    networkRegions.value = Array.isArray(response?.data) ? response.data : []
  } catch {
    window.$message?.error('所属地区加载失败，请重新打开弹窗重试')
  } finally {
    regionsLoading.value = false
  }
}

const modalRules = {
  country: [{ max: 50, message: '所属地区最长为 50 个字符', trigger: 'change' }],
  name: [
    {
      required: true,
      validator: (_rule, value) => Boolean(value?.trim()),
      message: '请输入供应商简称',
      trigger: ['blur', 'input'],
    },
  ],
  signing_entity_id: [
    { required: true, type: 'number', message: '请选择签约主体', trigger: 'change' },
  ],
}

async function fetchContractCompanies() {
  entitiesLoading.value = true
  try {
    const res = await api.customerCenterApi.signingEntities()
    contractCompanyList.value = res?.data || []
  } finally {
    entitiesLoading.value = false
  }
}

async function handleSigningEntityChange(signingEntityId) {
  if (modalForm.id) return
  const requestId = ++codeRequestId
  codeLoading.value = false
  if (!signingEntityId) {
    modalForm.code = ''
    return
  }
  const previousCode = modalForm.code
  codeLoading.value = true
  try {
    const response = await api.nextVendorCode(signingEntityId)
    if (
      requestId === codeRequestId &&
      modalVisible.value &&
      modalForm.signing_entity_id === signingEntityId &&
      modalForm.code === previousCode
    ) {
      modalForm.code = response?.data?.code || ''
    }
  } catch {
    if (requestId === codeRequestId && modalVisible.value) {
      if (modalForm.code === previousCode) modalForm.code = ''
      window.$message?.warning('编号预览获取失败，可手动填写或留空在保存时生成')
    }
  } finally {
    if (requestId === codeRequestId) codeLoading.value = false
  }
}

function handleModalVisibility(show) {
  if (!show) cancelModal()
}

async function fetchVendors() {
  const requestId = ++vendorRequestId
  loading.value = true
  loadError.value = ''
  try {
    const res = await api.getVendorList({
      page: pagination.page,
      page_size: pagination.pageSize,
      keyword: vendorQuery.keyword,
      signing_entity_id: vendorQuery.signing_entity_id || undefined,
      status: vendorQuery.status === null ? undefined : Boolean(vendorQuery.status),
    })
    if (requestId !== vendorRequestId) return
    pagination.itemCount = res?.total || 0
    const lastPage = Math.max(1, Math.ceil(pagination.itemCount / pagination.pageSize))
    if (pagination.page > lastPage) {
      pagination.page = lastPage
      return await fetchVendors()
    }
    vendorList.value = res?.data || []

    // 维持当前选中
    if (activeId.value) {
      const found = vendorList.value.find((v) => v.id === activeId.value)
      if (found) {
        currentVendor.value = found
        return
      }
    }
    currentVendor.value = vendorList.value[0] || null
    activeId.value = currentVendor.value?.id ?? null
  } catch {
    if (requestId === vendorRequestId) {
      vendorList.value = []
      loadError.value = '获取供应商失败，请点击刷新重试'
    }
  } finally {
    if (requestId === vendorRequestId) loading.value = false
  }
}

onMounted(async () => {
  try {
    await Promise.all([fetchVendors(), fetchContractCompanies()])
  } catch (e) {
    window.$message?.error?.('获取数据失败')
  }
})

const handleSelect = async (row) => {
  try {
    const response = await api.getVendorById({ vendor_id: row.id })
    currentVendor.value = response.data
  } catch {
    return
  }
  detailVisible.value = true
  activeId.value = row?.id ?? null
}

function resetModalForm() {
  codeRequestId += 1
  codeLoading.value = false
  legacyEntityUnmatched.value = false
  savedEntity.value = null
  attachments.value = []
  modalForm.id = null
  modalForm.name = ''
  modalForm.legal_name = ''
  modalForm.code = ''
  modalForm.country = ''
  modalForm.address = ''
  modalForm.signing_entity_id = null
  modalForm.remark = ''
  modalForm.status = true
}

function openAdd() {
  modalAction.value = 'add'
  modalTitle.value = '新增供应商'
  resetModalForm()
  modalVisible.value = true
  fetchRegions()
  fetchContractCompanies().catch(() =>
    window.$message?.error('签约主体加载失败，请重新打开弹窗重试')
  )
}

async function openEdit(vendor) {
  if (!vendor?.id) return
  try {
    const response = await api.getVendorById({ vendor_id: vendor.id })
    vendor = response.data
  } catch {
    return
  }
  detailVisible.value = false
  codeRequestId += 1
  codeLoading.value = false
  legacyEntityUnmatched.value = Boolean(vendor.legacy_signing_entity_unmatched)
  savedEntity.value = { id: vendor.signing_entity_id, name: vendor.signing_entity_name }
  attachments.value = vendor.attachments || []
  modalAction.value = 'edit'
  modalTitle.value = '编辑供应商'
  modalForm.id = vendor.id
  modalForm.name = vendor.name || ''
  modalForm.legal_name = vendor.legal_name || ''
  modalForm.code = vendor.code || ''
  modalForm.country = vendor.country || ''
  modalForm.address = vendor.address || ''
  modalForm.signing_entity_id = vendor.signing_entity_id ?? null
  modalForm.remark = vendor.remark || ''
  modalForm.status = !!vendor.status
  fetchRegions()
  modalVisible.value = true
}

async function handleSave() {
  if (modalLoading.value || attachmentBusy.value || codeLoading.value) return
  if (legacyEntityUnmatched.value && !modalForm.signing_entity_id) {
    window.$message?.error('请选择客户管理中的签约主体')
    return
  }
  try {
    modalLoading.value = true
    await modalFormRef.value?.validate?.()
    const payload = {
      ...modalForm,
      name: modalForm.name.trim(),
      legal_name: modalForm.legal_name.trim(),
      code: modalForm.code.trim(),
      country: modalForm.country || '',
      attachment_ids: attachments.value.map((item) => item.id),
    }
    delete payload.id
    // 如果code为空字符串，转为null让后端自动生成
    if (!payload.code) {
      delete payload.code
    }
    if (modalAction.value === 'add') {
      const res = await api.createVendor(payload)
      window.$message?.success?.('新增成功')
      if (res?.data?.id) activeId.value = res.data.id
    } else {
      const res = await api.updateVendor({ ...payload, id: modalForm.id })
      window.$message?.success?.('更新成功')
      if (res?.data?.id) activeId.value = res.data.id
    }
    modalVisible.value = false
    await fetchVendors()
  } catch (e) {
    if (e?.message) window.$message?.error?.(e.message)
  } finally {
    modalLoading.value = false
  }
}

async function handleDelete(vendor) {
  if (!vendor?.id) return
  window.$dialog?.confirm?.({
    title: '删除供应商',
    content: `确定删除「${vendor.name || ''}」吗？`,
    confirm: async () => {
      try {
        deleteLoading.value = true
        await api.deleteVendor({ vendor_id: vendor.id })
        window.$message?.success?.('删除成功')
        if (activeId.value === vendor.id) {
          detailVisible.value = false
          currentVendor.value = null
          activeId.value = null
        }
        await fetchVendors()
      } catch (e) {
        window.$message?.error?.('删除失败')
      } finally {
        deleteLoading.value = false
      }
    },
  })
}
async function cancelModal() {
  if (modalLoading.value || attachmentBusy.value) return
  if (modalAction.value === 'add' && attachments.value.length) {
    attachmentBusy.value = true
    try {
      for (const item of [...attachments.value]) {
        await api.deleteVendorAttachment(item.id)
        attachments.value = attachments.value.filter((value) => value.id !== item.id)
      }
    } catch {
      window.$message?.error('未保存附件清理失败，请重试取消或手动删除附件')
      return
    } finally {
      attachmentBusy.value = false
    }
  }
  modalVisible.value = false
  codeRequestId += 1
  codeLoading.value = false
}
</script>

<style scoped>
.vendor-page {
  padding: 16px;
  min-width: 0;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
}
.vendor-modal__intro {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  padding: 14px 16px;
  border: 1px solid #dceafe;
  border-radius: 8px;
  background: linear-gradient(135deg, #f8fbff 0%, #eef8f5 100%);
}
.vendor-modal__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  flex: 0 0 44px;
  border-radius: 8px;
  color: #0f766e;
  background: #dff7f1;
}
.vendor-modal__intro strong {
  display: block;
  color: #0f172a;
  font-size: 16px;
}
.vendor-modal__intro p {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 13px;
}
.vendor-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.form-section {
  padding: 14px 16px 2px;
  border: 1px solid #e8edf3;
  border-radius: 8px;
  background: #fff;
}
.form-section__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid #edf2f7;
}
.form-section__head span {
  color: #0f172a;
  font-size: 15px;
  font-weight: 700;
}
.form-section__head small {
  color: #94a3b8;
  font-size: 12px;
}
.vendor-modal :deep(.n-card-header) {
  padding: 20px 24px 12px;
}
.vendor-modal :deep(.n-card__content) {
  padding: 0 24px 8px;
  max-height: min(72vh, 680px);
  overflow: auto;
}
.vendor-modal :deep(.n-card__footer) {
  padding: 14px 24px 20px;
  border-top: 1px solid #e8edf3;
  background: #fbfdff;
}
.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  column-gap: 16px;
  row-gap: 2px;
}
.form-grid__full {
  grid-column: 1 / -1;
}
@media (max-width: 720px) {
  .form-grid {
    grid-template-columns: minmax(0, 1fr);
  }
  .vendor-modal__intro {
    align-items: flex-start;
  }
  .form-section {
    padding: 12px 12px 0;
  }
  .form-section__head {
    align-items: flex-start;
    flex-direction: column;
    gap: 2px;
  }
}
</style>
