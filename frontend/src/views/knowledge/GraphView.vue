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

      <!-- 视图开关 (常驻) -->
      <div class="graph-toggles">
        <label class="sem-toggle">
          <input type="checkbox" v-model="showSemantic" @change="load" />
          显示语义边
        </label>
        <label class="sem-toggle">
          <input type="checkbox" v-model="hideOrphans" @change="applyOrphanFilter" />
          隐藏孤立节点
        </label>
        <!-- 分类过滤 -->
        <template v-if="categories.length">
          <span class="toggle-divider"></span>
          <span class="filter-label">分类:</span>
          <button v-for="c in categories" :key="c.category"
                  class="kb-tag cat-chip" :class="{ active: activeCategories.has(c.category) }"
                  @click="toggleCategory(c.category)"><DSIcon name="folder" :size="12" />{{ c.category }} ({{ c.count }})</button>
        </template>
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
import fcose from 'cytoscape-fcose'
import layoutUtilities from 'cytoscape-layout-utilities'
import TopNav from '../../components/TopNav.vue'
import DSIcon from '../../components/DSIcon.vue'
import { kbGraph, kbCategories, kbCreateNote, kbRebuild } from '../../api'

// fcose 力导布局 (Cytoscape 官方推荐, 质量优于内置 cose);
// layout-utilities 是 fcose 的 packComponents (不相连分量自动打包) 必需依赖
cytoscape.use(layoutUtilities)
cytoscape.use(fcose)

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
// 本库手工双链较少, 语义边是主要连接组织, 默认开启; 可关掉只看显式双链
const showSemantic = ref(true)
// 隐藏度数为 0 的孤立节点 (与任何笔记都无连接的笔记)
const hideOrphans = ref(false)
const rebuilding = ref(false)

let cy = null
let lastGraph = null   // 最近一次图谱数据, 供本地过滤开关免请求重渲染
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

/** 节点标签: 单行最多 9 字, 超出省略; 全名放 tooltip, 让"点"而不是"文字"成为视觉主体 */
function shortLabel(title) {
  const t = (title || '').trim()
  const MAX = 9
  return t.length > MAX ? t.slice(0, MAX) + '…' : t
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

  // 孤立节点过滤: 度为 0 的点不渲染, 其相关边本来也不存在
  const visibleNodes = hideOrphans.value
    ? graph.nodes.filter(n => (degreeMap[n.id] ?? 0) > 0)
    : graph.nodes
  const visibleIds = new Set(visibleNodes.map(n => n.id))

  return {
    nodes: visibleNodes.map(n => {
      const deg = degreeMap[n.id] ?? 0
      const isVirtual = !!n.virtual
      const color = isVirtual ? TYPE_COLORS.virtual : (TYPE_COLORS[n.note_type] || TYPE_COLORS.note)
      // 节点尺寸: 10~22, Obsidian 风格小圆点, 枢纽点略大但不碾压整图
      const size = 10 + 12 * Math.sqrt(deg / maxDeg)
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
          deg,
        },
      }
    }),
    edges: graph.edges
      .filter(e => visibleIds.has(e.source) && visibleIds.has(e.target))
      .map((e, i) => ({
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

function applyOrphanFilter() {
  // 纯本地开关: 用已有数据重渲染, 不重新请求后端
  if (lastGraph) render(lastGraph)
}

function render(graph) {
  lastGraph = graph
  if (!graph.nodes.length) {
    nodeCount.value = 0
    virtualCount.value = 0
    wikiEdgeCount.value = 0
    semEdgeCount.value = 0
    return
  }

  noteIdByTitle.clear()
  for (const n of graph.nodes) noteIdByTitle.set(n.id, n.note_id)

  const { nodes, edges } = buildElements(graph)
  // 统计以实际渲染的元素为准 (孤立节点过滤后数量会变)
  nodeCount.value = nodes.length
  virtualCount.value = nodes.filter(n => n.data.virtual === 'yes').length
  wikiEdgeCount.value = edges.filter(e => e.data.kind === 'wiki').length
  semEdgeCount.value = edges.filter(e => e.data.kind === 'semantic').length

  nextTick(() => {
    if (cy) { cy.destroy(); cy = null }
    cy = cytoscape({
      container: cyContainer.value,
      elements: [...nodes, ...edges],
      style: [
        // ---- 节点基础 (小圆点 + 弱化单行标签, 全名 hover 看) ----
        {
          selector: 'node',
          style: {
            'label': 'data(label)',
            'title': 'data(fullLabel)',
            'background-color': 'data(color)',
            'width': 'data(size)',
            'height': 'data(size)',
            'border-width': 2,
            'border-color': 'data(borderColor)',
            'color': '#94a3b8',
            'font-size': 10,
            'font-weight': 500,
            'text-valign': 'bottom',
            'text-halign': 'center',
            'text-margin-y': 5,
            'text-wrap': 'none',
            'min-zoomed-font-size': 8,
          },
        },
        // ---- 虚节点 ----
        {
          selector: 'node[virtual = "yes"]',
          style: {
            'background-color': TYPE_COLORS.virtual,
            'border-color': '#9ca3af',
            'border-style': 'dashed',
            'color': '#b6bec9',
          },
        },
        // ---- 叶子/弱连接节点: 标签更淡, 把视觉让给枢纽 (hover 时由事件高亮) ----
        {
          selector: 'node[deg < 2]',
          style: {
            'color': '#c3cbd6',
            'font-size': 9,
          },
        },
        // ---- Wiki 边 (显式双链: 实线, 细而淡但仍比语义边强) ----
        {
          selector: 'edge[kind = "wiki"]',
          style: {
            'width': 1,
            'line-color': '#94a3b8',
            'curve-style': 'bezier',
            'opacity': 0.4,
          },
        },
        {
          selector: 'edge[kind = "wiki"][virtual = "yes"]',
          style: {
            'line-style': 'dashed',
            'line-color': '#cbd5e1',
            'opacity': 0.3,
          },
        },
        // ---- 语义边 (自动推断弱关系: 极淡虚线, 布局上用长距弱力, 不再拉扯簇结构) ----
        {
          selector: 'edge[kind = "semantic"]',
          style: {
            'width': 1,
            'line-style': 'dashed',
            'line-color': '#c4b5fd',
            'curve-style': 'bezier',
            'opacity': 0.22,
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
      layout: buildLayoutOptions(true),
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
      // 突出当前节点: 加粗描边 + 置顶 + 标签放大变清晰
      node.style({
        'border-width': 4,
        'border-color': '#7c3aed',
        'z-index': 999,
        'font-size': 13,
        'color': '#1e293b',
      })
      // 突出关联节点 (叶子标签也临时变深, 方便阅读)
      node.neighborhood().nodes().style({
        'border-width': 4,
        'border-color': '#7c3aed',
        'color': '#475569',
      })
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

/**
 * fcose 布局参数 (借鉴 Cytoscape 官方 fcose + Obsidian 紧凑团簇思路):
 *  - quality "proof": 最高质量档, 带后处理去重叠
 *  - nodeDimensionsIncludeLabels: 布局把标签矩形计入节点尺寸, 标签不压字
 *  - 簇收紧: wiki 双链 45px 高弹性(真实关系, 强力聚团);
 *    semantic 130px 低弹性(弱桥接, 只轻轻牵引, 不把不同主题拉散)
 *  - packComponents + tile: 无关分量靠近摆放、孤立点网格平铺且紧挨主图
 */
function buildLayoutOptions(animate = true) {
  return {
    name: 'fcose',
    quality: 'proof',
    randomize: true,
    animate,
    animationDuration: 700,
    animationEasing: 'ease-out-cubic',
    fit: true,
    padding: 40,
    nodeDimensionsIncludeLabels: true,
    packComponents: true,
    // layout-utilities 分量打包: 不相连分量之间紧凑排列, 避免中间大片留白
    componentSpacing: 20,
    nodeSeparation: 60,
    nodeRepulsion: () => 5500,
    idealEdgeLength: (edge) => (edge.data('kind') === 'semantic' ? 100 : 45),
    edgeElasticity: (edge) => (edge.data('kind') === 'semantic' ? 0.15 : 0.55),
    nestingFactor: 0.1,
    gravity: 0.4,
    gravityRange: 3.8,
    numIter: 4000,
    tile: true,
    tilingPaddingVertical: 14,
    tilingPaddingHorizontal: 14,
  }
}

function relayout() {
  if (!cy) return
  cy.layout(buildLayoutOptions(true)).run()
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

.graph-toggles {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}

.toggle-divider {
  width: 1px;
  height: 16px;
  background: var(--border-default);
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
