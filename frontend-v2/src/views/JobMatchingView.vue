<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getRoles } from '../api'
import Icon from '../components/Icon.vue'
import TopBar from '../components/TopBar.vue'

const router = useRouter()
const roles = ref([])
const resumeData = ref(null)
const suggestedRole = ref('')
const loadingRoles = ref(false)
const roleError = ref('')
const barW = ref({})

const skillCount = computed(() => (resumeData.value?.skills || []).length)
const initial = computed(() => (resumeData.value?.name || '简').trim().charAt(0) || '简')
const skillPreview = computed(() => (resumeData.value?.skills || []).slice(0, 4))
const skillRest = computed(() => Math.max(skillCount.value - skillPreview.value.length, 0))

function norm(x) {
  return String(x || '').toLowerCase().replace(/\s+/g, '')
}

// 匹配度 = 简历技能命中岗位标签的比例(前端计算,无后端字段)
function matchPct(role) {
  const skills = (resumeData.value?.skills || []).map(norm).filter(Boolean)
  const tags = role.tags || []
  if (!skills.length || !tags.length) return 0
  const hit = tags.filter((tag) => {
    const t = norm(tag)
    return t.length >= 2 && skills.some((s) => s.includes(t) || (s.length >= 2 && t.includes(s)))
  })
  return Math.round((hit.length / tags.length) * 100)
}

function isSuggested(role) {
  return !!suggestedRole.value && role.key === suggestedRole.value
}

function pad(n) {
  return String(n).padStart(2, '0')
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
    suggestedRole.value = resumeData.value?.suggested_role || ''
    const idx = roles.value.findIndex((role) => role.key === suggestedRole.value)
    if (idx > 0) {
      const [suggested] = roles.value.splice(idx, 1)
      roles.value.unshift(suggested)
    }
    await nextTick()
    const zero = {}
    for (const role of roles.value) zero[role.key] = 0
    barW.value = zero
    setTimeout(() => {
      const full = {}
      for (const role of roles.value) full[role.key] = matchPct(role)
      barW.value = full
    }, 80)
  } finally {
    loadingRoles.value = false
  }
}

function selectRole(role) {
  const config = {
    key: role.key,
    title: role.title,
    questionCount: 5,
    resumeContext: resumeData.value?.resume_context || '',
    resumeSkills: resumeData.value?.skills || [],
  }
  sessionStorage.setItem('selectedRole', JSON.stringify(config))
  // 记住最近一次面试配置(含简历上下文),刷新面试页可直接续上
  localStorage.setItem('interviewConfig', JSON.stringify(config))
  router.push('/interview')
}

onMounted(() => {
  const stored = sessionStorage.getItem('resumeData')
  if (stored) {
    try {
      resumeData.value = JSON.parse(stored)
    } catch (_) {
      resumeData.value = null
    }
  }
  loadRoles()
})
</script>

<template>
  <div>
    <TopBar crumb="岗位匹配" folio="卷·03">
      <template #actions>
        <RouterLink class="tlink" to="/resume-upload"><Icon name="arrowLeft" />返回上传</RouterLink>
      </template>
    </TopBar>

    <div class="page-body">
      <div class="page-head" v-reveal>
        <span class="sec-index">RESUME → ROLE</span>
        <h1 class="page-title" style="margin-top:14px">挑一个方向，开始练</h1>
        <p class="page-sub">按技能画像匹配到的岗位已排在最前，也可以选择其他方向——每张卡片都是一场完整面试。</p>
      </div>

      <!-- 无简历数据：引导回上传 -->
      <div v-if="!resumeData" class="empty" v-reveal>
        <div class="empty-ic"><Icon name="file" :size="30" /></div>
        <div class="empty-title">还没有简历解析结果</div>
        <div class="empty-sub">请先上传或粘贴简历，系统会按技能画像为你推荐岗位。</div>
        <div style="margin-top:22px">
          <RouterLink class="btn" to="/resume-upload">去上传简历<span class="ar"><Icon name="arrowRight" /></span></RouterLink>
        </div>
      </div>

      <template v-else>
        <div class="resume-strip" v-reveal="0.06">
          <div class="who">
            <span class="stamp-mini">{{ initial }}</span>
            <span>
              <span class="name">{{ resumeData.name || '未识别姓名' }}</span>
              <span class="meta" style="display:block">已完成简历分析 · {{ skillCount }} 项技能</span>
            </span>
          </div>
          <div class="skills">
            <span v-for="s in skillPreview" :key="s" class="tag">{{ s }}</span>
            <span v-if="skillRest > 0" class="tag">+{{ skillRest }}</span>
          </div>
        </div>

        <div v-if="loadingRoles" class="role-state" v-reveal>
          <span class="spin" style="display:inline-block; width:18px; height:18px; border:2px solid var(--line-strong); border-top-color:var(--vermilion); border-radius:50%"></span>
          正在加载岗位…
        </div>

        <div v-else-if="roleError" class="load-error" v-reveal>
          <span><Icon name="alert" :size="15" />{{ roleError }}</span>
          <button class="btn btn-ghost btn-sm" @click="loadRoles"><Icon name="refresh" :size="14" />重新加载</button>
        </div>

        <div v-else-if="!roles.length" class="empty" v-reveal>
          <div class="empty-ic"><Icon name="pin" :size="28" /></div>
          <div class="empty-title">暂无可选岗位</div>
          <div class="empty-sub">后端未返回岗位，请检查题库配置后重试。</div>
        </div>

        <div v-else class="role-grid" data-stagger>
          <article
            v-for="(role, idx) in roles"
            :key="role.key"
            class="role-card sheet sheet-hover"
            :class="{ 'is-best': idx === 0 && isSuggested(role) }"
            v-reveal
            @click="selectRole(role)"
          >
            <span v-if="isSuggested(role)" class="corner-tag verm">推荐 · MATCH</span>
            <span class="no">№ {{ pad(idx + 1) }}</span>
            <h3>{{ role.title }}</h3>
            <div class="tags">
              <span v-for="tag in role.tags.slice(0, 5)" :key="tag" class="tag">{{ tag }}</span>
            </div>
            <div class="foot">
              <div class="match">
                <div class="row"><span class="pct">{{ matchPct(role) }}</span><span class="k">% 匹配度</span></div>
                <div class="bar"><i :style="{ width: (barW[role.key] || 0) + '%' }"></i></div>
              </div>
              <button
                class="btn btn-sm"
                :class="{ 'btn-ghost': !(idx === 0 && isSuggested(role)) }"
                @click.stop="selectRole(role)"
              >
                开始面试<span class="ar"><Icon name="arrowRight" /></span>
              </button>
            </div>
          </article>
        </div>

        <div class="foot-note">
          <span>匹配度 = 技能与岗位标签的命中比例</span>
          <span>匹配度由前端按技能命中计算</span>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
  /* 简历摘要条 */
  .resume-strip {
    display: flex; align-items: center; gap: 22px; flex-wrap: wrap;
    padding: 18px 24px;
    border: 1px solid var(--line);
    background: var(--sheet-2);
    border-left: 3px solid var(--pine);
  }
  .resume-strip .who { display: flex; align-items: center; gap: 12px; }
  .resume-strip .stamp-mini {
    width: 42px; height: 42px; flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
    background: var(--ink); color: var(--paper);
    font-family: var(--f-display); font-weight: 900; font-size: 19px;
  }
  .resume-strip .name { font-family: var(--f-display); font-weight: 900; font-size: 17px; }
  .resume-strip .meta { font-family: var(--f-mono); font-size: 10.5px; letter-spacing: 0.16em; text-transform: uppercase; color: var(--ink-3); }
  .resume-strip .skills { display: flex; gap: 7px; flex-wrap: wrap; margin-left: auto; }

  /* 加载 / 错误 */
  .role-state {
    margin-top: 34px; padding: 48px 24px;
    display: flex; align-items: center; justify-content: center; gap: 10px;
    color: var(--ink-3); font-size: 13.5px;
  }
  .load-error {
    margin-top: 34px; padding: 16px 20px;
    display: flex; align-items: center; justify-content: space-between; gap: 14px; flex-wrap: wrap;
    border: 1px solid var(--verm-line); background: var(--verm-wash);
    color: var(--vermilion-deep); font-size: 13px;
  }
  .load-error > span { display: inline-flex; align-items: center; gap: 9px; }

  /* 岗位卡片 */
  .role-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(310px, 1fr)); gap: 22px; margin-top: 34px; }
  .role-card { padding: 26px 26px 22px; display: flex; flex-direction: column; gap: 16px; position: relative; overflow: hidden; cursor: pointer; }
  .role-card .no { font-family: var(--f-mono); font-size: 11px; letter-spacing: 0.18em; color: var(--ink-4); }
  .role-card h3 { font-size: 20px; margin-top: -6px; }
  .role-card .tags { display: flex; gap: 7px; flex-wrap: wrap; }
  .role-card .foot { display: flex; align-items: flex-end; justify-content: space-between; gap: 14px; margin-top: auto; padding-top: 18px; border-top: 1px solid var(--line); }
  .role-card .match { display: flex; flex-direction: column; gap: 6px; flex: 1; min-width: 0; }
  .role-card .match .row { display: flex; align-items: baseline; gap: 8px; }
  .role-card .match .pct { font-family: var(--f-mono); font-weight: 700; font-size: 24px; letter-spacing: -0.03em; }
  .role-card .match .k { font-family: var(--f-mono); font-size: 10px; letter-spacing: 0.16em; text-transform: uppercase; color: var(--ink-4); }
  .role-card .bar { height: 4px; background: var(--line-soft); position: relative; }
  .role-card .bar i { position: absolute; inset: 0 auto 0 0; background: var(--ink); transition: width 1s var(--ease); }
  .role-card.is-best .bar i { background: var(--vermilion); }
  .role-card.is-best { border-color: var(--line-strong); box-shadow: var(--sh-lift); }
  .role-card.is-best::after {
    content: ''; position: absolute; inset: 0; pointer-events: none;
    background: radial-gradient(320px 160px at 100% 0%, var(--verm-wash), transparent 70%);
  }

  .foot-note {
    margin-top: 40px; padding-top: 18px; border-top: 1px solid var(--line);
    display: flex; justify-content: space-between; gap: 16px; flex-wrap: wrap;
    font-family: var(--f-mono); font-size: 10.5px; letter-spacing: 0.14em; text-transform: uppercase; color: var(--ink-4);
  }

  @media (max-width: 700px) { .resume-strip .skills { margin-left: 0; } }
</style>