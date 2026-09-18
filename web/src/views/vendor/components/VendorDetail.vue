<template>
  <div v-if="vendor">
    <!-- 顶部卡片 -->
    <n-card class="header-card" :bordered="false">
      <div class="header">
        <div>
          <div class="title">
            {{ vendor.name }}
            <n-tag round :type="vendor.status ? 'success' : 'error'" size="small">
              {{ vendor.status ? '启用' : '禁用' }}
            </n-tag>
          </div>

          <div class="meta">
            <n-descriptions label-placement="left" title="" size="large" :column="2" bordered>
              <n-descriptions-item>
                <template #label> 编号 </template>
                {{ vendor.code }}
              </n-descriptions-item>
              <n-descriptions-item v-if="vendor.legal_name" label="供应商全称">{{
                vendor.legal_name
              }}</n-descriptions-item>
              <n-descriptions-item v-if="vendor.address" label="地址">
                {{ vendor.address }}
              </n-descriptions-item>
              <n-descriptions-item v-if="vendor.noc_email" label="NOC邮箱">
                {{ vendor.noc_email }}
              </n-descriptions-item>
              <n-descriptions-item v-if="vendor.noc_phone" label="NOC电话">
                {{ vendor.noc_phone }}
              </n-descriptions-item>
              <n-descriptions-item v-if="vendor.company_email" label="公司邮箱">
                {{ vendor.company_email }}
              </n-descriptions-item>
              <n-descriptions-item v-if="vendor.company_phone" label="公司电话">
                {{ vendor.company_phone }}
              </n-descriptions-item>
              <n-descriptions-item v-if="vendor.remark" label="备注">
                {{ vendor.remark }}
              </n-descriptions-item>
              <n-descriptions-item v-if="vendor.country" label="所属地区">
                {{ vendor.country }}
              </n-descriptions-item>
              <n-descriptions-item
                v-for="field in contactFields"
                :key="field.key"
                :label="field.label"
                :span="2"
              >
                <div class="contact-text">{{ vendor[field.key] || '-' }}</div>
              </n-descriptions-item>
            </n-descriptions>
          </div>
        </div>

        <n-space>
          <CButton
            show-delete
            show-edit
            :disabled="!vendor"
            :edit-loading="editLoading"
            :delete-loading="deleteLoading"
            @edit="emit('edit', vendor)"
            @delete="emit('delete', vendor)"
          />
        </n-space>
      </div>
    </n-card>

    <!-- Tabs -->
    <n-card :bordered="false" class="mt">
      <n-tabs type="line" animated>
        <n-tab-pane name="contacts" tab="供应商联系人">
          <n-empty v-if="!vendor.contacts?.length" description="暂无供应商联系人" />
          <n-descriptions
            v-for="contact in vendor.contacts || []"
            :key="contact.id"
            :title="contact.name || contact.email"
            :column="2"
            bordered
            class="mb-16"
          >
            <n-descriptions-item label="邮箱">{{ contact.email || '-' }}</n-descriptions-item>
            <n-descriptions-item label="电话">{{ contact.phone || '-' }}</n-descriptions-item>
            <n-descriptions-item label="地址" :span="2">{{
              contact.address || '-'
            }}</n-descriptions-item>
            <n-descriptions-item label="备注" :span="2"
              ><div class="contact-text">{{ contact.remark || '-' }}</div></n-descriptions-item
            >
          </n-descriptions>
        </n-tab-pane>
        <n-tab-pane name="attachments" tab="供应商附件">
          <VendorAttachments :model-value="vendor.attachments || []" readonly />
        </n-tab-pane>
        <n-tab-pane name="bank" tab="银行账户">
          <BankCard
            :company-id="vendor.id"
            :company-name="vendor.name"
            :company-tax-no="vendor.tax_no"
          />
        </n-tab-pane>

        <n-tab-pane name="invoice" tab="账单(PDF)">
          <InvoiceTable :company-id="vendor.id" />
        </n-tab-pane>
      </n-tabs>
    </n-card>
  </div>

  <div v-else class="empty">请选择供应商</div>
</template>

<script setup>
import BankCard from './BankCard.vue'
import CButton from '@/components/public/CButton.vue'
import InvoiceTable from './InvoiceTable.vue'
import VendorAttachments from './VendorAttachments.vue'

const contactFields = [
  { key: 'sales_contact', label: '销售联系人' },
  { key: 'billing_contact', label: '账单联系人' },
  { key: 'noc_contact', label: 'NOC 联系信息' },
]

defineProps({
  vendor: {
    type: Object,
    default: null,
  },
  editLoading: {
    type: Boolean,
    default: false,
  },
  deleteLoading: {
    type: Boolean,
    default: false,
  },
})
const emit = defineEmits(['edit', 'delete'])
</script>

<style scoped>
.header {
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 16px;
}
.contact-text {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.title {
  font-size: 18px;
  font-weight: bold;
  display: flex;
  gap: 10px;
  align-items: center;
}

.meta {
  margin-top: 15px;
  line-height: 1.8;
}

.mt {
  margin-top: 16px;
}

.empty {
  text-align: center;
  margin-top: 120px;
  color: #999;
}
</style>
