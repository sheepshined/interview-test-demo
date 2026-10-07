/* ============================================================
   墨卷档案 · 交互层 (Interactions)
   自定义光标 / 磁吸按钮 / 方向性墨水填充 / 墨水涟漪 /
   整页转场（墨幕 + 盖章）/ 逐字标题 / 雷达描线 /
   滚动速度斜切 / 解码字幕 / 3D 倾斜 / 回顶印章
   守卫：仅在 pointer:fine 且 prefers-reduced-motion 关闭时启用；
   所有持续效果基于 rAF 与 transform/opacity，不触发布局。
   ============================================================ */
(() => {
  'use strict';

  const fine = matchMedia('(pointer:fine)').matches;
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  // ?ix-force 仅供演示/自动化测试强制开启（正常访问不受影响）
  const force = new URLSearchParams(location.search).has('ix-force');
  const ix = (fine && !reduced) || force;
  window.__IX_WIPE = ix; // app.js 据此让出整页转场

  const clamp = (v, a, b) => Math.min(b, Math.max(a, v));

  /* ------------------------------------------------------------
     自动标注：无需改页面标记，统一在此挂属性
     ------------------------------------------------------------ */
  function autoTag(root) {
    (root || document).querySelectorAll('.btn-lg, .send-btn').forEach((b) => b.setAttribute('data-mag', ''));
    (root || document).querySelectorAll('.doc-score, .radar-box').forEach((el) => el.setAttribute('data-tilt', ''));
    const scope = root || document;
    const dz = scope.querySelector && scope.querySelector('#dropzone');
    if (dz) dz.setAttribute('data-cursor', '拖入 PDF');
    const gsvg = scope.querySelector && scope.querySelector('.gnode')
      ? scope.querySelector('.gnode').closest('svg') : null;
    if (gsvg) gsvg.setAttribute('data-cursor', '拖拽 · 探索图谱');
  }

  /* ------------------------------------------------------------
     整页转场：墨幕 + 盖章
     ------------------------------------------------------------ */
  function initWipe() {
    if (!ix) return;
    const el = document.createElement('div');
    el.className = 'ix-wipe';
    el.innerHTML = '<div class="ix-wipe-panel"></div><div class="ix-wipe-seal">面</div>';
    document.body.appendChild(el);

    // 入场：先无动画地盖上墨幕（避免闪白），再揭开
    const panel = el.querySelector('.ix-wipe-panel');
    panel.style.transition = 'none';
    el.classList.add('is-in');
    void el.offsetWidth;
    panel.style.transition = '';

    let revealed = false;
    function reveal() {
      if (revealed) return;
      revealed = true;
      setTimeout(() => {
        el.classList.remove('is-in');
        el.classList.add('is-out');
        setTimeout(() => { el.classList.remove('is-out'); el.style.visibility = 'hidden'; }, 800);
      }, 200);
    }
    if (document.readyState === 'complete') reveal();
    else window.addEventListener('load', reveal);
    window.addEventListener('pageshow', (e) => { if (e.persisted) reveal(); });

    // 拦截站内跳转
    document.addEventListener('click', (e) => {
      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      const a = e.target.closest('a[href$=".html"]');
      if (!a || a.target === '_blank') return;
      const href = a.getAttribute('href');
      if (!href || href.startsWith('http')) return;
      e.preventDefault();
      el.style.visibility = '';
      el.classList.remove('is-out');
      void el.offsetWidth;
      el.classList.add('is-in');
      setTimeout(() => { window.location.href = href; }, 480);
    });
  }

  /* ------------------------------------------------------------
     自定义光标
     ------------------------------------------------------------ */
  function initCursor() {
    if (!ix) return;
    document.documentElement.classList.add('ix-cursor');

    const dot = document.createElement('div');
    dot.className = 'ix-cursor-dot';
    const ring = document.createElement('div');
    ring.className = 'ix-cursor-ring';
    const label = document.createElement('div');
    label.className = 'ix-cursor-label';
    document.body.append(dot, ring, label);

    let x = innerWidth / 2, y = innerHeight / 2, rx = x, ry = y, shown = false;

    addEventListener('mousemove', (e) => {
      x = e.clientX; y = e.clientY;
      if (!shown) { shown = true; rx = x; ry = y; }
    }, { passive: true });
    document.documentElement.addEventListener('mouseleave', () => {
      dot.style.opacity = 0; ring.style.opacity = 0; label.classList.remove('is-on');
    });
    document.documentElement.addEventListener('mouseenter', () => {
      if (shown) { dot.style.opacity = ''; ring.style.opacity = ''; }
    });

    document.addEventListener('mouseover', (e) => {
      const t = e.target.closest('a, button, label, [role="button"], .pick, .tag, .tab, .dbtn, .tts-btn, input, textarea, select, [data-cursor], .gnode');
      const isText = !!t && /^(input|textarea|select)$/i.test(t.tagName);
      ring.classList.toggle('is-text', isText);
      ring.classList.toggle('is-hover', !!t && !isText);
      const cap = t && t.closest && t.closest('[data-cursor]');
      if (cap && !isText) {
        label.textContent = cap.getAttribute('data-cursor');
        label.classList.add('is-on');
      } else {
        label.classList.remove('is-on');
      }
    });
    document.addEventListener('mousedown', () => ring.classList.add('is-press'));
    document.addEventListener('mouseup', () => ring.classList.remove('is-press'));

    (function loop() {
      rx += (x - rx) * 0.16;
      ry += (y - ry) * 0.16;
      dot.style.transform = `translate3d(${x}px, ${y}px, 0)`;
      ring.style.transform = `translate3d(${rx.toFixed(1)}px, ${ry.toFixed(1)}px, 0)`;
      label.style.transform = `translate3d(${rx.toFixed(1)}px, ${ry.toFixed(1)}px, 0)`;
      requestAnimationFrame(loop);
    })();
  }

  /* ------------------------------------------------------------
     磁吸按钮
     ------------------------------------------------------------ */
  const magEls = [];
  let magLoopStarted = false;
  function initMagnetic(root) {
    if (!ix) return;
    const found = [...(root || document).querySelectorAll('[data-mag]')];
    found.forEach((el) => { if (!magEls.includes(el)) magEls.push(el); });
    if (!magLoopStarted && magEls.length) {
      magLoopStarted = true;
      let mx = -1e4, my = -1e4;
      addEventListener('mousemove', (e) => { mx = e.clientX; my = e.clientY; }, { passive: true });
      (function loop() {
        for (let i = magEls.length - 1; i >= 0; i--) {
          const el = magEls[i];
          if (!el.isConnected) { magEls.splice(i, 1); continue; }
        const r = el.getBoundingClientRect();
          if (!r.width) continue;
          const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
          const dx = mx - cx, dy = my - cy;
          const radius = Math.max(r.width, r.height) / 2 + 26;
          const inside = Math.hypot(dx, dy) < radius;
          if (inside) {
            el.classList.add('is-mag-live');
            el.classList.remove('is-mag-release');
            el.style.transform = `translate(${(dx * 0.26).toFixed(1)}px, ${(dy * 0.26).toFixed(1)}px)`;
          } else if (el.classList.contains('is-mag-live')) {
            el.classList.remove('is-mag-live');
            el.classList.add('is-mag-release');
            el.style.transform = '';
            setTimeout(() => el.classList.remove('is-mag-release'), 600);
          }
        }
        requestAnimationFrame(loop);
      })();
    }
  }

  /* ------------------------------------------------------------
     按钮：墨水按进入方向涂满 + 点击涟漪
     ------------------------------------------------------------ */
  function initInkButtons() {
    if (!ix) return;
    document.addEventListener('mouseover', (e) => {
      const b = e.target.closest('.btn');
      if (!b) return;
      const r = b.getBoundingClientRect();
      const x = (e.clientX - r.left) / r.width;
      const y = (e.clientY - r.top) / r.height;
      let dx = 0, dy = 101;
      if (x < 0.25) { dx = -101; dy = 0; }
      else if (x > 0.75) { dx = 101; dy = 0; }
      else if (y < 0.5) { dx = 0; dy = -101; }
      b.style.setProperty('--ix-dx', dx + '%');
      b.style.setProperty('--ix-dy', dy + '%');
    });

    document.addEventListener('click', (e) => {
      const b = e.target.closest('.btn, .send-btn, .end-btn');
      if (!b) return;
      const r = b.getBoundingClientRect();
      const d = Math.max(r.width, r.height) * 2.1;
      const s = document.createElement('span');
      s.className = 'ix-ripple';
      s.style.width = s.style.height = d + 'px';
      s.style.left = (e.clientX - r.left - d / 2) + 'px';
      s.style.top = (e.clientY - r.top - d / 2) + 'px';
      b.appendChild(s);
      s.addEventListener('animationend', () => s.remove());
    });
  }

  /* ------------------------------------------------------------
     3D 倾斜卡片
     ------------------------------------------------------------ */
  function initTilt(root) {
    if (!ix) return;
    (root || document).querySelectorAll('[data-tilt]').forEach((el) => {
      // .rv 的过渡会干扰倾斜，等揭示动画结束后摘除
      if (el.classList.contains('rv')) {
        setTimeout(() => el.classList.remove('rv', 'is-in'), 1100);
      }
      el.addEventListener('mousemove', (e) => {
        const r = el.getBoundingClientRect();
        const px = (e.clientX - r.left) / r.width - 0.5;
        const py = (e.clientY - r.top) / r.height - 0.5;
        el.classList.add('is-tilt-live');
        el.style.setProperty('--rx', (-py * 5).toFixed(2) + 'deg');
        el.style.setProperty('--ry', (px * 7).toFixed(2) + 'deg');
        el.style.setProperty('--gx', ((px + 0.5) * 100).toFixed(1) + '%');
        el.style.setProperty('--gy', ((py + 0.5) * 100).toFixed(1) + '%');
      });
      el.addEventListener('mouseleave', () => {
        el.classList.remove('is-tilt-live');
        el.style.setProperty('--rx', '0deg');
        el.style.setProperty('--ry', '0deg');
      });
    });
  }

  /* ------------------------------------------------------------
     逐字标题（仅 hero 大标题）
     ------------------------------------------------------------ */
  function initCharSplit() {
    if (!ix) return;
    document.querySelectorAll('.hero-title .rv-line > span').forEach((span) => {
      if (span.classList.contains('split')) return;
      const nodes = [...span.childNodes];
      span.textContent = '';
      let i = 0;
      nodes.forEach((node) => {
        if (node.nodeType === 3) {
          [...node.textContent].forEach((ch) => {
            if (ch === ' ') { span.appendChild(document.createTextNode(' ')); return; }
            const s = document.createElement('span');
            s.className = 'ch';
            s.style.setProperty('--cd', (i++ * 0.045).toFixed(3) + 's');
            s.textContent = ch;
            span.appendChild(s);
          });
        } else if (node.nodeType === 1) {
          const s = document.createElement('span');
          s.className = 'ch';
          s.style.setProperty('--cd', (i++ * 0.045).toFixed(3) + 's');
          s.appendChild(node);
          span.appendChild(s);
        }
      });
      span.classList.add('split');
    });
  }

  /* ------------------------------------------------------------
     雷达描线
     ------------------------------------------------------------ */
  function initRadar(root) {
    if (!ix) return;
    (root || document).querySelectorAll('.radar-box svg, .hero-stage .radar').forEach((svg) => {
      const poly = [...svg.querySelectorAll('path')].find((p) =>
        /vermilion|d93a1f/i.test(p.getAttribute('stroke') || ''));
      if (!poly) return;
      poly.setAttribute('pathLength', '100');
      poly.classList.add('ix-radar-poly');
      const dots = poly.nextElementSibling;
      if (dots && dots.tagName.toLowerCase() === 'g') dots.classList.add('ix-radar-dots');
      const host = svg.closest('.rv') || svg.closest('.hero-stage');
      const go = () => svg.classList.add('ix-radar-go');
      if (host && host.classList.contains('is-in')) setTimeout(go, 80);
      else if (host) {
        const io = new IntersectionObserver((es) => {
          if (es.some((x) => x.isIntersecting)) { io.disconnect(); setTimeout(go, 80); }
        }, { threshold: 0.2 });
        io.observe(host);
      } else setTimeout(go, 800);
    });
  }

  /* ------------------------------------------------------------
     等宽标注解码入场
     ------------------------------------------------------------ */
  function initDecode(root) {
    if (!ix) return;
    const POOL = '墨卷面试档案№§◆—·0123456789RAGLMTPS';
    const targets = (root || document).querySelectorAll('.sec-index, .statband .e');
    const io = new IntersectionObserver((es) => {
      es.forEach((en) => {
        if (!en.isIntersecting) return;
        io.unobserve(en.target);
        const el = en.target;
        const orig = el.textContent;
        if (!orig || orig.length > 26) return;
        let frame = 0;
        const total = 12;
        const timer = setInterval(() => {
          frame++;
          const settled = Math.floor((frame / total) * orig.length);
          el.textContent = orig.slice(0, settled) +
            [...orig.slice(settled)].map((c) => (c === ' ' ? ' ' : POOL[(Math.random() * POOL.length) | 0])).join('');
          if (frame >= total) { clearInterval(timer); el.textContent = orig; }
        }, 42);
      });
    }, { threshold: 0.4 });
    targets.forEach((el) => io.observe(el));
  }

  /* ------------------------------------------------------------
     滚动速度斜切（字幕带）
     ------------------------------------------------------------ */
  function initTickerSkew() {
    if (!ix) return;
    const tickers = [...document.querySelectorAll('.ticker')];
    if (!tickers.length) return;
    let lastY = scrollY, cur = 0, idle = true;
    addEventListener('scroll', () => { idle = false; }, { passive: true });
    (function loop() {
      const dy = scrollY - lastY;
      lastY = scrollY;
      const target = clamp(dy * 0.06, -2, 2);
      cur += (target - cur) * 0.09;
      if (Math.abs(cur) < 0.005) cur = 0;
      tickers.forEach((t) => { t.style.transform = cur ? `skewY(${cur.toFixed(3)}deg)` : ''; });
      requestAnimationFrame(loop);
    })();
  }

  /* ------------------------------------------------------------
     按下盖章弹跳（页签 / 开关 / 工具钮）
     ------------------------------------------------------------ */
  function initPop() {
    document.addEventListener('click', (e) => {
      const el = e.target.closest('.demo-switch button, .tab, .seg button, .tts-btn, .dbtn');
      if (!el) return;
      el.classList.remove('ix-pop');
      void el.offsetWidth;
      el.classList.add('ix-pop');
    });
  }

  /* ------------------------------------------------------------
     回到顶部印章（仅带公共顶栏的长页）
     ------------------------------------------------------------ */
  function initTopSeal() {
    if (!document.querySelector('.pubnav')) return;
    const b = document.createElement('button');
    b.className = 'ix-top';
    b.type = 'button';
    b.setAttribute('aria-label', '回到顶部');
    b.textContent = '面';
    document.body.appendChild(b);
    addEventListener('scroll', () => {
      b.classList.toggle('is-on', scrollY > 720);
    }, { passive: true });
    b.addEventListener('click', () => scrollTo({ top: 0, behavior: 'smooth' }));
  }

  /* ---------- 启动 ---------- */
  autoTag();
  initWipe();
  initCursor();
  initInkButtons();
  initCharSplit();
  initTickerSkew();
  initPop();
  initTopSeal();

  // SPA 换页后重新挂载页面级效果（tilt / 雷达描线 / 解码 / 磁吸）
  window.IX = {
    refresh(root) {
      autoTag(root);
      initMagnetic(root);
      initTilt(root);
      initRadar(root);
      initDecode(root);
    },
  };
  window.IX.refresh(document);
})();
