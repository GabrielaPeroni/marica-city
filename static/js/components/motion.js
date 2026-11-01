// Animações do site: revela seções e grades de cards ao rolar ([data-reveal],
// [data-reveal-stagger]), parallax das ilustrações e luz que segue o cursor.
(function () {
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const root = document.documentElement;

  if (!reduceMotion && 'IntersectionObserver' in window) {
    root.classList.add('motion');
    const observer = new window.IntersectionObserver(
      entries => {
        entries.forEach(entry => {
          if (!entry.isIntersecting) return;
          entry.target.classList.add('is-revealed');
          observer.unobserve(entry.target);
        });
      },
      { rootMargin: '0px 0px -8% 0px', threshold: 0.08 }
    );
    const watch = scope => {
      scope.querySelectorAll('[data-reveal-stagger]').forEach(group => {
        [...group.children].forEach((child, i) => {
          child.style.setProperty('--reveal-i', String(i % 8));
          if (!child.classList.contains('is-revealed')) observer.observe(child);
        });
      });
      scope
        .querySelectorAll('[data-reveal]:not(.is-revealed)')
        .forEach(el => observer.observe(el));
    };
    watch(document);
    // Conteúdo inserido depois (favoritos, resultados) também anima
    window.revealIn = watch;
  }

  // Ilustrações [data-parallax="0.1"] andam mais devagar/rápido que a página.
  // Só as que estão perto da tela são calculadas (e animadas): leituras de layout juntas, depois as escritas.
  const floats = [...document.querySelectorAll('[data-parallax]')];
  if (!reduceMotion && floats.length) {
    const near = new Set();
    let ticking = false;
    const update = () => {
      const mid = window.innerHeight / 2;
      const batch = [...near].map(el => {
        const rect = el.parentElement.getBoundingClientRect();
        return [
          el,
          (rect.top + rect.height / 2 - mid) * parseFloat(el.dataset.parallax),
        ];
      });
      batch.forEach(([el, offset]) =>
        el.style.setProperty('--parallax', offset.toFixed(1))
      );
      ticking = false;
    };
    const watcher = new window.IntersectionObserver(
      entries => {
        entries.forEach(entry => {
          entry.target.classList.toggle('is-offscreen', !entry.isIntersecting);
          if (entry.isIntersecting) near.add(entry.target);
          else near.delete(entry.target);
        });
        update();
      },
      { rootMargin: '200px 0px' }
    );
    floats.forEach(el => watcher.observe(el));
    window.addEventListener(
      'scroll',
      () => {
        if (!ticking) {
          ticking = true;
          window.requestAnimationFrame(update);
        }
      },
      { passive: true }
    );
  }

  // Ondas do hero e gaivotas do rodapé: só animam enquanto aparecem
  const loops = document.querySelectorAll('.hero-water, footer .deco-gulls');
  if (!reduceMotion && loops.length) {
    const pauser = new window.IntersectionObserver(entries =>
      entries.forEach(entry =>
        entry.target.classList.toggle('is-offscreen', !entry.isIntersecting)
      )
    );
    loops.forEach(el => pauser.observe(el));
  }

  if (window.matchMedia('(hover: hover) and (pointer: fine)').matches) {
    document.addEventListener(
      'pointermove',
      event => {
        const card = event.target.closest && event.target.closest('[data-spotlight]');
        if (!card) return;
        const rect = card.getBoundingClientRect();
        card.style.setProperty('--mx', `${event.clientX - rect.left}px`);
        card.style.setProperty('--my', `${event.clientY - rect.top}px`);
      },
      { passive: true }
    );
  }
})();
