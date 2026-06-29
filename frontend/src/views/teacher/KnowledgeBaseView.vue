<template>
  <div class="kb-view">
    <TeacherPageHeader :title="t('knowledgeBase.title')" />

    <section class="card instructions">
      <div class="card-header-row">
        <h2>{{ t('knowledgeBase.howItWorks') }}</h2>
        <button class="collapse-btn" @click="toggleSection('instructions')">
          <span class="collapse-btn__icon">{{ isSectionCollapsed('instructions') ? '▸' : '▾' }}</span>
          <span>{{ isSectionCollapsed('instructions') ? '展开' : '收起' }}</span>
        </button>
      </div>
      <div v-show="!isSectionCollapsed('instructions')">
        <ol>
          <li>{{ t('knowledgeBase.stepUpload') }}</li>
          <li>{{ t('knowledgeBase.stepPreview') }}</li>
          <li>{{ t('knowledgeBase.stepEmbed') }}</li>
        </ol>
        <p class="hint">
          <!-- TODO: backend endpoint for uploading QA pairs and triggering vectorization -->
          {{ t('knowledgeBase.backendPendingHint') }}
        </p>
      </div>
    </section>

    <section class="card knowledge-base-panel">
      <div class="knowledge-base-header">
        <div>
          <h2>{{ t('knowledgeBase.baseTitle') }}</h2>
          <p>{{ t('knowledgeBase.baseDesc') }}</p>
        </div>
        <div class="card-header-actions">
          <span class="total-hint">{{ t('knowledgeBase.totalKnowledgeBases', { count: knowledgeBases.length }) }}</span>
          <button class="collapse-btn" @click="toggleSection('knowledgeBase')">
            <span class="collapse-btn__icon">{{ isSectionCollapsed('knowledgeBase') ? '▸' : '▾' }}</span>
            <span>{{ isSectionCollapsed('knowledgeBase') ? '展开' : '收起' }}</span>
          </button>
        </div>
      </div>

      <div v-show="!isSectionCollapsed('knowledgeBase')">
        <div class="knowledge-base-controls">
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

          <div class="knowledge-base-select-group">
            <label>{{ t('knowledgeBase.selectKnowledgeBase') }}</label>
            <el-select
              v-model="selectedKnowledgeBaseId"
              class="knowledge-base-select"
              :placeholder="t('knowledgeBase.selectKnowledgeBasePlaceholder')"
            >
              <el-option
                v-for="item in knowledgeBases"
                :key="item.id"
                :label="`${item.name} (${item.doc_count || 0})`"
                :value="item.id"
              />
            </el-select>
          </div>
        </div>

        <div v-if="selectedKnowledgeBaseName" class="knowledge-base-active">
          {{ t('knowledgeBase.activeKnowledgeBase', { name: selectedKnowledgeBaseName }) }}
        </div>
        <div v-else class="knowledge-base-empty">
          {{ t('knowledgeBase.noKnowledgeBaseSelected') }}
        </div>
      </div>
    </section>

    <section class="card uploader">
      <div class="uploader-header">
        <div>
          <h2>{{ t('knowledgeBase.uploadTitle') }}</h2>
          <p>{{ t('knowledgeBase.uploadDesc') }}</p>
        </div>
        <button class="collapse-btn" @click="toggleSection('uploader')">
          <span class="collapse-btn__icon">{{ isSectionCollapsed('uploader') ? '▸' : '▾' }}</span>
          <span>{{ isSectionCollapsed('uploader') ? '展开' : '收起' }}</span>
        </button>
      </div>

      <div v-show="!isSectionCollapsed('uploader')">
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
      </div>
    </section>

    <section class="card url-import">
      <div class="url-header">
        <div>
          <h2>{{ t('knowledgeBase.urlImportTitle') }}</h2>
          <p>{{ t('knowledgeBase.urlImportDesc') }}</p>
        </div>
        <button class="collapse-btn" @click="toggleSection('urlImport')">
          <span class="collapse-btn__icon">{{ isSectionCollapsed('urlImport') ? '▸' : '▾' }}</span>
          <span>{{ isSectionCollapsed('urlImport') ? '展开' : '收起' }}</span>
        </button>
      </div>
      <div v-show="!isSectionCollapsed('urlImport')" class="url-form">
        <input v-model="importUrl" :placeholder="t('knowledgeBase.urlPlaceholder')" />
        <button class="primary" :disabled="urlLoading || !importUrl.trim() || !selectedKnowledgeBaseId" @click="handleImportUrl">
          <span v-if="urlLoading">⏳ {{ t('knowledgeBase.importingUrl') }}</span>
          <span v-else>🔗 {{ t('knowledgeBase.importUrlAction') }}</span>
        </button>
      </div>
    </section>

    <section class="card doc-list">
      <div class="card-header-row">
        <h2>文档列表</h2>
        <div class="card-header-actions">
          <span class="total-hint">{{ t('knowledgeBase.totalDocs', { count: docTotal }) }}</span>
          <button class="collapse-btn" @click="toggleSection('docList')">
            <span class="collapse-btn__icon">{{ isSectionCollapsed('docList') ? '▸' : '▾' }}</span>
            <span>{{ isSectionCollapsed('docList') ? '展开' : '收起' }}</span>
          </button>
        </div>
      </div>
      <div v-show="!isSectionCollapsed('docList')">
        <div class="doc-filters">
          <input v-model="docSearch" :placeholder="t('knowledgeBase.docSearchPlaceholder')" @keyup.enter="fetchDocs" />
          <select v-model="docStatus" @change="fetchDocs">
            <option :value="null">{{ t('knowledgeBase.statusAll') }}</option>
            <option value="ready">{{ t('knowledgeBase.statusReady') }}</option>
            <option value="pending">{{ t('knowledgeBase.statusPending') }}</option>
          </select>
          <button class="filter-btn primary" @click="fetchDocs">{{ t('settings.refresh') }}</button>
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
      </div>
    </section>

    <section class="card chunk-panel" v-if="selectedDocId">
      <div class="card-header-row">
        <h2>文档分块管理</h2>
        <button class="collapse-btn" @click="toggleSection('chunkPanel')">
          <span class="collapse-btn__icon">{{ isSectionCollapsed('chunkPanel') ? '▸' : '▾' }}</span>
          <span>{{ isSectionCollapsed('chunkPanel') ? '展开' : '收起' }}</span>
        </button>
      </div>
      <div v-show="!isSectionCollapsed('chunkPanel')" class="chunk-panel-body">
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
      </div>
    </section>

    <section class="card recall-card">
      <div class="recall-header">
        <div>
          <h2>{{ t('knowledgeBase.recallTitle') }}</h2>
          <p>{{ t('knowledgeBase.recallDesc') }}</p>
        </div>
        <div class="card-header-actions">
          <div class="topk-input">
            <label>Top K</label>
            <input type="number" v-model.number="recallTopK" min="1" max="20" />
          </div>
          <button class="collapse-btn" @click="toggleSection('recall')">
            <span class="collapse-btn__icon">{{ isSectionCollapsed('recall') ? '▸' : '▾' }}</span>
            <span>{{ isSectionCollapsed('recall') ? '展开' : '收起' }}</span>
          </button>
        </div>
      </div>
      <div v-show="!isSectionCollapsed('recall')">
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
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { ElMessage } from 'element-plus';
import request from '@/utils/request';
import TeacherPageHeader from '@/components/TeacherPageHeader.vue';

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
const collapsedSections = ref<Record<string, boolean>>({
  instructions: false,
  knowledgeBase: false,
  uploader: false,
  urlImport: false,
  docList: false,
  chunkPanel: false,
  recall: false,
});

const selectedKnowledgeBaseName = computed(() => {
  const current = knowledgeBases.value.find((item) => item.id === selectedKnowledgeBaseId.value);
  return current?.name || '';
});

const toggleSection = (sectionKey: string) => {
  collapsedSections.value[sectionKey] = !collapsedSections.value[sectionKey];
};

const isSectionCollapsed = (sectionKey: string) => {
  return !!collapsedSections.value[sectionKey];
};

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
  min-width: 0;
}

.kb-view > .card + .card {
  margin-top: 24px;
}

.card {
  background: rgba(255, 255, 255, 0.9);
  border-radius: 26px;
  padding: 24px 28px;
  border: 1px solid rgba(214, 227, 243, 0.9);
  box-shadow: 0 6px 20px rgba(44, 62, 80, 0.08);
}

.instructions ol {
  margin: 12px 0;
  padding-left: 20px;
  line-height: 1.6;
  color: #566573;
  font-size: 14px;
}

.card-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.card-header-row h2 {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  color: #243246;
  line-height: 1.4;
}

.card-header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.collapse-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 36px;
  border: none;
  border-radius: 12px;
  padding: 0 12px;
  background: transparent;
  color: #8191a7;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  transition: background-color 0.2s ease, color 0.2s ease;
}

.collapse-btn:hover,
.collapse-btn:focus-visible {
  background: #eef2f6;
  color: #243246;
  outline: none;
}

.collapse-btn__icon {
  font-size: 12px;
  line-height: 1;
}

.hint {
  margin-top: 12px;
  font-size: 13px;
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
  font-size: 22px;
  font-weight: 700;
  color: #243246;
  line-height: 1.4;
}

.knowledge-base-header p,
.uploader-header p,
.url-header p,
.recall-header p {
  margin: 8px 0 0;
  color: #7a8798;
  font-size: 14px;
  line-height: 1.6;
}

.uploader-header h2,
.url-header h2,
.recall-header h2,
.chunk-list h3,
.add-chunk h3 {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  color: #243246;
  line-height: 1.4;
}

.uploader-header,
.url-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.uploader-header > div,
.url-header > div {
  min-width: 0;
}

.knowledge-base-controls {
  display: grid;
  grid-template-columns: 1.2fr 1fr;
  gap: 16px;
}

.knowledge-base-select-group,
.knowledge-base-create-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
  color: #566573;
  font-size: 13px;
  font-weight: 600;
}

.knowledge-base-create-group input,
.doc-filters input,
.doc-filters select,
.url-form input,
.recall-input,
.add-chunk textarea,
.chunk-edit textarea,
.topk-input input {
  min-height: 44px;
  box-sizing: border-box;
  padding: 12px;
  border-radius: 14px;
  border: 1px solid #d9e3ee;
  background: #ffffff;
  color: #273142;
  font-size: 14px;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background-color 0.2s ease;
}

.knowledge-base-create-group input:focus,
.doc-filters input:focus,
.doc-filters select:focus,
.url-form input:focus,
.recall-input:focus,
.add-chunk textarea:focus,
.chunk-edit textarea:focus,
.topk-input input:focus {
  outline: none;
  border-color: #243041;
  box-shadow: none;
}

.knowledge-base-create-group input::placeholder,
.doc-filters input::placeholder,
.url-form input::placeholder,
.recall-input::placeholder,
.add-chunk textarea::placeholder,
.chunk-edit textarea::placeholder {
  color: #a3afbf;
}

.knowledge-base-create-row {
  display: flex;
  gap: 10px;
  align-items: stretch;
  min-width: 0;
}

.knowledge-base-create-row input {
  flex: 1 1 auto;
  min-width: 0;
}

.knowledge-base-select-group :deep(.el-select) {
  width: 100%;
}

.knowledge-base-select-group :deep(.el-select__wrapper) {
  min-height: 44px;
  border-radius: 14px;
  border: 1px solid #d9e3ee;
  box-shadow: none;
  background: #ffffff;
  color: #273142;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background-color 0.2s ease;
}

.knowledge-base-select-group :deep(.el-select__wrapper.is-focused) {
  border-color: #243041;
  box-shadow: none;
}

.knowledge-base-select-group :deep(.el-select__placeholder),
.knowledge-base-select-group :deep(.el-select__selected-item) {
  font-size: 14px;
  color: #273142;
}

.knowledge-base-create-row button,
.actions button,
.url-form button,
.filter-btn.primary,
.add-chunk .primary,
.recall-actions .primary,
.doc-btn,
.chunk-buttons button,
.clear-btn {
  min-height: 44px;
  border: 1px solid #d9e3ee;
  border-radius: 14px;
  padding: 0 16px;
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  background: #ffffff;
  color: #6f8098;
  box-shadow: 0 3px 12px rgba(22, 34, 51, 0.04);
  transition: background-color 0.2s ease, border-color 0.2s ease, color 0.2s ease, box-shadow 0.2s ease;
  white-space: nowrap;
}

.knowledge-base-create-row button:hover:not(:disabled),
.actions button:hover:not(:disabled),
.url-form button:hover:not(:disabled),
.filter-btn.primary:hover:not(:disabled),
.add-chunk .primary:hover:not(:disabled),
.recall-actions .primary:hover:not(:disabled),
.doc-btn:hover:not(:disabled),
.chunk-buttons button:hover:not(:disabled),
.clear-btn:hover:not(:disabled) {
  border-color: #c3d0e0;
  background: #f9fbfd;
  color: #42526b;
}

.knowledge-base-create-row button:active:not(:disabled),
.actions button:active:not(:disabled),
.url-form button:active:not(:disabled),
.filter-btn.primary:active:not(:disabled),
.add-chunk .primary:active:not(:disabled),
.recall-actions .primary:active:not(:disabled),
.doc-btn:active:not(:disabled),
.chunk-buttons button:active:not(:disabled),
.clear-btn:active:not(:disabled),
.knowledge-base-create-row button:focus-visible:not(:disabled),
.actions button:focus-visible:not(:disabled),
.url-form button:focus-visible:not(:disabled),
.filter-btn.primary:focus-visible:not(:disabled),
.add-chunk .primary:focus-visible:not(:disabled),
.recall-actions .primary:focus-visible:not(:disabled),
.doc-btn:focus-visible:not(:disabled),
.chunk-buttons button:focus-visible:not(:disabled),
.clear-btn:focus-visible:not(:disabled) {
  outline: none;
  border-color: #202a39;
  background: #202a39;
  color: #ffffff;
  box-shadow: 0 10px 20px rgba(32, 42, 57, 0.14);
}

.knowledge-base-create-row button:disabled,
.actions button:disabled,
.url-form button:disabled,
.filter-btn.primary:disabled,
.add-chunk .primary:disabled,
.recall-actions .primary:disabled,
.doc-btn:disabled,
.chunk-buttons button:disabled,
.clear-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  box-shadow: none;
}

.knowledge-base-active,
.knowledge-base-empty {
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(44, 62, 80, 0.05);
  color: rgba(44, 62, 80, 0.78);
  font-size: 13px;
  line-height: 1.6;
}

.upload-dropzone {
  margin-top: 16px;
  border: 2px dashed rgba(44, 62, 80, 0.15);
  border-radius: 18px;
  padding: 40px;
  display: block;
  text-align: center;
  cursor: pointer;
  background: #f9fbfd;
  transition: border-color 0.3s ease, background-color 0.3s ease;
}

.upload-dropzone:hover {
  border-color: rgba(44, 62, 80, 0.4);
  background: #ffffff;
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
  color: #243246;
  font-size: 14px;
}

.file-size {
  margin: 2px 0 0;
  color: rgba(44, 62, 80, 0.6);
  font-size: 13px;
}

.clear-btn {
  color: #d7534b;
}

.preview-placeholder {
  padding: 16px;
  border-radius: 12px;
  background: rgba(44, 62, 80, 0.05);
  font-size: 13px;
  color: #6c7a89;
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
  flex-wrap: wrap;
}

.doc-list {
  margin-top: 24px;
}

.doc-filters {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.total-hint {
  color: #8a96a8;
  font-size: 13px;
  font-weight: 600;
}

.doc-table {
  width: 100%;
  border-collapse: collapse;
}

.doc-table th,
.doc-table td {
  border-bottom: 1px solid #f0f4f8;
  padding: 12px 14px;
  text-align: left;
  color: #425168;
  font-size: 13px;
}

.doc-table th {
  background: #ffffff;
  border-bottom: 1px solid #e4ebf3;
  color: #73839a;
  font-size: 12px;
  font-weight: 700;
}

.doc-actions {
  display: flex;
  gap: 8px;
}

.doc-btn {
  min-height: 36px;
  padding: 0 14px;
}

.chunk-panel {
  margin-top: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.chunk-panel-body {
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
  border: 1px solid #d9e3ee;
  border-radius: 18px;
  padding: 16px;
  max-height: 420px;
  overflow: auto;
  background: rgba(255, 255, 255, 0.95);
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
  color: #8a96a8;
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
  min-height: 88px;
  font-family: inherit;
  resize: vertical;
}

.chunk-edit .meta-input {
  min-height: 60px;
}

.chunk-buttons {
  display: flex;
  gap: 8px;
}

.chunk-buttons button {
  min-height: 36px;
  padding: 0 14px;
}

.add-chunk {
  border: 1px solid #d9e3ee;
  border-radius: 18px;
  padding: 16px;
  background: rgba(255, 255, 255, 0.9);
}

.url-form {
  display: flex;
  gap: 12px;
  margin-top: 16px;
  align-items: stretch;
}

@media (max-width: 900px) {
  .knowledge-base-controls,
  .chunk-panel-body {
    grid-template-columns: 1fr;
  }

  .url-form,
  .knowledge-base-create-row,
  .doc-filters {
    flex-direction: column;
    align-items: stretch;
  }
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
  color: #566573;
  font-size: 13px;
  font-weight: 600;
}

.topk-input input {
  width: 80px;
}

.recall-input {
  width: 100%;
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
  border: 1px solid #d9e3ee;
  border-radius: 16px;
  padding: 12px;
  background: #ffffff;
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
  color: #6f8098;
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
  background: #f4f7fb;
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

.url-form input {
  flex: 1;
}

@media (max-width: 900px) {
  .recall-header {
    flex-direction: column;
    align-items: stretch;
  }

  .card-header-row,
  .uploader-header,
  .url-header {
    flex-direction: column;
    align-items: stretch;
  }

  .card-header-actions {
    justify-content: space-between;
  }

  .topk-input input {
    width: 100%;
  }
}
</style>
