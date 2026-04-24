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
              <n-descriptions-item label="地址"> {{ vendor.address }} </n-descriptions-item>
              <n-descriptions-item label="NOC邮箱"> {{ vendor.noc_email }} </n-descriptions-item>
              <n-descriptions-item label="NOC电话"> {{ vendor.noc_phone }} </n-descriptions-item>
              <n-descriptions-item label="备注"> {{ vendor.remark }} </n-descriptions-item>
            </n-descriptions>
          </div>
        </div>

        <n-space>
          <n-button type="info" round secondary>
            <template #icon>
              <n-icon>
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  xmlns:xlink="http://www.w3.org/1999/xlink"
                  viewBox="0 0 24 24"
                >
                  <path opacity=".3" d="M5 6h14v2H5z" fill="currentColor"></path>
                  <path
                    d="M5 10h14v2h2V6c0-1.1-.9-2-2-2h-1V2h-2v2H8V2H6v2H5c-1.11 0-1.99.9-1.99 2L3 20a2 2 0 0 0 2 2h7v-2H5V10zm0-4h14v2H5V6zm17.84 10.28l-.71.71l-2.12-2.12l.71-.71a.996.996 0 0 1 1.41 0l.71.71c.39.39.39 1.02 0 1.41zm-3.54-.7l2.12 2.12l-5.3 5.3H14v-2.12l5.3-5.3z"
                    fill="currentColor"
                  ></path>
                </svg>
              </n-icon>
            </template>
            编辑</n-button
          >
          <n-button type="error" round secondary>
            <template #icon>
              <n-icon>
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  xmlns:xlink="http://www.w3.org/1999/xlink"
                  viewBox="0 0 20 20"
                >
                  <g fill="none">
                    <path
                      d="M7.5 4a2.5 2.5 0 0 1 5 0H17a.5.5 0 0 1 0 1h-.554l-.923 8h-1.007l.922-8H4.561l1.282 11.115a1 1 0 0 0 .994.885h5.248c.066.186.168.356.297.5c-.13.144-.23.314-.297.5H6.837a2 2 0 0 1-1.987-1.77L3.553 5H3a.5.5 0 0 1-.492-.41L2.5 4.5A.5.5 0 0 1 3 4h4.5zm4 0a1.5 1.5 0 0 0-3 0h3zm2 12a.5.5 0 0 0 0 1h5a.5.5 0 0 0 0-1h-5zm0-2a.5.5 0 0 0 0 1h5a.5.5 0 0 0 0-1h-5zm-.5 4.5a.5.5 0 0 1 .5-.5h5a.5.5 0 0 1 0 1h-5a.5.5 0 0 1-.5-.5z"
                      fill="currentColor"
                    ></path>
                  </g>
                </svg>
              </n-icon>
            </template>

            删除</n-button
          >
        </n-space>
      </div>
    </n-card>

    <!-- Tabs -->
    <n-card :bordered="false" class="mt">
      <n-tabs type="line" animated>
        <n-tab-pane name="bank" tab="银行账户">
          <BankCard />
        </n-tab-pane>

        <n-tab-pane name="invoice" tab="账单(PDF)">
          <InvoiceTable />
        </n-tab-pane>
      </n-tabs>
    </n-card>
  </div>

  <div v-else class="empty">请选择供应商</div>
</template>

<script setup>
import BankCard from './BankCard.vue'
import InvoiceTable from './InvoiceTable.vue'

defineProps({ vendor: Object })
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