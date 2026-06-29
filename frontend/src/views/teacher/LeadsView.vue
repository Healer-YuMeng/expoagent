<template>
  <div class="leads-view">
    <TeacherPageHeader :title="t('leads.title')" :meta-text="t('leads.totalCount', { count: total })" />

    <!-- 快捷筛选按钮和搜索框 -->
    <div class="filter-section">
      <div class="filter-row">
        <div class="quick-filters">
          <button
            class="quick-filter-btn"
            :class="{ active: isAllLeadsFilterActive() }"
            @click="quickFilter('all')"
          >
            <el-icon class="filter-icon"><Tickets /></el-icon>
            <span>{{ t('leads.allLeads') }}</span>
          </button>
          <button
            class="quick-filter-btn"
            :class="{ active: filters.high_intent_only }"
            @click="quickFilter('high_intent')"
          >
            <el-icon class="filter-icon"><Opportunity /></el-icon>
            <span>{{ t('leads.highIntent') }}</span>
          </button>
          <button
            class="quick-filter-btn"
            :class="{ active: filters.manual_callback_only }"
            @click="quickFilter('manual_callback')"
          >
            <el-icon class="filter-icon"><Warning /></el-icon>
            <span>{{ t('leads.manualCallback') }}</span>
          </button>
        </div>

        <div class="toolbar-actions">
          <button class="filter-btn utility-btn" @click="handleExport" :disabled="exporting">
            <el-icon class="btn-icon"><Download /></el-icon>
            <span>{{ exporting ? t('leads.exportingExcel') : t('leads.exportExcel') }}</span>
          </button>
          <button class="filter-btn utility-btn danger-lite" :disabled="!canBulkDelete" @click="handleBulkDelete">
            <el-icon class="btn-icon"><Delete /></el-icon>
            <span>{{ t('leads.bulkDelete') }}</span>
          </button>
        </div>
      </div>

      <div class="advanced-filter-bar">
        <div class="advanced-filter-grid">
          <div class="search-input-wrap search-input-wrap--wide">
            <el-icon class="search-input-icon"><Search /></el-icon>
            <el-input
              v-model="localFilters.search"
              :placeholder="t('leads.searchPlaceholder')"
              class="search-input"
              clearable
              @keyup.enter="applyFilters"
            />
          </div>

          <el-select
            v-model="localFilters.intended_product"
            class="filter-select"
            clearable
            filterable
            allow-create
            default-first-option
            :placeholder="t('leads.productFilterPlaceholder')"
          >
            <el-option
              v-for="option in productOptions"
              :key="option"
              :label="option"
              :value="option"
            />
          </el-select>

          <el-select
            v-model="localFilters.interest_level"
            class="filter-select"
            clearable
            :placeholder="t('leads.interestFilterPlaceholder')"
          >
            <el-option
              v-for="option in interestLevelOptions"
              :key="option"
              :label="option"
              :value="option"
            />
          </el-select>

          <el-select
            v-model="localFilters.follow_up_owner_name"
            class="filter-select"
            clearable
            filterable
            allow-create
            default-first-option
            :placeholder="t('leads.ownerFilterPlaceholder')"
          >
            <el-option
              v-for="option in ownerOptions"
              :key="option"
              :label="option"
              :value="option"
            />
          </el-select>
        </div>

        <div class="advanced-filter-actions">
          <button class="filter-btn utility-btn" @click="applyFilters">
            <el-icon class="btn-icon"><Search /></el-icon>
            <span>{{ t('common.search') }}</span>
          </button>
          <button class="filter-btn utility-btn" @click="resetFilters">
            <el-icon class="btn-icon"><RefreshRight /></el-icon>
            <span>{{ t('common.reset') }}</span>
          </button>
        </div>
      </div>
    </div>

    <div class="table-section" v-loading="loading">
      <div class="table-wrapper">
        <table class="leads-table">
          <thead>
            <tr>
              <th class="selection-col">
                <input
                  class="lead-checkbox"
                  type="checkbox"
                  :checked="isCurrentPageFullySelected()"
                  @change="toggleCurrentPageSelection"
                />
              </th>
              <th>{{ t('leads.parentName') }}</th>
              <th>{{ t('leads.contact') }}</th>
              <th>{{ t('leads.intendedProduct') }}</th>
              <th>{{ t('leads.interestLevel') }}</th>
              <th>{{ t('leads.followUpOwner') }}</th>
              <th class="action-col">{{ t('leads.actions') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="lead in leads" :key="lead.id" class="table-row">
              <td class="selection-col">
                <input
                  class="lead-checkbox"
                  type="checkbox"
                  :checked="isLeadSelected(lead.id)"
                  @change="toggleLeadSelection(lead.id)"
                />
              </td>
              <td>
                <div class="name-cell">
                  <button class="name-link" @click="viewDetails(lead.id)">
                    {{ lead.display_name || lead.parent_name || t('leads.notIdentified') }}
                  </button>
                </div>
              </td>
              <td>{{ lead.display_phone || lead.parent_phone || t('leads.notProvided') }}</td>
              <td>
                <span class="product-text">{{ getIntendedProductText(lead) }}</span>
              </td>
              <td>
                <span class="status-badge" :class="getInterestLevelClass(lead.interest_level)">
                  {{ lead.interest_level || t('leads.notProvided') }}
                </span>
              </td>
              <td>
                {{ getOwnerName(lead) }}
              </td>
              <td class="action-col">
                <div class="action-buttons">
                  <button class="action-btn lock-btn" @click="handleLock(lead)">
                    <span>{{ t('leads.lock') }}</span>
                  </button>
                  <button class="action-btn view-btn" @click="viewDetails(lead.id)">
                    <span>{{ t('common.view') }}</span>
                  </button>
                  <button class="action-btn assign-btn" @click="openAssignDialog(lead)">
                    <span class="icon-hover-shell" aria-hidden="true">
                      <span class="custom-icon custom-icon-assign">
                        <svg viewBox="0 0 24 24" fill="none">
                          <circle cx="9" cy="8" r="4" stroke="currentColor" stroke-width="2" />
                          <path d="M2.5 20C3.4 16.9 5.9 15 9 15C12.1 15 14.6 16.9 15.5 20" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
                          <path d="M18 5V13" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
                          <path d="M14 9H22" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
                        </svg>
                      </span>
                    </span>
                    <span class="sr-only">{{ t('leads.assign') }}</span>
                  </button>
                  <button class="action-btn delete-btn" @click="handleDelete(lead.id)">
                    <span class="icon-hover-shell" aria-hidden="true">
                      <span class="custom-icon custom-icon-delete">
                        <svg viewBox="0 0 24 24" fill="none">
                          <path d="M4 7H20" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
                          <path d="M9 4H15" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
                          <path d="M7 7V19C7 20.1 7.9 21 9 21H15C16.1 21 17 20.1 17 19V7" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
                          <path d="M10 11V17" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
                          <path d="M14 11V17" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
                        </svg>
                      </span>
                    </span>
                    <span class="sr-only">{{ t('common.delete') }}</span>
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>

        <!-- 空状态 -->
        <div v-if="!loading && leads.length === 0" class="empty-state">
          <div class="empty-icon">
            <el-icon><DocumentCopy /></el-icon>
          </div>
          <div class="empty-text">{{ t('leads.noData') }}</div>
        </div>
      </div>

      <!-- 分页 -->
      <div v-if="total > 0" class="pagination-wrapper">
        <el-pagination
          layout="prev, pager, next"
          :total="total"
          :page-size="filters.page_size"
          :current-page="filters.page"
          @current-change="handlePageChange"
        />
      </div>
    </div>

    <div v-if="error" class="error-alert">
      <el-icon class="error-icon"><Warning /></el-icon>
      <div class="error-text">{{ error }}</div>
    </div>

    <el-dialog
      v-model="assignDialogVisible"
      :title="t('leads.assignDialogTitle')"
      width="420px"
    >
      <p class="assign-hint">
        {{ t('leads.assignDialogHint') }}
      </p>
      <el-radio-group v-model="selectedTeacherId" class="assign-radios">
        <el-radio
          v-for="teacher in mockTeachers"
          :key="teacher.id"
          :label="teacher.id"
        >
          {{ teacher.name }}
        </el-radio>
      </el-radio-group>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="closeAssignDialog">{{ t('common.cancel') }}</el-button>
          <el-button type="primary" @click="assignLead" :disabled="!selectedTeacherId">
            {{ t('leads.assignAction') }}
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, watch, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { storeToRefs } from 'pinia';
import { useLeadStore } from '@/stores/lead';
import { useI18n } from 'vue-i18n';
import type { LeadListItem } from '@/types';
import { ElMessage, ElMessageBox } from 'element-plus';
import {
  Delete,
  DocumentCopy,
  Download,
  Opportunity,
  RefreshRight,
  Search,
  Tickets,
  Warning,
} from '@element-plus/icons-vue';
import TeacherPageHeader from '@/components/TeacherPageHeader.vue';
import { exportLeads as exportLeadsApi } from '@/api/lead';
import { useAuthStore } from '@/stores/auth';
import { getPortalLeadDetailPath } from '@/router/portalRoutes';

const router = useRouter();
const route = useRoute();
const { t, locale } = useI18n();
const leadStore = useLeadStore();
const authStore = useAuthStore();
const { leads, total, loading, error, filters } = storeToRefs(leadStore);

// Local state for filters to avoid direct mutation before applying
const localFilters = reactive({
  search: filters.value.search || '',
  intended_product: filters.value.intended_product || '',
  interest_level: filters.value.interest_level || '',
  follow_up_owner_name: filters.value.follow_up_owner_name || '',
});

const assignDialogVisible = ref(false);
const selectedTeacherId = ref<string | null>(null);
const assignTargetLead = ref<LeadListItem | null>(null);
const exporting = ref(false);
const selectedLeadIds = ref<string[]>([]);
// TODO: replace mock data with backend teacher list once assignment API is ready.
const mockTeachers = [
  { id: 'teacher_a', name: 'A老师（模拟数据，后端上线需删除）' },
  { id: 'teacher_b', name: 'B老师（模拟数据，后端上线需删除）' },
  { id: 'teacher_c', name: 'C老师（模拟数据，后端上线需删除）' },
];

const isAllLeadsFilterActive = () => (
  !filters.value.high_intent_only
  && !filters.value.manual_callback_only
  && !filters.value.appointment_status
  && !filters.value.search
  && !filters.value.intended_product
  && !filters.value.interest_level
  && !filters.value.follow_up_owner_name
);

const productOptions = computed(() =>
  Array.from(
    new Set(
      leads.value
        .map((lead) => (lead.intended_product || '').trim())
        .filter(Boolean)
    )
  ).sort((a, b) => a.localeCompare(b, 'zh-CN'))
);

const ownerOptions = computed(() =>
  Array.from(
    new Set(
      leads.value
        .map((lead) => (lead.follow_up_owner?.name || '').trim())
        .filter(Boolean)
    )
  ).sort((a, b) => a.localeCompare(b, 'zh-CN'))
);

const interestLevelOptions = computed(() => ['一般', '高', '极高']);
const canBulkDelete = computed(() => selectedLeadIds.value.length > 0);

const applyFilters = () => {
  void leadStore.setFilters({
    search: localFilters.search,
    intended_product: localFilters.intended_product,
    interest_level: localFilters.interest_level,
    follow_up_owner_name: localFilters.follow_up_owner_name,
    high_intent_only: filters.value.high_intent_only,
    manual_callback_only: filters.value.manual_callback_only,
    appointment_status: filters.value.appointment_status,
  });
};

const resetFilters = () => {
  localFilters.search = '';
  localFilters.intended_product = '';
  localFilters.interest_level = '';
  localFilters.follow_up_owner_name = '';
  
  void leadStore.setFilters({
    search: '',
    intended_product: '',
    interest_level: '',
    follow_up_owner_name: '',
    high_intent_only: undefined,
    manual_callback_only: undefined,
    appointment_status: undefined,
  });
};

const quickFilter = (type: string) => {
  // 重置搜索
  localFilters.search = '';
  localFilters.intended_product = '';
  localFilters.interest_level = '';
  localFilters.follow_up_owner_name = '';
  
  switch (type) {
    case 'all':
      void leadStore.setFilters({
        search: '',
        intended_product: '',
        interest_level: '',
        follow_up_owner_name: '',
        high_intent_only: undefined,
        manual_callback_only: undefined,
        appointment_status: undefined,
      });
      break;
    case 'high_intent':
      void leadStore.setFilters({
        search: '',
        intended_product: '',
        interest_level: '',
        follow_up_owner_name: '',
        high_intent_only: true,
        manual_callback_only: undefined,
        appointment_status: undefined,
      });
      break;
    case 'manual_callback':
      void leadStore.setFilters({
        search: '',
        intended_product: '',
        interest_level: '',
        follow_up_owner_name: '',
        high_intent_only: undefined,
        manual_callback_only: true,
        appointment_status: undefined,
      });
      break;
    case 'pending_appointment':
      void leadStore.setFilters({
        search: '',
        intended_product: '',
        interest_level: '',
        follow_up_owner_name: '',
        high_intent_only: undefined,
        manual_callback_only: undefined,
        appointment_status: 'pending',
      });
      break;
    case 'confirmed_appointment':
      void leadStore.setFilters({
        search: '',
        intended_product: '',
        interest_level: '',
        follow_up_owner_name: '',
        high_intent_only: undefined,
        manual_callback_only: undefined,
        appointment_status: 'confirmed',
      });
      break;
  }
};

const handlePageChange = (page: number) => {
  leadStore.setPage(page);
};

const viewDetails = (id: string) => {
  router.push(getPortalLeadDetailPath(authStore.userRole, id));
};

const handleDelete = async (id: string) => {
  await leadStore.removeLead(id);
  selectedLeadIds.value = selectedLeadIds.value.filter((item) => item !== id);
};

const handleBulkDelete = async () => {
  if (!selectedLeadIds.value.length) return;

  try {
    await ElMessageBox.confirm(
      t('leads.bulkDeleteConfirm', { count: selectedLeadIds.value.length }),
      t('leads.bulkDeleteTitle'),
      {
        type: 'warning',
        confirmButtonText: t('common.delete'),
        cancelButtonText: t('common.cancel'),
      }
    );

    await leadStore.removeLeads(selectedLeadIds.value);
    selectedLeadIds.value = [];
  } catch {
    // 用户取消时不提示错误
  }
};

const isLeadSelected = (id: string) => selectedLeadIds.value.includes(id);

const isCurrentPageFullySelected = () => (
  leads.value.length > 0
  && leads.value.every((lead) => selectedLeadIds.value.includes(lead.id))
);

const toggleLeadSelection = (id: string) => {
  selectedLeadIds.value = selectedLeadIds.value.includes(id)
    ? selectedLeadIds.value.filter((item) => item !== id)
    : [...selectedLeadIds.value, id];
};

const toggleCurrentPageSelection = () => {
  if (isCurrentPageFullySelected()) {
    const currentIds = new Set(leads.value.map((lead) => lead.id));
    selectedLeadIds.value = selectedLeadIds.value.filter((id) => !currentIds.has(id));
    return;
  }
  selectedLeadIds.value = Array.from(new Set([
    ...selectedLeadIds.value,
    ...leads.value.map((lead) => lead.id),
  ]));
};

const handleLock = (lead: LeadListItem) => {
  ElMessage.info(`${lead.display_name || lead.parent_name || t('leads.notIdentified')}：${t('leads.lockTodo')}`);
};

const handleExport = async () => {
  exporting.value = true;
  try {
    const blob = await exportLeadsApi({ ...filters.value });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    const today = new Date();
    const yyyy = today.getFullYear();
    const mm = String(today.getMonth() + 1).padStart(2, '0');
    const dd = String(today.getDate()).padStart(2, '0');
    link.download = `leads_${yyyy}${mm}${dd}.xlsx`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
    ElMessage.success(t('leads.exportSuccess'));
  } catch (e) {
    console.error(e);
    ElMessage.error(t('leads.exportError'));
  } finally {
    exporting.value = false;
  }
};

const openAssignDialog = (lead: LeadListItem) => {
  assignTargetLead.value = lead;
  selectedTeacherId.value = null;
  assignDialogVisible.value = true;
};

const closeAssignDialog = () => {
  assignDialogVisible.value = false;
  selectedTeacherId.value = null;
  assignTargetLead.value = null;
};

const assignLead = () => {
  if (!assignTargetLead.value || !selectedTeacherId.value) return;
  /**
   * TODO:
   * 1. 调用后端“分配线索”接口，传入 leadId 与 teacherId。
   * 2. 后端返回成功后刷新列表并提示用户。
   * 当前先用提示占位，避免误导。
   */
  ElMessage.info(
    t('leads.assignTodo', {
      lead: assignTargetLead.value.parent_name || assignTargetLead.value.display_name,
      teacher: mockTeachers.find((item) => item.id === selectedTeacherId.value)?.name || selectedTeacherId.value,
    })
  );
  closeAssignDialog();
};

const getIntendedProductText = (lead: LeadListItem) => (
  lead.intended_product || t('leads.notProvided')
);

const getInterestLevelClass = (level: string | null | undefined) => {
  switch (level) {
    case '极高':
    case 'Very High':
      return 'status-danger';
    case '高':
    case 'High':
      return 'status-warning';
    case '一般':
    case 'Normal':
      return 'status-info';
    default:
      return 'status-muted';
  }
};

const getOwnerName = (lead: LeadListItem) => {
  const name = lead.follow_up_owner?.name;
  if (!name) {
    return t('leads.followUpOwnerNone');
  }
  if (name === '默认学校管理员' || name === '默认普通管理员' || name === 'Default School Admin' || name === 'Default Admin') {
    return t('teacher.layout.defaultSchoolAdmin');
  }
  if (name === '默认超级管理员' || name === 'Default Super Admin') {
    return t('teacher.layout.defaultSuperAdmin');
  }
  return name;
};

const parseBooleanQuery = (value: unknown): boolean | undefined => {
  if (value === undefined || value === null) return undefined;
  if (typeof value === 'string') {
    if (value === 'true' || value === '1') return true;
    if (value === 'false' || value === '0') return false;
  }
  if (typeof value === 'boolean') return value;
  return undefined;
};

onMounted(async () => {
  const appointmentStatusQuery = route.query.appointment_status as string | undefined;
  const highIntentQuery = parseBooleanQuery(route.query.high_intent_only);
  const manualCallbackQuery = parseBooleanQuery(route.query.manual_callback_only);

  const initialFilters: Record<string, unknown> = {};

  if (appointmentStatusQuery) {
    initialFilters.appointment_status = appointmentStatusQuery;
  }
  if (highIntentQuery !== undefined) {
    initialFilters.high_intent_only = highIntentQuery;
  }
  if (manualCallbackQuery !== undefined) {
    initialFilters.manual_callback_only = manualCallbackQuery;
  }

  if (Object.keys(initialFilters).length > 0) {
    await leadStore.setFilters({
      ...initialFilters,
      language: locale.value,
    });
  } else {
    await leadStore.fetchLeads(locale.value);
  }
});

watch(
  () => route.query.appointment_status,
  (value) => {
    if (value) {
      void leadStore.setFilters({
        appointment_status: value as string,
      });
    } else if (value === undefined) {
      void leadStore.setFilters({
        appointment_status: undefined,
      });
    }
  }
);

watch(
  () => locale.value,
  (value) => {
    void leadStore.fetchLeads(value);
  }
);
watch(
  () => route.query.high_intent_only,
  (value) => {
    const parsed = parseBooleanQuery(value);
    if (parsed !== undefined) {
      void leadStore.setFilters({
        high_intent_only: parsed,
      });
    } else if (value === undefined) {
      void leadStore.setFilters({
        high_intent_only: undefined,
      });
    }
  }
);

watch(
  () => route.query.manual_callback_only,
  (value) => {
    const parsed = parseBooleanQuery(value);
    if (parsed !== undefined) {
      void leadStore.setFilters({
        manual_callback_only: parsed,
      });
    } else if (value === undefined) {
      void leadStore.setFilters({
        manual_callback_only: undefined,
      });
    }
  }
);
</script>

<style scoped>
.leads-view {
  padding: 0;
  color: #273142;
}

.page-header {
  display: flex;
  align-items: center;
  margin-bottom: 14px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e5ebf2;
}

.page-title {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 20px;
  font-weight: 750;
  letter-spacing: -0.02em;
  color: #1f2937;
  margin: 0;
}

.total-count {
  display: inline-flex;
  align-items: center;
  min-height: 20px;
  padding: 0;
  border: 0;
  background: transparent;
  color: #8a97a8;
  font-size: 12px;
  font-weight: 650;
  line-height: 1;
}

.total-count--inline {
  margin-top: 1px;
}

.filter-section {
  margin-bottom: 24px;
  padding: 18px 20px;
  border-radius: 20px;
  border: 1px solid #dde6f0;
  background: #ffffff;
  box-shadow: 0 10px 30px rgba(29, 41, 57, 0.06);
}

.filter-row {
  display: flex;
  gap: 14px;
  align-items: center;
  justify-content: space-between;
}

.quick-filters {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  flex: 1;
}

.quick-filter-btn {
  display: flex;
  align-items: center;
  gap: 9px;
  min-height: 48px;
  padding: 0 18px;
  border-radius: 15px;
  border: 1px solid #d9e3ee;
  background: #ffffff;
  color: #6f8098;
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  transition: background-color 0.2s ease, color 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
  white-space: nowrap;
  box-shadow: 0 3px 12px rgba(22, 34, 51, 0.04);
}

.quick-filter-btn:hover {
  border-color: #c3d0e0;
  background: #f9fbfd;
  color: #42526b;
}

.quick-filter-btn.active {
  background: #202a39;
  color: #ffffff;
  border-color: #202a39;
  box-shadow: 0 10px 20px rgba(32, 42, 57, 0.14);
}

.filter-icon {
  font-size: 16px;
}

.toolbar-actions {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-shrink: 0;
  flex-wrap: wrap;
}

.advanced-filter-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: 14px;
  padding: 14px 16px;
  border-radius: 18px;
  border: 1px solid #e2e9f1;
  background: #f9fbfd;
}

.advanced-filter-grid {
  display: grid;
  grid-template-columns: minmax(220px, 1.5fr) repeat(3, minmax(160px, 1fr));
  gap: 12px;
  flex: 1;
}

.advanced-filter-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.search-input-wrap {
  position: relative;
  display: flex;
  align-items: center;
  width: 100%;
  min-height: 44px;
  padding-left: 40px;
  border-radius: 14px;
  border: 1px solid #d9e3ee;
  background: #ffffff;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background-color 0.2s ease;
}

.search-input-wrap--wide {
  min-width: 0;
}

.search-input-wrap:focus-within {
  border-color: #243041;
  box-shadow: none;
}

.search-input-icon {
  position: absolute;
  left: 14px;
  color: #8292a8;
  font-size: 17px;
  pointer-events: none;
}

.search-input {
  width: 100%;
}

.filter-select {
  width: 100%;
}

:deep(.search-input .el-input__wrapper) {
  padding: 0;
  box-shadow: none;
  background: transparent;
}

:deep(.search-input .el-input__inner) {
  height: 42px;
  color: #273142;
  font-size: 14px;
}

:deep(.search-input .el-input__inner::placeholder) {
  color: #a3afbf;
}

:deep(.filter-select .el-select__wrapper) {
  min-height: 44px;
  border-radius: 14px;
  border: 1px solid #d9e3ee;
  box-shadow: none;
  background: #ffffff;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background-color 0.2s ease;
}

:deep(.filter-select .el-select__wrapper.is-focused) {
  border-color: #243041;
  box-shadow: none;
}

:deep(.filter-select .el-select__placeholder),
:deep(.filter-select .el-select__selected-item) {
  font-size: 14px;
}

.filter-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  justify-content: center;
  min-height: 44px;
  padding: 0 16px;
  border-radius: 14px;
  border: 1px solid transparent;
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  transition: background-color 0.2s ease, border-color 0.2s ease, color 0.2s ease, box-shadow 0.2s ease;
  white-space: nowrap;
}

.filter-btn.utility-btn {
  min-height: 40px;
  padding: 0 14px;
  border-color: #d9e3ee;
  background: #ffffff;
  color: #6f8098;
  box-shadow: 0 3px 12px rgba(22, 34, 51, 0.04);
}

.filter-btn.utility-btn:hover {
  border-color: #c3d0e0;
  background: #f4f7fb;
  color: #42526b;
}

.filter-btn.utility-btn:active,
.filter-btn.utility-btn:focus-visible {
  border-color: #202a39;
  background: #202a39;
  color: #ffffff;
  outline: none;
  box-shadow: 0 10px 20px rgba(32, 42, 57, 0.14);
}

.filter-btn.danger-lite {
  color: #d65a51;
  border-color: #f0d8d3;
}

.filter-btn.danger-lite:hover {
  background: #fff6f4;
  border-color: #eac2ba;
  color: #c74b43;
}

.filter-btn:disabled {
  opacity: 0.68;
  cursor: not-allowed;
  box-shadow: none;
}

.btn-icon {
  font-size: 15px;
}

.table-section {
  display: flex;
  flex-direction: column;
  padding: 0;
  border-radius: 18px;
  border: 1px solid #dde6f0;
  background: #ffffff;
  box-shadow: 0 10px 24px rgba(29, 41, 57, 0.045);
  min-height: calc(100vh - 318px);
  overflow: hidden;
}

.table-wrapper {
  flex: 1;
  overflow-x: auto;
  border-radius: 18px 18px 0 0;
}

.leads-table {
  width: 100%;
  min-width: 980px;
  border-collapse: collapse;
  background: #ffffff;
}

.leads-table thead th {
  padding: 12px 16px;
  text-align: left;
  font-size: 12px;
  font-weight: 700;
  color: #73839a;
  border-bottom: 1px solid #e4ebf3;
  background: #ffffff;
  white-space: nowrap;
}

.leads-table tbody tr {
  transition: background-color 0.2s ease;
}

.leads-table tbody tr:hover {
  background: #fafcfe;
}

.leads-table tbody td {
  padding: 12px 16px;
  border-bottom: 1px solid #f0f4f8;
  color: #425168;
  font-size: 13px;
  vertical-align: middle;
}

.selection-col {
  width: 46px;
  text-align: center !important;
}

.action-col {
  width: 320px;
  min-width: 320px;
}

.lead-checkbox {
  width: 15px;
  height: 15px;
  accent-color: #202a39;
  cursor: pointer;
}

.name-cell {
  display: flex;
  align-items: center;
  gap: 0;
  font-weight: 600;
  color: #1f2937;
}

.name-link {
  border: 0;
  padding: 0;
  background: transparent;
  color: #1f2937;
  font: inherit;
  font-weight: 700;
  font-size: 13px;
  cursor: pointer;
  text-align: left;
}

.name-link:hover {
  color: #2d8acf;
}

.product-text {
  font-weight: 600;
  color: #273142;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
}

.status-warning {
  background: #fff3dd;
  color: #b7791f;
}

.status-success {
  background: #e5f7ec;
  color: #239b64;
}

.status-info {
  background: #e9f3ff;
  color: #3576b5;
}

.status-danger {
  background: #ffe9e7;
  color: #d7534b;
}

.status-muted {
  background: #f0f3f7;
  color: #6f8098;
}

.action-buttons {
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: flex-start;
  flex-wrap: wrap;
}

.action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 28px;
  padding: 0;
  border: none;
  background: transparent;
  font-weight: 600;
  font-size: 13px;
  cursor: pointer;
  transition: color 0.2s ease, opacity 0.2s ease, transform 0.2s ease;
  white-space: nowrap;
}

.view-btn {
  color: #347fc5;
}

.view-btn:hover {
  color: #2468a8;
}

.lock-btn {
  gap: 6px;
  color: #6f7e92;
}

.lock-btn:hover {
  color: #435163;
}

.assign-btn {
  color: #6a7c96;
}

.assign-btn:hover {
  color: #42546d;
}

.delete-btn {
  color: #ff6a5f;
}

.delete-btn:hover {
  color: #f25549;
}

.icon-hover-shell {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 10px;
  transition: background-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}

.assign-btn:hover .icon-hover-shell,
.delete-btn:hover .icon-hover-shell {
  background: #f4f7fb;
  box-shadow: 0 10px 20px rgba(148, 163, 184, 0.18);
  transform: translateY(-1px);
}

.custom-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.custom-icon svg {
  display: block;
  width: 100%;
  height: 100%;
}

.custom-icon-assign {
  width: 20px;
  height: 20px;
}

.custom-icon-delete {
  width: 20px;
  height: 20px;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.empty-state {
  text-align: center;
  padding: 84px 20px 90px;
}

.empty-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 84px;
  height: 84px;
  margin-bottom: 18px;
  border-radius: 24px;
  background: #f4f7fb;
  color: #8ea0b6;
  font-size: 38px;
}

.empty-text {
  font-size: 16px;
  color: #8a99ad;
  font-weight: 600;
}

.assign-hint {
  margin-bottom: 16px;
  color: #6e7d90;
  line-height: 1.5;
}

.assign-radios {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}

.pagination-wrapper {
  margin-top: auto;
  padding: 12px 18px 14px;
  display: flex;
  justify-content: flex-end;
  border-top: 1px solid #f1f5f9;
  background: linear-gradient(180deg, rgba(255,255,255,0.7), #ffffff);
  border-radius: 0 0 18px 18px;
}

:deep(.pagination-wrapper .btn-prev),
:deep(.pagination-wrapper .btn-next),
:deep(.pagination-wrapper .el-pager li) {
  min-width: 30px;
  height: 30px;
  margin: 0 2px;
  border-radius: 8px;
  border: 0;
  background: transparent;
  color: #7a8798;
  box-shadow: none;
  font-size: 13px;
  font-weight: 650;
}

:deep(.pagination-wrapper .btn-prev:hover),
:deep(.pagination-wrapper .btn-next:hover),
:deep(.pagination-wrapper .el-pager li:hover) {
  background: #f3f6fa;
  color: #1f2937;
}

:deep(.pagination-wrapper .el-pager li.is-active) {
  background: transparent;
  color: #1f2937;
  box-shadow: inset 0 -2px 0 #1f2937;
}

.error-alert {
  margin-top: 20px;
  padding: 18px 22px;
  border-radius: 18px;
  display: flex;
  align-items: center;
  gap: 14px;
  border: 1px solid #f7d3d0;
  background: #fff6f5;
}

.error-icon {
  font-size: 22px;
  color: #d65a51;
}

.error-text {
  color: #bf4a43;
  font-weight: 500;
  flex: 1;
}

/* 响应式设计 */
@media (max-width: 1400px) {
  .filter-row {
    flex-wrap: wrap;
  }

  .toolbar-actions {
    flex-basis: 100%;
    justify-content: flex-start;
  }

  .advanced-filter-bar {
    flex-direction: column;
    align-items: stretch;
  }

  .advanced-filter-actions {
    justify-content: flex-start;
  }
}

@media (max-width: 992px) {
  .filter-row {
    flex-direction: column;
    align-items: stretch;
  }

  .quick-filters {
    width: 100%;
  }

  .toolbar-actions {
    width: 100%;
    justify-content: flex-end;
  }

  .advanced-filter-grid {
    grid-template-columns: 1fr 1fr;
  }

  .advanced-filter-actions {
    width: 100%;
    flex-wrap: wrap;
  }
}

@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
  
  .page-title {
    font-size: 24px;
  }
  
  .filter-section {
    padding: 18px;
  }
  
  .quick-filters {
    gap: 8px;
  }
  
  .quick-filter-btn {
    flex: 1;
    justify-content: center;
    min-width: calc(50% - 4px);
    min-height: 44px;
    padding: 0 12px;
    font-size: 13px;
  }
  
  .filter-icon {
    font-size: 14px;
  }

  .advanced-filter-grid {
    grid-template-columns: 1fr;
  }

  .advanced-filter-actions,
  .toolbar-actions {
    flex-direction: column;
    gap: 8px;
  }

  .filter-btn {
    width: 100%;
    justify-content: center;
    min-height: 42px;
  }
  
  .table-section {
    padding-top: 10px;
  }
  
  .leads-table {
    font-size: 13px;
  }
  
  .leads-table thead th,
  .leads-table tbody td {
    padding: 14px 12px;
  }
  
}
</style>
