<template>
  <el-container class="parent-layout">
    <el-main class="main-content">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
</script>

<style scoped>
.parent-layout {
  height: 100vh;
  width: 100%;
  position: relative;
  overflow: hidden;
}

.main-content {
  width: 100%;
  height: 100vh;
  padding: 0 !important;
  background: transparent;
  overflow: hidden;
}

:deep(.el-main) {
  padding: 0;
}
</style>
