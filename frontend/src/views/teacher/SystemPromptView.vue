<template>
  <div class="prompt-view">
    <TeacherPageHeader :title="t('teacher.layout.menu.systemPrompt')" />

    <section class="card section-card welcome-card">
      <div class="section-header welcome-toolbar">
        <div class="welcome-title-row">
          <h2 class="section-title">AI首句欢迎语设置</h2>
          <span class="welcome-badge">对话开场</span>
        </div>

        <div class="welcome-toolbar-actions">
          <template v-if="welcomeEditing">
            <button class="welcome-save-btn" @click="handleSaveWelcomeMessage" :disabled="welcomeSaving">
              <span class="welcome-save-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none">
                  <path d="M6 3.5H15.8L19.5 7.2V20.5H6V3.5Z" stroke="currentColor" stroke-width="2" stroke-linejoin="round" />
                  <path d="M9 3.5V9H15V3.5" stroke="currentColor" stroke-width="2" stroke-linejoin="round" />
                  <path d="M9 20.5V14H16.5V20.5" stroke="currentColor" stroke-width="2" stroke-linejoin="round" />
                </svg>
              </span>
              <span v-if="welcomeSaving">保存中...</span>
              <span v-else>保存</span>
            </button>
            <button class="welcome-reset-btn" @click="handleResetWelcomeMessage" :disabled="welcomeSaving">
              <el-icon class="welcome-action-icon"><RefreshRight /></el-icon>
              <span>重置</span>
            </button>
          </template>
          <template v-else>
            <button class="welcome-edit-btn" @click="startEditWelcomeMessage" :disabled="welcomeLoading || welcomeSaving">
              编辑
            </button>
            <button class="welcome-reset-btn" @click="handleResetWelcomeMessage" :disabled="welcomeLoading || welcomeSaving">
              <el-icon class="welcome-action-icon"><RefreshRight /></el-icon>
              <span>重置</span>
            </button>
          </template>
        </div>
      </div>

      <div class="welcome-panel" :class="{ editing: welcomeEditing }">
        <template v-if="welcomeEditing">
          <textarea
            v-model="welcomeMessageDraft"
            class="welcome-input"
            :disabled="welcomeLoading || welcomeSaving"
            rows="6"
            :placeholder="DEFAULT_WELCOME_MESSAGE"
          />
        </template>
        <template v-else>
          <p class="welcome-preview">{{ welcomeMessage || DEFAULT_WELCOME_MESSAGE }}</p>
        </template>
      </div>
    </section>

    <section class="card section-card">
      <div class="section-header">
        <div>
          <h2 class="section-title">知识库和助手配置</h2>
          <p class="section-subtitle">为不同助手绑定专属知识库，并维护各自的系统提示词。</p>
        </div>
      </div>

      <div class="meta-row" v-if="authRole === 'super_admin'">
        <label>
          选择学校
          <select v-model="schoolId">
            <option value="">请选择学校</option>
            <option v-for="s in schools" :key="s.id" :value="s.id">{{ s.name }}</option>
          </select>
        </label>
      </div>

      <div class="assistant-row assistant-row--assistant">
        <label class="field grow">
          新建助手
          <div class="inline-row">
            <input
              v-model="newAssistantName"
              type="text"
              placeholder="例如：售前咨询助手"
              :disabled="!effectiveSchoolId || creatingAssistant"
              @keyup.enter="handleCreateAssistant"
            />
            <button class="ghost" @click="handleCreateAssistant" :disabled="!effectiveSchoolId || creatingAssistant || !newAssistantName.trim()">
              <span v-if="creatingAssistant">创建中...</span>
              <span v-else>新建助手</span>
            </button>
          </div>
        </label>

        <label class="field grow">
          选择助手
          <el-select
            v-model="selectedAssistantId"
            class="assistant-select"
            placeholder="请选择助手"
            :disabled="!effectiveSchoolId || loadingAssistants"
          >
            <el-option
              v-for="assistant in assistants"
              :key="assistant.id"
              :label="assistant.name"
              :value="assistant.id"
            />
          </el-select>
        </label>
      </div>

      <div class="assistant-row assistant-row--knowledge">
        <label class="field grow knowledge-field">
          <div class="field-title-row">
            <span>专属知识库</span>
            <span class="knowledge-inline-meta">当前状态：{{ isDefault ? '默认模板' : '自定义生效' }}</span>
            <span v-if="currentKnowledgeBaseNames" class="knowledge-inline-meta">当前知识库：{{ currentKnowledgeBaseNames }}</span>
            <span v-if="version" class="knowledge-inline-meta">版本：{{ version }}</span>
            <span v-if="updatedBy" class="knowledge-inline-meta">更新人：{{ updatedBy }}</span>
            <span v-if="updatedAt" class="knowledge-inline-meta">更新时间：{{ updatedAt }}</span>
          </div>
          <div class="inline-row">
            <el-select
              v-model="selectedKnowledgeBaseIds"
              class="knowledge-base-select"
              multiple
              filterable
              clearable
              collapse-tags
              collapse-tags-tooltip
              placeholder="请选择一个或多个知识库"
              no-data-text="暂无知识库"
              :disabled="!selectedAssistantId || bindingKnowledgeBase"
              >
              <el-option
                v-for="kb in knowledgeBases"
                :key="kb.id"
                :label="`${kb.name} (${kb.doc_count || 0} 篇)`"
                :value="kb.id"
              />
            </el-select>
            <span class="bind-button-wrapper" :title="bindKnowledgeBaseTooltip">
              <button
                class="ghost"
                :class="{ 'bind-success': knowledgeBaseBindSuccess }"
                @click="handleBindKnowledgeBase"
                :disabled="isBindKnowledgeBaseButtonDisabled"
              >
                <span>{{ bindKnowledgeBaseButtonText }}</span>
              </button>
            </span>
          </div>
        </label>
      </div>

      <div class="prompt-section-header">
        <h3 class="prompt-section-title">模型人设提示词配置</h3>
        <div class="prompt-actions">
          <button class="prompt-action-btn" @click="resetToDefault" :disabled="loading || saving || !selectedAssistantId">
            默认提示词
          </button>
          <button class="prompt-action-btn prompt-action-btn--save" @click="handleSave" :disabled="saving || !selectedAssistantId">
            <span v-if="saving">保存中...</span>
            <span v-else>保存</span>
          </button>
        </div>
      </div>

      <textarea
        v-model="content"
        class="prompt-input"
        :placeholder="placeholder"
        :disabled="loading || !selectedAssistantId"
        rows="20"
      />
      <p v-if="!selectedAssistantId" class="empty-hint">请先选择或创建一个助手，再绑定知识库并编辑提示词。</p>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { ElMessage } from 'element-plus';
import { RefreshRight } from '@element-plus/icons-vue';
import { useI18n } from 'vue-i18n';
import {
  createAssistant,
  getWelcomeMessage,
  getSystemPrompt,
  listAssistants,
  listKnowledgeBases,
  listManagedUsers,
  updateAssistant,
  updateSystemPrompt,
  updateWelcomeMessage,
  type AssistantItem,
  type KnowledgeBaseItem,
  type PromptResponse,
} from '@/api/teacher';
import TeacherPageHeader from '@/components/TeacherPageHeader.vue';
import { useAuthStore } from '@/stores/auth';
import { formatChinaDateTime } from '@/utils/time';
import { useFeatureGateBootstrap } from '@/composables/useFeatureGateBootstrap';

const authStore = useAuthStore();
useFeatureGateBootstrap();
const { t } = useI18n();
const authRole = computed(() => authStore.userRole);
const effectiveSchoolId = computed(() => {
  if (authRole.value === 'admin') {
    return authStore.user?.school_id || '';
  }
  return schoolId.value;
});

const loading = ref(false);
const saving = ref(false);
const loadingAssistants = ref(false);
const creatingAssistant = ref(false);
const bindingKnowledgeBase = ref(false);
const knowledgeBaseBindSuccess = ref(false);
const welcomeLoading = ref(false);
const welcomeSaving = ref(false);

const content = ref('');
const defaultContent = ref('');
const isDefault = ref(false);
const version = ref<number | null>(null);
const updatedAt = ref<string | null>(null);
const updatedBy = ref<string | null>(null);
const welcomeMessage = ref('');
const welcomeMessageDraft = ref('');
const welcomeEditing = ref(false);
const DEFAULT_WELCOME_MESSAGE = '配置访客初次进入聊天时看到的欢迎语。';

const schoolId = ref('');
const schools = ref<{ id: string; name: string }[]>([]);

const assistants = ref<AssistantItem[]>([]);
const selectedAssistantId = ref('');
const newAssistantName = ref('');

const knowledgeBases = ref<KnowledgeBaseItem[]>([]);
const selectedKnowledgeBaseIds = ref<string[]>([]);
let knowledgeBaseBindSuccessTimer: ReturnType<typeof setTimeout> | null = null;
const FALLBACK_DEFAULT_PROMPT = `你是一名专业、自然、简洁的通用智能助手。

你的目标：
1. 优先基于知识库回答用户问题；
2. 在自然对话中收集两个关键信息：parent_name、phone；
3. 如果知识库没有明确答案，可以坦诚说明当前资料不足，并在合适时机自然询问手机号。

行为要求：
- 回答必须自然、口语化，不要像表单。
- 每轮尽量只推进一个问题。
- 没有拿到姓名时，可以自然询问如何称呼对方。
- 没有拿到手机号时，可以自然询问联系电话。
- 不要主动收集校区、年龄、国籍、预约、邮箱等无关字段。
- 如果知识库已命中，优先回答问题本身，再决定是否继续收集信息。
- 仅输出纯文本，不要输出 Markdown。

知识库参考：
{context}`;

const placeholder = '在此编辑该助手的系统提示词。建议写清楚角色、回答风格、知识库使用规则，以及只需采集 parent_name 和 phone。';

const selectedAssistant = computed(() => {
  return assistants.value.find((item) => item.id === selectedAssistantId.value) || null;
});

const currentKnowledgeBaseNames = computed(() => {
  if (!selectedKnowledgeBaseIds.value.length) return '';
  const selectedIds = new Set(selectedKnowledgeBaseIds.value);
  return knowledgeBases.value
    .filter((item) => selectedIds.has(item.id))
    .map((item) => item.name)
    .join('、');
});

const hasSelectedKnowledgeBase = computed(() => selectedKnowledgeBaseIds.value.length > 0);

const isBindKnowledgeBaseButtonDisabled = computed(() => {
  return !selectedAssistantId.value || bindingKnowledgeBase.value || !hasSelectedKnowledgeBase.value;
});

const bindKnowledgeBaseButtonText = computed(() => {
  if (bindingKnowledgeBase.value) return '保存中...';
  if (knowledgeBaseBindSuccess.value) return '绑定成功';
  return '保存绑定';
});

const bindKnowledgeBaseTooltip = computed(() => {
  if (!selectedAssistantId.value) return '请先选择助手';
  if (!hasSelectedKnowledgeBase.value) return '请先选择知识库';
  return '';
});

const clearKnowledgeBaseBindSuccessTimer = () => {
  if (knowledgeBaseBindSuccessTimer) {
    clearTimeout(knowledgeBaseBindSuccessTimer);
    knowledgeBaseBindSuccessTimer = null;
  }
};

const setKnowledgeBaseBindSuccessState = () => {
  clearKnowledgeBaseBindSuccessTimer();
  knowledgeBaseBindSuccess.value = true;
  knowledgeBaseBindSuccessTimer = setTimeout(() => {
    knowledgeBaseBindSuccess.value = false;
    knowledgeBaseBindSuccessTimer = null;
  }, 3000);
};

const resetPromptState = () => {
  content.value = '';
  defaultContent.value = FALLBACK_DEFAULT_PROMPT;
  isDefault.value = false;
  version.value = null;
  updatedAt.value = null;
  updatedBy.value = null;
};

const loadPrompt = async () => {
  if (!selectedAssistantId.value) {
    resetPromptState();
    return;
  }
  loading.value = true;
  try {
    const res: PromptResponse = await getSystemPrompt(undefined, effectiveSchoolId.value || undefined, selectedAssistantId.value);
    content.value = res.content || '';
    defaultContent.value = res.default_content || FALLBACK_DEFAULT_PROMPT;
    isDefault.value = !!res.is_default;
    version.value = res.version ?? null;
    updatedAt.value = formatChinaDateTime(res.updated_at) || null;
    updatedBy.value = res.updated_by || null;
  } catch (err) {
    console.error(err);
    ElMessage.error('加载提示词失败');
  } finally {
    loading.value = false;
  }
};

const loadAssistants = async () => {
  if (!effectiveSchoolId.value) {
    assistants.value = [];
    selectedAssistantId.value = '';
    return;
  }
  loadingAssistants.value = true;
  try {
    const res = await listAssistants(effectiveSchoolId.value);
    assistants.value = res.items || [];
    if (selectedAssistantId.value && !assistants.value.some((item) => item.id === selectedAssistantId.value)) {
      selectedAssistantId.value = '';
    }
    if (!selectedAssistantId.value && assistants.value.length > 0) {
      selectedAssistantId.value = assistants.value[0]?.id || '';
    }
  } catch (err) {
    console.error(err);
    ElMessage.error('加载助手列表失败');
  } finally {
    loadingAssistants.value = false;
  }
};

const loadKnowledgeBases = async () => {
  if (!effectiveSchoolId.value) {
    knowledgeBases.value = [];
    selectedKnowledgeBaseIds.value = [];
    return;
  }
  try {
    const res = await listKnowledgeBases(effectiveSchoolId.value || undefined);
    knowledgeBases.value = res.items || [];
  } catch (err) {
    console.error(err);
    ElMessage.error('加载知识库列表失败');
  }
};

const handleCreateAssistant = async () => {
  const name = newAssistantName.value.trim();
  if (!name || !effectiveSchoolId.value) return;
  creatingAssistant.value = true;
  try {
    const assistant = await createAssistant({
      name,
      school_id: authRole.value === 'super_admin' ? effectiveSchoolId.value : undefined,
    });
    ElMessage.success('助手已创建');
    newAssistantName.value = '';
    await loadAssistants();
    selectedAssistantId.value = assistant.id;
  } catch (err: any) {
    console.error(err);
    ElMessage.error(err?.response?.data?.detail || '创建助手失败');
  } finally {
    creatingAssistant.value = false;
  }
};

const handleBindKnowledgeBase = async () => {
  if (!selectedAssistantId.value || !hasSelectedKnowledgeBase.value) return;
  bindingKnowledgeBase.value = true;
  try {
    const updated = await updateAssistant(selectedAssistantId.value, {
      knowledge_base_ids: selectedKnowledgeBaseIds.value,
    });
    assistants.value = assistants.value.map((item) => item.id === updated.id ? updated : item);
    setKnowledgeBaseBindSuccessState();
    ElMessage.success('知识库绑定已保存');
  } catch (err: any) {
    console.error(err);
    ElMessage.error(err?.response?.data?.detail || '保存知识库绑定失败');
  } finally {
    bindingKnowledgeBase.value = false;
  }
};

const handleSave = async () => {
  const trimmed = content.value.trim();
  if (!selectedAssistantId.value || !trimmed) {
    ElMessage.warning('请先选择助手并填写提示词');
    return;
  }
  saving.value = true;
  try {
    const res = await updateSystemPrompt({
      content: trimmed,
      school_id: effectiveSchoolId.value || undefined,
      assistant_id: selectedAssistantId.value,
    });
    content.value = res.content || trimmed;
    isDefault.value = !!res.is_default;
    version.value = res.version ?? null;
    updatedAt.value = formatChinaDateTime(res.updated_at) || null;
    updatedBy.value = res.updated_by || null;
    ElMessage.success('提示词已保存并生效');
  } catch (err) {
    console.error(err);
    ElMessage.error('保存失败');
  } finally {
    saving.value = false;
  }
};

const loadWelcomeMessage = async () => {
  welcomeLoading.value = true;
  try {
    const response = await getWelcomeMessage();
    welcomeMessage.value = response.messages?.['zh-CN'] || '';
    welcomeMessageDraft.value = welcomeMessage.value;
  } catch (err) {
    console.error(err);
    ElMessage.error('加载欢迎语失败');
  } finally {
    welcomeLoading.value = false;
  }
};

const startEditWelcomeMessage = () => {
  welcomeMessageDraft.value = welcomeMessage.value || DEFAULT_WELCOME_MESSAGE;
  welcomeEditing.value = true;
};

const handleSaveWelcomeMessage = async () => {
  const trimmed = welcomeMessageDraft.value.trim();
  if (!trimmed) {
    ElMessage.warning('请填写中文欢迎语');
    return;
  }

  welcomeSaving.value = true;
  try {
    const response = await updateWelcomeMessage({
      messages: {
        'zh-CN': trimmed,
      },
    });
    welcomeMessage.value = response.messages?.['zh-CN'] || trimmed;
    welcomeMessageDraft.value = welcomeMessage.value;
    welcomeEditing.value = false;
    ElMessage.success('欢迎语已保存');
  } catch (err: any) {
    console.error(err);
    ElMessage.error(err?.response?.data?.detail || '保存欢迎语失败');
  } finally {
    welcomeSaving.value = false;
  }
};

const handleResetWelcomeMessage = () => {
  welcomeMessageDraft.value = DEFAULT_WELCOME_MESSAGE;
  welcomeMessage.value = DEFAULT_WELCOME_MESSAGE;
  welcomeEditing.value = false;
  ElMessage.info('已恢复默认欢迎语');
};

const resetToDefault = () => {
  content.value = defaultContent.value || FALLBACK_DEFAULT_PROMPT;
  ElMessage.info('已填充默认模板，可直接保存或继续编辑');
};

watch(effectiveSchoolId, async () => {
  resetPromptState();
  selectedAssistantId.value = '';
  selectedKnowledgeBaseIds.value = [];
  await loadKnowledgeBases();
  await loadAssistants();
});

watch(selectedAssistant, async (assistant) => {
  clearKnowledgeBaseBindSuccessTimer();
  knowledgeBaseBindSuccess.value = false;
  if (assistant?.knowledge_base_ids?.length) {
    selectedKnowledgeBaseIds.value = [...assistant.knowledge_base_ids];
  } else if (assistant?.knowledge_base_id) {
    selectedKnowledgeBaseIds.value = [assistant.knowledge_base_id];
  } else {
    selectedKnowledgeBaseIds.value = [];
  }
  await loadPrompt();
});

watch(selectedKnowledgeBaseIds, () => {
  if (!knowledgeBaseBindSuccess.value) return;
  clearKnowledgeBaseBindSuccessTimer();
  knowledgeBaseBindSuccess.value = false;
});

onMounted(() => {
  void loadWelcomeMessage();
  if (authRole.value === 'super_admin') {
    void (async () => {
      try {
        const res = await listManagedUsers('admin');
        schools.value = (res.items || [])
          .filter((u) => u.school_id)
          .map((u) => ({ id: u.school_id as string, name: u.school_name || (u.school_id as string) }));
        if (!schoolId.value && schools.value.length > 0) {
          schoolId.value = schools.value[0]?.id || '';
        }
      } catch (err) {
        console.error(err);
        ElMessage.error('加载学校列表失败');
      }
    })();
  } else {
    void loadKnowledgeBases();
    void loadAssistants();
  }
});

onBeforeUnmount(() => {
  clearKnowledgeBaseBindSuccessTimer();
});
</script>

<style scoped>
.prompt-view {
  display: flex;
  flex-direction: column;
}

.prompt-view > .card + .card {
  margin-top: 24px;
}

.nav-header {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding-top: 4px;
}

.nav-title {
  margin: 0;
  font-size: 26px;
  font-weight: 700;
  color: #243246;
}

.nav-divider {
  width: 100%;
  height: 1px;
  background: #dfe7f2;
}

.knowledge-base-select {
  width: 100%;
}

.actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.actions button,
.inline-row button {
  min-height: 44px;
  border: 1px solid #d9e3ee;
  border-radius: 14px;
  padding: 0 16px;
  cursor: pointer;
  font-weight: 600;
  font-size: 14px;
  background: #ffffff;
  color: #6f8098;
  box-shadow: 0 3px 12px rgba(22, 34, 51, 0.04);
  transition: background-color 0.2s ease, border-color 0.2s ease, color 0.2s ease, box-shadow 0.2s ease;
  white-space: nowrap;
}

.actions button:hover:not(:disabled),
.inline-row button:hover:not(:disabled) {
  border-color: #c3d0e0;
  background: #f9fbfd;
  color: #42526b;
}

.ghost {
  background: #ffffff;
}

.primary {
  background: #ffffff;
  color: #6f8098;
}

.primary:hover:not(:disabled),
.ghost:hover:not(:disabled) {
  border-color: #c3d0e0;
  background: #f9fbfd;
  color: #42526b;
  box-shadow: 0 3px 12px rgba(22, 34, 51, 0.04);
}

.actions button:active:not(:disabled),
.inline-row button:active:not(:disabled),
.actions button:focus-visible:not(:disabled),
.inline-row button:focus-visible:not(:disabled) {
  border-color: #202a39;
  background: #202a39;
  color: #ffffff;
  box-shadow: 0 10px 20px rgba(32, 42, 57, 0.14);
  outline: none;
}

.actions button:disabled,
.inline-row button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  box-shadow: none;
}

.inline-row button.bind-success {
  border-color: #1fa971;
  background: #1fa971;
  color: #ffffff;
  box-shadow: 0 10px 22px rgba(31, 169, 113, 0.18);
}

.card {
  background: rgba(255, 255, 255, 0.9);
  border-radius: 26px;
  padding: 24px 28px;
  border: 1px solid rgba(214, 227, 243, 0.9);
  box-shadow: 0 6px 20px rgba(44, 62, 80, 0.08);
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.section-card {
  gap: 20px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 18px;
}

.section-title {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  color: #243246;
  line-height: 1.4;
}

.section-subtitle {
  margin: 8px 0 0;
  color: #7a8798;
  font-size: 14px;
  line-height: 1.6;
}

.meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 13px;
  color: #6c7a89;
}

.assistant-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

.assistant-row--assistant {
  align-items: end;
}

.assistant-row--knowledge {
  grid-template-columns: 1fr;
  align-items: start;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 8px;
  color: #566573;
  font-size: 13px;
  font-weight: 600;
  min-width: 0;
}

.grow {
  width: 100%;
}

.knowledge-field {
  min-width: 0;
}

.field-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.knowledge-inline-meta {
  font-size: 11px;
  font-weight: 600;
  color: #8a96a8;
  line-height: 1.4;
}

.inline-row {
  display: flex;
  gap: 10px;
  align-items: stretch;
  min-width: 0;
}

.inline-row input,
.inline-row select,
.meta-row select {
  width: 100%;
}

.inline-row input,
.inline-row :deep(.el-select) {
  flex: 1 1 auto;
  min-width: 0;
}

.inline-row button {
  flex: 0 0 120px;
}

.bind-button-wrapper {
  display: inline-flex;
  flex: 0 0 120px;
}

.inline-row :deep(.el-select) {
  width: 100%;
}

select,
input,
.prompt-input {
  min-height: 44px;
  box-sizing: border-box;
  border-radius: 14px;
  border: 1px solid #d9e3ee;
  padding: 12px;
  font-size: 14px;
  background: #ffffff;
  color: #273142;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background-color 0.2s ease;
}

select:focus,
input:focus,
.prompt-input:focus {
  outline: none;
  border-color: #243041;
  box-shadow: none;
}

select::placeholder,
input::placeholder,
.prompt-input::placeholder {
  color: #a3afbf;
}

:deep(.assistant-select .el-select__wrapper),
:deep(.knowledge-base-select .el-select__wrapper) {
  min-height: 44px;
  border-radius: 14px;
  border: 1px solid #d9e3ee;
  box-shadow: none;
  background: #ffffff;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background-color 0.2s ease;
}

.assistant-row :deep(.el-select),
.assistant-row :deep(.el-select__wrapper) {
  width: 100%;
}

:deep(.assistant-select .el-select__wrapper.is-focused),
:deep(.knowledge-base-select .el-select__wrapper.is-focused) {
  border-color: #243041;
  box-shadow: none;
}

:deep(.assistant-select .el-select__placeholder),
:deep(.assistant-select .el-select__selected-item),
:deep(.knowledge-base-select .el-select__placeholder),
:deep(.knowledge-base-select .el-select__selected-item),
:deep(.knowledge-base-select .el-tag) {
  font-size: 14px;
}

.prompt-section-header {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.prompt-section-title {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: #35465c;
  line-height: 1.5;
}

.prompt-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-left: auto;
  padding-right: 14px;
}

.prompt-action-btn {
  border: none;
  background: transparent;
  color: #8a97ab;
  font-size: 16px;
  font-weight: 700;
  line-height: 1;
  padding: 10px 14px;
  border-radius: 14px;
  cursor: pointer;
  transition: background-color 0.2s ease, color 0.2s ease;
}

.prompt-action-btn:hover:not(:disabled),
.prompt-action-btn:focus-visible:not(:disabled) {
  background: #e7ebf1;
  color: #000000;
  outline: none;
}

.prompt-action-btn:disabled {
  color: #b5bfcd;
  cursor: not-allowed;
  background: transparent;
}

.prompt-action-btn--save {
  color: #17b26a;
}

.prompt-action-btn--save:hover:not(:disabled),
.prompt-action-btn--save:focus-visible:not(:disabled) {
  background: #dff6ea;
  color: #11995b;
}

.prompt-input {
  width: 100%;
  min-height: 280px;
  font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
  resize: vertical;
  line-height: 1.7;
}

.empty-hint {
  margin: 0;
  color: #7f8c8d;
  font-size: 13px;
}

.welcome-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.welcome-toolbar-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

.welcome-title-row {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}

.welcome-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 8px 16px;
  border-radius: 999px;
  background: #eef2f7;
  color: #526277;
  font-size: 14px;
  font-weight: 700;
  line-height: 1;
}

.welcome-save-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  border: none;
  border-radius: 18px;
  padding: 12px 24px;
  background: transparent;
  color: #17b26a;
  font-size: 16px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: none;
  transition: transform 0.2s ease, box-shadow 0.2s ease, background-color 0.2s ease, color 0.2s ease;
}

.welcome-save-btn:hover:not(:disabled) {
  background: #dff6ea;
  color: #11995b;
  transform: translateY(-1px);
  box-shadow: 0 14px 28px rgba(95, 208, 154, 0.22);
}

.welcome-save-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.welcome-edit-btn,
.welcome-reset-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: none;
  border-radius: 14px;
  min-height: auto;
  padding: 10px 14px;
  background: transparent;
  color: #7c8ca2;
  font-size: 16px;
  font-weight: 700;
  cursor: pointer;
  transition: background-color 0.2s ease, color 0.2s ease, box-shadow 0.2s ease;
}

.welcome-reset-btn {
  color: #ff6b63;
}

.welcome-edit-btn:hover:not(:disabled),
.welcome-reset-btn:hover:not(:disabled) {
  background: #e2e8f0;
  color: #1f2937;
  box-shadow: 0 8px 18px rgba(31, 41, 55, 0.08);
}

.welcome-reset-btn:hover:not(:disabled) {
  background: #ffe8e6;
  color: #e0554d;
  box-shadow: 0 8px 18px rgba(255, 107, 99, 0.14);
}

.welcome-action-icon {
  font-size: 18px;
  line-height: 1;
}

.welcome-save-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  line-height: 1;
}

.welcome-save-icon svg {
  display: block;
  width: 100%;
  height: 100%;
}

.welcome-panel {
  box-sizing: border-box;
  border-radius: 22px;
  border: 1px solid #d6e3f3;
  background: #ffffff;
  box-shadow: inset 0 0 0 1px rgba(214, 227, 243, 0.25);
  padding: 22px 26px;
  height: 160px;
  overflow: hidden;
}

.welcome-panel.editing {
  padding: 18px 22px;
}

.welcome-preview {
  margin: 0;
  color: #6c7d95;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.8;
  height: 100%;
  overflow-y: auto;
  padding-right: 6px;
  box-sizing: border-box;
  white-space: pre-wrap;
}

.welcome-input {
  width: 100%;
  height: 100%;
  min-height: 0;
  border: none;
  box-shadow: none;
  padding: 0;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.8;
  color: #1f2d3d;
  background: transparent;
  overflow-y: auto;
  resize: none;
  box-sizing: border-box;
  padding-right: 6px;
}

.welcome-input:focus {
  outline: none;
}

.welcome-input::placeholder {
  color: #98a5b5;
}

@media (max-width: 960px) {
  .assistant-row {
    grid-template-columns: 1fr;
    display: grid;
  }

  .assistant-row--knowledge {
    grid-template-columns: 1fr;
  }

  .section-header {
    gap: 14px;
    flex-direction: column;
    align-items: stretch;
  }

  .actions,
  .inline-row,
  .welcome-toolbar,
  .welcome-toolbar-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .nav-title {
    font-size: 22px;
  }

  .section-title {
    font-size: 20px;
  }

  .welcome-badge {
    font-size: 14px;
  }

  .welcome-input {
    font-size: 14px;
    min-height: 120px;
  }

  .welcome-preview {
    font-size: 14px;
  }
}
</style>
