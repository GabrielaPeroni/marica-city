// Slim top bar while the next page loads (only when it takes longer than a blink).
(function () {
  const bar = document.createElement('div');
  bar.className = 'nav-progress';
  bar.setAttribute('aria-hidden', 'true');
  document.body.appendChild(bar);
  let timer = null;
  let slowTimer = null;
  const SLOW_NAV_MS = 5000;

  function stillLoading() {
    if (window.showConnectionNotice) {
      window.showConnectionNotice(
        gettext('Ainda carregando… a conexão pode estar lenta. Aguarde um instante.'),
        'slow'
      );
    }
  }

  function start() {
    clearTimeout(timer);
    clearTimeout(slowTimer);
    timer = setTimeout(() => bar.classList.add('is-loading'), 120);
    slowTimer = setTimeout(stillLoading, SLOW_NAV_MS);
  }

  function reset() {
    clearTimeout(timer);
    clearTimeout(slowTimer);
    bar.classList.remove('is-loading', 'is-done');
    if (window.hideConnectionNotice) window.hideConnectionNotice('slow');
  }

  document.addEventListener('click', e => {
    const link = e.target.closest('a[href]');
    if (!link || e.defaultPrevented || e.button !== 0) return;
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    if (link.target && link.target !== '_self') return;
    if (link.hasAttribute('download') || link.origin !== location.origin) return;
    const url = new URL(link.href);
    if (url.pathname === location.pathname && url.search === location.search) return;
    start();
  });

  // Runs after other submit handlers, so AJAX forms (preventDefault) are skipped
  document.addEventListener('submit', e => {
    setTimeout(() => {
      if (!e.defaultPrevented) start();
    }, 0);
  });

  window.addEventListener('pageshow', reset);
  window.addEventListener('pagehide', reset);

  // Nesta página: se as imagens ainda estão chegando, a barra continua e termina quando tudo carrega
  if (document.readyState !== 'complete') {
    const slow = setTimeout(() => bar.classList.add('is-loading'), 150);
    const slowNotice = setTimeout(stillLoading, SLOW_NAV_MS);
    window.addEventListener(
      'load',
      () => {
        clearTimeout(slow);
        clearTimeout(slowNotice);
        if (window.hideConnectionNotice) window.hideConnectionNotice('slow');
        if (!bar.classList.contains('is-loading')) return;
        bar.classList.add('is-done');
        setTimeout(() => bar.classList.remove('is-loading', 'is-done'), 450);
      },
      { once: true }
    );
  }
})();
