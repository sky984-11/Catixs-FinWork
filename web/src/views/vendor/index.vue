<template>
  <div class="vendor-page">
    <div class="left-panel">
      <VendorList @select="handleSelect" :vendorList="vendorList" />
    </div>

    <div class="right-panel">
      <VendorDetail :vendor="currentVendor" />
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import VendorList from './components/VendorList.vue'
import VendorDetail from './components/VendorDetail.vue'


const vendorList = ref([
  {
    id: 1,
    name: 'Chief Telecom Inc',
    country: '台湾',
    code: 'VU00024',
    role: 2,
    address: '台北市內湖區陽光街250號 是方電訊 麗源大樓',
    noc_email: 'datacenter@chief.com.tw',
    noc_phone: '886-70-1017-1777',
    remark: '是方電訊股份有限公司',
    status: true,
  },
  { id: 2, name: '77 Telecom Ltd', country: '香港' },
])
const currentVendor = ref(vendorList.value[0])

const handleSelect = (row) => {
  console.log('Selected vendor:', row)
  currentVendor.value = row
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