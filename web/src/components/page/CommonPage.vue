<template>
  <AppPage :show-footer="showFooter">
    <header v-if="showHeader" class="common-page-header">
      <slot v-if="$slots.header" name="header" />
      <template v-else>
        <h2 class="common-page-title">{{ title || route.meta?.title }}</h2>
        <div v-if="$slots.action" class="common-page-actions">
          <slot name="action" />
        </div>
      </template>
    </header>

    <n-card class="common-page-card" :bordered="false">
      <slot />
    </n-card>
  </AppPage>
</template>

<script setup>
defineProps({
  showFooter: {
    type: Boolean,
    default: false,
  },
  showHeader: {
    type: Boolean,
    default: true,
  },
  title: {
    type: String,
    default: undefined,
  },
})
const route = useRoute()
</script>

<style scoped>
.common-page-header {
  display: flex;
  min-height: 44px;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
  padding: 0 2px;
}

.common-page-title {
  min-width: 0;
  margin: 0;
  color: #111827;
  font-size: 20px;
  font-weight: 650;
  line-height: 1.25;
}

.common-page-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
}

.common-page-card {
  flex: 1;
  min-height: 0;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 8px;
}

.common-page-card :deep(> .n-card__content) {
  display: flex;
  min-height: 0;
  flex-direction: column;
  padding: 16px;
}

html.dark .common-page-title {
  color: #e5e7eb;
}

html.dark .common-page-card {
  border-color: rgba(148, 163, 184, 0.14);
}

@media (max-width: 768px) {
  .common-page-header {
    align-items: stretch;
    flex-direction: column;
  }

  .common-page-title {
    font-size: 18px;
  }

  .common-page-actions {
    justify-content: flex-start;
  }

  .common-page-actions :deep(.n-space),
  .common-page-actions :deep(.n-button) {
    flex-wrap: wrap;
  }

  .common-page-card :deep(> .n-card__content) {
    padding: 12px;
  }
}
</style>
