// Aviso de conexão (offline, voltou, página lenta) anunciado em #connection-live.
// window.showConnectionNotice(text, state) / hideConnectionNotice(state) servem a outros scripts.
(function () {
  const banner = document.getElementById('connection-banner');
  const live = document.getElementById('connection-live');
  if (!banner || !live) return;
  const iconSlot = banner.querySelector('[data-connection-icon]');
  const textSlot = banner.querySelector('[data-connection-text]');
  const ICONS = {
    offline: 'wifi-off',
    slow: 'loader-circle',
    online: 'check',
  };
  let state = '';
  let hideTimer = null;

  function show(text, next) {
    clearTimeout(hideTimer);
    state = next;
    const icon = cloneIcon(ICONS[next]);
    iconSlot.replaceChildren(...(icon ? [icon] : []));
    textSlot.textContent = text;
    banner.hidden = false;
    // Anuncia mesmo que o texto seja igual ao anterior
    live.textContent = '';
    window.setTimeout(() => (live.textContent = text), 50);
  }

  function hide(only) {
    if (only && state !== only) return;
    clearTimeout(hideTimer);
    state = '';
    banner.hidden = true;
    live.textContent = '';
  }

  window.showConnectionNotice = (text, next = 'slow') => {
    if (state === 'offline' && next !== 'offline') return;
    show(text, next);
  };
  window.hideConnectionNotice = hide;

  function goOffline() {
    show(
      gettext('Você está sem conexão. Algumas ações só funcionam com internet.'),
      'offline'
    );
  }

  function goOnline() {
    if (state !== 'offline') return;
    show(gettext('Conexão restabelecida.'), 'online');
    hideTimer = window.setTimeout(() => hide('online'), 3000);
  }

  window.addEventListener('offline', goOffline);
  window.addEventListener('online', goOnline);
  if (navigator.onLine === false) goOffline();

  // Voltou do cache de páginas (botão voltar): o estado de rede pode ter mudado
  window.addEventListener('pageshow', event => {
    if (!event.persisted) return;
    if (navigator.onLine === false) goOffline();
    else if (state === 'slow') hide('slow');
    else goOnline();
  });
})();
