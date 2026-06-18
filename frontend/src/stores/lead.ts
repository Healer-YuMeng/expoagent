import { defineStore } from 'pinia';
import { ref, reactive } from 'vue';
import { getLeads, deleteLead } from '@/api/lead';
import type { LeadListItem, PaginatedLeads } from '@/types';
import type { LeadFilters } from '@/api/lead';
import { ElMessage } from 'element-plus';

export const useLeadStore = defineStore('lead', () => {
  const leads = ref<LeadListItem[]>([]);
  const total = ref(0);
  const loading = ref(false);
  const error = ref<string | null>(null);

  const filters = reactive<LeadFilters>({
    page: 1,
    page_size: 10,
    language: 'zh-CN',
    tags: [],
    appointment_status: undefined,
    wecom_status: undefined,
    high_intent_only: undefined,
    manual_callback_only: undefined,
  });

  async function fetchLeads(language?: string) {
    if (language) {
      filters.language = language;
    }
    loading.value = true;
    error.value = null;
    try {
      const response: PaginatedLeads = await getLeads(filters);
      leads.value = response.items;
      total.value = response.total;
    } catch (e) {
      error.value = '无法加载线索列表';
      console.error(e);
    }
    loading.value = false;
  }

  function setFilters(newFilters: Partial<LeadFilters>) {
    Object.assign(filters, newFilters);
    filters.page = 1; // Reset to first page when filters change
    return fetchLeads();
  }

  function setPage(page: number) {
    filters.page = page;
    fetchLeads();
  }

  async function removeLead(id: string) {
    try {
      await deleteLead(id);
      ElMessage.success('线索已删除');
      await fetchLeads(); // 刷新列表
    } catch (e) {
      ElMessage.error('删除失败，请重试');
      console.error(e);
    }
  }

  return {
    leads,
    total,
    loading,
    error,
    filters,
    fetchLeads,
    setFilters,
    setPage,
    removeLead,
  };
});
