import { defineStore } from 'pinia';
import { ref } from 'vue';
import { getTeacherDashboard } from '@/api/teacher';
import type { DashboardStats } from '@/api/teacher';

export const useDashboardStore = defineStore('dashboard', () => {
  const stats = ref<DashboardStats | null>(null);
  const loading = ref(false);
  const error = ref<string | null>(null);

  async function fetchDashboardStats() {
    loading.value = true;
    error.value = null;
    try {
      const data = await getTeacherDashboard();
      stats.value = data;
    } catch (e) {
      error.value = '无法加载工作台数据';
      console.error(e);
    }
    loading.value = false;
  }

  return {
    stats,
    loading,
    error,
    fetchDashboardStats,
  };
});
