<template>
  <div class="leads-view">
    <!-- 页面标题 -->
    <div class="page-header">
      <h1 class="page-title">📋 {{ t('leads.title') }}</h1>
      <div class="header-actions">
        <span class="total-count">{{ t('leads.totalCount', { count: total }) }}</span>
      </div>
    </div>

    <!-- 快捷筛选按钮和搜索框 -->
    <div class="filter-section glass">
      <div class="filter-row">
        <!-- 快捷筛选按钮组 -->
        <div class="quick-filters">
          <button 
            class="quick-filter-btn" 
            :class="{ active: isAllLeadsFilterActive() }"
            @click="quickFilter('all')"
          >
            <span class="filter-icon">📋</span>
            <span>{{ t('leads.allLeads') }}</span>
          </button>
          <button 
            class="quick-filter-btn" 
            :class="{ active: filters.high_intent_only }"
            @click="quickFilter('high_intent')"
          >
            <span class="filter-icon">🔥</span>
            <span>{{ t('leads.highIntent') }}</span>
          </button>
          <button 
            class="quick-filter-btn" 
            :class="{ active: filters.manual_callback_only }"
            @click="quickFilter('manual_callback')"
          >
            <span class="filter-icon">⚠️</span>
            <span>{{ t('leads.manualCallback') }}</span>
          </button>
          <button 
            class="quick-filter-btn" 
            :class="{ active: filters.wecom_status === 'added' }"
            @click="quickFilter('wecom_added')"
          >
            <span class="filter-icon">✅</span>
            <span>{{ t('leads.wecomAddedFilter') }}</span>
          </button>
          <button 
            class="quick-filter-btn" 
            :class="{ active: filters.wecom_status === 'not_added' }"
            @click="quickFilter('wecom_not_added')"
          >
            <span class="filter-icon">📱</span>
            <span>{{ t('leads.wecomNotAddedFilter') }}</span>
          </button>
        </div>

        <!-- 搜索区域 -->
        <div class="search-area">
          <el-input
            v-model="localFilters.search"
            :placeholder="'🔍 ' + t('leads.searchPlaceholder')"
            class="search-input"
            clearable
            @keyup.enter="applyFilters"
          />
          <button class="filter-btn primary" @click="applyFilters">
            <span class="btn-icon">🔍</span>
            <span>{{ t('common.search') }}</span>
          </button>
          <button class="filter-btn secondary" @click="resetFilters">
            <span class="btn-icon">🔄</span>
            <span>{{ t('common.reset') }}</span>
          </button>
          <button class="filter-btn primary" @click="handleExport" :disabled="exporting">
            <span class="btn-icon">⬇️</span>
            <span>{{ exporting ? t('leads.exportingExcel') : t('leads.exportExcel') }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- 表格区域 -->
    <div class="table-section glass" v-loading="loading">
      <div class="table-wrapper">
        <table class="leads-table">
          <thead>
            <tr>
              <th>{{ t('leads.parentName') }}</th>
              <th>{{ t('leads.contact') }}</th>
              <th>{{ t('leads.intendedCampus') }}</th>
              <th>{{ t('leads.wecomStatus') }}</th>
              <th>{{ t('leads.wecomNickname') }}</th>
              <th>{{ t('leads.followUpOwner') }}</th>
              <th class="summary-col">{{ t('leads.aiSummary') }}</th>
              <th>{{ t('leads.actions') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="lead in leads" :key="lead.id" class="table-row">
              <td>
                <div class="name-cell">
                  <span class="avatar">👤</span>
                  <span>{{ lead.display_name || lead.parent_name || t('leads.notIdentified') }}</span>
                </div>
              </td>
              <td>{{ lead.display_phone || lead.parent_phone || t('leads.notProvided') }}</td>
              <td>
                <span class="campus-tag">{{ getCampusText(lead.campus) }}</span>
              </td>
              <td>
                <span
                  class="status-badge"
                  :class="getWecomStatusClass(lead.wecom_status)"
                >
                  {{ getWecomStatusText(lead.wecom_status) }}
                </span>
              </td>
              <td>
                {{ lead.wecom_contact_name || t('leads.wecomNicknameNone') }}
              </td>
              <td>
                {{ getOwnerName(lead) }}
              </td>
              <td class="summary-col">
                <div class="summary-text">{{ getSummaryText(lead) }}</div>
              </td>
              <td>
                <div class="action-buttons">
                  <button class="action-btn view-btn" @click="viewDetails(lead.id)">
                    {{ t('common.view') }}
                  </button>
                  <button class="action-btn assign-btn" @click="openAssignDialog(lead)">
                    {{ t('leads.assign') }}
                  </button>
                  <button class="action-btn delete-btn" @click="handleDelete(lead.id)">
                    {{ t('common.delete') }}
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>

        <!-- 空状态 -->
        <div v-if="!loading && leads.length === 0" class="empty-state">
          <div class="empty-icon">📭</div>
          <div class="empty-text">{{ t('leads.noData') }}</div>
        </div>
      </div>

      <!-- 分页 -->
      <div v-if="total > 0" class="pagination-wrapper">
        <el-pagination
          background
          layout="prev, pager, next"
          :total="total"
          :page-size="filters.page_size"
          :current-page="filters.page"
          @current-change="handlePageChange"
        />
      </div>
    </div>

    <!-- 错误提示 -->
    <div v-if="error" class="error-alert glass">
      <div class="error-icon">⚠️</div>
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
import { onMounted, reactive, watch, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { storeToRefs } from 'pinia';
import { useLeadStore } from '@/stores/lead';
import { useI18n } from 'vue-i18n';
import type { LeadListItem, WecomStatus } from '@/types';
import { ElMessage } from 'element-plus';
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
});

const assignDialogVisible = ref(false);
const selectedTeacherId = ref<string | null>(null);
const assignTargetLead = ref<LeadListItem | null>(null);
const exporting = ref(false);
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
  && !filters.value.wecom_status
);

const applyFilters = () => {
  void leadStore.setFilters({
    search: localFilters.search,
    high_intent_only: filters.value.high_intent_only,
    manual_callback_only: filters.value.manual_callback_only,
    appointment_status: filters.value.appointment_status,
    wecom_status: filters.value.wecom_status,
  });
};

const resetFilters = () => {
  localFilters.search = '';
  
  void leadStore.setFilters({
    search: '',
    high_intent_only: undefined,
    manual_callback_only: undefined,
    appointment_status: undefined,
    wecom_status: undefined,
  });
};

const quickFilter = (type: string) => {
  // 重置搜索
  localFilters.search = '';
  
  switch (type) {
    case 'all':
      void leadStore.setFilters({
        search: '',
        high_intent_only: undefined,
        manual_callback_only: undefined,
        appointment_status: undefined,
        wecom_status: undefined,
      });
      break;
    case 'high_intent':
      void leadStore.setFilters({
        search: '',
        high_intent_only: true,
        manual_callback_only: undefined,
        appointment_status: undefined,
        wecom_status: undefined,
      });
      break;
    case 'manual_callback':
      void leadStore.setFilters({
        search: '',
        high_intent_only: undefined,
        manual_callback_only: true,
        appointment_status: undefined,
        wecom_status: undefined,
      });
      break;
    case 'pending_appointment':
      void leadStore.setFilters({
        search: '',
        high_intent_only: undefined,
        manual_callback_only: undefined,
        appointment_status: 'pending',
        wecom_status: undefined,
      });
      break;
    case 'confirmed_appointment':
      void leadStore.setFilters({
        search: '',
        high_intent_only: undefined,
        manual_callback_only: undefined,
        appointment_status: 'confirmed',
        wecom_status: undefined,
      });
      break;
    case 'wecom_added':
      void leadStore.setFilters({
        search: '',
        high_intent_only: undefined,
        manual_callback_only: undefined,
        appointment_status: undefined,
        wecom_status: 'added',
      });
      break;
    case 'wecom_not_added':
      void leadStore.setFilters({
        search: '',
        high_intent_only: undefined,
        manual_callback_only: undefined,
        appointment_status: undefined,
        wecom_status: 'not_added',
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

const getWecomStatusClass = (status: string | null | undefined) => {
  switch (status) {
    case 'added':
      return 'status-success';
    case 'pending':
      return 'status-warning';
    default:
      return 'status-danger';
  }
};

const getWecomStatusText = (status: string | null | undefined) => {
  switch (status) {
    case 'added':
      return t('leads.statusAdded');
    case 'pending':
      return t('leads.statusPendingBind');
    default:
      return t('leads.statusNotAdded');
  }
};

const getCampusText = (campus: string | null | undefined) => {
  switch (campus) {
    case '浦东':
    case 'Pudong':
      return t('leads.campusPudong');
    case '浦西':
    case 'Puxi':
      return t('leads.campusPuxi');
    case '临港':
    case 'Lingang':
      return t('leads.campusLingang');
    default:
      return t('leads.campusUnknown');
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

const getSummaryText = (lead: LeadListItem) => {
  const summary = locale.value === 'en'
    ? (lead.en_summary || lead.summary)
    : lead.summary;

  if (!summary || !summary.trim()) {
    return t('leads.noSummary');
  }
  if (summary === '暂无有效信息' || summary === 'No valid summary yet') {
    return t('leads.noSummary');
  }
  return summary;
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
  const wecomStatusQuery = route.query.wecom_status as string | undefined;
  const highIntentQuery = parseBooleanQuery(route.query.high_intent_only);
  const manualCallbackQuery = parseBooleanQuery(route.query.manual_callback_only);

  const initialFilters: Record<string, unknown> = {};

  if (appointmentStatusQuery) {
    initialFilters.appointment_status = appointmentStatusQuery;
  }
  if (wecomStatusQuery && ['added', 'not_added', 'pending'].includes(wecomStatusQuery)) {
    initialFilters.wecom_status = wecomStatusQuery as WecomStatus;
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
  () => route.query.wecom_status,
  (value) => {
    if (typeof value === 'string' && ['added', 'pending', 'not_added'].includes(value)) {
      void leadStore.setFilters({
        wecom_status: value as WecomStatus,
      });
    } else if (value === undefined) {
      void leadStore.setFilters({
        wecom_status: undefined,
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
}

/* 毛玻璃效果 */
.glass {
  background: rgba(255, 255, 255, 0.25);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.4);
  box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.1);
}

/* 页面标题 */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-title {
  font-size: 28px;
  font-weight: 700;
  color: #2c3e50;
  margin: 0;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 15px;
}

.total-count {
  font-size: 15px;
  color: rgba(44, 62, 80, 0.7);
  font-weight: 600;
  padding: 8px 18px;
  background: rgba(52, 152, 219, 0.1);
  border-radius: 12px;
}

/* 筛选区域 */
.filter-section {
  padding: 20px;
  border-radius: 15px;
  margin-bottom: 20px;
  transition: all 0.3s ease;
}

.filter-section:hover {
  background: rgba(255, 255, 255, 0.35);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.15);
}

.filter-row {
  display: flex;
  gap: 15px;
  align-items: center;
  justify-content: space-between;
}

/* 快捷筛选按钮组 */
.quick-filters {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  flex: 1;
}

.quick-filter-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 18px;
  border-radius: 12px;
  border: 2px solid transparent;
  background: rgba(255, 255, 255, 0.4);
  color: rgba(44, 62, 80, 0.7);
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.3s ease;
  white-space: nowrap;
}

.quick-filter-btn:hover {
  background: rgba(255, 255, 255, 0.6);
  transform: translateY(-2px);
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
}

.quick-filter-btn.active {
  background: linear-gradient(135deg, #3498db, #2980b9);
  color: white;
  border-color: rgba(52, 152, 219, 0.5);
  box-shadow: 0 4px 15px rgba(52, 152, 219, 0.3);
}

.filter-icon {
  font-size: 16px;
}

/* 搜索区域 */
.search-area {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-shrink: 0;
}

.search-input {
  width: 240px;
}

.filter-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 22px;
  border-radius: 10px;
  border: none;
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.3s ease;
  white-space: nowrap;
}

.filter-btn.primary {
  background: linear-gradient(135deg, #3498db, #2980b9);
  color: white;
}

.filter-btn.primary:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(52, 152, 219, 0.4);
}

.filter-btn.secondary {
  background: rgba(149, 165, 166, 0.15);
  color: #7f8c8d;
}

.filter-btn.secondary:hover {
  background: rgba(149, 165, 166, 0.25);
  transform: translateY(-2px);
  box-shadow: 0 4px 15px rgba(149, 165, 166, 0.2);
}

.btn-icon {
  font-size: 16px;
}

/* 表格区域 */
.table-section {
  padding: 25px;
  border-radius: 20px;
  min-height: 400px;
}

.table-wrapper {
  overflow-x: auto;
}

.leads-table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0 10px;
}

.leads-table thead th {
  padding: 15px 20px;
  text-align: left;
  font-size: 14px;
  font-weight: 600;
  color: rgba(44, 62, 80, 0.7);
  border: none;
  background: transparent;
}

.leads-table tbody tr {
  background: rgba(255, 255, 255, 0.4);
  transition: all 0.3s ease;
}

.leads-table tbody tr:hover {
  background: rgba(255, 255, 255, 0.6);
  transform: translateX(5px);
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
}

.leads-table tbody td {
  padding: 20px;
  border: none;
  color: #2c3e50;
  font-size: 14px;
}

.leads-table tbody tr td:first-child {
  border-radius: 12px 0 0 12px;
}

.leads-table tbody tr td:last-child {
  border-radius: 0 12px 12px 0;
}

/* 名称单元格 */
.name-cell {
  display: flex;
  align-items: center;
  gap: 12px;
  font-weight: 500;
}

.avatar {
  font-size: 24px;
  line-height: 1;
}

/* 校区标签 */
.campus-tag {
  padding: 6px 14px;
  border-radius: 8px;
  background: rgba(52, 152, 219, 0.15);
  color: #2980b9;
  font-size: 13px;
  font-weight: 500;
}

/* 状态标签 */
.status-badge {
  padding: 6px 14px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  display: inline-block;
}

.status-warning {
  background: rgba(241, 196, 15, 0.2);
  color: #f39c12;
}

.status-success {
  background: rgba(46, 204, 113, 0.2);
  color: #27ae60;
}

.status-info {
  background: rgba(52, 152, 219, 0.2);
  color: #2980b9;
}

.status-danger {
  background: rgba(231, 76, 60, 0.2);
  color: #c0392b;
}

/* 摘要列 */
.summary-col {
  max-width: 300px;
}

.summary-text {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.5;
  color: rgba(44, 62, 80, 0.8);
}

/* 操作按钮 */
.action-buttons {
  display: flex;
  gap: 10px;
  align-items: center;
}

.action-btn {
  padding: 8px 18px;
  border-radius: 10px;
  border: none;
  font-weight: 600;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.3s ease;
  white-space: nowrap;
}

.view-btn {
  background: rgba(52, 152, 219, 0.15);
  color: #2980b9;
}

.view-btn:hover {
  background: rgba(52, 152, 219, 0.25);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(52, 152, 219, 0.3);
}

.assign-btn {
  background: rgba(52, 73, 94, 0.12);
  color: #34495e;
}

.assign-btn:hover {
  background: rgba(52, 73, 94, 0.2);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(52, 73, 94, 0.25);
}

.delete-btn {
  background: rgba(231, 76, 60, 0.15);
  color: #c0392b;
}

.delete-btn:hover {
  background: rgba(231, 76, 60, 0.25);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(231, 76, 60, 0.3);
}

/* 空状态 */
.empty-state {
  text-align: center;
  padding: 60px 20px;
}

.empty-icon {
  font-size: 64px;
  margin-bottom: 20px;
  opacity: 0.6;
}

.empty-text {
  font-size: 16px;
  color: rgba(44, 62, 80, 0.6);
  font-weight: 500;
}

.assign-hint {
  margin-bottom: 16px;
  color: rgba(44, 62, 80, 0.7);
  line-height: 1.5;
}

.assign-radios {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}

/* 分页 */
.pagination-wrapper {
  margin-top: 25px;
  display: flex;
  justify-content: flex-end;
}

/* 错误提示 */
.error-alert {
  margin-top: 20px;
  padding: 20px 25px;
  border-radius: 15px;
  display: flex;
  align-items: center;
  gap: 15px;
  border-left: 4px solid #e74c3c;
}

.error-icon {
  font-size: 24px;
}

.error-text {
  color: #c0392b;
  font-weight: 500;
  flex: 1;
}

/* 响应式设计 */
@media (max-width: 1400px) {
  .filter-row {
    flex-wrap: wrap;
  }
  
  .search-area {
    flex-basis: 100%;
    justify-content: flex-end;
    margin-top: 10px;
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
  
  .search-area {
    width: 100%;
    margin-top: 10px;
  }
  
  .search-input {
    flex: 1;
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
    padding: 15px;
  }
  
  .quick-filters {
    gap: 8px;
  }
  
  .quick-filter-btn {
    flex: 1;
    justify-content: center;
    min-width: calc(50% - 4px);
    padding: 10px 12px;
    font-size: 13px;
  }
  
  .filter-icon {
    font-size: 14px;
  }
  
  .search-area {
    flex-direction: column;
    gap: 8px;
  }
  
  .search-input {
    width: 100%;
  }
  
  .filter-btn {
    width: 100%;
    justify-content: center;
  }
  
  .table-section {
    padding: 15px;
  }
  
  .leads-table {
    font-size: 13px;
  }
  
  .leads-table thead th,
  .leads-table tbody td {
    padding: 12px;
  }
  
  .summary-col {
    display: none;
  }
}
</style>
