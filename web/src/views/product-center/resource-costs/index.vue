<template>
  <AppPage class="resource-cost-page"><ResourceCostLibrary /></AppPage>
</template>
<script setup>
import ResourceCostLibrary from '../components/ResourceCostLibrary.vue'
</script>
<style scoped>
.resource-cost-page.app-page-shell {
  min-height: 0;
  overflow: hidden;
}
</style>
