import { defineStore } from 'pinia';
import { computed, ref } from 'vue';
import {
  getTeacherFeatureGates,
  updateTeacherFeatureGate,
  type ControlledPortalFeatureTarget,
  type FeatureGateModules,
} from '@/api/teacher';

export const FEATURE_GATE_SYNC_EVENT_KEY = 'ycis_feature_gate_updated_at';
const FEATURE_GATE_CACHE_KEY = 'ycis_feature_gate_modules';

const DEFAULT_FEATURE_GATES: FeatureGateModules = {
  manualCallbacks: true,
  systemPrompt: true,
  userManagement: true,
  systemSettings: true,
};

function loadFeatureGateModulesCache(): FeatureGateModules {
  if (typeof window === 'undefined') {
    return { ...DEFAULT_FEATURE_GATES };
  }

  try {
    const rawValue = window.localStorage.getItem(FEATURE_GATE_CACHE_KEY);
    if (!rawValue) {
      return { ...DEFAULT_FEATURE_GATES };
    }
    const parsedValue = JSON.parse(rawValue);
    if (!parsedValue || typeof parsedValue !== 'object') {
      return { ...DEFAULT_FEATURE_GATES };
    }
    return {
      ...DEFAULT_FEATURE_GATES,
      ...parsedValue,
    };
  } catch (error) {
    console.warn('Failed to restore feature gate cache:', error);
    return { ...DEFAULT_FEATURE_GATES };
  }
}

function persistFeatureGateModulesCache(modules: FeatureGateModules) {
  if (typeof window === 'undefined') {
    return;
  }

  window.localStorage.setItem(FEATURE_GATE_CACHE_KEY, JSON.stringify(modules));
}

export const useFeatureGateStore = defineStore('featureGate', () => {
  const modules = ref<FeatureGateModules>(loadFeatureGateModulesCache());
  const loaded = ref(false);
  const loading = ref(false);
  const updatingModule = ref<ControlledPortalFeatureTarget | null>(null);

  function applyFeatureGateModules(nextModules: Partial<FeatureGateModules> | null | undefined) {
    modules.value = { ...DEFAULT_FEATURE_GATES, ...(nextModules || {}) };
    persistFeatureGateModulesCache(modules.value);
    loaded.value = true;
    return modules.value;
  }

  async function fetchFeatureGates(force = false) {
    if (loaded.value && !force) {
      return modules.value;
    }
    loading.value = true;
    try {
      const response = await getTeacherFeatureGates();
      return applyFeatureGateModules(response.modules);
    } catch (error) {
      throw error;
    } finally {
      loading.value = false;
    }
  }

  async function setFeatureGate(target: ControlledPortalFeatureTarget, enabled: boolean) {
    updatingModule.value = target;
    try {
      const response = await updateTeacherFeatureGate(target, enabled);
      applyFeatureGateModules(response.modules);
      localStorage.setItem(FEATURE_GATE_SYNC_EVENT_KEY, String(Date.now()));
      return modules.value;
    } finally {
      updatingModule.value = null;
    }
  }

  const hasLoadedFeatureGates = computed(() => loaded.value);

  return {
    modules,
    loaded,
    loading,
    updatingModule,
    hasLoadedFeatureGates,
    applyFeatureGateModules,
    fetchFeatureGates,
    setFeatureGate,
  };
});
