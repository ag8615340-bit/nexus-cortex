/* ============================================
   NEXUS CORTEX — UI Effects & Animations
   ============================================ */

document.addEventListener('DOMContentLoaded', () => {

  // ==========================================
  // 1. 3D CARD TILT EFFECT
  // ==========================================
  const tiltCards = document.querySelectorAll('.tilt-card');

  tiltCards.forEach(card => {
    const shine = card.querySelector('.agent-card-shine');

    card.addEventListener('mousemove', (e) => {
      const rect = card.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;

      // Calculate rotation: map mouse position to degrees (-8 to +8)
      const centerX = rect.width / 2;
      const centerY = rect.height / 2;
      const rotateY = ((x - centerX) / centerX) * 6;   // max ±6deg
      const rotateX = ((centerY - y) / centerY) * 6;

      // Apply 3D transform
      card.style.transform = `
        perspective(800px)
        rotateX(${rotateX}deg)
        rotateY(${rotateY}deg)
        translateZ(10px)
      `;

      // Update shine position
      if (shine) {
        const pctX = (x / rect.width) * 100;
        const pctY = (y / rect.height) * 100;
        shine.style.setProperty('--mx', pctX + '%');
        shine.style.setProperty('--my', pctY + '%');
        shine.style.opacity = '1';
      }
    });

    card.addEventListener('mouseleave', () => {
      // Smooth reset
      card.style.transform = `
        perspective(800px)
        rotateX(0deg)
        rotateY(0deg)
        translateZ(0)
      `;
      card.style.transition = 'transform 0.5s cubic-bezier(0.4, 0, 0.2, 1)';

      if (shine) {
        shine.style.opacity = '0';
      }

      // Remove transition after reset
      setTimeout(() => {
        card.style.transition = '';
      }, 500);
    });

    // Prevent transition conflicts during mouse move
    card.addEventListener('mouseenter', () => {
      card.style.transition = 'box-shadow 0.3s ease';
    });
  });

  // ==========================================
  // 2. METRIC CARD FLOATING ANIMATION
  // ==========================================
  const metricCards = document.querySelectorAll('.metric-card');

  metricCards.forEach((card, index) => {
    card.style.setProperty('--float-delay', (index * 0.15) + 's');
    card.classList.add('float-in');
  });

  // ==========================================
  // 3. SUB-AGENT NEON PULSE SYNC
  // ==========================================
  const subagents = document.querySelectorAll('.subagent.active');
  subagents.forEach((sub, i) => {
    const dot = sub.querySelector('.sg-dot');
    if (dot) {
      dot.style.animationDelay = (i * 0.15) + 's';
    }
  });

  // ==========================================
  // 4. INTERSECTION OBSERVER — FADE IN
  // ==========================================
  const animateElements = document.querySelectorAll(
    '.feature-card, .metric-card, .stat-card, .testimonial-card, .agent-card'
  );

  const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -40px 0px',
  };

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry, idx) => {
      if (entry.isIntersecting) {
        const el = entry.target;
        const delay = parseFloat(el.style.getPropertyValue('--delay') || 0) || (idx * 0.05);
        el.style.setProperty('--fade-delay', delay + 's');
        el.classList.add('visible');
        observer.unobserve(el);
      }
    });
  }, observerOptions);

  animateElements.forEach(el => observer.observe(el));

  // ==========================================
  // 5. STATIC RANDOM GRID LINES (ambient)
  // ==========================================
  function createAmbientGrid() {
    const main = document.querySelector('.main-content');
    if (!main) return;

    // Subtle grid overlay already exists via CSS background,
    // but we can add a decorative scanner line
    const scanner = document.createElement('div');
    scanner.className = 'scanner-line';
    scanner.style.cssText = `
      position: fixed;
      top: 0;
      left: var(--sidebar-w, 260px);
      right: 0;
      height: 1px;
      background: linear-gradient(90deg, transparent, rgba(99, 102, 241, 0.15), transparent);
      pointer-events: none;
      z-index: 999;
      animation: scannerMove 4s ease-in-out infinite;
    `;
    document.body.appendChild(scanner);

    // Inject scanner keyframes if not already present
    if (!document.getElementById('scannerKeyframes')) {
      const style = document.createElement('style');
      style.id = 'scannerKeyframes';
      style.textContent = `
        @keyframes scannerMove {
          0% { top: 0; opacity: 0; }
          10% { opacity: 1; }
          90% { opacity: 1; }
          100% { top: 100%; opacity: 0; }
        }
      `;
      document.head.appendChild(style);
    }
  }

  createAmbientGrid();

  // ==========================================
  // 6. PARTICLE BACKGROUND (lightweight)
  // ==========================================
  function createParticles() {
    const canvas = document.createElement('canvas');
    canvas.className = 'particle-canvas';
    canvas.style.cssText = `
      position: fixed;
      inset: 0;
      pointer-events: none;
      z-index: 0;
      opacity: 0.4;
    `;

    // Insert behind main content
    const main = document.querySelector('.main-content');
    if (main) {
      main.prepend(canvas);
    }

    const ctx = canvas.getContext('2d');
    let w, h;
    const particles = [];
    const count = 40;

    function resize() {
      w = window.innerWidth;
      h = window.innerHeight;
      canvas.width = w;
      canvas.height = h;
    }

    function createParticle() {
      return {
        x: Math.random() * w,
        y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.3,
        vy: (Math.random() - 0.5) * 0.3,
        r: Math.random() * 1.5 + 0.5,
        alpha: Math.random() * 0.3 + 0.1,
      };
    }

    function init() {
      resize();
      for (let i = 0; i < count; i++) {
        particles.push(createParticle());
      }
    }

    function draw() {
      ctx.clearRect(0, 0, w, h);

      particles.forEach(p => {
        p.x += p.vx;
        p.y += p.vy;

        if (p.x < 0) p.x = w;
        if (p.x > w) p.x = 0;
        if (p.y < 0) p.y = h;
        if (p.y > h) p.y = 0;

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(99, 102, 241, ${p.alpha})`;
        ctx.fill();
      });

      // Draw connections
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x;
          const dy = particles[i].y - particles[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);

          if (dist < 120) {
            ctx.beginPath();
            ctx.moveTo(particles[i].x, particles[i].y);
            ctx.lineTo(particles[j].x, particles[j].y);
            ctx.strokeStyle = `rgba(99, 102, 241, ${0.06 * (1 - dist / 120)})`;
            ctx.lineWidth = 0.5;
            ctx.stroke();
          }
        }
      }

      requestAnimationFrame(draw);
    }

    init();
    draw();

    window.addEventListener('resize', resize);
  }

  createParticles();

  // ==========================================
  // 7. SMOOTH COUNT UP (Overview metrics)
  // ==========================================
  function animateCountUp() {
    const metricValues = document.querySelectorAll('.metric-value');

    metricValues.forEach(el => {
      const text = el.textContent.trim();
      // Extract numeric part
      const numMatch = text.match(/[\d,.]+/);
      if (!numMatch) return;

      const targetStr = numMatch[0].replace(/,/g, '');
      const target = parseFloat(targetStr);
      if (isNaN(target)) return;

      const suffix = text.slice(numMatch[0].length);

      // Check if already animated
      if (el.dataset.animated) return;
      el.dataset.animated = 'true';

      const duration = 1500;
      const startTime = performance.now();

      function step(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        // Ease out cubic
        const eased = 1 - Math.pow(1 - progress, 3);
        const current = eased * target;

        // Format
        let display;
        if (Number.isInteger(target) && target > 1000) {
          display = Math.floor(current).toLocaleString();
        } else if (Number.isInteger(target)) {
          display = Math.floor(current).toString();
        } else {
          display = current.toFixed(1);
        }

        el.textContent = display + suffix;

        if (progress < 1) {
          requestAnimationFrame(step);
        } else {
          el.textContent = text; // Restore exact original
        }
      }

      requestAnimationFrame(step);
    });
  }

  // Run count-up when overview tab is shown
  const overviewObserver = new MutationObserver(() => {
    const overviewPanel = document.getElementById('tab-overview');
    if (overviewPanel?.classList.contains('active')) {
      setTimeout(animateCountUp, 300);
    }
  });

  const tabPanels = document.querySelectorAll('.tab-panel');
  tabPanels.forEach(panel => {
    overviewObserver.observe(panel, {
      attributes: true,
      attributeFilter: ['class'],
    });
  });

  // Initial trigger if overview is already active
  if (document.getElementById('tab-overview')?.classList.contains('active')) {
    setTimeout(animateCountUp, 500);
  }

  // ==========================================
  // 8. CIRCULAR CURSOR GLOW (ambient)
  // ==========================================
  const cursorGlow = document.createElement('div');
  cursorGlow.className = 'cursor-glow';
  // FIXED: increased z-index to be visible above content
  cursorGlow.style.cssText = `
    position: fixed;
    width: 300px;
    height: 300px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(99, 102, 241, 0.06), transparent 70%);
    pointer-events: none;
    z-index: 9999;
    transform: translate(-50%, -50%);
    transition: opacity 0.3s;
    opacity: 0;
  `;
  document.body.appendChild(cursorGlow);

  let glowTimeout;
  document.addEventListener('mousemove', (e) => {
    cursorGlow.style.left = e.clientX + 'px';
    cursorGlow.style.top = e.clientY + 'px';
    cursorGlow.style.opacity = '1';

    clearTimeout(glowTimeout);
    glowTimeout = setTimeout(() => {
      cursorGlow.style.opacity = '0';
    }, 2000);
  });

  // ==========================================
  // 9. DYNAMIC SIDEBAR — highlight active item
  // ==========================================
  const activeNavItem = document.querySelector('.nav-item.active');
  if (activeNavItem) {
    activeNavItem.style.boxShadow = 'inset 3px 0 0 var(--indigo-500), 0 0 20px rgba(99, 102, 241, 0.05)';
  }

  // ==========================================
  // 10. NAVBAR SCROLL GLASS EFFECT
  // ==========================================
  const topbar = document.querySelector('.topbar');

  window.addEventListener('scroll', () => {
    const scrollY = window.scrollY;
    if (scrollY > 10) {
      topbar?.classList.add('scrolled');
    } else {
      topbar?.classList.remove('scrolled');
    }
  });

  console.log('%c Nexus Cortex v3.2 ', 'background:#6366F1;color:#fff;font-weight:700;padding:4px 8px;border-radius:4px;');
  console.log('%c Enterprise Agent Dashboard loaded successfully.', 'color:#9CA3AF;');

});