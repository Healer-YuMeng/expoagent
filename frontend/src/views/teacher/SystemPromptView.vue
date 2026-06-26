<template>
  <div class="prompt-view">
    <header class="page-header">
      <div>
        <h1 class="title">助手配置</h1>
        <p class="subtitle">为不同助手绑定专属知识库，并维护各自的系统提示词。</p>
      </div>
      <div class="actions">
        <button class="ghost" @click="resetToDefault" :disabled="loading || saving || !selectedAssistantId">
          使用默认
        </button>
        <button class="primary" @click="handleSave" :disabled="saving || !selectedAssistantId">
          <span v-if="saving">保存中...</span>
          <span v-else>保存提示词</span>
        </button>
      </div>
    </header>

    <section class="card">
      <div class="meta-row" v-if="authRole === 'super_admin'">
        <label>
          选择学校
          <select v-model="schoolId">
            <option value="">请选择学校</option>
            <option v-for="s in schools" :key="s.id" :value="s.id">{{ s.name }}</option>
          </select>
        </label>
      </div>

      <div class="assistant-row">
        <label class="field grow">
          选择助手
          <select v-model="selectedAssistantId" :disabled="!effectiveSchoolId || loadingAssistants">
            <option value="">请选择助手</option>
            <option v-for="assistant in assistants" :key="assistant.id" :value="assistant.id">
              {{ assistant.name }}
            </option>
          </select>
        </label>

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
      </div>

      <div class="assistant-row">
        <label class="field grow">
          专属知识库
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
            <button class="ghost" @click="handleBindKnowledgeBase" :disabled="!selectedAssistantId || bindingKnowledgeBase">
              <span v-if="bindingKnowledgeBase">保存中...</span>
              <span v-else>保存绑定</span>
            </button>
          </div>
        </label>
      </div>

      <div class="meta-row">
        <span>当前状态：{{ isDefault ? '默认模板' : '自定义生效' }}</span>
        <span v-if="currentKnowledgeBaseNames">当前知识库：{{ currentKnowledgeBaseNames }}</span>
        <span v-if="version">版本：{{ version }}</span>
        <span v-if="updatedBy">更新人：{{ updatedBy }}</span>
        <span v-if="updatedAt">更新时间：{{ updatedAt }}</span>
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
import { computed, onMounted, ref, watch } from 'vue';
import { ElMessage } from 'element-plus';
import {
  createAssistant,
  getSystemPrompt,
  listAssistants,
  listKnowledgeBases,
  listManagedUsers,
  updateAssistant,
  updateSystemPrompt,
  type AssistantItem,
  type KnowledgeBaseItem,
  type PromptResponse,
} from '@/api/teacher';
import { useAuthStore } from '@/stores/auth';
import { formatChinaDateTime } from '@/utils/time';
import { useFeatureGateBootstrap } from '@/composables/useFeatureGateBootstrap';

const authStore = useAuthStore();
useFeatureGateBootstrap();
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

const content = ref('');
const defaultContent = ref('');
const isDefault = ref(false);
const version = ref<number | null>(null);
const updatedAt = ref<string | null>(null);
const updatedBy = ref<string | null>(null);

const schoolId = ref('');
const schools = ref<{ id: string; name: string }[]>([]);

const assistants = ref<AssistantItem[]>([]);
const selectedAssistantId = ref('');
const newAssistantName = ref('');

const knowledgeBases = ref<KnowledgeBaseItem[]>([]);
const selectedKnowledgeBaseIds = ref<string[]>([]);

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

const resetPromptState = () => {
  content.value = '';
  defaultContent.value = '';
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
    defaultContent.value = res.default_content || '';
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
  if (!selectedAssistantId.value) return;
  bindingKnowledgeBase.value = true;
  try {
    const updated = await updateAssistant(selectedAssistantId.value, {
      knowledge_base_ids: selectedKnowledgeBaseIds.value,
    });
    assistants.value = assistants.value.map((item) => item.id === updated.id ? updated : item);
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

const resetToDefault = () => {
  content.value = defaultContent.value || '';
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
  if (assistant?.knowledge_base_ids?.length) {
    selectedKnowledgeBaseIds.value = [...assistant.knowledge_base_ids];
  } else if (assistant?.knowledge_base_id) {
    selectedKnowledgeBaseIds.value = [assistant.knowledge_base_id];
  } else {
    selectedKnowledgeBaseIds.value = [];
  }
  await loadPrompt();
});

onMounted(() => {
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
</script>

<style scoped>
.prompt-view {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: rgba(255, 255, 255, 0.85);
  border-radius: 18px;
  padding: 20px;
  box-shadow: 0 10px 30px rgba(44, 62, 80, 0.1);
}

.title {
  margin: 0;
  font-size: 26px;
}

.subtitle {
  margin: 6px 0 0;
  color: rgba(44, 62, 80, 0.7);
}

.knowledge-base-select {
  width: 100%;
}

.actions {
  display: flex;
  gap: 10px;
}

.actions button,
.inline-row button {
  border: none;
  border-radius: 10px;
  padding: 10px 16px;
  cursor: pointer;
  font-weight: 600;
}

.actions .primary {
  background: linear-gradient(135deg, #0077ff, #00c6ff);
  color: #fff;
}

.ghost {
  background: rgba(44, 62, 80, 0.08);
}

.card {
  background: rgba(255, 255, 255, 0.9);
  border-radius: 18px;
  padding: 18px;
  box-shadow: 0 8px 24px rgba(44, 62, 80, 0.08);
  display: flex;
  flex-direction: column;
  gap: 14px;
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

.field {
  display: flex;
  flex-direction: column;
  gap: 8px;
  color: #566573;
  font-size: 14px;
}

.grow {
  width: 100%;
}

.inline-row {
  display: flex;
  gap: 10px;
  align-items: center;
}

.inline-row input,
.inline-row select,
.meta-row select {
  width: 100%;
}

.inline-row :deep(.el-select) {
  width: 100%;
}

select,
input,
.prompt-input {
  border-radius: 12px;
  border: 1px solid rgba(0, 0, 0, 0.12);
  padding: 12px;
  font-size: 14px;
  background: #fdfefe;
}

.prompt-input {
  width: 100%;
  min-height: 420px;
  font-family: 'Menlo', 'Fira Code', monospace;
  resize: vertical;
}

.empty-hint {
  margin: 0;
  color: #7f8c8d;
  font-size: 13px;
}

@media (max-width: 960px) {
  .page-header,
  .assistant-row {
    grid-template-columns: 1fr;
    display: grid;
  }

  .page-header {
    gap: 14px;
  }

  .actions,
  .inline-row {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
