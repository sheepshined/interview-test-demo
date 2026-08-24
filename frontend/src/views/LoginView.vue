<template>
  <div style="min-height:100vh;display:flex;align-items:center;justify-content:center;background:var(--bg-100);padding:24px;">
    <form class="ds-card" style="padding:40px;width:100%;max-width:400px;" @submit.prevent="submitLogin">
      <div style="text-align:center;margin-bottom:28px;">
        <h1 style="font-size:24px;font-weight:700;color:var(--text-primary);margin-bottom:6px;">AI模拟面试官</h1>
        <p style="font-size:14px;color:var(--text-muted);">请登录后开始模拟面试</p>
      </div>

      <label for="login-username" style="display:block;font-size:13px;font-weight:600;margin-bottom:6px;color:var(--text-primary);">用户名</label>
      <input id="login-username" v-model="username" class="ds-input" autocomplete="username" placeholder="请输入用户名" :disabled="loading" />

      <label for="login-password" style="display:block;font-size:13px;font-weight:600;margin:18px 0 6px;color:var(--text-primary);">密码</label>
      <input id="login-password" v-model="password" class="ds-input" type="password" autocomplete="current-password" placeholder="请输入密码" :disabled="loading" />

      <div v-if="errorMsg" style="margin-top:14px;padding:10px 12px;border-radius:8px;background:rgba(220,38,38,.08);color:var(--error);font-size:13px;">
        {{ errorMsg }}
      </div>

      <button class="ds-btn ds-btn-primary w-full" style="padding:12px;margin-top:22px;" type="submit" :disabled="loading || !username.trim() || !password">
        {{ loading ? '登录中…' : '登录' }}
      </button>
      <p style="font-size:12px;color:var(--text-faint);text-align:center;margin-top:18px;">演示账号：admin / 123123</p>
    </form>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { login } from '../api'
import { saveAuth } from '../auth'

const route = useRoute()
const router = useRouter()
const username = ref('')
const password = ref('')
const loading = ref(false)
const errorMsg = ref('')

async function submitLogin() {
  if (loading.value) return
  loading.value = true
  errorMsg.value = ''
  try {
    const result = await login(username.value.trim(), password.value)
    if (!result.success) {
      errorMsg.value = result.message || '登录失败'
      return
    }
    saveAuth(result.token, result.username)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    router.replace(redirect.startsWith('/') ? redirect : '/')
  } finally {
    loading.value = false
  }
}
</script>
