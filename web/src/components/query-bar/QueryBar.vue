<template>
  <div
    class="query-bar"
    bg="#fafafc"
    min-h-60
    flex
    items-start
    justify-between
    b-1
    rounded-8
    p-15
    bc-ccc
    dark:bg-black
  >
    <n-space wrap :size="[35, 15]">
      <slot />
      <div>
        <n-button secondary type="primary" round @click="emit('reset')">重置</n-button>
        <n-button ml-20 type="primary" round @click="emit('search')">搜索</n-button>
      </div>
    </n-space>
  </div>
</template>

<script setup>
const emit = defineEmits(['search', 'reset'])
</script>

<style scoped>
.query-bar {
  min-width: 0;
}

.query-bar :deep(.n-space) {
  max-width: 100%;
}

@media (max-width: 768px) {
  .query-bar {
    padding: 12px;
  }

  .query-bar :deep(.n-space) {
    width: 100%;
  }

  .query-bar :deep(.n-space > *) {
    min-width: 0;
    width: 100%;
  }

  .query-bar :deep(.n-button) {
    width: auto;
  }
}
</style>
