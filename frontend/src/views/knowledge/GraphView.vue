<template>
  <div class="kb-page">
    <TopNav />

    <div class="kb-container">
      <div class="graph-header">
        <div>
          <h1 class="kb-title">知识图谱</h1>
          <p class="kb-subtitle">
            节点大小 = 连接数 ·
            <span class="legend-dot note"></span>笔记
            <span class="legend-dot file"></span>文件
            <span class="legend-dot url"></span>网址
            <span class="legend-dot virtual"></span>未创建 ·
            实线 = [[链接]]，虚线 = 语义关联
          </p>
        </div>
        <div class="graph-actions">
          <button v-if="!rebuilding" class="ds-btn ds-btn-ghost" style="padding:6px 12px;font-size:13px;"
                  title="重建向量与语义关联 (上传/修改较多后使用)" @click="rebuild"><DSIcon name="refresh" :size="13" />重建索引</button>
          <button v-else class="ds-btn ds-btn-ghost" style="padding:6px 12px;font-size:13px;" disabled>重建中…</button>
          <button class="ds-btn ds-btn-ghost" style="padding:6px 12px;font-size:13px;" @click="relayout">重新布局</button>
          <button class="ds-btn ds-btn-ghost" style="padding:6px 12px;font-size:13px;" @click="load">刷新</button>
        </div>
      </div>

      <!-- 过滤工具条 -->
      <div v-if="categories.length" class="filter-bar">
        <span class="filter-label">分类过滤:</span>
        <button v-for="c in categories" :key="c.category"
                class="kb-tag cat-chip" :class="{ active: activeCategories.has(c.category) }"
                @click="toggleCategory(c.category)"><DSIcon name="folder" :size="12" />{{ c.category }} ({{ c.count }})</button>
        <label class="sem-toggle">
          <input type="checkbox" v-model="showSemantic" @change="load" />
          显示语义边
        </label>
      </div>

      <div class="graph-wrap ds-card">
        <div v-if="loading" class="graph-status">图谱加载中…</div>
        <div v-else-if="error" class="graph-status" style="color: var(--error);">{{ error }}</div>
        <div v-else-if="!nodeCount" class="graph-status">
          图谱为空。先去写几篇笔记或导入文件，用 [[标题]] 互相链接起来吧。
          <router-link to="/knowledge" style="color: var(--brand-600);">去写笔记 →</router-link>
        </div>
        <div ref="cyContainer" class="cy-container" v-show="nodeCount > 0"></div>

        <div v-if="nodeCount" class="graph-stats">
          {{ nodeCount }} 节点（{{ virtualCount }} 虚）· {{ wikiEdgeCount }} 双链 · {{ semEdgeCount }} 语义
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import cytoscape from 'cytoscape'
import TopNav from '../../components/TopNav.vue'
import DSIcon from '../../components/DSIcon.vue'
import { kbGraph, kbCategories, kbCreateNote, kbRebuild } from '../../api'

const router = useRouter()
const cyContainer = ref(null)
const loading = ref(false)
const error = ref('')
const nodeCount = ref(0)
const virtualCount = ref(0)
const wikiEdgeCount = ref(0)
const semEdgeCount = ref(0)
const categories = ref([])
const activeCategories = ref(new Set())
const showSemantic = ref(true)
const rebuilding = ref(false)

let cy = null
const noteIdByTitle = new Map()

// 类型 → 配色 (高饱和度 + 白色描边, 保证视觉区分度)
const TYPE_COLORS = {
  note:    '#3b82f6',   // 亮蓝
  file:    '#10b981',   // 翠绿
  url:     '#f59e0b',   // 琥珀
  virtual: '#9ca3af',   // 中灰
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const catParam = [...activeCategories.value].join(',')
    const result = await kbGraph(showSemantic.value, catParam)
    if (!result.success) {
      error.value = result.message || '加载失败'
      return
    }
    render(result.graph)
  } catch (e) {
    error.value = '无法连接后端服务'
  } finally {
    loading.value = false
  }
}

async function loadCategories() {
  const result = await kbCategories()
  if (result.success) categories.value = result.categories
}

function toggleCategory(c) {
  if (activeCategories.value.has(c)) activeCategories.value.delete(c)
  else activeCategories.value.add(c)
  activeCategories.value = new Set(activeCategories.value)
  load()
}

async function rebuild() {
  if (rebuilding.value) return
  rebuilding.value = true
  try {
    const result = await kbRebuild()
    if (result.success) {
      alert(`重建完成: ${result.notes} 篇笔记向量, ${result.sem_links} 条语义关联`)
      await load()
    } else {
      alert(result.message || '重建失败')
    }
  } finally {
    rebuilding.value = false
  }
}

/** 节点标签: 最多两行、每行 8 字, 超出省略; 全名放 tooltip, 避免长问题文本互相遮挡 */
function shortLabel(title) {
  const t = (title || '').trim()
  if (!t) return ''
  const LINE = 8
  const MAX = LINE * 2
  if (t.length <= LINE) return t
  const line1 = t.slice(0, LINE)
  const line2 = t.slice(LINE, MAX) + (t.length > MAX ? '…' : '')
  return line1 + '\n' + line2
}

/** 计算节点度并分配尺寸/颜色 */
function buildElements(graph) {
  // 重新算 degree (后端返回的可能不准)
  const degreeMap = {}
  graph.nodes.forEach(n => { degreeMap[n.id] = 0 })
  graph.edges.forEach(e => {
    if (degreeMap[e.source] !== undefined) degreeMap[e.source]++
    if (degreeMap[e.target] !== undefined) degreeMap[e.target]++
  })
  const maxDeg = Math.max(1, ...Object.values(degreeMap))

  return {
    nodes: graph.nodes.map(n => {
      const deg = degreeMap[n.id] ?? 0
      const isVirtual = !!n.virtual
      const color = isVirtual ? TYPE_COLORS.virtual : (TYPE_COLORS[n.note_type] || TYPE_COLORS.note)
      // 节点尺寸: 18~36, 避免过大导致重叠
      const size = 18 + 18 * Math.sqrt(deg / maxDeg)
      return {
        data: {
          id: n.id,
          label: shortLabel(n.id),
          fullLabel: n.id,
          size,
          color,
          borderColor: isVirtual ? '#6b7280' : '#ffffff',
          // cytoscape 选择器不支持布尔字面量, 用字符串标记
          virtual: isVirtual ? 'yes' : 'no',
          category: n.category || '',
          noteType: n.note_type || 'note',
        },
      }
    }),
    edges: graph.edges.map((e, i) => ({
      data: {
        id: `e${i}`,
        source: e.source,
        target: e.target,
        kind: e.kind,
        virtual: e.virtual ? 'yes' : 'no',
        score: e.score,
      },
    })),
  }
}

function render(graph) {
  nodeCount.value = graph.nodes.length
  virtualCount.value = graph.nodes.filter(n => n.virtual).length
  wikiEdgeCount.value = graph.edges.filter(e => e.kind === 'wiki').length
  semEdgeCount.value = graph.edges.filter(e => e.kind === 'semantic').length
  if (!graph.nodes.length) return

  noteIdByTitle.clear()
  for (const n of graph.nodes) noteIdByTitle.set(n.id, n.note_id)

  const { nodes, edges } = buildElements(graph)

  nextTick(() => {
    if (cy) { cy.destroy(); cy = null }
    cy = cytoscape({
      container: cyContainer.value,
      elements: [...nodes, ...edges],
      style: [
        // ---- 节点基础 ----
        {
          selector: 'node',
          style: {
            'label': 'data(label)',
            'title': 'data(fullLabel)',
            'background-color': 'data(color)',
            'width': 'data(size)',
            'height': 'data(size)',
            'border-width': 3,
            'border-color': 'data(borderColor)',
            'color': '#1e293b',
            'font-size': 12,
            'font-weight': 600,
            'text-valign': 'bottom',
            'text-halign': 'center',
            'text-margin-y': 8,
            'text-wrap': 'wrap',
            'text-max-width': 112,
            'text-outline-color': '#ffffff',
            'text-outline-width': 2,
            'text-background-color': '#ffffff',
            'text-background-opacity': 0.85,
            'text-background-padding': 2,
            'text-background-shape': 'roundrectangle',
          },
        },
        // ---- 虚节点 ----
        {
          selector: 'node[virtual = "yes"]',
          style: {
            'background-color': TYPE_COLORS.virtual,
            'border-color': '#6b7280',
            'border-style': 'dashed',
            'color': '#6b7280',
            'font-size': 11,
          },
        },
        // ---- Wiki 边 (实线, 深灰) ----
        {
          selector: 'edge[kind = "wiki"]',
          style: {
            'width': 2,
            'line-color': '#94a3b8',
            'curve-style': 'bezier',
            'opacity': 0.7,
          },
        },
        {
          selector: 'edge[kind = "wiki"][virtual = "yes"]',
          style: {
            'line-style': 'dashed',
            'line-color': '#cbd5e1',
            'opacity': 0.5,
          },
        },
        // ---- 语义边 (虚线, 淡紫) ----
        {
          selector: 'edge[kind = "semantic"]',
          style: {
            'width': 1.5,
            'line-style': 'dashed',
            'line-color': '#a78bfa',
            'curve-style': 'bezier',
            'opacity': 0.45,
          },
        },
        // ---- 选中 ----
        {
          selector: 'node:selected',
          style: {
            'border-width': 4,
            'border-color': '#ef4444',
          },
        },
      ],
      layout: {
        name: 'cose',
        animate: true,
        animationDuration: 800,
        animationEasing: 'ease-out-cubic',
        // 关键参数: 强排斥 + 长边距 → 节点自然散开
        nodeRepulsion: () => 12000,
        idealEdgeLength: () => 160,
        edgeElasticity: () => 80,
        nestingFactor: 1.2,
        gravity: 0.15,
        numIter: 2000,
        initialTemp: 300,
        coolingFactor: 0.97,
        minTemp: 1.0,
        padding: 60,
        nodeDimensionsIncludeLabels: true,
      },
      minZoom: 0.3,
      maxZoom: 3,
      wheelSensitivity: 0.3,
    })
    window.__cy = cy // 调试句柄, 便于控制台排查图谱

    // ---- hover: 聚焦当前节点及其关联 ----
    cy.on('mouseover', 'node', (event) => {
      const node = event.target
      const hood = node.closedNeighborhood()
      // 虚化无关节点/连线
      cy.elements().difference(hood).style({ opacity: 0.08 })
      hood.style({ opacity: 1 })
      // 突出当前节点: 加粗描边 + 置顶 + 标签放大
      node.style({
        'border-width': 4,
        'border-color': '#7c3aed',
        'z-index': 999,
        'font-size': 13,
      })
      // 突出关联节点
      node.neighborhood().nodes().style({ 'border-width': 4, 'border-color': '#7c3aed' })
      // 突出连接线: 加粗 + 提色
      node.connectedEdges().forEach(e => {
        const isWiki = e.data('kind') === 'wiki'
        e.style({
          opacity: 1,
          width: isWiki ? 3 : 2.5,
          'line-color': isWiki ? '#475569' : '#7c3aed',
        })
      })
    })
    cy.on('mouseout', 'node', () => {
      cy.elements().removeStyle()
    })

    // ---- 语义边 hover: 高亮 ----
    cy.on('mouseover', 'edge[kind = "semantic"]', (event) => {
      const e = event.target
      e.style({ 'line-color': '#7c3aed', width: 3, opacity: 1 })
      e.source().style({ 'border-width': 4, 'border-color': '#7c3aed' })
      e.target().style({ 'border-width': 4, 'border-color': '#7c3aed' })
    })
    cy.on('mouseout', 'edge[kind = "semantic"]', () => {
      cy.elements().removeStyle()
    })

    // ---- 点击节点: 跳转或创建 ----
    cy.on('tap', 'node', async (event) => {
      const node = event.target
      const title = node.id()
      const noteId = noteIdByTitle.get(title)
      if (noteId) {
        router.push(`/knowledge/note/${noteId}`)
        return
      }
      const created = await kbCreateNote(title, `# ${title}\n\n（从图谱虚节点创建）\n\n`)
      if (created.success) router.push(`/knowledge/note/${created.id}`)
    })
  })
}

function relayout() {
  if (!cy) return
  cy.layout({
    name: 'cose',
    animate: true,
    animationDuration: 800,
    nodeRepulsion: () => 12000,
    idealEdgeLength: () => 160,
    edgeElasticity: () => 80,
    nestingFactor: 1.2,
    gravity: 0.15,
    numIter: 2000,
    initialTemp: 300,
    coolingFactor: 0.97,
    minTemp: 1.0,
    padding: 60,
    nodeDimensionsIncludeLabels: true,
  }).run()
}

onMounted(() => { load(); loadCategories() })
onBeforeUnmount(() => { if (cy) cy.destroy() })
</script>

<style scoped>
.kb-page { min-height: 100vh; }

.kb-container {
  max-width: var(--max-width);
  margin: 0 auto;
  padding: 28px 24px 60px;
}

.graph-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}

.kb-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 4px;
}

.kb-subtitle { font-size: 13px; color: var(--text-muted); margin: 0; }

.legend-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  vertical-align: middle;
  margin: 0 2px;
}

.legend-dot.note { background: #3b82f6; }
.legend-dot.file { background: #10b981; }
.legend-dot.url { background: #f59e0b; }
.legend-dot.virtual { background: #9ca3af; border: 2px dashed #6b7280; }

.graph-actions { display: flex; gap: 8px; flex-wrap: wrap; }

.filter-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}

.filter-label { font-size: 12px; color: var(--text-faint); font-weight: 600; }

.cat-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border: 1px solid #ddd6fe;
  background: #ede9fe;
  color: #6d28d9;
  border-radius: 999px;
  font-size: 12px;
  padding: 3px 10px;
  cursor: pointer;
}

.cat-chip.active { background: #6d28d9; color: #fff; border-color: #6d28d9; }

.sem-toggle {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--text-secondary);
  margin-left: auto;
  cursor: pointer;
}

.graph-wrap {
  position: relative;
  height: calc(100vh - 300px);
  min-height: 420px;
  overflow: hidden;
}

.cy-container { width: 100%; height: 100%; }

.graph-status {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  font-size: 14px;
  flex-direction: column;
  gap: 8px;
}

.graph-stats {
  position: absolute;
  right: 12px;
  bottom: 10px;
  font-size: 12px;
  color: var(--text-faint);
  background: var(--surface);
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-default);
}
</style>
