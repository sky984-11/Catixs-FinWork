<template>
  <div class="bills-table">
    <n-table :data="bills" :loading="loading">
      <thead>
        <tr>
          <th style="width:40px"><input type="checkbox" /></th>
          <th>账单编号</th>
          <th>账单类型</th>
          <th>账单日期</th>
          <th>到期日期</th>
          <th>金额</th>
          <th>已付金额</th>
          <th>未付金额</th>
          <th>状态</th>
          <th>负责人</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in bills" :key="row.id">
          <td><input type="checkbox" /></td>
          <td class="bill-no"><a @click.prevent="onView(row)">{{ row.billNo }}</a></td>
          <td>{{ row.type }}</td>
          <td>{{ row.billDate }}</td>
          <td>{{ row.dueDate }}</td>
          <td class="num">{{ formatCurrency(row.amount, row.currency) }}</td>
          <td class="num">{{ formatCurrency(row.paid, row.currency) }}</td>
          <td class="num">{{ formatCurrency(row.unpaid, row.currency) }}</td>
          <td>
            <n-tag :type="tagType(row.status)">{{ row.status }}</n-tag>
          </td>
          <td>{{ row.owner }}</td>
          <td>
            <n-space>
              <a class="link" @click.prevent="onView(row)">查看</a>
              <!--  支持邮件和飞书通知 -->
              <a class="link" @click.prevent="onPay(row)">付款通知</a>
            </n-space>
          </td>
        </tr>
      </tbody>
    </n-table>

    <div class="pager">
      <n-pagination :page.sync="page" :page-size.sync="pageSize" :page-count="Math.ceil(total / pageSize)" show-quick-jumper @update:page="onPageChange" />
    </div>
  </div>
</template>

<script setup>
import { toRef } from 'vue'

const props = defineProps({
  bills: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  page: { type: Number, default: 1 },
  pageSize: { type: Number, default: 10 },
  total: { type: Number, default: 0 }
})

const emit = defineEmits(['page-change'])

function tagType(status) {
  if (status === '已付款') return 'success'
  if (status === '部分付款') return 'warning'
  return 'error'
}

function formatCurrency(value, currency = 'CNY') {
  const num = Number(value)
  if (Number.isNaN(num)) return value
  // Format number with thousands separators and two decimals
  const formatted = new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(num)
  const symbolMap = { USD: '$', EUR: '€', CNY: '¥' }
  const symbol = symbolMap[currency] || currency
  return `${formatted} ${symbol}`
}

function onView(row) {
  const content = `账单编号: ${row.billNo}\n账单类型: ${row.type}\n账单日期: ${row.billDate}\n到期日期: ${row.dueDate}\n金额: ${formatCurrency(row.amount, row.currency)}\n已付: ${formatCurrency(row.paid, row.currency)}\n未付: ${formatCurrency(row.unpaid, row.currency)}\n负责人: ${row.owner}`
  $dialog.confirm({
    title: '账单详情',
    type: 'info',
    content,
    confirm() {},
  })
}
function onPay(row) {
  $message.info('付款功能暂未实现')
}
function onPageChange(p) {
  emit('page-change', p)
}
</script>

<style scoped>
.bills-table table { width: 100%; border-collapse: collapse }
.bills-table th, .bills-table td { padding: 10px; text-align: left; border-bottom: 1px solid #f0f0f0 }
.bill-no a { color: #1890ff; cursor: pointer }
.link { color: #1890ff; cursor: pointer; margin-right: 8px }
.num { text-align: right }
.pager { display:flex; justify-content: flex-end; margin-top: 12px }
</style>
