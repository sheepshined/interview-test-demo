<template>
  <div style="min-height:100vh;display:flex;align-items:center;justify-content:center;background:var(--bg-100);">
    <div class="ds-card" style="padding:48px 40px;width:100%;max-width:400px;text-align:center;">
      <h1 style="font-size:24px;font-weight:700;color:var(--text-primary);margin-bottom:6px;">AI模拟面试官</h1>
      <p style="font-size:14px;color:var(--text-muted);margin-bottom:32px;">智能面试练习平台</p>
      <button class="ds-btn ds-btn-primary w-full" style="padding:14px;font-size:15px;" @click="enterApp">进入系统</button>
      <p style="font-size:12px;color:var(--text-faint);margin-top:20px;">点击即可开始使用</p>
    </div>
  </div>
</template>
<script setup>
import { useRouter } from 'vue-router'
const router = useRouter()
function enterApp() { localStorage.setItem('token','demo'); localStorage.setItem('username','访客'); router.push('/') }
</script>
