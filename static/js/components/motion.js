// Animações do site: revela seções e grades de cards ao rolar ([data-reveal],
// [data-reveal-stagger]) e acende uma luz que segue o cursor ([data-spotlight]).
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
