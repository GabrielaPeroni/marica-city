// Foto que não carrega (offline, 404, bloqueio): fundo neutro com ícone em vez do ícone quebrado.
// Quando a internet volta, tenta de novo as que falharam.
(function () {
  const failed = new Set();

  function fallback(img) {
    if (img.dataset.failed || img.closest('.leaflet-container') || !img.parentElement)
      return;
    img.dataset.failed = 'true';
    const box = document.createElement('div');
    box.className = `img-fallback ${img.className}`;
    box.setAttribute('role', 'img');
    box.setAttribute('aria-label', img.alt || gettext('Foto indisponível'));
    const icon = cloneIcon('image-off');
    if (icon) box.append(icon);
    img.hidden = true;
    img.after(box);
    img.fallbackBox = box;
    failed.add(img);
  }

  function retry(img) {
    if (img.fallbackBox) img.fallbackBox.remove();
    img.fallbackBox = null;
    delete img.dataset.failed;
    img.hidden = false;
    const src = img.getAttribute('src');
    img.removeAttribute('src');
    img.setAttribute('src', src);
  }

  // `error` não borbulha: captura no document
  document.addEventListener(
    'error',
    event => {
      if (event.target instanceof HTMLImageElement) fallback(event.target);
    },
    true
  );

  // Fotos que já falharam antes deste script rodar
  document.querySelectorAll('img[src]').forEach(img => {
    if (img.complete && img.naturalWidth === 0) fallback(img);
  });

  window.addEventListener('online', () => {
    [...failed].forEach(img => {
      failed.delete(img);
      if (img.isConnected) retry(img);
    });
  });
})();
