<template>
  <n-layout has-sider wh-full class="app-layout">
    <n-layout-sider
      class="app-sider"
      collapse-mode="width"
      :collapsed-width="64"
      :width="220"
      :native-scrollbar="false"
      :collapsed="appStore.collapsed"
    >
      <SideBar />
    </n-layout-sider>

    <n-drawer
      class="mobile-menu-drawer"
      :show="mobileMenuVisible"
      placement="left"
      :width="240"
      @update:show="handleMobileMenuUpdate"
    >
      <n-drawer-content :native-scrollbar="false" body-content-style="padding: 0">
        <SideBar />
      </n-drawer-content>
    </n-drawer>

    <article flex-col flex-1 overflow-hidden>
      <header
        class="app-header flex items-center px-15"
        :style="`height: ${header.height}px`"
      >
        <AppHeader />
      </header>
      <section v-if="tags.visible" class="app-tags-wrap" hidden sm:block>
        <AppTags :style="{ height: `${tags.height}px` }" />
      </section>
      <section class="app-main-wrap" flex-1 overflow-hidden>
        <AppMain />
      </section>
    </article>
  </n-layout>
</template>

<script setup>
import AppHeader from './components/header/index.vue'
import SideBar from './components/sidebar/index.vue'
import AppMain from './components/AppMain.vue'
import AppTags from './components/tags/index.vue'
import { useAppStore } from '@/store'
import { header, tags } from '~/settings'

// 移动端适配
import { useBreakpoints } from '@vueuse/core'

const appStore = useAppStore()
const route = useRoute()
const breakpointsEnum = {
  xl: 1600,
  lg: 1199,
  md: 991,
  sm: 666,
  xs: 575,
}
const breakpoints = reactive(useBreakpoints(breakpointsEnum))
const isMobile = breakpoints.smaller('sm')
const isPad = breakpoints.between('sm', 'md')
const isPC = breakpoints.greater('md')
const isNarrow = breakpoints.smaller('md')
const mobileMenuVisible = computed(() => isNarrow.value && !appStore.collapsed)

function handleMobileMenuUpdate(show) {
  if (!show) appStore.setCollapsed(true)
}

watchEffect(() => {
  if (isMobile.value) {
    // Mobile
    appStore.setCollapsed(true)
    appStore.setFullScreen(false)
  }

  if (isPad.value) {
    // IPad
    appStore.setCollapsed(true)
    appStore.setFullScreen(false)
  }

  if (isPC.value) {
    // PC
    appStore.setCollapsed(false)
    appStore.setFullScreen(true)
  }
})

watch(
  () => route.fullPath,
  () => {
    if (isNarrow.value) appStore.setCollapsed(true)
  }
)
</script>

<style scoped>
.app-layout,
.app-main-wrap {
  background: #f3f6fa;
}

.app-sider {
  border-right: 1px solid rgba(15, 23, 42, 0.08);
  background: #fff;
}

.app-header {
  border-bottom: 1px solid rgba(15, 23, 42, 0.08);
  background: #fff;
}

.app-tags-wrap {
  border-bottom: 1px solid rgba(15, 23, 42, 0.08);
  background: #fff;
}

html.dark .app-layout,
html.dark .app-main-wrap {
  background: #0f1117;
}

html.dark .app-sider,
html.dark .app-header,
html.dark .app-tags-wrap {
  border-color: rgba(148, 163, 184, 0.12);
  background: #111827;
}

@media (max-width: 768px) {
  .app-header {
    padding-inline: 10px;
  }

  .app-sider {
    display: none;
  }
}

:deep(.mobile-menu-drawer .n-drawer-body-content-wrapper) {
  padding: 0;
}

:deep(.mobile-menu-drawer .n-drawer-content) {
  background: #fff;
}

html.dark :deep(.mobile-menu-drawer .n-drawer-content) {
  background: #111827;
}
</style>
