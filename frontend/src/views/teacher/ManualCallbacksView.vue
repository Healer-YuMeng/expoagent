<template>
  <div class="callbacks-view">
    <TeacherPageHeader :title="t('teacher.layout.menu.manualCallbacks')" />

    <!-- 错误提示 -->
    <div v-if="error" class="error-alert glass">
      <div class="error-icon">⚠️</div>
      <div class="error-text">{{ error }}</div>
    </div>

    <!-- 提醒列表 -->
    <div class="callbacks-section glass" v-loading="loading">
      <div class="callbacks-toolbar">
        <button class="refresh-btn glass" @click="reload">
          <span class="btn-icon">🔄</span>
          <span>{{ t('teacher.reminders.refresh') }}</span>
        </button>
      </div>

      <div v-if="!loading && callbacks.length === 0" class="empty-state">
        <div class="empty-icon">✅</div>
        <div class="empty-text">{{ t('teacher.reminders.emptyState') }}</div>
      </div>

      <div v-else class="callbacks-list">
        <div
          v-for="callback in callbacks"
          :key="callback.conversation_id"
          class="callback-item glass-item"
        >
          <div class="callback-content">
            <div class="callback-icon">🔔</div>
            <div class="callback-info">
              <div class="parent-text">{{ callback.parent_name || '未提供姓名' }}</div>
              <div class="query-text">{{ callback.query }}</div>
            </div>
          </div>
          <div class="action-buttons">
            <button class="action-btn view-btn" @click="viewCallback(callback)">
              {{ t('teacher.reminders.view') }}
            </button>
            <button class="action-btn delete-btn" @click="handleDelete(callback.conversation_id)">
              {{ t('teacher.reminders.delete') }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { getManualCallbacks, deleteManualCallback } from '@/api/teacher';
import type { ManualCallbackItem } from '@/types';
import { ElMessage } from 'element-plus';
import { useAuthStore } from '@/stores/auth';
import { getPortalConversationPath, getPortalLeadDetailPath } from '@/router/portalRoutes';
import { useFeatureGateBootstrap } from '@/composables/useFeatureGateBootstrap';
import TeacherPageHeader from '@/components/TeacherPageHeader.vue';

const { t } = useI18n();
useFeatureGateBootstrap();

const callbacks = ref<ManualCallbackItem[]>([]);
const loading = ref(false);
const error = ref<string | null>(null);
const router = useRouter();
const authStore = useAuthStore();

async function fetchCallbacks() {
  loading.value = true;
  error.value = null;
  try {
    const response = await getManualCallbacks();
    callbacks.value = response.items;
  } catch (e) {
    error.value = t('teacher.reminders.errorLoading');
    console.error(e);
  }
  loading.value = false;
}

function viewCallback(callback: ManualCallbackItem) {
  if (callback.lead_id) {
    router.push(getPortalLeadDetailPath(authStore.userRole, callback.lead_id));
    return;
  }

  router.push(getPortalConversationPath(authStore.userRole, callback.conversation_id));
}

async function handleDelete(conversationId: string) {
  try {
    await deleteManualCallback(conversationId);
    ElMessage.success(t('teacher.reminders.deleteSuccess'));
    await fetchCallbacks(); // 刷新列表
  } catch (e) {
    ElMessage.error(t('teacher.reminders.deleteError'));
    console.error(e);
  }
}

function reload() {
  void fetchCallbacks();
}

onMounted(() => {
  void fetchCallbacks();
});
</script>

<style scoped>
.callbacks-view {
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

.glass-item {
  background: rgba(255, 255, 255, 0.4);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.5);
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.08);
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

.refresh-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 24px;
  border-radius: 12px;
  border: none;
  color: #2c3e50;
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.refresh-btn:hover {
  background: rgba(255, 255, 255, 0.4);
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.15);
}

.btn-icon {
  font-size: 16px;
}

/* 错误提示 */
.error-alert {
  margin-bottom: 20px;
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

/* 提醒列表区域 */
.callbacks-section {
  padding: 30px;
  border-radius: 20px;
  min-height: 400px;
}

.callbacks-toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 18px;
}

.callbacks-list {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

/* 提醒项 */
.callback-item {
  padding: 25px;
  border-radius: 15px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
  transition: all 0.3s ease;
}

.callback-item:hover {
  background: rgba(255, 255, 255, 0.5);
  transform: translateX(5px);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.12);
}

.callback-content {
  flex: 1;
  display: flex;
  align-items: flex-start;
  gap: 20px;
}

.callback-icon {
  font-size: 32px;
  line-height: 1;
  flex-shrink: 0;
}

.callback-info {
  flex: 1;
}

.parent-text {
  font-size: 15px;
  font-weight: 700;
  color: #1f2f49;
  margin-bottom: 6px;
}

.query-text {
  font-size: 14px;
  color: rgba(44, 62, 80, 0.7);
  line-height: 1.6;
}

/* 操作按钮 */
.action-buttons {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-shrink: 0;
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
  padding: 80px 20px;
}

.empty-icon {
  font-size: 72px;
  margin-bottom: 20px;
  opacity: 0.6;
}

.empty-text {
  font-size: 18px;
  color: rgba(44, 62, 80, 0.6);
  font-weight: 500;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 15px;
  }

  .page-title {
    font-size: 24px;
  }

  .refresh-btn {
    width: 100%;
    justify-content: center;
  }

  .callbacks-section {
    padding: 20px;
  }

  .callback-item {
    flex-direction: column;
    align-items: flex-start;
    padding: 20px;
  }

  .callback-content {
    gap: 15px;
  }

  .callback-icon {
    font-size: 28px;
  }

  .query-text {
    font-size: 13px;
  }

  .action-buttons {
    width: 100%;
    flex-direction: column;
  }

  .action-btn {
    width: 100%;
    justify-content: center;
  }
}
</style>
