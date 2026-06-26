<template>
  <div class="dashboard-container">
    <div class="stats-grid">
      <div class="stat-card" v-loading="loading">
        <div class="stat-icon-panel slate">
          <el-icon class="stat-icon"><Histogram /></el-icon>
        </div>
        <div class="stat-label">{{ t('dashboard.todayConsultations') }}</div>
        <div class="stat-value">{{ stats?.today_consultations || 0 }}</div>
      </div>

      <div class="stat-card" v-loading="loading">
        <div class="stat-icon-panel success">
          <el-icon class="stat-icon"><CircleCheck /></el-icon>
        </div>
        <div class="stat-label">{{ t('dashboard.validLeads') }}</div>
        <div class="stat-value">{{ stats?.valid_leads || 0 }}</div>
      </div>

      <div class="stat-card clickable" v-loading="loading" @click="goToHighPriority">
        <div class="stat-icon-panel accent">
          <el-icon class="stat-icon"><Opportunity /></el-icon>
        </div>
        <div class="stat-label">{{ t('dashboard.urgentFollowups') }}</div>
        <div class="stat-value-container">
          <div class="stat-value">{{ stats?.urgent_followups || 0 }}</div>
          <span class="stat-badge neutral">{{ t('dashboard.highPriorityBadge') }}</span>
        </div>
      </div>

      <div class="stat-card clickable" v-loading="loading" @click="goToManualCallbacks">
        <div class="stat-icon-panel warning">
          <el-icon class="stat-icon"><Warning /></el-icon>
        </div>
        <div class="stat-label">{{ t('dashboard.manualCallbacks') }}</div>
        <div class="stat-value-container">
          <div class="stat-value">{{ stats?.manual_callbacks || 0 }}</div>
          <span class="stat-badge neutral">{{ t('dashboard.manualBadge') }}</span>
        </div>
      </div>
    </div>

    <div v-if="error" class="error-alert">
      <el-icon class="error-icon"><Warning /></el-icon>
      <div class="error-text">{{ error }}</div>
    </div>

    <div class="charts-section">
      <div class="chart-card">
        <div class="chart-header">
          <h3 class="chart-title">{{ t('dashboard.consultationSource') }}</h3>
          <div class="chart-actions">
            <button
              v-for="period in sourcePeriods"
              :key="period"
              :class="['period-btn', { active: selectedSourcePeriod === period }]"
              @click="selectedSourcePeriod = period"
            >
              {{ t(`dashboard.period.${period}`) }}
            </button>
          </div>
        </div>
        <div ref="sourceChartRef" class="chart-container"></div>
      </div>

      <div class="chart-card">
        <div class="chart-header">
          <h3 class="chart-title">{{ t('dashboard.userFocus') }}</h3>
        </div>
        <div ref="radarChartRef" class="chart-container"></div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { storeToRefs } from 'pinia';
import { useDashboardStore } from '@/stores/dashboard';
import { useI18n } from 'vue-i18n';
import { CircleCheck, Histogram, Opportunity, Warning } from '@element-plus/icons-vue';
import * as echarts from 'echarts';
import type { ECharts } from 'echarts';
import { useAuthStore } from '@/stores/auth';
import { getPortalPath } from '@/router/portalRoutes';

const dashboardStore = useDashboardStore();
const { t, locale } = useI18n();
const { stats, loading, error } = storeToRefs(dashboardStore);
const router = useRouter();
const authStore = useAuthStore();

const sourceChartRef = ref<HTMLElement>();
const radarChartRef = ref<HTMLElement>();
let sourceChart: ECharts | null = null;
let radarChart: ECharts | null = null;
type SourcePeriod = 'daily' | 'monthly' | 'yearly';
const sourcePeriods: SourcePeriod[] = ['daily', 'monthly', 'yearly'];
const selectedSourcePeriod = ref<SourcePeriod>('daily');
const radarValues = [92, 88, 85, 78, 75, 82, 86];
const channelOrder = ['xhs', 'dy', 'blbl', 'wb', 'gzh', 'wxsp'];
const channelLabelKeys: Record<string, string> = {
  xhs: 'dashboard.sources.xiaohongshu',
  dy: 'dashboard.sources.douyin',
  blbl: 'dashboard.sources.bilibili',
  wb: 'dashboard.sources.weibo',
  gzh: 'dashboard.sources.wechatOfficialAccount',
  wxsp: 'dashboard.sources.wechatVideo',
};

onMounted(() => {
  dashboardStore.fetchDashboardStats();
  initSourceChart();
  initRadarChart();
  window.addEventListener('resize', handleResize);
});

watch(
  () => stats.value?.source_stats,
  () => {
    updateSourceChart();
  }
);

watch(selectedSourcePeriod, () => {
  updateSourceChart();
});

watch(
  () => locale.value,
  () => {
    updateSourceChart();
    updateRadarChart();
  }
);

onUnmounted(() => {
  window.removeEventListener('resize', handleResize);
  if (sourceChart) {
    sourceChart.dispose();
  }
  if (radarChart) {
    radarChart.dispose();
  }
});

const handleResize = () => {
  if (sourceChart) {
    sourceChart.resize();
  }
  if (radarChart) {
    radarChart.resize();
  }
};

const baseTooltip = {
  backgroundColor: 'rgba(255, 255, 255, 0.98)',
  borderColor: '#dbe3ee',
  borderWidth: 1,
  textStyle: {
    color: '#243041',
  },
};

const initSourceChart = () => {
  if (!sourceChartRef.value) return;

  sourceChart = echarts.init(sourceChartRef.value);

  sourceChart.setOption({
    tooltip: {
      ...baseTooltip,
      trigger: 'axis',
      axisPointer: {
        type: 'shadow',
      },
    },
    legend: {
      data: [t('dashboard.visit'), t('dashboard.appointment')],
      top: 10,
      right: 18,
      textStyle: {
        color: '#6a7890',
        fontSize: 13,
        fontWeight: 600,
      },
      itemWidth: 16,
      itemHeight: 10,
      itemGap: 18,
    },
    grid: {
      left: '4%',
      right: '4%',
      bottom: '4%',
      top: '54px',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: getChannelLabels(),
      axisLine: {
        lineStyle: {
          color: '#d9e1ec',
        },
      },
      axisLabel: {
        color: '#6b7a90',
        fontSize: 13,
        interval: 0,
      },
      axisTick: {
        show: false,
      },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      axisLine: {
        show: false,
      },
      axisTick: {
        show: false,
      },
      axisLabel: {
        color: '#8b97aa',
        fontSize: 12,
        formatter: (value: number) => Math.round(value).toString(),
      },
      splitLine: {
        lineStyle: {
          color: '#edf2f8',
          type: 'dashed',
        },
      },
    },
    series: [
      {
        name: t('dashboard.visit'),
        type: 'bar',
        data: getSeriesData('visits'),
        barWidth: '28%',
        itemStyle: {
          borderRadius: [8, 8, 0, 0],
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#94a3b8' },
            { offset: 1, color: '#7c8ea7' },
          ]),
        },
        emphasis: {
          itemStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: '#7f90a8' },
              { offset: 1, color: '#6d7f98' },
            ]),
          },
        },
        label: {
          show: true,
          position: 'top',
          color: '#4e5b6d',
          fontSize: 12,
          fontWeight: 600,
        },
      },
      {
        name: t('dashboard.appointment'),
        type: 'bar',
        data: getSeriesData('appointments'),
        barWidth: '28%',
        itemStyle: {
          borderRadius: [8, 8, 0, 0],
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#7ee0b0' },
            { offset: 1, color: '#5ecf9d' },
          ]),
        },
        emphasis: {
          itemStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: '#6fd6a8' },
              { offset: 1, color: '#4ebd8d' },
            ]),
          },
        },
        label: {
          show: true,
          position: 'top',
          color: '#4e5b6d',
          fontSize: 12,
          fontWeight: 600,
        },
      },
    ],
  });

  updateSourceChart();
};

const getChannelLabels = () => channelOrder.map((slug) => t(channelLabelKeys[slug] ?? slug));

const getSeriesData = (metric: 'visits' | 'appointments') => {
  const periodStats = stats.value?.source_stats?.[selectedSourcePeriod.value] ?? [];
  return channelOrder.map((slug) => {
    const entry = periodStats.find((item) => item.channel === slug);
    if (!entry) return 0;
    return metric === 'visits' ? entry.visits : entry.appointments;
  });
};

const getRadarIndicators = () => [
  { name: t('dashboard.teachingStaff'), max: 100 },
  { name: t('dashboard.enrollment'), max: 100 },
  { name: t('dashboard.environment'), max: 100 },
  { name: t('dashboard.food'), max: 100 },
  { name: t('dashboard.accommodation'), max: 100 },
  { name: t('dashboard.facilities'), max: 100 },
  { name: t('dashboard.tuition'), max: 100 },
];

const getRadarSeriesItem = () => ({
  value: radarValues,
  name: t('dashboard.userAttention'),
  areaStyle: {
    color: new echarts.graphic.RadialGradient(0.5, 0.5, 1, [
      { offset: 0, color: 'rgba(148, 163, 184, 0.28)' },
      { offset: 1, color: 'rgba(148, 163, 184, 0.08)' },
    ]),
  },
  lineStyle: {
    color: '#7d8ea7',
    width: 2.5,
  },
  itemStyle: {
    color: '#7d8ea7',
    borderColor: '#ffffff',
    borderWidth: 2,
  },
  label: {
    show: true,
    formatter: (params: any) => params.value,
    color: '#526071',
    fontSize: 13,
    fontWeight: 600,
  },
});

const updateSourceChart = () => {
  if (!sourceChart) return;
  sourceChart.setOption({
    legend: {
      data: [t('dashboard.visit'), t('dashboard.appointment')],
    },
    xAxis: { data: getChannelLabels() },
    series: [
      { name: t('dashboard.visit'), data: getSeriesData('visits') },
      { name: t('dashboard.appointment'), data: getSeriesData('appointments') },
    ],
  });
};

const initRadarChart = () => {
  if (!radarChartRef.value) return;

  radarChart = echarts.init(radarChartRef.value);

  radarChart.setOption({
    tooltip: {
      ...baseTooltip,
      trigger: 'item',
    },
    radar: {
      indicator: getRadarIndicators(),
      shape: 'polygon',
      splitNumber: 4,
      radius: '68%',
      center: ['50%', '52%'],
      axisName: {
        color: '#5d6c82',
        fontSize: 15,
        fontWeight: 600,
      },
      splitLine: {
        lineStyle: {
          color: '#dde5ef',
        },
      },
      splitArea: {
        show: true,
        areaStyle: {
          color: [
            'rgba(148, 163, 184, 0.05)',
            'rgba(148, 163, 184, 0.08)',
            'rgba(148, 163, 184, 0.12)',
            'rgba(148, 163, 184, 0.16)',
          ],
        },
      },
      axisLine: {
        lineStyle: {
          color: '#d6deea',
        },
      },
    },
    series: [
      {
        name: t('dashboard.attention'),
        type: 'radar',
        data: [getRadarSeriesItem()],
      },
    ],
  });
};

const updateRadarChart = () => {
  if (!radarChart) return;
  radarChart.setOption({
    radar: {
      indicator: getRadarIndicators(),
    },
    series: [
      {
        name: t('dashboard.attention'),
        type: 'radar',
        data: [getRadarSeriesItem()],
      },
    ],
  });
};

const goToHighPriority = () => {
  router.push({
    path: getPortalPath(authStore.userRole, 'leads'),
    query: { high_intent_only: 'true' },
  });
};

const goToManualCallbacks = () => {
  router.push(getPortalPath(authStore.userRole, 'manualCallbacks'));
};
</script>

<style scoped>
.dashboard-container {
  padding: 4px 6px 10px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 18px;
  margin-bottom: 22px;
}

.stat-card {
  position: relative;
  overflow: hidden;
  padding: 28px 28px 26px;
  border: 1px solid #e5e9ef;
  border-radius: 24px;
  background: #ffffff;
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.05);
  transition:
    transform 0.22s ease,
    box-shadow 0.22s ease,
    border-color 0.22s ease;
}

.stat-card:hover {
  transform: translateY(-2px);
  border-color: #d8dee6;
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.07);
}

.stat-card.clickable {
  cursor: pointer;
}

.stat-icon-panel {
  display: grid;
  width: 72px;
  height: 72px;
  margin-bottom: 18px;
  place-items: center;
  border-radius: 22px;
}

.stat-icon-panel.slate {
  background: #f4f6f8;
  color: #303948;
}

.stat-icon-panel.success {
  background: #f4f6f8;
  color: #4f5f72;
}

.stat-icon-panel.accent {
  background: #f4f6f8;
  color: #4f5f72;
}

.stat-icon-panel.warning {
  background: #f4f6f8;
  color: #4f5f72;
}

.stat-icon {
  font-size: 34px;
}

.stat-label {
  margin-bottom: 14px;
  color: #6d7c91;
  font-size: 15px;
  font-weight: 600;
}

.stat-value {
  color: #1f2937;
  font-size: 58px;
  font-weight: 700;
  line-height: 1;
  letter-spacing: -0.04em;
}

.stat-value-container {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.stat-badge {
  padding: 7px 12px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 600;
}

.stat-badge.neutral {
  background: #eef1f5;
  color: #617286;
}

.error-alert {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 20px;
  padding: 18px 22px;
  border: 1px solid #ecd7d3;
  border-radius: 18px;
  background: #fffafa;
}

.error-icon {
  color: #d26a5c;
  font-size: 20px;
}

.error-text {
  flex: 1;
  color: #b65449;
  font-weight: 600;
}

.charts-section {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px;
}

.chart-card {
  padding: 30px 34px;
  border: 1px solid #e5e9ef;
  border-radius: 26px;
  background: #ffffff;
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.05);
}

.chart-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
}

.chart-title {
  margin: 0;
  color: #1f2937;
  font-size: 20px;
  font-weight: 700;
}

.chart-actions {
  display: flex;
  gap: 8px;
}

.period-btn {
  min-width: 60px;
  padding: 10px 15px;
  border: 1px solid #dde3ea;
  border-radius: 999px;
  background: #ffffff;
  color: #66778e;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition:
    background-color 0.2s ease,
    color 0.2s ease,
    border-color 0.2s ease,
    box-shadow 0.2s ease;
}

.period-btn.active {
  border-color: #222f40;
  background: #222f40;
  box-shadow: 0 8px 16px rgba(34, 47, 64, 0.18);
  color: #ffffff;
}

.chart-container {
  width: 100%;
  height: 450px;
}

@media (max-width: 1600px) {
  .stats-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (max-width: 1200px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .charts-section {
    grid-template-columns: 1fr;
  }

  .stat-card {
    padding: 24px 22px;
  }

  .stat-label {
    font-size: 14px;
  }

  .stat-value {
    font-size: 48px;
  }
}

@media (max-width: 900px) {
  .stats-grid {
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }

  .stat-card {
    padding: 22px 18px;
  }

  .stat-value {
    font-size: 42px;
  }

  .stat-badge {
    padding: 6px 10px;
    font-size: 12px;
  }
}

@media (max-width: 768px) {
  .dashboard-container {
    padding: 0;
  }

  .stats-grid {
    grid-template-columns: 1fr;
    gap: 12px;
  }

  .stat-card {
    padding: 22px 20px;
  }

  .stat-label {
    font-size: 14px;
  }

  .stat-value {
    font-size: 44px;
  }

  .chart-card {
    padding: 24px 18px;
  }

  .chart-container {
    height: 320px;
  }

  .chart-title {
    font-size: 16px;
  }

  .chart-header {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
