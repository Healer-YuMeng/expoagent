import { onMounted } from 'vue';
import { getTeacherFeatureGates } from '@/api/teacher';
import { useFeatureGateStore } from '@/stores/featureGate';

export function useFeatureGateBootstrap() {
  const featureGateStore = useFeatureGateStore();

  onMounted(() => {
    void getTeacherFeatureGates().then((response) => {
      featureGateStore.applyFeatureGateModules(response.modules || {});
    }).catch((error) => {
      console.error('Failed to bootstrap feature gates:', error);
    });
  });
}
