<template>
  <div v-if="option" style="width:100%;height:380px;">
    <v-chart class="chart" :option="option" autoresize />
  </div>
  <div v-else style="text-align:center;color:var(--text-muted);padding:40px;">暂无雷达数据</div>
</template>

<script setup>
import { computed } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { RadarChart as ERadarChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent, TitleComponent } from 'echarts/components'
import VChart from 'vue-echarts'

use([CanvasRenderer, ERadarChart, TooltipComponent, LegendComponent, TitleComponent])

const props = defineProps({ radar: Object })

const option = computed(() => {
  if (!props.radar || !props.radar.dimensions) return null
  const d = props.radar.dimensions
  const indicators = [
    { name: '准确性', max: 10 },
    { name: '完整性', max: 10 },
    { name: '深度', max: 10 },
    { name: '清晰度', max: 10 },
  ]
  const values = [d.accuracy, d.completeness, d.depth, d.clarity]
  return {
    title: {
      text: '能力雷达图', left: 'center', top: 8,
      textStyle: { fontSize: 14, fontWeight: 600, color: '#52525b' },
    },
    tooltip: { trigger: 'item' },
    legend: { bottom: 0, data: [props.radar.role_title || '候选人'] },
    radar: {
      indicator: indicators,
      radius: '62%',
      center: ['50%', '54%'],
      splitArea: { areaStyle: { color: ['#fafafa', '#f4f4f5'] } },
      splitLine: { lineStyle: { color: '#e4e4e7' } },
      axisLine: { lineStyle: { color: '#d4d4d8' } },
      axisName: { color: '#52525b', fontSize: 12 },
    },
    series: [{
      type: 'radar',
      data: [{
        value: values,
        name: props.radar.role_title || '候选人',
        areaStyle: { color: 'rgba(82,82,91,0.22)' },
        lineStyle: { color: '#52525b', width: 2 },
        itemStyle: { color: '#18181b' },
      }],
    }],
  }
})
</script>
