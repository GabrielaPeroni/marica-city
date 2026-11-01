// Navbar: compacta ao rolar (data-scrolled), some ao descer e volta ao subir
// (data-hidden), e uma pílula desliza até o link sob o cursor.
(function () {
  const nav = document.querySelector('[data-site-nav]');
  if (!nav) return;

  let lastY = window.scrollY;
  let ticking = false;
  const update = () => {
    const y = window.scrollY;
    nav.toggleAttribute('data-scrolled', y > 8);
    const menuOpen = nav.querySelector('[aria-expanded="true"]');
    nav.toggleAttribute('data-hidden', y > 240 && y > lastY + 4 && !menuOpen);
    if (y < lastY - 4 || y <= 240) nav.removeAttribute('data-hidden');
    lastY = y;
    ticking = false;
  };
  update();
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
  nav.addEventListener('focusin', () => nav.removeAttribute('data-hidden'));

  const list = nav.querySelector('[data-nav-links]');
  const indicator = list && list.querySelector('.site-nav-indicator');
  if (!indicator) return;
  const current = list.querySelector('[aria-current="page"]');
  const moveTo = link => {
    if (!link) {
      indicator.removeAttribute('data-ready');
      return;
    }
    indicator.style.setProperty('--indicator-x', `${link.offsetLeft}px`);
    indicator.style.setProperty('--indicator-w', `${link.offsetWidth}px`);
    indicator.setAttribute('data-ready', '');
  };
  moveTo(current);
  list.querySelectorAll('.site-nav-link').forEach(link => {
    link.addEventListener('pointerenter', () => moveTo(link));
    link.addEventListener('focus', () => moveTo(link));
  });
  list.addEventListener('pointerleave', () => moveTo(current));
  list.addEventListener('focusout', () => moveTo(current));
  window.addEventListener('resize', () => moveTo(current));
  document.fonts && document.fonts.ready.then(() => moveTo(current));
})();
