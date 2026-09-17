<template>
  <div class="home">
    <TopNav />

    <!-- Hero -->
    <section class="hero">
      <div class="hero-inner">
        <div class="hero-copy reveal">
          <span class="hero-eyebrow">
            <span class="eyebrow-dot"></span>
            AI 面试教练 · 应届生求职陪练
          </span>
          <h1 class="hero-title">让每一次练习，<br />都离 offer 更近<em>一步</em></h1>
          <p class="hero-sub">
            上传简历智能匹配岗位，或自主选择方向开启模拟面试；面试结束生成四维评估报告，薄弱点一键沉淀进个人知识库。
          </p>
          <div class="hero-actions">
            <router-link to="/resume-upload" class="ds-btn ds-btn-primary hero-btn">
              开始模拟面试
              <DSIcon name="arrow-right" :size="16" />
            </router-link>
            <router-link to="/choose-job" class="ds-btn ds-btn-outline hero-btn">自主选岗练习</router-link>
          </div>
          <div class="hero-stats">
            <div class="stat">
              <span class="stat-num">133</span>
              <span class="stat-label">精选题库</span>
            </div>
            <div class="stat-divider"></div>
            <div class="stat">
              <span class="stat-num">4</span>
              <span class="stat-label">维度评估</span>
            </div>
          </div>
        </div>

        <div class="hero-visual reveal-2">
          <div class="hero-frame">
            <img src="/assets/hero-interview.jpg" alt="AI 模拟面试" />
          </div>
          <div class="hero-chip chip-a">
            <span class="chip-icon"><DSIcon name="bar-chart" :size="18" /></span>
            <div class="chip-text">
              <strong>四维能力雷达</strong>
              <span>准确 / 完整 / 深度 / 条理</span>
            </div>
          </div>
          <div class="hero-chip chip-b">
            <span class="chip-icon"><DSIcon name="book-open" :size="18" /></span>
            <div class="chip-text">
              <strong>薄弱点存知识库</strong>
              <span>双链笔记 + 语义检索</span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 两种方式 -->
    <section class="modes">
      <div class="modes-inner">
        <div class="modes-head reveal-2">
          <h2>选择你的练习方式</h2>
          <p>简历匹配省去选择困难，自主选岗灵活定制</p>
        </div>
        <div class="modes-grid">
          <article class="ds-card ds-card-hover mode-card reveal-3" @click="$router.push('/resume-upload')">
            <div class="mode-icon icon-indigo">
              <DSIcon name="file" :size="22" color="#fff" />
            </div>
            <h3>简历智能匹配</h3>
            <p>上传你的简历，AI 自动分析技能画像并匹配最合适的岗位，直接进入针对性模拟面试。</p>
            <span class="mode-cta">
              上传简历
              <DSIcon name="arrow-right" :size="14" />
            </span>
          </article>
          <article class="ds-card ds-card-hover mode-card reveal-4" @click="$router.push('/choose-job')">
            <div class="mode-icon icon-amber">
              <DSIcon name="map-pin" :size="22" color="#fff" />
            </div>
            <h3>自主选择岗位</h3>
            <p>自由选择目标岗位、题量与难度，灵活定制练习计划，随时开始一场针对性面试。</p>
            <span class="mode-cta">
              选择岗位
              <DSIcon name="arrow-right" :size="14" />
            </span>
          </article>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import TopNav from '../components/TopNav.vue'
import DSIcon from '../components/DSIcon.vue'
</script>

<style scoped>
.home {
  min-height: 100vh;
  background:
    radial-gradient(900px 420px at 85% -10%, var(--brand-100), transparent 65%),
    radial-gradient(700px 380px at -10% 20%, var(--accent-100), transparent 60%),
    var(--bg-100);
}

/* ── Hero ── */
.hero {
  padding: 36px 24px 44px;
}

.hero-inner {
  max-width: var(--max-width);
  margin: 0 auto;
  display: grid;
  grid-template-columns: 11fr 9fr;
  gap: 56px;
  align-items: center;
}

.hero-eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 14px;
  border-radius: 999px;
  background: var(--accent-100);
  border: 1px solid var(--accent-200);
  color: var(--accent-700);
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.eyebrow-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent-500);
}

.hero-title {
  font-size: clamp(28px, 3.4vw, 42px);
  font-weight: 900;
  line-height: 1.25;
  letter-spacing: 0.01em;
  color: var(--text-primary);
  margin-top: 14px;
}

.hero-title em {
  font-style: normal;
  color: var(--brand-700);
  position: relative;
  white-space: nowrap;
}

.hero-title em::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: 4px;
  height: 10px;
  background: var(--accent-200);
  z-index: -1;
  border-radius: 2px;
}

.hero-sub {
  margin-top: 14px;
  max-width: 480px;
  font-size: 14.5px;
  line-height: 1.75;
  color: var(--text-muted);
}

.hero-actions {
  display: flex;
  gap: 12px;
  margin-top: 22px;
  flex-wrap: wrap;
}

.hero-btn {
  padding: 11px 24px;
  font-size: 14.5px;
}

.hero-stats {
  display: flex;
  align-items: center;
  gap: 26px;
  margin-top: 26px;
  padding-top: 18px;
  border-top: 1px solid var(--border-default);
}

.stat {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.stat-num {
  font-family: var(--font-mono);
  font-size: 24px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--brand-800);
  line-height: 1.1;
}

.stat-label {
  font-size: 13px;
  color: var(--text-muted);
}

.stat-divider {
  width: 1px;
  height: 34px;
  background: var(--border-default);
}

/* ── Hero 视觉 ── */
.hero-visual {
  position: relative;
}

.hero-frame {
  aspect-ratio: 16 / 10;
  max-height: 340px;
  width: 100%;
  border-radius: var(--radius-lg);
  overflow: hidden;
  border: 1px solid var(--border-default);
  box-shadow: var(--shadow-lg);
}

.hero-frame img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.hero-chip {
  position: absolute;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: var(--radius-md);
  background: var(--surface);
  border: 1px solid var(--border-default);
  box-shadow: var(--shadow-md);
}

.chip-a { left: -22px; bottom: 44px; animation: float-y 5s ease-in-out infinite; }
.chip-b { right: -14px; top: 36px; animation: float-y 5s ease-in-out 1.2s infinite; }

.chip-icon { font-size: 20px; line-height: 1; }

.chip-text {
  display: flex;
  flex-direction: column;
  line-height: 1.35;
}

.chip-text strong {
  font-size: 13px;
  color: var(--text-primary);
}

.chip-text span {
  font-size: 11.5px;
  color: var(--text-muted);
}

@keyframes float-y {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-6px); }
}

/* ── 方式卡片 ── */
.modes {
  padding: 8px 24px 56px;
}

.modes-inner {
  max-width: var(--max-width);
  margin: 0 auto;
}

.modes-head {
  margin-bottom: 20px;
}

.modes-head h2 {
  font-size: 22px;
  color: var(--text-primary);
}

.modes-head p {
  margin-top: 4px;
  font-size: 13.5px;
  color: var(--text-muted);
}

.modes-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
}

.mode-card {
  padding: 24px 28px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  cursor: pointer;
}

.mode-icon {
  width: 46px;
  height: 46px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
}

.icon-indigo { background: var(--brand-700); }
.icon-amber { background: var(--accent-600); }

.mode-card h3 {
  font-size: 18px;
  color: var(--text-primary);
}

.mode-card p {
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-muted);
}

.mode-cta {
  margin-top: auto;
  padding-top: 10px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13.5px;
  font-weight: 600;
  color: var(--brand-700);
}

.mode-cta :deep(svg) {
  transition: transform var(--dur-fast) var(--ease-out);
}

.mode-card:hover .mode-cta :deep(svg) {
  transform: translateX(3px);
}

@media (max-width: 767px) {
  .hero-inner { grid-template-columns: 1fr; gap: 36px; }
  .hero { padding: 40px 20px 56px; }
  .modes-grid { grid-template-columns: 1fr; }
  .hero-stats { gap: 18px; }
  .chip-a { left: -6px; }
  .chip-b { right: -4px; }
}

@media (prefers-reduced-motion: reduce) {
  .chip-a, .chip-b { animation: none; }
}
</style>
