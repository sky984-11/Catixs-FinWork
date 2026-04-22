<template>
  <div class="supplier-tree">
    <div class="title">供应商管理</div>
    <div class="tree-wrap">
      <n-tree
        :data="treeData"
        block-node
        @node-click="onNodeClick"
        selectable
        default-expand-all
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
      key: 'vendor',
      children: [
        { label: 'DC', key: 'dc',children:[
          { label: '是方数据中心', key: 'chief',name:'是方数据中心',contact_name:'Ken Yang',contact_phone:'+886-910114505',address:'台北市內湖區陽光街250號 是方電訊 麗源大樓',remark:'主要提供云服务器托管服务',status:1 },
        ] },

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
.title { text-align: left; font-size: 25px; font-weight: 700; margin-bottom: 12px }
.supplier-tree .search { margin-bottom: 12px }
.tree-wrap { max-height: calc(100vh - 260px); overflow: auto }
.footer { margin-top: 16px }
</style>
