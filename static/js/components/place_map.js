// Mapa do detalhe do lugar (Leaflet + OpenStreetMap), montado quando entra na tela
(function () {
  const container = document.getElementById('place-map');
  if (!container) return;

  const position = [
    parseFloat(container.dataset.latitude),
    parseFloat(container.dataset.longitude),
  ];
  if (position.some(isNaN)) {
    container.hidden = true;
    return;
  }

  function mount(L) {
    const map = L.map(container, { scrollWheelZoom: false }).setView(position, 15);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      // O site manda Referrer-Policy same-origin; os tiles do OSM exigem a origem
      referrerPolicy: 'strict-origin-when-cross-origin',
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map);
    const brand = window
      .getComputedStyle(document.documentElement)
      .getPropertyValue('--brand')
      .trim();
    L.circleMarker(position, {
      radius: 10,
      color: 'white',
      weight: 3,
      fillColor: brand,
      fillOpacity: 1,
    })
      .addTo(map)
      .bindTooltip(container.dataset.placeName, {
        direction: 'top',
        offset: [0, -10],
      });
  }

  window.lazyMap(container, mount);
})();
