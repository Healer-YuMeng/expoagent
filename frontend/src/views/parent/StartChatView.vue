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
const assistantId = ref<string>('');

const processChannelSource = () => {
  captureSourceFromQuery(route.query);
};

const initConversation = async () => {
  try {
    const conversation = await conversationStore.createNewConversation();
    if (conversation?.id) {
      router.push({
        name: 'ParentChat',
        params: { id: conversation.id },
        query: {
          ...route.query,
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
  const assistantFromQuery = typeof route.query.assistant_id === 'string' ? route.query.assistant_id : '';
  const storedAssistantId = getAppStorageItem('selectedAssistantId') || '';
  assistantId.value = assistantFromQuery || storedAssistantId;
  removeAppStorageItem('selectedSchoolId');
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
