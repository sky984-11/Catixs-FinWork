<template>
  <transition name="fade-slide" mode="out-in" appear>
    <section class="app-page-shell cus-scroll-y wh-full flex-col">
      <slot />
      <AppFooter v-if="showFooter" mt-15 />
      <n-back-top :bottom="20" />
    </section>
  </transition>
</template>

<script setup>
defineProps({
  showFooter: {
    type: Boolean,
    default: false,
  },
})
</script>

<style scoped>
.app-page-shell {
  min-height: 100%;
  padding: 16px;
  background: #f3f6fa;
}

html.dark .app-page-shell {
  background: #0f1117;
}

@media (max-width: 768px) {
  .app-page-shell {
    padding: 10px;
  }
}
</style>
