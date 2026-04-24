<template>
  <n-card title="PDF 预览" class="pdf">
    <iframe :src="url" width="100%" height="500px" />
  </n-card>
</template>

<script setup>
defineProps({ url: String })
</script>

<style scoped>
.pdf {
  margin-top: 10px;
}
</style>