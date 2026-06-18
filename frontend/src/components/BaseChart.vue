<template>
  <div ref="chartRef" :style="{ height: height, width: width }" />
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue';
import * as echarts from 'echarts';

type EChartsOption = echarts.EChartsOption;

const props = withDefaults(defineProps<{
  option: EChartsOption;
  width?: string;
  height?: string;
}>(), {
  width: '100%',
  height: '400px',
});

const chartRef = ref<HTMLDivElement>();
let chart: echarts.ECharts | null = null;

const initChart = () => {
  if (chartRef.value) {
    chart = echarts.init(chartRef.value);
    chart.setOption(props.option);
  }
};

const resizeChart = () => {
  chart?.resize();
};

watch(() => props.option, (newOption) => {
  if (chart) {
    chart.setOption(newOption);
  }
}, { deep: true });

onMounted(() => {
  nextTick(() => {
    initChart();
  });
  window.addEventListener('resize', resizeChart);
});

onUnmounted(() => {
  chart?.dispose();
  window.removeEventListener('resize', resizeChart);
});
</script>
