<template>
  <div class="kb-view">
    <header class="page-header">
      <div>
        <h1 class="title">{{ t('knowledgeBase.title') }}</h1>
        <p class="subtitle">{{ t('knowledgeBase.subtitle') }}</p>
      </div>
    </header>

    <section class="card instructions">
      <h2>{{ t('knowledgeBase.howItWorks') }}</h2>
      <ol>
        <li>{{ t('knowledgeBase.stepUpload') }}</li>
        <li>{{ t('knowledgeBase.stepPreview') }}</li>
        <li>{{ t('knowledgeBase.stepEmbed') }}</li>
      </ol>
      <p class="hint">
        <!-- TODO: backend endpoint for uploading QA pairs and triggering vectorization -->
        {{ t('knowledgeBase.backendPendingHint') }}
      </p>
    </section>

    <section class="card knowledge-base-panel">
      <div class="knowledge-base-header">
        <div>
          <h2>{{ t('knowledgeBase.baseTitle') }}</h2>
          <p>{{ t('knowledgeBase.baseDesc') }}</p>
        </div>
        <span class="total-hint">{{ t('knowledgeBase.totalKnowledgeBases', { count: knowledgeBases.length }) }}</span>
      </div>

      <div class="knowledge-base-controls">
        <div class="knowledge-base-select-group">
          <label>{{ t('knowledgeBase.selectKnowledgeBase') }}</label>
          <select v-model="selectedKnowledgeBaseId">
            <option value="">{{ t('knowledgeBase.selectKnowledgeBasePlaceholder') }}</option>
            <option v-for="item in knowledgeBases" :key="item.id" :value="item.id">
              {{ item.name }} ({{ item.doc_count || 0 }})
            </option>
          </select>
        </div>

        <div class="knowledge-base-create-group">
          <label>{{ t('knowledgeBase.newKnowledgeBase') }}</label>
          <div class="knowledge-base-create-row">
            <input
              v-model="newKnowledgeBaseName"
              :placeholder="t('knowledgeBase.newKnowledgeBasePlaceholder')"
              @keyup.enter="createKnowledgeBase"
            />
            <button class="primary" :disabled="creatingKnowledgeBase || !newKnowledgeBaseName.trim()" @click="createKnowledgeBase">
              <span v-if="creatingKnowledgeBase">{{ t('common.loading') }}</span>
              <span v-else>{{ t('knowledgeBase.createKnowledgeBaseAction') }}</span>
            </button>
          </div>
        </div>
      </div>

      <div v-if="selectedKnowledgeBaseName" class="knowledge-base-active">
        {{ t('knowledgeBase.activeKnowledgeBase', { name: selectedKnowledgeBaseName }) }}
      </div>
      <div v-else class="knowledge-base-empty">
        {{ t('knowledgeBase.noKnowledgeBaseSelected') }}
      </div>
    </section>

    <section class="card uploader">
      <div class="uploader-header">
        <h2>{{ t('knowledgeBase.uploadTitle') }}</h2>
        <p>{{ t('knowledgeBase.uploadDesc') }}</p>
      </div>

      <label
        class="upload-dropzone"
        @dragover.prevent
        @drop.prevent="handleDrop"
      >
        <input
          type="file"
          accept=".pdf,.docx,.pptx,.xlsx,.txt,.md,.jpg,.jpeg,.png,.xls"
          multiple
          @change="handleFileChange"
        />
        <div class="dropzone-content">
          <span class="icon">📤</span>
          <p>{{ t('knowledgeBase.uploadPlaceholder') }}</p>
          <small>{{ t('knowledgeBase.fileLimit') }}</small>
        </div>
      </label>

      <div v-if="selectedFiles.length" class="file-preview">
        <div class="file-meta">
          <div>
            <p class="file-name">{{ t('knowledgeBase.selectedFiles', { count: selectedFiles.length }) }}</p>
            <ul class="file-list">
              <li v-for="f in selectedFiles" :key="f.name">{{ f.name }} · {{ formatSize(f.size) }}</li>
            </ul>
          </div>
          <button class="clear-btn" @click="clearSelection">
            {{ t('knowledgeBase.clear') }}
          </button>
        </div>

        <div class="preview-placeholder" v-if="previewRows.length === 0">
          <p>{{ t('knowledgeBase.previewPlaceholder') }}</p>
          <p class="placeholder-hint">{{ t('knowledgeBase.previewHint') }}</p>
        </div>

        <div class="actions">
          <button
            class="primary"
            :disabled="selectedFiles.length === 0 || isUploading || !selectedKnowledgeBaseId"
            @click="handleUpload"
          >
            <span v-if="isUploading">⏳ {{ t('knowledgeBase.uploading') }}</span>
            <span v-else>🚀 {{ t('knowledgeBase.uploadAction') }}</span>
          </button>
        </div>
      </div>
    </section>

    <section class="card url-import">
      <div class="url-header">
        <div>
          <h2>{{ t('knowledgeBase.urlImportTitle') }}</h2>
          <p>{{ t('knowledgeBase.urlImportDesc') }}</p>
        </div>
      </div>
      <div class="url-form">
        <input v-model="importUrl" :placeholder="t('knowledgeBase.urlPlaceholder')" />
        <button class="primary" :disabled="urlLoading || !importUrl.trim() || !selectedKnowledgeBaseId" @click="handleImportUrl">
          <span v-if="urlLoading">⏳ {{ t('knowledgeBase.importingUrl') }}</span>
          <span v-else>🔗 {{ t('knowledgeBase.importUrlAction') }}</span>
        </button>
      </div>
    </section>

    <section class="card doc-list">
      <div class="doc-filters">
        <input v-model="docSearch" :placeholder="t('knowledgeBase.docSearchPlaceholder')" @keyup.enter="fetchDocs" />
        <select v-model="docStatus" @change="fetchDocs">
          <option :value="null">{{ t('knowledgeBase.statusAll') }}</option>
          <option value="ready">{{ t('knowledgeBase.statusReady') }}</option>
          <option value="pending">{{ t('knowledgeBase.statusPending') }}</option>
        </select>
        <button class="filter-btn primary" @click="fetchDocs">{{ t('settings.refresh') }}</button>
        <span class="total-hint">{{ t('knowledgeBase.totalDocs', { count: docTotal }) }}</span>
      </div>

      <table class="doc-table" v-if="docs.length">
        <thead>
          <tr>
            <th>{{ t('knowledgeBase.tableName') }}</th>
            <th>{{ t('knowledgeBase.tableKnowledgeBase') }}</th>
            <th>{{ t('knowledgeBase.tableStatus') }}</th>
            <th>{{ t('knowledgeBase.tableChunkCount') }}</th>
            <th>{{ t('knowledgeBase.tableActions') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="doc in docs" :key="doc.id">
            <td>{{ doc.name }}</td>
            <td>{{ getKnowledgeBaseName(doc.knowledge_base_id) }}</td>
            <td>{{ getDocStatusText(doc.status) }}</td>
            <td>{{ doc.chunk_count || 0 }}</td>
            <td>
              <div class="doc-actions">
                <button
                  class="doc-btn view"
                  :disabled="loadingDocId === doc.id"
                  @click="handleSelectDoc(doc)"
                >
                  {{ loadingDocId === doc.id ? t('common.loading') : t('knowledgeBase.viewChunks') }}
                </button>
                <button class="doc-btn delete" @click="handleDeleteDoc(doc.id)">{{ t('common.delete') }}</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else class="recall-empty">{{ t('knowledgeBase.noDocs') }}</div>
      <div v-if="chunkLoadError" class="chunk-error">{{ chunkLoadError }}</div>
    </section>

    <section class="card chunk-panel" v-if="selectedDocId">
      <div class="chunk-list" v-loading="chunkLoading">
        <h3>{{ t('knowledgeBase.chunkListTitle') }}<span v-if="selectedDocName"> · {{ selectedDocName }}</span></h3>
        <div v-if="!chunkLoading && !chunks.length" class="recall-empty">{{ t('knowledgeBase.noChunks') }}</div>
        <div v-for="chunk in chunks" :key="chunk.id" class="chunk-item">
          <div class="chunk-edit">
            <textarea v-model="chunk.content" />
            <div class="chunk-buttons">
              <button class="save" @click="handleSaveChunk(chunk)">{{ t('knowledgeBase.saveChunk') }}</button>
              <button class="delete" @click="deleteChunk(chunk.id)">{{ t('knowledgeBase.deleteChunk') }}</button>
            </div>
          </div>
          <div class="chunk-metadata">{{ t('knowledgeBase.chunkId') }}: {{ chunk.id }}</div>
        </div>
      </div>
      <div class="add-chunk">
        <h3>{{ t('knowledgeBase.addChunkTitle') }}</h3>
        <textarea v-model="newChunkContent" :placeholder="t('knowledgeBase.chunkContentPlaceholder')"></textarea>
        <textarea v-model="newChunkMeta" :placeholder="t('knowledgeBase.chunkMetaPlaceholder')"></textarea>
        <button class="primary" @click="addChunk">{{ t('knowledgeBase.addChunkAction') }}</button>
      </div>
    </section>

    <section class="card recall-card">
      <div class="recall-header">
        <div>
          <h2>{{ t('knowledgeBase.recallTitle') }}</h2>
          <p>{{ t('knowledgeBase.recallDesc') }}</p>
        </div>
      <div class="topk-input">
          <label>Top K</label>
          <input type="number" v-model.number="recallTopK" min="1" max="20" />
        </div>
      </div>
      <textarea
        class="recall-input"
        v-model="recallQuery"
        rows="3"
        :placeholder="t('knowledgeBase.recallPlaceholder')"
      />
      <div class="recall-actions">
        <button class="primary" :disabled="recallLoading || !recallQuery.trim() || !selectedKnowledgeBaseId" @click="runRecall">
          <span v-if="recallLoading">⏳ {{ t('knowledgeBase.recallLoading') }}</span>
          <span v-else>🔍 {{ t('knowledgeBase.recallAction') }}</span>
        </button>
      </div>
      <div class="recall-results" v-if="recallResults.length">
        <div class="result-item" v-for="item in recallResults" :key="item.id">
          <div class="result-meta">
            <span class="doc-name">{{ item.doc_name || t('knowledgeBase.unknownDoc') }}</span>
            <span class="score">{{ t('knowledgeBase.score') }}: {{ (item.score || 0).toFixed(3) }}</span>
          </div>
          <div class="result-content">{{ item.content }}</div>
          <div class="result-tags">
            <span v-if="item.metadata?.page">{{ t('knowledgeBase.page') }}: {{ item.metadata.page }}</span>
            <span v-if="item.metadata?.slide">{{ t('knowledgeBase.slide') }}: {{ item.metadata.slide }}</span>
            <span v-if="item.metadata?.sheet">{{ t('knowledgeBase.sheet') }}: {{ item.metadata.sheet }}</span>
            <span v-if="item.metadata?.row_index">{{ t('knowledgeBase.row') }}: {{ item.metadata.row_index }}</span>
          </div>
        </div>
      </div>
      <div class="recall-empty" v-else>
        <p>{{ t('knowledgeBase.noRecallResults') }}</p>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { ElMessage } from 'element-plus';
import request from '@/utils/request';

const { t } = useI18n();
const selectedFiles = ref<File[]>([]);
const previewRows = ref<Array<{ question: string; answer: string }>>([]);
const isUploading = ref(false);
const recallQuery = ref('');
const recallResults = ref<any[]>([]);
const recallTopK = ref(5);
const recallLoading = ref(false);
const docs = ref<any[]>([]);
const docTotal = ref(0);
const docLoading = ref(false);
const docSearch = ref('');
const docStatus = ref<string | null>(null);
const chunks = ref<any[]>([]);
const chunkLoading = ref(false);
const selectedDocId = ref<string | null>(null);
const selectedDocName = ref('');
const loadingDocId = ref<string | null>(null);
const chunkLoadError = ref('');
const newChunkContent = ref('');
const newChunkMeta = ref('{}');
const importUrl = ref('');
const urlLoading = ref(false);
const knowledgeBases = ref<Array<{ id: string; name: string; description?: string; doc_count?: number }>>([]);
const selectedKnowledgeBaseId = ref('');
const newKnowledgeBaseName = ref('');
const creatingKnowledgeBase = ref(false);

const selectedKnowledgeBaseName = computed(() => {
  const current = knowledgeBases.value.find((item) => item.id === selectedKnowledgeBaseId.value);
  return current?.name || '';
});

type ChunkItem = {
  id: string;
  doc_id: string;
  school_id?: string;
  admin_id?: string;
  content: string;
  metadata: Record<string, any>;
  metadataJson: string;
};

const showWarningIfNeeded = (res: any) => {
  if (res?.warning) {
    ElMessage.warning(res.warning);
  }
};

const getDocStatusText = (status: string | null | undefined) => {
  if (status === 'ready') return t('knowledgeBase.statusReady');
  if (status === 'pending') return t('knowledgeBase.statusPending');
  return status || '-';
};

const getKnowledgeBaseName = (knowledgeBaseId: string | null | undefined) => {
  if (!knowledgeBaseId) return '-';
  const current = knowledgeBases.value.find((item) => item.id === knowledgeBaseId);
  return current?.name || knowledgeBaseId;
};

const ensureKnowledgeBaseSelected = () => {
  if (selectedKnowledgeBaseId.value) return;
  const firstKnowledgeBase = knowledgeBases.value[0];
  if (firstKnowledgeBase) {
    selectedKnowledgeBaseId.value = firstKnowledgeBase.id;
  }
};

const fetchKnowledgeBases = async () => {
  try {
    const res: any = await request.get('/v1/docs/knowledge-bases');
    knowledgeBases.value = Array.isArray(res?.items) ? res.items : [];
    if (
      selectedKnowledgeBaseId.value &&
      !knowledgeBases.value.some((item) => item.id === selectedKnowledgeBaseId.value)
    ) {
      selectedKnowledgeBaseId.value = '';
    }
    ensureKnowledgeBaseSelected();
  } catch (e) {
    console.error(e);
    ElMessage.error(t('knowledgeBase.fetchKnowledgeBasesError'));
  }
};

const createKnowledgeBase = async () => {
  const name = newKnowledgeBaseName.value.trim();
  if (!name) return;
  creatingKnowledgeBase.value = true;
  try {
    const res: any = await request.post('/v1/docs/knowledge-bases', { name });
    ElMessage.success(t('knowledgeBase.createKnowledgeBaseSuccess', { name: res.name || name }));
    newKnowledgeBaseName.value = '';
    await fetchKnowledgeBases();
    if (res?.id) {
      selectedKnowledgeBaseId.value = res.id;
    }
  } catch (error: any) {
    console.error(error);
    ElMessage.error(error?.response?.data?.detail || t('knowledgeBase.createKnowledgeBaseError'));
  } finally {
    creatingKnowledgeBase.value = false;
  }
};

const normalizeChunkMetadata = (metadata: unknown): Record<string, any> => {
  if (!metadata) return {};
  if (typeof metadata === 'string') {
    const trimmed = metadata.trim();
    if (!trimmed) return {};
    try {
      const parsed = JSON.parse(trimmed);
      return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
        ? parsed
        : { raw: trimmed };
    } catch (error) {
      return { raw: trimmed };
    }
  }
  if (typeof metadata === 'object' && !Array.isArray(metadata)) {
    return metadata as Record<string, any>;
  }
  return { value: metadata };
};

const safeStringify = (value: unknown) => {
  try {
    return JSON.stringify(value ?? {}, null, 2);
  } catch (error) {
    return '{}';
  }
};

const normalizeChunkItem = (chunk: any, docId: string, index: number): ChunkItem => {
  const metadata = normalizeChunkMetadata(chunk?.metadata);
  return {
    id: typeof chunk?.id === 'string' && chunk.id.trim() ? chunk.id : `${docId}-${index}`,
    doc_id: typeof chunk?.doc_id === 'string' ? chunk.doc_id : String(chunk?.doc_id || docId),
    school_id: typeof chunk?.school_id === 'string' ? chunk.school_id : undefined,
    admin_id: typeof chunk?.admin_id === 'string' ? chunk.admin_id : undefined,
    content: typeof chunk?.content === 'string' ? chunk.content : String(chunk?.content || ''),
    metadata,
    metadataJson: safeStringify(metadata),
  };
};

const updateSelectedDocChunkCount = (delta: number) => {
  if (!selectedDocId.value) return;
  const doc = docs.value.find((item: any) => item.id === selectedDocId.value);
  if (!doc) return;
  doc.chunk_count = Math.max(0, Number(doc.chunk_count || 0) + delta);
};

const addFiles = (files: FileList | null) => {
  if (!files?.length) return;
  for (const file of Array.from(files)) {
    selectedFiles.value.push(file);
  }
  previewRows.value = [];
};

const handleFileChange = (event: Event) => {
  const target = event.target as HTMLInputElement;
  addFiles(target.files);
};

const handleDrop = (event: DragEvent) => {
  addFiles(event.dataTransfer?.files || null);
};

const clearSelection = () => {
  selectedFiles.value = [];
  previewRows.value = [];
};

const handleUpload = async () => {
  if (!selectedFiles.value.length) return;
  if (!selectedKnowledgeBaseId.value) {
    ElMessage.warning(t('knowledgeBase.selectKnowledgeBaseFirst'));
    return;
  }
  isUploading.value = true;
  try {
    for (const file of selectedFiles.value) {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('use_async', 'true');
      formData.append('knowledge_base_id', selectedKnowledgeBaseId.value);
      const res: any = await request.post('/v1/docs', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 300000,
      });
      ElMessage.success(t('knowledgeBase.uploadSuccess', {
        name: res.name || file.name,
        count: res.chunk_count ?? '-',
      }));
      showWarningIfNeeded(res);
    }
    clearSelection();
    await fetchDocs();
  } catch (e) {
    console.error(e);
    ElMessage.error(t('knowledgeBase.uploadError'));
  } finally {
    isUploading.value = false;
  }
};

const formatSize = (size: number) => {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
};

const runRecall = async () => {
  if (!recallQuery.value.trim()) return;
  if (!selectedKnowledgeBaseId.value) {
    ElMessage.warning(t('knowledgeBase.selectKnowledgeBaseFirst'));
    return;
  }
  recallLoading.value = true;
  try {
    const res: any = await request.post('/v1/docs/query', {
      query: recallQuery.value,
      top_k: recallTopK.value,
      knowledge_base_id: selectedKnowledgeBaseId.value,
    });
    recallResults.value = res.items || [];
  } catch (e) {
    console.error(e);
    ElMessage.error(t('knowledgeBase.recallError'));
  } finally {
    recallLoading.value = false;
  }
};

const fetchDocs = async () => {
  if (!selectedKnowledgeBaseId.value) {
    docs.value = [];
    docTotal.value = 0;
    return;
  }
  docLoading.value = true;
  try {
    const res: any = await request.get('/v1/docs', {
      params: {
        status: docStatus.value || undefined,
        search: docSearch.value || undefined,
        knowledge_base_id: selectedKnowledgeBaseId.value,
      },
    });
    docs.value = res.items || [];
    docTotal.value = res.total || 0;
  } catch (e) {
    console.error(e);
    ElMessage.error(t('knowledgeBase.fetchDocsError'));
  } finally {
    docLoading.value = false;
  }
};

const refreshChunks = async (docId: string) => {
  chunkLoading.value = true;
  try {
    const res: any = await request.get(`/v1/docs/${docId}/chunks`, {
      timeout: 120000,
    });
    const items = Array.isArray(res?.items) ? res.items : [];
    chunks.value = items.map((chunk: any, index: number) => normalizeChunkItem(chunk, docId, index));
  } catch (e) {
    chunks.value = [];
    throw e;
  } finally {
    chunkLoading.value = false;
  }
};

const handleSelectDoc = async (doc: any) => {
  const docId = String(doc?.id || '');
  if (!docId) {
    chunkLoadError.value = t('knowledgeBase.fetchChunksError');
    ElMessage.error(t('knowledgeBase.fetchChunksError'));
    return;
  }
  loadingDocId.value = docId;
  chunkLoadError.value = '';
  try {
    await refreshChunks(docId);
    selectedDocId.value = docId;
    selectedDocName.value = typeof doc?.name === 'string' ? doc.name : docId;
  } catch (e) {
    console.error(e);
    chunkLoadError.value = t('knowledgeBase.fetchChunksError');
    ElMessage.error(t('knowledgeBase.fetchChunksError'));
  } finally {
    loadingDocId.value = null;
  }
};

const handleDeleteDoc = async (docId: string) => {
  try {
    await request.delete(`/v1/docs/${docId}`);
    ElMessage.success(t('knowledgeBase.docDeleted'));
    if (selectedDocId.value === docId) {
      selectedDocId.value = null;
      selectedDocName.value = '';
      chunks.value = [];
    }
    fetchDocs();
  } catch (e) {
    console.error(e);
    ElMessage.error(t('knowledgeBase.deleteError'));
  }
};

const handleSaveChunk = async (chunk: any) => {
  try {
    let meta = {};
    try {
      meta = chunk.metadataJson ? JSON.parse(chunk.metadataJson) : {};
    } catch (e) {
      ElMessage.error(t('knowledgeBase.invalidJson'));
      return;
    }
    const res: any = await request.patch(`/v1/docs/chunks/${chunk.id}`, {
      content: chunk.content,
      metadata: meta,
    }, {
      timeout: 120000,
    });
    ElMessage.success(t('knowledgeBase.chunkUpdated'));
    showWarningIfNeeded(res);
    chunk.metadata = meta;
    chunk.metadataJson = safeStringify(meta);
  } catch (e) {
    console.error(e);
    ElMessage.error(t('knowledgeBase.updateChunkError'));
  }
};

const deleteChunk = async (chunkId: string) => {
  try {
    const index = chunks.value.findIndex((item: any) => item.id === chunkId);
    await request.delete(`/v1/docs/chunks/${chunkId}`, {
      timeout: 120000,
    });
    ElMessage.success(t('knowledgeBase.chunkDeleted'));
    if (index >= 0) {
      chunks.value.splice(index, 1);
      updateSelectedDocChunkCount(-1);
    }
  } catch (e) {
    console.error(e);
    ElMessage.error(t('knowledgeBase.deleteChunkError'));
  }
};

const addChunk = async () => {
  if (!selectedDocId.value) {
    ElMessage.warning(t('knowledgeBase.selectDocFirst'));
    return;
  }
  let meta: any = {};
  try {
    meta = newChunkMeta.value ? JSON.parse(newChunkMeta.value) : {};
  } catch (e) {
    ElMessage.error(t('knowledgeBase.invalidJson'));
    return;
  }
  if (!newChunkContent.value.trim()) {
    ElMessage.warning(t('knowledgeBase.emptyContent'));
    return;
  }
  try {
    const res: any = await request.post(`/v1/docs/${selectedDocId.value}/chunks`, {
      content: newChunkContent.value,
      metadata: meta,
    }, {
      timeout: 120000,
    });
    ElMessage.success(t('knowledgeBase.chunkAdded'));
    showWarningIfNeeded(res);
    chunks.value.push({
      id: res.id,
      doc_id: selectedDocId.value,
      content: newChunkContent.value,
      metadata: meta,
      metadataJson: safeStringify(meta),
    });
    updateSelectedDocChunkCount(1);
    newChunkContent.value = '';
    newChunkMeta.value = '{}';
  } catch (e) {
    console.error(e);
    ElMessage.error(t('knowledgeBase.addChunkError'));
  }
};

const handleImportUrl = async () => {
  if (!importUrl.value.trim()) return;
  if (!selectedKnowledgeBaseId.value) {
    ElMessage.warning(t('knowledgeBase.selectKnowledgeBaseFirst'));
    return;
  }
  urlLoading.value = true;
  try {
    const res: any = await request.post('/v1/docs/url', {
      url: importUrl.value.trim(),
      knowledge_base_id: selectedKnowledgeBaseId.value,
    }, {
      timeout: 300000,
    });
    ElMessage.success(t('knowledgeBase.importSuccess', {
      name: (res as any).name || (res as any).id,
    }));
    showWarningIfNeeded(res);
    importUrl.value = '';
    await fetchDocs();
  } catch (e) {
    console.error(e);
    ElMessage.error(t('knowledgeBase.importError'));
  } finally {
    urlLoading.value = false;
  }
};

watch(selectedKnowledgeBaseId, async () => {
  selectedDocId.value = null;
  selectedDocName.value = '';
  chunks.value = [];
  recallResults.value = [];
  await fetchDocs();
});

onMounted(async () => {
  await fetchKnowledgeBases();
  await fetchDocs();
});
</script>

<style scoped>
.kb-view {
  display: flex;
  flex-direction: column;
  gap: 24px;
  min-width: 0;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(255, 255, 255, 0.75);
  border-radius: 18px;
  padding: 24px;
  box-shadow: 0 10px 30px rgba(44, 62, 80, 0.1);
}

.title {
  font-size: 28px;
  margin: 0;
}

.subtitle {
  margin: 6px 0 0;
  color: rgba(44, 62, 80, 0.7);
}

.card {
  background: rgba(255, 255, 255, 0.85);
  border-radius: 18px;
  padding: 24px;
  box-shadow: 0 10px 30px rgba(44, 62, 80, 0.08);
}

.instructions ol {
  margin: 12px 0;
  padding-left: 20px;
  line-height: 1.6;
}

.hint {
  margin-top: 12px;
  font-size: 14px;
  color: #e67e22;
}

.knowledge-base-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.knowledge-base-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.knowledge-base-header h2 {
  margin: 0;
}

.knowledge-base-controls {
  display: grid;
  grid-template-columns: 1fr 1.2fr;
  gap: 16px;
}

.knowledge-base-select-group,
.knowledge-base-create-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.knowledge-base-select-group select,
.knowledge-base-create-group input {
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid rgba(0, 0, 0, 0.12);
}

.knowledge-base-create-row {
  display: flex;
  gap: 10px;
}

.knowledge-base-create-row input {
  flex: 1;
}

.knowledge-base-create-row button,
.url-form button,
.filter-btn.primary,
.add-chunk .primary,
.recall-actions .primary {
  border: none;
  border-radius: 10px;
  padding: 10px 16px;
  font-weight: 600;
  cursor: pointer;
  background: linear-gradient(135deg, #0077ff, #00c6ff);
  color: #fff;
}

.knowledge-base-active,
.knowledge-base-empty {
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(44, 62, 80, 0.05);
  color: rgba(44, 62, 80, 0.78);
}

.uploader-header h2 {
  margin: 0;
}

.upload-dropzone {
  margin-top: 16px;
  border: 2px dashed rgba(44, 62, 80, 0.15);
  border-radius: 16px;
  padding: 40px;
  display: block;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.3s ease;
}

.upload-dropzone:hover {
  border-color: rgba(44, 62, 80, 0.4);
}

.upload-dropzone input {
  display: none;
}

.dropzone-content .icon {
  font-size: 40px;
  display: block;
  margin-bottom: 12px;
}

.file-preview {
  margin-top: 20px;
  border-top: 1px solid rgba(44, 62, 80, 0.1);
  padding-top: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.file-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.file-name {
  font-weight: 600;
  margin: 0;
}

.file-size {
  margin: 2px 0 0;
  color: rgba(44, 62, 80, 0.6);
}

.clear-btn {
  border: none;
  background: transparent;
  color: #e74c3c;
  cursor: pointer;
}

.preview-placeholder {
  padding: 16px;
  border-radius: 12px;
  background: rgba(44, 62, 80, 0.05);
}

.preview-table {
  width: 100%;
  border-collapse: collapse;
}

.preview-table th,
.preview-table td {
  border: 1px solid rgba(44, 62, 80, 0.1);
  padding: 10px;
  text-align: left;
}

.actions {
  display: flex;
  gap: 12px;
}

.actions button {
  border: none;
  border-radius: 10px;
  padding: 12px 18px;
  font-weight: 600;
  cursor: pointer;
}

.actions .primary {
  background: linear-gradient(135deg, #0077ff, #00c6ff);
  color: #fff;
}

.actions .primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.actions .secondary {
  background: rgba(44, 62, 80, 0.08);
}

.doc-list {
  margin-top: 24px;
}

.doc-filters {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 12px;
}

.total-hint {
  color: #7f8c8d;
  font-size: 13px;
}

.doc-filters input,
.doc-filters select {
  padding: 8px 10px;
  border-radius: 10px;
  border: 1px solid rgba(0, 0, 0, 0.12);
}

.doc-table {
  width: 100%;
  border-collapse: collapse;
}

.doc-table th,
.doc-table td {
  border: 1px solid rgba(44, 62, 80, 0.08);
  padding: 10px;
  text-align: left;
}

.doc-table th {
  background: rgba(44, 62, 80, 0.05);
}

.doc-actions {
  display: flex;
  gap: 8px;
}

.doc-btn {
  border: none;
  border-radius: 8px;
  padding: 6px 10px;
  cursor: pointer;
}

.doc-btn:disabled {
  cursor: not-allowed;
  opacity: 0.7;
}

.doc-btn.view {
  background: rgba(52, 152, 219, 0.12);
}

.doc-btn.delete {
  background: rgba(231, 76, 60, 0.12);
  color: #c0392b;
}

.chunk-panel {
  margin-top: 24px;
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 16px;
}

.chunk-error {
  margin-top: 12px;
  color: #c0392b;
  font-size: 14px;
}

.chunk-list {
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 12px;
  padding: 12px;
  max-height: 420px;
  overflow: auto;
  background: rgba(255, 255, 255, 0.85);
}

.chunk-item {
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);
  padding: 10px 0;
}

.chunk-item:last-child {
  border-bottom: none;
}

.chunk-metadata {
  font-size: 12px;
  color: #7f8c8d;
  margin-top: 6px;
}

.chunk-edit {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.chunk-edit textarea {
  width: 100%;
  min-height: 80px;
  border-radius: 10px;
  border: 1px solid rgba(0, 0, 0, 0.12);
  padding: 8px;
  font-size: 13px;
  font-family: inherit;
}

.chunk-edit .meta-input {
  min-height: 60px;
}

.chunk-buttons {
  display: flex;
  gap: 8px;
}

.chunk-buttons button {
  border: none;
  border-radius: 8px;
  padding: 6px 10px;
  cursor: pointer;
}

.chunk-buttons .save {
  background: rgba(52, 152, 219, 0.15);
}

.chunk-buttons .delete {
  background: rgba(231, 76, 60, 0.15);
  color: #c0392b;
}

.add-chunk {
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 12px;
  padding: 12px;
  background: rgba(255, 255, 255, 0.9);
}

.url-form {
  display: flex;
  gap: 12px;
  margin-top: 16px;
}

.url-form input,
.recall-input,
.add-chunk textarea {
  width: 100%;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid rgba(0, 0, 0, 0.12);
}

@media (max-width: 900px) {
  .knowledge-base-controls,
  .chunk-panel {
    grid-template-columns: 1fr;
  }

  .url-form,
  .knowledge-base-create-row,
  .doc-filters {
    flex-direction: column;
    align-items: stretch;
  }
}

.add-chunk textarea {
  width: 100%;
  border-radius: 10px;
  border: 1px solid rgba(0, 0, 0, 0.12);
  padding: 8px;
  font-size: 13px;
  margin-bottom: 8px;
  font-family: inherit;
}

.recall-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: rgba(255, 255, 255, 0.9);
  min-width: 0;
}

.recall-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  min-width: 0;
}

.topk-input {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.topk-input input {
  width: 80px;
  padding: 6px 10px;
  border-radius: 10px;
  border: 1px solid rgba(0, 0, 0, 0.1);
}

.recall-input {
  width: 100%;
  border-radius: 12px;
  border: 1px solid rgba(0, 0, 0, 0.12);
  padding: 12px;
  font-size: 14px;
  font-family: inherit;
  resize: vertical;
}

.recall-actions {
  display: flex;
  gap: 10px;
}

.recall-results {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
}

.result-item {
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 12px;
  padding: 12px;
  background: #f9fbff;
  min-width: 0;
  overflow: hidden;
}

.result-meta {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 13px;
  color: #34495e;
  margin-bottom: 6px;
  min-width: 0;
}

.doc-name {
  font-weight: 700;
  min-width: 0;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.score {
  color: #2980b9;
  flex-shrink: 0;
}

.result-content {
  font-size: 14px;
  line-height: 1.6;
  margin-bottom: 6px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.result-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 12px;
  color: #7f8c8d;
}

.result-tags span {
  background: rgba(0, 0, 0, 0.04);
  padding: 3px 8px;
  border-radius: 8px;
}

.recall-empty {
  font-size: 14px;
  color: #7f8c8d;
}

.url-import {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.url-form {
  display: flex;
  gap: 10px;
}

.url-form input {
  flex: 1;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid rgba(0, 0, 0, 0.12);
}

@media (max-width: 900px) {
  .recall-header {
    flex-direction: column;
    align-items: stretch;
  }

  .topk-input input {
    width: 100%;
  }
}
</style>
