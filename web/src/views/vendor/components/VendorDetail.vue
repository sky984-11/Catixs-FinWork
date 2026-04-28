<template>
  <div v-if="vendor">
    <!-- 顶部卡片 -->
    <n-card class="header-card" :bordered="false">
      <div class="header">
        <div>
          <div class="title">
            {{ vendor.name }}
            <n-tag round size="small" :type="vendor.status ? 'success' : 'error'">
              {{ vendor.status ? '启用' : '禁用' }}
            </n-tag>
          </div>

          <div class="meta">
            <n-descriptions label-placement="left" title="" size="large" :column="4" bordered>
              <n-descriptions-item>
                <template #label> 编号 </template>
                {{ vendor.code }}
              </n-descriptions-item>
              <n-descriptions-item v-if="vendor.address" label="地址"> {{ vendor.address }} </n-descriptions-item>
              <n-descriptions-item v-if="vendor.noc_email" label="NOC邮箱"> {{ vendor.noc_email }} </n-descriptions-item>
              <n-descriptions-item v-if="vendor.noc_phone" label="NOC电话"> {{ vendor.noc_phone }} </n-descriptions-item>
              <n-descriptions-item v-if="vendor.tax_no" label="税号"> {{ vendor.tax_no }} </n-descriptions-item>
              <n-descriptions-item v-if="vendor.remark" label="备注"> {{ vendor.remark }} </n-descriptions-item>
            </n-descriptions>
          </div>
        </div>

        <n-space>
          <CButton showEdit showDelete :disabled="!vendor" @edit="emit('edit', vendor)" @delete="emit('delete', vendor)" />
        </n-space>
      </div>
    </n-card>

    <!-- Tabs -->
    <n-card :bordered="false" class="mt">
      <n-tabs type="line" animated>
        <n-tab-pane name="bank" tab="银行账户">
          <BankCard :company-id="vendor.id" :company-name="vendor.name" :company-tax-no="vendor.tax_no" />
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

defineProps({
  vendor: {
    type: Object,
    default: null,
  },
})
const emit = defineEmits(['edit', 'delete'])
</script>

<style scoped>
.header {
  display: flex;
  justify-content: space-between;
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
