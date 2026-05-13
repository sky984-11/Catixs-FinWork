<template>
  <router-link class="side-logo" to="/" :title="title">
    <!-- <img class="side-logo__mark" :src="logoUrl" alt="Catixs FinWork" /> -->
    <n-avatar round :size="48" :src="logoUrl" />
    <h2 v-show="!appStore.collapsed" class="side-logo__title">
    </h2>
  </router-link>
</template>

<script setup>
import { useAppStore } from '@/store'
import logoUrl from '@/assets/svg/logo.svg?url'

const title = import.meta.env.VITE_TITLE

const appStore = useAppStore()
</script>

<style scoped>
.side-logo {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 60px;
  gap: 8px;
  overflow: hidden;
  text-decoration: none;
}

.side-logo__mark {
  width: 38px;
  height: 38px;
  flex: 0 0 38px;
  object-fit: contain;
}

.side-logo__title {
  display: flex;
  align-items: baseline;
  max-width: 150px;
  margin: 0 8px 0 0;
  flex-shrink: 0;
  font-size: 16px;
  font-weight: 800;
  line-height: 1;
  white-space: nowrap;
}

.side-logo__title-blue {
  color: #092a6b;
}

.side-logo__title-green {
  margin-left: 5px;
  color: #17a889;
}
</style>
