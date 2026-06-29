<template>
  <header class="page-header">
    <div class="page-header-main">
      <h1 class="page-title">
        <span>{{ title }}</span>
        <span v-if="metaText" class="page-meta">{{ metaText }}</span>
      </h1>
    </div>
    <div v-if="$slots.actions" class="page-actions">
      <slot name="actions" />
    </div>
  </header>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  metaText?: string
}>();
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e5ebf2;
}

.page-header-main {
  min-width: 0;
}

.page-title {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin: 0;
  font-size: 20px;
  font-weight: 750;
  letter-spacing: -0.02em;
  color: #1f2937;
}

.page-meta {
  display: inline-flex;
  align-items: center;
  min-height: 20px;
  margin-top: 1px;
  color: #8a97a8;
  font-size: 12px;
  font-weight: 650;
  line-height: 1;
}

.page-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

@media (max-width: 960px) {
  .page-header {
    flex-direction: column;
    align-items: stretch;
    gap: 12px;
  }

  .page-actions {
    width: 100%;
    justify-content: flex-start;
    flex-wrap: wrap;
  }
}
</style>
