<template>
  <div class="auth-shell">
    <!-- 左：品牌面板 -->
    <aside class="auth-brand">
      <div class="brand-inner">
        <div class="brand-row">
          <span class="brand-mark">面</span>
          <span class="brand-name">AI 模拟面试官</span>
        </div>
        <h2 class="brand-headline">练到临场不慌，<br />答到点子上。</h2>
        <ul class="brand-features">
          <li>
            <DSIcon name="circle-check" :size="16" color="var(--accent-300)" />
            简历智能匹配，9 大岗位针对性出题
          </li>
          <li>
            <DSIcon name="circle-check" :size="16" color="var(--accent-300)" />
            四维评估 + 好差答案对比，反馈可执行
          </li>
          <li>
            <DSIcon name="circle-check" :size="16" color="var(--accent-300)" />
            薄弱点一键沉淀，双链笔记构建知识体系
          </li>
        </ul>
        <div class="brand-foot">
          <span class="stat-num">133</span> 道精选题
          <span class="foot-dot"></span>
          <span class="stat-num">9</span> 个岗位方向
        </div>
      </div>
      <div class="deco deco-char">面</div>
      <div class="deco deco-ring ring-1"></div>
      <div class="deco deco-ring ring-2"></div>
    </aside>

    <!-- 右：表单 -->
    <main class="auth-form-side">
      <form class="auth-card reveal" @submit.prevent="submit">
        <div class="auth-head">
          <h1>{{ mode === 'login' ? '欢迎回来' : '创建账号' }}</h1>
          <p>{{ mode === 'login' ? '登录后继续你的模拟面试练习' : '注册即可开始，无需邮箱验证' }}</p>
        </div>

        <label for="login-username" class="field-label">用户名</label>
        <input id="login-username" v-model="username" class="ds-input" autocomplete="username" placeholder="3-20 位字母、数字或下划线" :disabled="loading" />

        <label for="login-password" class="field-label field-gap">密码</label>
        <input id="login-password" v-model="password" class="ds-input" type="password" :autocomplete="mode === 'login' ? 'current-password' : 'new-password'" placeholder="至少 6 位" :disabled="loading" />

        <template v-if="mode === 'register'">
          <label for="login-password2" class="field-label field-gap">确认密码</label>
          <input id="login-password2" v-model="password2" class="ds-input" type="password" autocomplete="new-password" placeholder="再输入一次密码" :disabled="loading" />
        </template>

        <div v-if="errorMsg" class="msg msg-error">{{ errorMsg }}</div>
        <div v-else-if="noticeMsg" class="msg msg-notice">{{ noticeMsg }}</div>

        <button class="ds-btn ds-btn-primary w-full auth-submit" type="submit" :disabled="loading || !username.trim() || !password">
          {{ loading ? (mode === 'login' ? '登录中…' : '注册中…') : (mode === 'login' ? '登 录' : '注册并登录') }}
        </button>

        <p class="auth-switch">
          {{ mode === 'login' ? '还没有账号？' : '已有账号？' }}
          <a href="javascript:void(0)" class="switch-link" @click="switchMode">
            {{ mode === 'login' ? '注册新用户' : '返回登录' }}
          </a>
        </p>
        <p v-if="mode === 'login'" class="auth-demo">演示账号：admin / 123123</p>
      </form>
    </main>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { login, register } from '../api'
import { saveAuth } from '../auth'
import DSIcon from '../components/DSIcon.vue'

const route = useRoute()
const router = useRouter()
const mode = ref('login')
const username = ref('')
const password = ref('')
const password2 = ref('')
const loading = ref(false)
const errorMsg = ref('')
const noticeMsg = ref('')

function switchMode() {
  mode.value = mode.value === 'login' ? 'register' : 'login'
  errorMsg.value = ''
  noticeMsg.value = ''
  password.value = ''
  password2.value = ''
}

function _goHome() {
  const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
  router.replace(redirect.startsWith('/') ? redirect : '/')
}

async function submit() {
  if (loading.value) return
  errorMsg.value = ''
  noticeMsg.value = ''

  if (mode.value === 'register' && password.value !== password2.value) {
    errorMsg.value = '两次输入的密码不一致'
    return
  }

  loading.value = true
  try {
    const action = mode.value === 'login' ? login : register
    const result = await action(username.value.trim(), password.value)
    if (!result.success) {
      errorMsg.value = result.message || (mode.value === 'login' ? '登录失败' : '注册失败')
      return
    }
    // 注册/登录成功均直接签发 token, 免二次登录
    saveAuth(result.token, result.username)
    _goHome()
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 5fr 6fr;
}

/* ── 左侧品牌面板 ── */
.auth-brand {
  position: relative;
  background: linear-gradient(160deg, var(--brand-900) 0%, var(--brand-800) 55%, #29246e 100%);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  padding: 48px;
}

.brand-inner {
  position: relative;
  z-index: 1;
  max-width: 420px;
}

.brand-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.brand-mark {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.12);
  backdrop-filter: blur(4px);
  border: 1px solid rgba(255, 255, 255, 0.18);
  font-family: var(--font-display);
  font-size: 21px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}

.brand-name {
  font-family: var(--font-display);
  font-size: 17px;
  font-weight: 700;
  letter-spacing: 0.02em;
}

.brand-headline {
  font-family: var(--font-display);
  font-size: clamp(28px, 2.6vw, 38px);
  font-weight: 900;
  line-height: 1.4;
  margin-top: 44px;
  letter-spacing: 0.02em;
}

.brand-features {
  list-style: none;
  margin-top: 28px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.brand-features li {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  color: rgba(255, 255, 255, 0.85);
}

.brand-foot {
  margin-top: 48px;
  padding-top: 22px;
  border-top: 1px solid rgba(255, 255, 255, 0.16);
  font-size: 13.5px;
  color: rgba(255, 255, 255, 0.75);
  display: flex;
  align-items: center;
  gap: 8px;
}

.brand-foot .stat-num {
  font-family: var(--font-mono);
  font-size: 17px;
  font-weight: 700;
  color: var(--accent-300);
}

.foot-dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.35);
  margin: 0 4px;
}

/* 装饰 */
.deco {
  position: absolute;
  pointer-events: none;
}

.deco-char {
  right: -36px;
  bottom: -60px;
  font-family: var(--font-display);
  font-size: 340px;
  font-weight: 900;
  line-height: 1;
  color: rgba(255, 255, 255, 0.045);
  user-select: none;
}

.deco-ring {
  border-radius: 50%;
  border: 1px solid rgba(255, 255, 255, 0.09);
}

.ring-1 { width: 380px; height: 380px; top: -140px; left: -120px; }
.ring-2 { width: 240px; height: 240px; bottom: -80px; left: 32%; border-style: dashed; }

/* ── 右侧表单 ── */
.auth-form-side {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 24px;
  background:
    radial-gradient(600px 320px at 110% 0%, var(--accent-100), transparent 60%),
    var(--bg-100);
}

.auth-card {
  width: 100%;
  max-width: 400px;
  background: var(--surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-md);
  padding: 40px 36px;
}

.auth-head h1 {
  font-size: 26px;
  color: var(--text-primary);
}

.auth-head p {
  margin-top: 6px;
  font-size: 14px;
  color: var(--text-muted);
}

.field-label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 6px;
  color: var(--text-primary);
}

.field-gap {
  margin-top: 18px;
}

.msg {
  margin-top: 14px;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  font-size: 13px;
}

.msg-error {
  background: var(--error-bg);
  color: var(--error);
}

.msg-notice {
  background: var(--success-bg);
  color: var(--success);
}

.auth-submit {
  padding: 12px;
  margin-top: 24px;
  font-size: 15px;
  letter-spacing: 0.08em;
}

.auth-switch {
  font-size: 13px;
  color: var(--text-muted);
  text-align: center;
  margin-top: 18px;
}

.switch-link {
  color: var(--brand-600);
  font-weight: 600;
}

.switch-link:hover {
  color: var(--brand-700);
  text-decoration: underline;
}

.auth-demo {
  font-size: 12px;
  color: var(--text-faint);
  text-align: center;
  margin-top: 8px;
}

@media (max-width: 900px) {
  .auth-shell { grid-template-columns: 1fr; }
  .auth-brand { display: none; }
  .auth-form-side { min-height: 100vh; }
}
</style>
