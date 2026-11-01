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
      autoplayTimeLeft(swiper, timeLeft, progress) {
        section.style.setProperty('--hero-progress', String(1 - progress));
      },
      slideChange() {
        section.style.setProperty('--hero-progress', '0');
      },
    },
    threshold: 10,
  });

  // Parallax: o texto sobe e some conforme a página rola para fora do hero
  if (!reduceMotion) {
    let ticking = false;
    const onScroll = () => {
      const progress = Math.min(window.scrollY / section.offsetHeight, 1);
      section.style.setProperty('--hero-scroll', progress.toFixed(3));
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

  const scrollCue = section.querySelector('.hero-scroll');
  if (scrollCue) {
    scrollCue.addEventListener('click', event => {
      const next = section.nextElementSibling;
      if (!next) return;
      event.preventDefault();
      next.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth' });
    });
  }

  const pauseBtn = section.querySelector('.hero-pause-btn');
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
  initHero();
  initFeatured();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initLanding);
} else {
  initLanding();
}
