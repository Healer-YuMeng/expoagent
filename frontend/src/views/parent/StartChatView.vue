<template>
  <div class="container">
    <div class="loading-container">
      <el-icon class="is-loading" size="26"><Loading /></el-icon>
      <p>{{ t('chat.connecting') }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { Loading } from '@element-plus/icons-vue';
import { useConversationStore } from '@/stores/conversation';
import { useI18n } from 'vue-i18n';
import { captureSourceFromQuery } from '@/utils/channelSource';
import { getAppStorageItem, removeAppStorageItem, setAppStorageItem } from '@/utils/browserStorage';

const router = useRouter();
const route = useRoute();
const conversationStore = useConversationStore();
const { t } = useI18n();
const schoolId = ref<string>('');
const assistantId = ref<string>('');

const processChannelSource = () => {
  captureSourceFromQuery(route.query);
};

const initConversation = async () => {
  try {
    const conversation = await conversationStore.createNewConversation(schoolId.value);
    if (conversation?.id) {
      router.push({
        name: 'ParentChat',
        params: { id: conversation.id },
        query: {
          ...route.query,
          ...(schoolId.value ? { school_id: schoolId.value } : {}),
          ...(assistantId.value ? { assistant_id: assistantId.value } : {}),
        },
      });
    }
  } catch (error) {
    console.error(error);
    ElMessage.error(t('chat.createConversationError'));
  }
};

onMounted(() => {
  processChannelSource();
  const fromQuery = typeof route.query.school_id === 'string' ? route.query.school_id : '';
  const assistantFromQuery = typeof route.query.assistant_id === 'string' ? route.query.assistant_id : '';
  const stored = getAppStorageItem('selectedSchoolId') || '';
  const storedAssistantId = getAppStorageItem('selectedAssistantId') || '';
  schoolId.value = fromQuery || stored;
  assistantId.value = assistantFromQuery || storedAssistantId;
  if (schoolId.value) {
    setAppStorageItem('selectedSchoolId', schoolId.value);
  }
  if (assistantId.value) {
    setAppStorageItem('selectedAssistantId', assistantId.value);
  } else {
    removeAppStorageItem('selectedAssistantId');
  }
  initConversation();
});
</script>

<style scoped>
.container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  color: #606266;
}

.loading-container,
.error-container {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
}

.error-container p,
.loading-container p {
  margin-top: 10px;
}
</style>
