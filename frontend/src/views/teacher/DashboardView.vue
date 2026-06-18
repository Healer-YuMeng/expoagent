<template>
  <div class="dashboard-container">
    <!-- 统计卡片 - 四个卡片同一行 -->
    <div class="stats-grid">
      <div 
        class="stat-card glass"
        v-loading="loading"
      >
        <div class="stat-icon">📊</div>
        <div class="stat-label">{{ t('dashboard.todayConsultations') }}</div>
        <div class="stat-value">{{ stats?.today_consultations || 0 }}</div>
      </div>

      <div 
        class="stat-card glass"
        v-loading="loading"
      >
        <div class="stat-icon">✅</div>
        <div class="stat-label">{{ t('dashboard.validLeads') }}</div>
        <div class="stat-value">{{ stats?.valid_leads || 0 }}</div>
      </div>

      <div 
        class="stat-card glass clickable"
        v-loading="loading"
        @click="goToHighPriority"
      >
        <div class="stat-icon">🔥</div>
        <div class="stat-label">{{ t('dashboard.urgentFollowups') }}</div>
        <div class="stat-value-container">
          <div class="stat-value">{{ stats?.urgent_followups || 0 }}</div>
          <span class="stat-badge danger">{{ t('dashboard.highPriorityBadge') }}</span>
        </div>
      </div>

      <div 
        class="stat-card glass clickable"
        v-loading="loading"
        @click="goToManualCallbacks"
      >
        <div class="stat-icon">⚠️</div>
        <div class="stat-label">{{ t('dashboard.manualCallbacks') }}</div>
        <div class="stat-value-container">
          <div class="stat-value">{{ stats?.manual_callbacks || 0 }}</div>
          <span class="stat-badge danger">{{ t('dashboard.manualBadge') }}</span>
        </div>
      </div>
    </div>

    <!-- 错误提示 -->
    <div v-if="error" class="error-alert glass">
      <div class="error-icon">⚠️</div>
      <div class="error-text">{{ error }}</div>
    </div>

    <!-- 图表区域 -->
    <div class="charts-section">
      <!-- 左侧：咨询来源柱状图 -->
      <div class="chart-card glass">
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
      
      <!-- 右侧：用户关注雷达图 -->
      <div class="chart-card glass">
        <div class="chart-header">
          <h3 class="chart-title">{{ t('dashboard.userFocus') }}</h3>
        </div>
        <div ref="radarChartRef" class="chart-container"></div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, onUnmounted, watch } from 'vue';
import { useRouter } from 'vue-router';
import { storeToRefs } from 'pinia';
import { useDashboardStore } from '@/stores/dashboard';
import { useI18n } from 'vue-i18n';
import * as echarts from 'echarts';
import type { ECharts } from 'echarts';

const dashboardStore = useDashboardStore();
const { t, locale } = useI18n();
const { stats, loading, error } = storeToRefs(dashboardStore);
const router = useRouter();

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
  
  // 监听窗口大小变化
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

const initSourceChart = () => {
  if (!sourceChartRef.value) return;
  
  sourceChart = echarts.init(sourceChartRef.value);
  
  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow'
      },
      backgroundColor: 'rgba(255, 255, 255, 0.9)',
      borderColor: 'rgba(255, 255, 255, 0.4)',
      borderWidth: 1,
      textStyle: {
        color: '#2c3e50'
      }
    },
    legend: {
      data: [t('dashboard.visit'), t('dashboard.appointment')],
      top: 10,
      right: 20,
      textStyle: {
        color: 'rgba(44, 62, 80, 0.8)',
        fontSize: 13
      },
      itemWidth: 20,
      itemHeight: 12
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      top: '50px',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: getChannelLabels(),
      axisLine: {
        lineStyle: {
          color: 'rgba(44, 62, 80, 0.3)'
        }
      },
      axisLabel: {
        color: 'rgba(44, 62, 80, 0.8)',
        fontSize: 13,
        interval: 0,
        rotate: 0
      }
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      axisLine: {
        show: false
      },
      axisTick: {
        show: false
      },
      axisLabel: {
        color: 'rgba(44, 62, 80, 0.6)',
        fontSize: 12,
        formatter: (value: number) => Math.round(value).toString()
      },
      splitLine: {
        lineStyle: {
          color: 'rgba(44, 62, 80, 0.1)',
          type: 'dashed'
        }
      }
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
            { offset: 0, color: 'rgba(52, 152, 219, 0.9)' },
            { offset: 1, color: 'rgba(52, 152, 219, 0.6)' }
          ])
        },
        emphasis: {
          itemStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(52, 152, 219, 1)' },
              { offset: 1, color: 'rgba(52, 152, 219, 0.8)' }
            ])
          }
        },
        label: {
          show: true,
          position: 'top',
          color: 'rgba(44, 62, 80, 0.8)',
          fontSize: 12,
          fontWeight: 600
        }
      },
      {
        name: t('dashboard.appointment'),
        type: 'bar',
        data: getSeriesData('appointments'),
        barWidth: '28%',
        itemStyle: {
          borderRadius: [8, 8, 0, 0],
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(46, 204, 113, 0.9)' },
            { offset: 1, color: 'rgba(46, 204, 113, 0.6)' }
          ])
        },
        emphasis: {
          itemStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(46, 204, 113, 1)' },
              { offset: 1, color: 'rgba(46, 204, 113, 0.8)' }
            ])
          }
        },
        label: {
          show: true,
          position: 'top',
          color: 'rgba(44, 62, 80, 0.8)',
          fontSize: 12,
          fontWeight: 600
        }
      }
    ]
  };
  
  sourceChart.setOption(option);
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
  { name: t('dashboard.tuition'), max: 100 }
];

const getRadarSeriesItem = () => ({
  value: radarValues,
  name: t('dashboard.userAttention'),
  areaStyle: {
    color: new echarts.graphic.RadialGradient(0.5, 0.5, 1, [
      { offset: 0, color: 'rgba(52, 152, 219, 0.3)' },
      { offset: 1, color: 'rgba(52, 152, 219, 0.1)' }
    ])
  },
  lineStyle: {
    color: 'rgba(52, 152, 219, 0.9)',
    width: 2.5
  },
  itemStyle: {
    color: 'rgba(52, 152, 219, 1)',
    borderColor: '#fff',
    borderWidth: 2
  },
  label: {
    show: true,
    formatter: (params: any) => params.value,
    color: 'rgba(44, 62, 80, 0.8)',
    fontSize: 13,
    fontWeight: 600
  }
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
  
  const option = {
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(255, 255, 255, 0.9)',
      borderColor: 'rgba(255, 255, 255, 0.4)',
      borderWidth: 1,
      textStyle: {
        color: '#2c3e50'
      }
    },
    radar: {
      indicator: getRadarIndicators(),
      shape: 'polygon',
      splitNumber: 4,
      radius: '68%',
      center: ['50%', '52%'],
      axisName: {
        color: 'rgba(44, 62, 80, 0.8)',
        fontSize: 15,
        fontWeight: 500
      },
      splitLine: {
        lineStyle: {
          color: 'rgba(44, 62, 80, 0.15)'
        }
      },
      splitArea: {
        show: true,
        areaStyle: {
          color: [
            'rgba(52, 152, 219, 0.05)',
            'rgba(52, 152, 219, 0.1)',
            'rgba(52, 152, 219, 0.15)',
            'rgba(52, 152, 219, 0.2)'
          ]
        }
      },
      axisLine: {
        lineStyle: {
          color: 'rgba(44, 62, 80, 0.2)'
        }
      }
    },
    series: [
      {
        name: t('dashboard.attention'),
        type: 'radar',
        data: [getRadarSeriesItem()]
      }
    ]
  };
  
  radarChart.setOption(option);
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
        data: [getRadarSeriesItem()]
      }
    ]
  });
};

const goToHighPriority = () => {
  router.push({ name: 'HighIntentLeads' });
};

const goToManualCallbacks = () => {
  router.push({ name: 'ManualCallbacks' });
};
</script>

<style scoped>
.dashboard-container {
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

/* 统计卡片网格 - 四个卡片同一行 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 15px;
  margin-bottom: 20px;
}

/* 统计卡片 */
.stat-card {
  padding: 25px 20px;
  border-radius: 20px;
  transition: all 0.3s ease;
  position: relative;
  overflow: hidden;
}

.stat-card:hover {
  background: rgba(255, 255, 255, 0.35);
  transform: translateY(-5px);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.15);
}

.stat-card.clickable {
  cursor: pointer;
}

.stat-icon {
  font-size: 32px;
  margin-bottom: 12px;
}

.stat-label {
  font-size: 13px;
  color: rgba(44, 62, 80, 0.7);
  margin-bottom: 10px;
  font-weight: 500;
}

.stat-value {
  font-size: 32px;
  font-weight: 700;
  color: #2c3e50;
  line-height: 1;
}

.stat-value-container {
  display: flex;
  align-items: center;
  gap: 10px;
}

.stat-badge {
  padding: 4px 10px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
}

.stat-badge.danger {
  background: rgba(231, 76, 60, 0.3);
  color: #c0392b;
}

.stat-badge.warning {
  background: rgba(241, 196, 15, 0.3);
  color: #f39c12;
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

/* 图表区域 */
.charts-section {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-top: 20px;
}

.chart-card {
  padding: 30px;
  border-radius: 20px;
}

.chart-header {
  margin-bottom: 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.chart-title {
  font-size: 18px;
  font-weight: 600;
  color: #2c3e50;
  margin: 0;
}

.chart-actions {
  display: flex;
  gap: 8px;
}

.period-btn {
  border: 1px solid rgba(44, 62, 80, 0.2);
  border-radius: 999px;
  padding: 6px 14px;
  background: transparent;
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  color: rgba(44, 62, 80, 0.7);
}

.period-btn.active {
  background: rgba(52, 152, 219, 0.15);
  border-color: rgba(52, 152, 219, 0.4);
  color: #2980b9;
}

.chart-container {
  width: 100%;
  height: 450px;
}

/* 响应式设计 */
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
    padding: 20px 18px;
  }
  
  .stat-icon {
    font-size: 28px;
  }
  
  .stat-label {
    font-size: 12px;
  }
  
  .stat-value {
    font-size: 28px;
  }
}

@media (max-width: 900px) {
  .stats-grid {
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }
  
  .stat-card {
    padding: 18px 15px;
  }
  
  .stat-icon {
    font-size: 26px;
    margin-bottom: 8px;
  }
  
  .stat-value {
    font-size: 24px;
  }
  
  .stat-badge {
    font-size: 10px;
    padding: 3px 8px;
  }
}

@media (max-width: 768px) {
  .stats-grid {
    grid-template-columns: 1fr;
    gap: 12px;
  }
  
  .stat-card {
    padding: 20px;
  }
  
  .stat-icon {
    font-size: 32px;
  }
  
  .stat-label {
    font-size: 13px;
  }
  
  .stat-value {
    font-size: 32px;
  }
  
  .chart-card {
    padding: 20px;
  }
  
  .chart-container {
    height: 320px;
  }
  
  .chart-title {
    font-size: 16px;
  }
}
</style>
