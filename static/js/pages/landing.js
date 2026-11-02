/* Página inicial: carrossel do hero e trilho de lugares "Onde ir" (Swiper) */

const HERO_DELAY = 6500;

function initHero() {
  const section = document.querySelector('[data-hero]');
  if (!section) return;
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const labels = [...section.querySelectorAll('.swiper-slide')].map(
    s => s.dataset.label
  );

  const hero = new Swiper('.hero-swiper', {
    loop: true,
    effect: 'fade',
    fadeEffect: { crossFade: true },
    speed: reduceMotion ? 0 : 1200,
    autoplay: reduceMotion
      ? false
      : {
          delay: HERO_DELAY,
          disableOnInteraction: false,
          pauseOnMouseEnter: false,
        },
    keyboard: { enabled: true, onlyInViewport: true },
    a11y: {
      prevSlideMessage: gettext('Slide anterior'),
      nextSlideMessage: gettext('Próximo slide'),
      paginationBulletMessage: gettext('Ir para o slide {{index}}'),
    },
    pagination: {
      el: section.querySelector('.hero-pagination'),
      clickable: true,
      bulletClass: 'hero-dot',
      bulletActiveClass: 'is-active',
      renderBullet: (index, className) =>
        `<button type="button" class="${className}"><span class="hero-dot-label">` +
        `${String(index + 1).padStart(2, '0')} · ${labels[index] || ''}</span>` +
        '<span class="hero-dot-bar"><span></span></span></button>',
    },
    on: {
      // Direto na barra ativa: uma variável na seção recalcula o estilo do hero inteiro a cada quadro
      autoplayTimeLeft(swiper, timeLeft, progress) {
        const bar = section.querySelector('.hero-dot.is-active .hero-dot-bar > span');
        if (bar) bar.style.scale = `${1 - progress} 1`;
      },
      slideChange() {
        section
          .querySelectorAll('.hero-dot-bar > span')
          .forEach(bar => bar.style.removeProperty('scale'));
      },
    },
    threshold: 10,
  });

  // Parallax: o texto sobe e some conforme a página rola para fora do hero
  if (!reduceMotion) {
    const copies = section.querySelectorAll('.hero-copy');
    let ticking = false;
    let last = '';
    const onScroll = () => {
      const progress = Math.min(window.scrollY / section.offsetHeight, 1).toFixed(3);
      if (progress !== last) {
        last = progress;
        copies.forEach(copy => copy.style.setProperty('--hero-scroll', progress));
      }
      ticking = false;
    };
    window.addEventListener(
      'scroll',
      () => {
        if (!ticking) {
          ticking = true;
          window.requestAnimationFrame(onScroll);
        }
      },
      { passive: true }
    );
  }

  const pauseBtn = section.querySelector('.hero-pause-btn');

  // Fora da tela o carrossel não precisa trocar de foto
  if (!reduceMotion && 'IntersectionObserver' in window) {
    new window.IntersectionObserver(([entry]) => {
      if (pauseBtn?.getAttribute('aria-pressed') === 'true') return;
      if (entry.isIntersecting) hero.autoplay.resume();
      else hero.autoplay.pause();
    }).observe(section);
  }

  if (!pauseBtn) return;
  const setPaused = paused => {
    pauseBtn.setAttribute('aria-pressed', String(paused));
    pauseBtn.setAttribute(
      'aria-label',
      paused ? gettext('Retomar apresentação') : gettext('Pausar apresentação')
    );
  };
  setPaused(reduceMotion);
  pauseBtn.addEventListener('click', () => {
    const paused = pauseBtn.getAttribute('aria-pressed') === 'true';
    if (paused && hero.autoplay.running) {
      hero.autoplay.resume();
    } else if (paused) {
      hero.params.autoplay = { delay: HERO_DELAY, disableOnInteraction: false };
      hero.autoplay.start();
    } else {
      hero.autoplay.pause();
    }
    setPaused(!paused);
  });
}

function initFeatured() {
  if (!document.querySelector('.featured-swiper')) return;
  new Swiper('.featured-swiper', {
    slidesPerView: 'auto',
    spaceBetween: 20,
    grabCursor: true,
    freeMode: true,
    mousewheel: { forceToAxis: true },
    a11y: { enabled: true },
  });
}

function initLanding() {
  const start = () =>
    window
      .loadSwiper()
      .then(() => {
        initHero();
        initFeatured();
      })
      // Sem a CDN a página segue legível (primeiro slide, trilho rolável); tenta de novo ao voltar a internet
      .catch(() => window.addEventListener('online', start, { once: true }));
  start();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initLanding);
} else {
  initLanding();
}
