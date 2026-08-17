<template>
  <AppProvider>
    <router-view v-slot="{ Component }">
      <component :is="Component" />
    </router-view>
    <FwAssistant />
  </AppProvider>
</template>

<script setup>
import AppProvider from '@/components/common/AppProvider.vue'
import FwAssistant from '@/components/common/FwAssistant.vue'
</script>
