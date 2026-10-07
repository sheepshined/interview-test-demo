<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getRoles } from '../api'
import Icon from '../components/Icon.vue'
import TopBar from '../components/TopBar.vue'

const router = useRouter()
const CONFIG_KEY = 'interviewConfig'
const roles = ref([])
const selectedRole = ref('')
const questionCount = ref(5)
const loadingRoles = ref(false)
const roleError = ref('')

const countOptions = [
  { value: 5, est: '约 10 分钟' },
  { value: 8, est: '约 15 分钟' },
  { value: 10, est: '约 20 分钟' },
  { value: 15, est: '约 28 分钟' },
]

const selectedRoleTitle = computed(
  () => roles.value.find((r) => r.key === selectedRole.value)?.title || '—'
)
const estLabel = computed(() => countOptions.find((c) => c.value === questionCount.value)?.est || '—')

function pad(n) {
  return String(n).padStart(2, '0')
}

function loadSaved() {
  try {
    return JSON.parse(localStorage.getItem(CONFIG_KEY) || 'null')
  } catch (_) {
    return null
  }
}

async function loadRoles() {
  loadingRoles.value = true
  roleError.value = ''
  roles.value = []
  try {
    const result = await getRoles()
    if (!result.success) {
      roleError.value = result.message || '岗位加载失败'
      return
    }
    if (!Array.isArray(result.roles) || result.roles.length === 0) {
      roleError.value = '后端未返回可用岗位，请检查题库配置'
      return
    }
    roles.value = [...result.roles]
    // 默认回显上次选择的岗位与题量,不必每次重选
    const saved = loadSaved()
    selectedRole.value =
      saved && roles.value.some((r) => r.key === saved.key) ? saved.key : roles.value[0].key
    if (saved && countOptions.some((c) => c.value === saved.questionCount)) {
      questionCount.value = saved.questionCount
    }
  } finally {
    loadingRoles.value = false
  }
}

function startInterview() {
  const role = roles.value.find((r) => r.key === selectedRole.value)
  if (!role) {
    roleError.value = '请先选择一个岗位'
    return
  }
  const config = { key: role.key, title: role.title, questionCount: questionCount.value }
  // sessionStorage 供本次跳转使用; localStorage 记住配置,刷新/重进免重选
  sessionStorage.setItem('selectedRole', JSON.stringify(config))
  localStorage.setItem(CONFIG_KEY, JSON.stringify(config))
  router.push('/interview')
}

onMounted(loadRoles)
</script>

<template>
  <div>
    <TopBar crumb="选择岗位" folio="卷·03">
      <template #actions>
        <RouterLink class="tlink" to="/resume-upload">改用简历匹配<Icon name="arrowRight" /></RouterLink>
      </template>
    </TopBar>

    <div class="page-body">
      <div class="page-head" v-reveal>
        <span class="sec-index">CONFIGURATION</span>
        <h1 class="page-title" style="margin-top:14px">设定本场面试</h1>
        <p class="page-sub">选择目标岗位与题量，其余交给面试官——出题范围、追问深度都按这个方向展开。</p>
      </div>

      <div class="setup-grid">
        <!-- 左：配置 -->
        <div>
          <div class="block" v-reveal="0.05">
            <div class="block-head">
              <span class="no">01</span><h3>岗位类别</h3>
              <span class="hint">选择 1 个方向</span>
            </div>

            <div v-if="loadingRoles" class="role-state">
              <span class="spin" style="display:inline-block; width:18px; height:18px; border:2px solid var(--line-strong); border-top-color:var(--vermilion); border-radius:50%"></span>
              正在加载岗位…
            </div>
            <div v-else-if="roleError" class="load-error">
              <span><Icon name="alert" :size="15" />{{ roleError }}</span>
              <button class="btn btn-ghost btn-sm" @click="loadRoles"><Icon name="refresh" :size="14" />重新加载</button>
            </div>
            <div v-else-if="!roles.length" class="empty">
              <div class="empty-ic"><Icon name="pin" :size="28" /></div>
              <div class="empty-title">暂无可选岗位</div>
              <div class="empty-sub">后端未返回岗位，请检查题库配置后重试。</div>
            </div>
            <div v-else class="role-picks">
              <button
                v-for="(role, idx) in roles"
                :key="role.key"
                type="button"
                class="pick role-pick"
                :class="{ 'is-on': selectedRole === role.key }"
                @click="selectedRole = role.key"
              >
                <div class="head"><span class="t">{{ role.title }}</span><span class="n">№{{ pad(idx + 1) }}</span></div>
                <div class="tags"><span v-for="tag in role.tags.slice(0, 3)" :key="tag" class="tag">{{ tag }}</span></div>
              </button>
            </div>
          </div>

          <div class="block" v-reveal="0.12">
            <div class="block-head">
              <span class="no">02</span><h3>面试题量</h3>
              <span class="hint">题量越多，追问越深</span>
            </div>
            <div class="count-picks">
              <button
                v-for="c in countOptions"
                :key="c.value"
                type="button"
                class="pick count-pick"
                :class="{ 'is-on': questionCount === c.value }"
                @click="questionCount = c.value"
              >
                <div class="num">{{ c.value }}</div><div class="unit">题</div><div class="est">{{ c.est }}</div>
              </button>
            </div>
          </div>

          <div class="block" v-reveal="0.18">
            <div class="block-head"><span class="no">03</span><h3>本场能力项</h3></div>
            <div class="feature-pills">
              <span class="tag"><Icon name="mic" :size="13" />语音输入作答</span>
              <span class="tag"><Icon name="volume" :size="13" />面试官语音朗读</span>
              <span class="tag"><Icon name="bulb" :size="13" />每题 2 次提示</span>
              <span class="tag"><Icon name="quote" :size="13" />低分自动追问</span>
              <span class="tag"><Icon name="records" :size="13" />逐题记录留档</span>
            </div>
          </div>
        </div>

        <!-- 右：本场说明 -->
        <aside class="brief" v-reveal="0.1">
          <div class="sheet sheet-pad">
            <div class="mono" style="margin-bottom:10px">Session Brief</div>
            <h3 class="d3" style="margin-bottom:6px">本场说明</h3>
            <p style="font-size:13.5px; color:var(--ink-3); line-height:1.85; margin-bottom:18px">
              出题基于混合检索题库（BM25 + 向量，RRF 融合），并会结合你的简历上下文。
            </p>

            <div class="brief-rows">
              <div class="brief-row"><span class="k">岗位</span><span class="v"><b>{{ selectedRoleTitle }}</b></span></div>
              <div class="brief-row"><span class="k">题量</span><span class="v"><b>{{ questionCount }}</b> 题</span></div>
              <div class="brief-row"><span class="k">预计时长</span><span class="v">{{ estLabel }}</span></div>
              <div class="brief-row"><span class="k">难度</span><span class="v">Intermediate · 进阶</span></div>
            </div>

            <div style="margin-top:22px">
              <div class="mono" style="margin-bottom:8px">面试官人设 · 随机其一</div>
              <ul class="persona-list">
                <li><Icon name="user" :size="15" /><span><b>严谨 CTO</b> · 直奔技术核心，追问『为什么』与底层原理</span></li>
                <li><Icon name="user" :size="15" /><span><b>温和 HR</b> · 先肯定再引导，关注表达与项目经验</span></li>
                <li><Icon name="user" :size="15" /><span><b>技术深挖型</b> · 层层递进，从概念到实现再到边界</span></li>
              </ul>
            </div>
          </div>

          <div class="start-bar">
            <div class="summary">本场配置：<b>{{ selectedRoleTitle }}</b> · <b>{{ questionCount }}</b> 题 · 可随时提前结束</div>
            <button class="btn btn-lg btn-block" :disabled="loadingRoles || !selectedRole" @click="startInterview">
              进入面试间<span class="ar"><Icon name="arrowRight" /></span>
            </button>
          </div>
        </aside>
      </div>
    </div>
  </div>
</template>

<style scoped>
  .setup-grid { display: grid; grid-template-columns: 1.5fr 1fr; gap: clamp(28px, 4vw, 52px); align-items: start; }

  .block { margin-bottom: 40px; }
  .block-head { display: flex; align-items: baseline; gap: 14px; margin-bottom: 18px; }
  .block-head .no { font-family: var(--f-mono); font-size: 11px; font-weight: 700; letter-spacing: 0.16em; color: var(--vermilion); }
  .block-head h3 { font-size: 20px; }
  .block-head .hint { margin-left: auto; font-family: var(--f-mono); font-size: 10.5px; letter-spacing: 0.14em; text-transform: uppercase; color: var(--ink-4); }

  /* 加载 / 错误 */
  .role-state {
    padding: 24px 0; display: flex; align-items: center; gap: 10px;
    color: var(--ink-3); font-size: 13px;
  }
  .load-error {
    padding: 15px 18px; display: flex; align-items: center; justify-content: space-between; gap: 14px; flex-wrap: wrap;
    border: 1px solid var(--verm-line); background: var(--verm-wash);
    color: var(--vermilion-deep); font-size: 13px;
  }
  .load-error > span { display: inline-flex; align-items: center; gap: 9px; }

  /* 岗位选择 */
  .role-picks { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
  .role-pick { text-align: left; padding: 20px 20px 18px; }
  .role-pick .head { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
  .role-pick .t { font-family: var(--f-display); font-weight: 900; font-size: 16.5px; line-height: 1.4; }
  .role-pick .n { font-family: var(--f-mono); font-size: 10.5px; color: var(--ink-4); }
  .role-pick .tags { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 12px; }
  .role-pick .tags .tag { font-size: 11.5px; padding: 3px 9px; }
  .role-pick.is-on .t { color: var(--vermilion-deep); }
  .role-pick.is-on .n { color: var(--vermilion); }
  .role-pick.is-on .tag { border-color: var(--verm-line); color: var(--vermilion-deep); }

  /* 题量选择 */
  .count-picks { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
  .count-pick { text-align: center; padding: 20px 12px 16px; }
  .count-pick .num { font-family: var(--f-mono); font-weight: 700; font-size: 30px; line-height: 1; letter-spacing: -0.04em; }
  .count-pick .unit { font-size: 12px; color: var(--ink-3); margin-top: 6px; }
  .count-pick .est { font-family: var(--f-mono); font-size: 10px; letter-spacing: 0.12em; text-transform: uppercase; color: var(--ink-4); margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--line); }
  .count-pick.is-on .num { color: var(--vermilion-deep); }
  .count-pick.is-on .est { border-color: var(--verm-line); color: var(--vermilion-deep); }

  /* 右侧：本场说明 */
  .brief { position: sticky; top: 92px; }
  .brief-rows { border-top: 1px solid var(--line-strong); }
  .brief-row { display: flex; align-items: baseline; justify-content: space-between; gap: 14px; padding: 15px 2px; border-bottom: 1px solid var(--line); }
  .brief-row .k { font-family: var(--f-mono); font-size: 10.5px; letter-spacing: 0.14em; text-transform: uppercase; color: var(--ink-3); }
  .brief-row .v { font-size: 14px; text-align: right; }
  .brief-row .v b { font-family: var(--f-display); font-weight: 900; font-size: 15px; }

  .persona-list li { display: flex; gap: 12px; padding: 12px 0; border-bottom: 1px dashed var(--line); font-size: 13px; color: var(--ink-2); }
  .persona-list li:last-child { border-bottom: 0; }
  .persona-list .ic { color: var(--indigo-ink); flex-shrink: 0; margin-top: 2px; }
  .persona-list b { color: var(--ink); }

  .feature-pills { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }

  .start-bar {
    margin-top: 26px; padding: 20px;
    background: var(--ink); color: var(--room-ink);
    display: flex; flex-direction: column; gap: 14px;
  }
  .start-bar .summary { font-size: 13px; color: rgba(240,234,216,.72); }
  .start-bar .summary b { color: var(--room-ink); }
  .start-bar .btn { --btn-bg: var(--vermilion); border-color: var(--vermilion); }
  .start-bar .btn::before { background: var(--room-ink); }
  .start-bar .btn:hover { color: var(--ink); }

  @media (max-width: 1080px) {
    .setup-grid { grid-template-columns: 1fr; }
    .brief { position: static; }
  }
  @media (max-width: 620px) {
    .role-picks { grid-template-columns: 1fr; }
    .count-picks { grid-template-columns: 1fr 1fr; }
  }
</style>