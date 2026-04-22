<template>
  <div class="supplier-tree">
    <div class="search">
      <n-input v-model="query" placeholder="搜索供应商名称" clearable @input="onInput"/>
    </div>
    <div class="tree-wrap">
      <n-tree
        :data="treeData"
        block-node
        accordion
        @node-click="onNodeClick"
      />
    </div>
    <div class="footer">
      <n-button @click="onAdd" block>+ 新增供应商</n-button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'


const emit = defineEmits(['select'])
const query = ref('')

const treeData = computed(() => {
  // provide 10 network suppliers for demo; keys are used to filter bills
  return [
    {
      label: '全部供应商',
      key: 'network_suppliers',
      children: [
        { label: '中国电信股份有限公司', key: 'telecom' },
        { label: '中国联通有限公司', key: 'unicom' },
        { label: '中国移动通信集团', key: 'cmcc' },
        { label: '华为技术有限公司', key: 'huawei' },
        { label: '新华三技术有限公司', key: 'h3c' },
        { label: '中兴通讯股份有限公司', key: 'zte' },
        { label: '戴尔科技有限公司', key: 'dell' },
        { label: '联想集团有限公司', key: 'lenovo' },
        { label: '思科系统（中国）有限公司', key: 'cisco' },
        { label: '瞻博网络（Juniper）', key: 'juniper' }
      ]
    }
  ]
})

function onNodeClick(node) {
  emit('select', node)
}

function onInput() {
  // placeholder for filter
}

function onAdd() {
  console.log('新增供应商')
}
</script>

<style scoped>
.supplier-tree .search { margin-bottom: 12px }
.tree-wrap { max-height: calc(100vh - 240px); overflow: auto }
.footer { margin-top: 12px }
</style>
