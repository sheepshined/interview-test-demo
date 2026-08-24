<template>
  <div>
    <TopNav />
    <section style="padding:64px 24px 80px;">
      <div class="hero-grid" style="max-width:1152px;margin:0 auto;display:grid;grid-template-columns:3fr 2fr;gap:48px;align-items:center;">
        <div>
          <h1 style="font-size:clamp(28px,3.5vw,48px);font-weight:400;line-height:1.2;color:var(--text-primary);letter-spacing:-0.01em;">让AI成为你的面试教练</h1>
          <p style="color:var(--text-muted);max-width:520px;line-height:1.7;margin-top:16px;font-size:16px;">针对应届生的智能模拟面试平台，通过简历智能匹配或自主选择岗位，获得真实的面试体验和专业的评估反馈</p>
          <div style="margin-top:32px;">
            <router-link to="/resume-upload" class="ds-btn ds-btn-primary" style="padding:12px 28px;">开始面试</router-link>
          </div>
        </div>
        <div style="aspect-ratio:4/3;border-radius:var(--radius-lg);overflow:hidden;">
          <img src="/assets/hero-interview.jpg" alt="AI面试" style="width:100%;height:100%;object-fit:cover;" />
        </div>
      </div>
    </section>
    <section style="padding:0 24px 80px;">
      <div style="max-width:1152px;margin:0 auto;">
        <h2 style="font-size:24px;font-weight:600;margin-bottom:32px;color:var(--text-primary);">选择面试方式</h2>
        <div class="cards-grid" style="display:grid;grid-template-columns:repeat(2,1fr);gap:24px;">
          <article class="ds-card" style="padding:28px;display:flex;flex-direction:column;gap:16px;cursor:pointer;transition:border-color 0.2s;" @click="$router.push('/resume-upload')">
            <div style="width:48px;height:48px;border-radius:12px;background:var(--bg-100);display:flex;align-items:center;justify-content:center;">
              <DSIcon name="file" :size="24" color="var(--brand-600)" />
            </div>
            <h3 style="font-size:16px;font-weight:600;color:var(--text-primary);">简历智能匹配</h3>
            <p style="font-size:14px;color:var(--text-muted);line-height:1.6;">上传你的简历，AI自动分析并匹配最适合的岗位，开启针对性模拟面试</p>
            <div style="margin-top:auto;padding-top:8px;">
              <span class="ds-btn ds-btn-outline" style="font-size:13px;padding:8px 20px;">上传简历</span>
            </div>
          </article>
          <article class="ds-card" style="padding:28px;display:flex;flex-direction:column;gap:16px;cursor:pointer;transition:border-color 0.2s;" @click="$router.push('/choose-job')">
            <div style="width:48px;height:48px;border-radius:12px;background:var(--bg-100);display:flex;align-items:center;justify-content:center;">
              <DSIcon name="map-pin" :size="24" color="var(--brand-600)" />
            </div>
            <h3 style="font-size:16px;font-weight:600;color:var(--text-primary);">自主选择岗位</h3>
            <p style="font-size:14px;color:var(--text-muted);line-height:1.6;">自由选择目标岗位和面试题量，灵活定制你的面试练习计划</p>
            <div style="margin-top:auto;padding-top:8px;">
              <span class="ds-btn ds-btn-outline" style="font-size:13px;padding:8px 20px;">选择岗位</span>
            </div>
          </article>
        </div>
      </div>
    </section>
    <section style="background:var(--bg-200);padding:40px 24px;">
      <div style="max-width:1152px;margin:0 auto;display:flex;justify-content:center;gap:64px;flex-wrap:wrap;">
        <div style="text-align:center;"><div style="font-family:var(--font-mono);font-size:28px;font-weight:700;letter-spacing:-0.03em;color:var(--text-primary);">8</div><div style="font-size:14px;margin-top:4px;color:var(--text-muted);">覆盖岗位方向</div></div>
        <div style="text-align:center;"><div style="font-family:var(--font-mono);font-size:28px;font-weight:700;letter-spacing:-0.03em;color:var(--text-primary);">86</div><div style="font-size:14px;margin-top:4px;color:var(--text-muted);">精选面试题</div></div>
        <div style="text-align:center;"><div style="font-family:var(--font-mono);font-size:28px;font-weight:700;letter-spacing:-0.03em;color:var(--text-primary);">4</div><div style="font-size:14px;margin-top:4px;color:var(--text-muted);">维度能力评估</div></div>
      </div>
    </section>
  </div>
</template>
<script setup>
import TopNav from '../components/TopNav.vue'
import DSIcon from '../components/DSIcon.vue'
</script>
<style scoped>
@media (max-width:767px) { .hero-grid { grid-template-columns: 1fr !important; } .cards-grid { grid-template-columns: 1fr !important; } }
</style>
