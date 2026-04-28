<template>
  <div class="vendor-page">
    <div class="left-panel">
      <VendorList
        v-model:activeId="activeId"
        :vendor-list="vendorList"
        @select="handleSelect"
        @add="openAdd"
      />
    </div>

    <div class="right-panel">
      <VendorDetail
        :vendor="currentVendor"
        :edit-loading="editLoading"
        :delete-loading="deleteLoading"
        @edit="openEdit"
        @delete="handleDelete"
      />
    </div>

    <CrudModal
      v-model:visible="modalVisible"
      :title="modalTitle"
      :loading="modalLoading"
      @save="handleSave"
    >
      <NForm
        ref="modalFormRef"
        label-placement="left"
        label-align="left"
        :label-width="90"
        :model="modalForm"
        :rules="modalRules"
      >
        <NFormItem label="名称" path="name">
          <NInput v-model:value="modalForm.name" clearable placeholder="请输入供应商名称" />
        </NFormItem>
        <NFormItem label="签约主体" path="contract_company_id">
          <NSelect
            v-model:value="modalForm.contract_company_id"
            clearable
            filterable
            :options="contractCompanyOptions"
            placeholder="请选择签约主体公司"
          />
        </NFormItem>
        <NFormItem label="国家/地区" path="country">
          <NInput v-model:value="modalForm.country" clearable placeholder="如：中国/香港/台湾" />
        </NFormItem>
        <NFormItem label="地址" path="address">
          <NInput
            v-model:value="modalForm.address"
            type="textarea"
            :autosize="{ minRows: 2, maxRows: 4 }"
          />
        </NFormItem>
        <NFormItem label="公司邮箱" path="company_email">
          <NInput v-model:value="modalForm.company_email" clearable placeholder="请输入公司邮箱" />
        </NFormItem>
        <NFormItem label="公司电话" path="company_phone">
          <NInput v-model:value="modalForm.company_phone" clearable placeholder="请输入公司电话" />
        </NFormItem>
        <NFormItem label="NOC邮箱" path="noc_email">
          <NInput v-model:value="modalForm.noc_email" clearable placeholder="请输入NOC邮箱" />
        </NFormItem>
        <NFormItem label="NOC电话" path="noc_phone">
          <NInput v-model:value="modalForm.noc_phone" clearable placeholder="请输入NOC电话" />
        </NFormItem>
        <NFormItem label="注册号" path="registration_no">
          <NInput v-model:value="modalForm.registration_no" clearable placeholder="如：公司注册号" />
        </NFormItem>
        <NFormItem label="税号" path="tax_no">
          <NInput v-model:value="modalForm.tax_no" clearable placeholder="中国供应商可填写" />
        </NFormItem>
        <NFormItem label="备注" path="remark">
          <NInput
            v-model:value="modalForm.remark"
            type="textarea"
            :autosize="{ minRows: 2, maxRows: 4 }"
          />
        </NFormItem>
        <NFormItem label="启用" path="status">
          <NSwitch
            v-model:value="modalForm.status"
            :checked-value="true"
            :unchecked-value="false"
          />
        </NFormItem>
      </NForm>
    </CrudModal>
  </div>
</template>

<script setup>
import VendorList from './components/VendorList.vue'
import VendorDetail from './components/VendorDetail.vue'
import CrudModal from '@/components/table/CrudModal.vue'
import api from '@/api'

const vendorList = ref([])
const contractCompanyList = ref([])
const currentVendor = ref(null)
const activeId = ref(null)

const contractCompanyOptions = computed(() => {
  return (contractCompanyList.value || []).map((c) => ({
    label: c.name,
    value: c.id,
  }))
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
  code: '',
  country: '',
  address: '',
  company_email: '',
  company_phone: '',
  noc_email: '',
  noc_phone: '',
  registration_no: '',
  tax_no: '',
  contract_company_id: null,
  remark: '',
  status: true,
})

const modalRules = {
  name: [{ required: true, message: '请输入供应商名称', trigger: ['blur', 'input'] }],
  noc_email: [
    {
      trigger: ['blur'],
      validator: (rule, value, callback) => {
        const v = String(value || '').trim()
        if (!v) return callback()
        const re = /^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+)+$/
        if (!re.test(v)) return callback('邮箱格式错误')
        return callback()
      },
    },
  ],
  company_email: [
    {
      trigger: ['blur'],
      validator: (rule, value, callback) => {
        const v = String(value || '').trim()
        if (!v) return callback()
        const re = /^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+)+$/
        if (!re.test(v)) return callback('邮箱格式错误')
        return callback()
      },
    },
  ],
}

async function fetchContractCompanies() {
  const res = await api.getCompanyList({ page: 1, page_size: 9999, role: 0 })
  contractCompanyList.value = res?.data || []
}

async function fetchVendors() {
  const res = await api.getVendorList({ page: 1, page_size: 9999 })
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
}

onMounted(async () => {
  try {
    await Promise.all([fetchVendors(), fetchContractCompanies()])
  } catch (e) {
    window.$message?.error?.('获取数据失败')
  }
})

const handleSelect = (row) => {
  currentVendor.value = row
  activeId.value = row?.id ?? null
}

function resetModalForm() {
  modalForm.id = null
  modalForm.name = ''
  modalForm.code = ''
  modalForm.country = ''
  modalForm.address = ''
  modalForm.company_email = ''
  modalForm.company_phone = ''
  modalForm.noc_email = ''
  modalForm.noc_phone = ''
  modalForm.registration_no = ''
  modalForm.tax_no = ''
  modalForm.contract_company_id = null
  modalForm.remark = ''
  modalForm.status = true
}

function openAdd() {
  modalAction.value = 'add'
  modalTitle.value = '新增供应商'
  resetModalForm()
  modalVisible.value = true
}

function openEdit(vendor) {
  if (!vendor?.id) return
  modalAction.value = 'edit'
  modalTitle.value = '编辑供应商'
  modalForm.id = vendor.id
  modalForm.name = vendor.name || ''
  modalForm.code = vendor.code || ''
  modalForm.country = vendor.country || ''
  modalForm.address = vendor.address || ''
  modalForm.company_email = vendor.company_email || ''
  modalForm.company_phone = vendor.company_phone || ''
  modalForm.noc_email = vendor.noc_email || ''
  modalForm.noc_phone = vendor.noc_phone || ''
  modalForm.registration_no = vendor.registration_no || ''
  modalForm.tax_no = vendor.tax_no || ''
  modalForm.contract_company_id = vendor.contract_company_id ?? null
  modalForm.remark = vendor.remark || ''
  modalForm.status = !!vendor.status
  modalVisible.value = true
}

async function handleSave() {
  try {
    modalLoading.value = true
    await modalFormRef.value?.validate?.()
    const payload = { ...modalForm }
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
      const res = await api.updateVendor({ ...modalForm, id: modalForm.id })
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
</script>

<style scoped>
.vendor-page {
  display: flex;
  height: 100%;
}

.left-panel {
  width: 320px;
  padding: 16px;
}

.right-panel {
  flex: 1;
  padding: 16px;
}
</style>
