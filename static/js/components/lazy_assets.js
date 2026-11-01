// Bibliotecas de CDN (Leaflet, Swiper) baixadas só quando a página precisa, sem travar a renderização.
// Se a CDN falhar, a promise rejeita e quem chamou mostra um estado de erro com "Tentar de novo".
(function () {
  const LEAFLET = '1.9.4';
  const SWIPER = '11.2.10';
  const LOAD_TIMEOUT_MS = 20000;
  const loading = new Map();

  function load(tag, attrs) {
    const url = attrs.src || attrs.href;
    if (loading.has(url)) return loading.get(url);
    const promise = new Promise((resolve, reject) => {
      const el = document.createElement(tag);
      Object.assign(el, attrs);
      const fail = () => {
        clearTimeout(timer);
        el.remove();
        loading.delete(url);
        reject(new Error(`Falha ao carregar ${url}`));
      };
      const timer = setTimeout(fail, LOAD_TIMEOUT_MS);
      el.onload = () => {
        clearTimeout(timer);
        resolve();
      };
      el.onerror = fail;
      document.head.appendChild(el);
    });
    loading.set(url, promise);
    return promise;
  }

  window.loadLeaflet = () =>
    window.L
      ? Promise.resolve()
      : Promise.all([
          load('link', {
            rel: 'stylesheet',
            href: `https://unpkg.com/leaflet@${LEAFLET}/dist/leaflet.css`,
            integrity: 'sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=',
            crossOrigin: '',
          }),
          load('script', {
            src: `https://unpkg.com/leaflet@${LEAFLET}/dist/leaflet.js`,
            integrity: 'sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=',
            crossOrigin: '',
          }),
        ]);

  window.loadSwiper = () =>
    window.Swiper
      ? Promise.resolve()
      : Promise.all([
          load('link', {
            rel: 'stylesheet',
            href: `https://cdn.jsdelivr.net/npm/swiper@${SWIPER}/swiper-bundle.min.css`,
          }),
          load('script', {
            src: `https://cdn.jsdelivr.net/npm/swiper@${SWIPER}/swiper-bundle.min.js`,
          }),
        ]);

  /**
   * Monta um mapa Leaflet quando o contêiner chega perto da tela.
   * Esqueleto enquanto baixa; se a biblioteca não vier, estado de erro com retry
   * (e retry automático quando a internet volta).
   * @param {HTMLElement} container
   * @param {(L: object) => void} mount
   */
  window.lazyMap = function (container, mount) {
    const initial = [...container.childNodes].map(node => node.cloneNode(true));
    let failed = false;

    function showFailure() {
      failed = true;
      const template = document.getElementById('map-error-template');
      container.setAttribute('aria-busy', 'false');
      container.replaceChildren(template.content.cloneNode(true));
      container
        .querySelector('[data-map-retry]')
        .addEventListener('click', () => run(true));
    }

    async function run(isRetry) {
      if (isRetry) {
        container.replaceChildren(...initial.map(node => node.cloneNode(true)));
        container.setAttribute('aria-busy', 'true');
      }
      failed = false;
      try {
        await window.loadLeaflet();
      } catch (error) {
        showFailure();
        return;
      }
      container.replaceChildren();
      container.removeAttribute('aria-busy');
      mount(window.L);
    }

    window.addEventListener('online', () => failed && run(true));

    const observer = new window.IntersectionObserver(
      entries => {
        if (entries.some(entry => entry.isIntersecting)) {
          observer.disconnect();
          run(false);
        }
      },
      { rootMargin: '400px' }
    );
    observer.observe(container);
  };
})();
