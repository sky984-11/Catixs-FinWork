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
      <VendorDetail :vendor="currentVendor" @edit="openEdit" @delete="handleDelete" />
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
        <NFormItem label="国家/地区" path="country">
          <NInput v-model:value="modalForm.country" clearable placeholder="如：中国/香港/台湾" />
        </NFormItem>
        <NFormItem label="编号" path="code">
          <NInput v-model:value="modalForm.code" clearable placeholder="如：VU00024" />
        </NFormItem>
        <NFormItem label="地址" path="address">
          <NInput
            v-model:value="modalForm.address"
            type="textarea"
            :autosize="{ minRows: 2, maxRows: 4 }"
          />
        </NFormItem>
        <NFormItem label="NOC邮箱" path="noc_email">
          <NInput v-model:value="modalForm.noc_email" clearable placeholder="请输入邮箱" />
        </NFormItem>
        <NFormItem label="NOC电话" path="noc_phone">
          <NInput v-model:value="modalForm.noc_phone" clearable placeholder="请输入电话" />
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
import { onMounted, reactive, ref } from 'vue'
import VendorList from './components/VendorList.vue'
import VendorDetail from './components/VendorDetail.vue'
import CrudModal from '@/components/table/CrudModal.vue'
import api from '@/api'

const vendorList = ref([])
const currentVendor = ref(null)
const activeId = ref(null)

const modalVisible = ref(false)
const modalLoading = ref(false)
const modalAction = ref('add') // add | edit
const modalTitle = ref('新增供应商')
const modalFormRef = ref(null)
const modalForm = reactive({
  id: null,
  name: '',
  country: '',
  code: '',
  address: '',
  noc_email: '',
  noc_phone: '',
  remark: '',
  status: true,
})

const modalRules = {
  name: [{ required: true, message: '请输入供应商名称', trigger: ['blur', 'input'] }],
  code: [{ required: true, message: '请输入供应商编号', trigger: ['blur', 'input'] }],
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
    await fetchVendors()
  } catch (e) {
    window.$message?.error?.('获取供应商列表失败')
  }
})

const handleSelect = (row) => {
  currentVendor.value = row
  activeId.value = row?.id ?? null
}

function resetModalForm() {
  modalForm.id = null
  modalForm.name = ''
  modalForm.country = ''
  modalForm.code = ''
  modalForm.address = ''
  modalForm.noc_email = ''
  modalForm.noc_phone = ''
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
  modalForm.country = vendor.country || ''
  modalForm.code = vendor.code || ''
  modalForm.address = vendor.address || ''
  modalForm.noc_email = vendor.noc_email || ''
  modalForm.noc_phone = vendor.noc_phone || ''
  modalForm.remark = vendor.remark || ''
  modalForm.status = !!vendor.status
  modalVisible.value = true
}

async function handleSave() {
  try {
    modalLoading.value = true
    await modalFormRef.value?.validate?.()
    if (modalAction.value === 'add') {
      const payload = { ...modalForm }
      delete payload.id
      const res = await api.createVendor(payload)
      window.$message?.success?.('新增成功')
      if (res?.data?.id) activeId.value = res.data.id
    } else {
      const res = await api.updateVendor({ ...modalForm })
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
        await api.deleteVendor({ vendor_id: vendor.id })
        window.$message?.success?.('删除成功')
        if (activeId.value === vendor.id) {
          currentVendor.value = null
          activeId.value = null
        }
        await fetchVendors()
      } catch (e) {
        window.$message?.error?.('删除失败')
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
