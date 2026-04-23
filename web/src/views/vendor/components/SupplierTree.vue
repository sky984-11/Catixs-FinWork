<template>
  <div class="supplier-tree">
    <div class="title">供应商管理</div>
    <div class="tree-wrap">
      <n-tree
        :data="treeData"
        block-node
        accordion
        selectable
        default-expand-all
        :selected-keys="[activeKey]"
        :node-props="nodeProps"
      />
    </div>
    <div class="footer">
      <n-button @click="onAdd" block>+ 新增供应商</n-button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const emit = defineEmits(['select', 'click'])
const query = ref('')
const activeKey = ref(null)

const treeData = computed(() => {
  // provide 10 network suppliers for demo; keys are used to filter bills
  return [
    {
      label: '全部供应商',
      key: 'vendor',
      children: [
        {
          label: 'DC',
          key: 'dc',
          children: [
            {
              label: '是方数据中心',
              key: 'chief',
              catixs_entity: 'Catixs Ltd(UK)',
              name: 'Chief Telecom Inc.',
              billing_email: 'chiefbilling@chief.com.tw',
              noc_email: 'datacenter@chief.com.tw',
              noc_phone: '886-70-1017-1777',
              address: '台北市內湖區陽光街250號 是方電訊 麗源大樓',
              remark: '是方電訊股份有限公司',
            },
          ],
        },
      ],
    },
  ]
})

function onNodeClick(node) {
  activeKey.value = node.key
  emit('select', node)
}


function nodeProps({ option }) {
  return {
    onClick() {
       emit('click', option)
    }
  };
}

function onInput() {
  // placeholder for filter
}

function onAdd() {
  $message.info('请先选择供应商')
  console.log('新增供应商')
}
</script>

<style scoped>
.title {
  text-align: left;
  font-size: 18px;
  font-weight: 700;
  margin-bottom: 12px;
}
.supplier-tree .search {
  margin-bottom: 12px;
}
.tree-wrap {
  max-height: calc(100vh - 260px);
  overflow: auto;
}
.footer {
  margin-top: 16px;
}
</style>
