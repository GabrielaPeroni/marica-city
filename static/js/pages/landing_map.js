// Mapa da página inicial (Leaflet + OpenStreetMap) com todos os lugares, montado quando entra na tela
(function () {
  const container = document.getElementById('landing-map');
  if (!container) return;

  const MARICA = [-22.9194, -42.8186];

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  }

  function popupFor(place) {
    const card = el('a', 'block w-60 text-foreground no-underline');
    card.href = place.url;

    if (place.image_url) {
      const img = el('img', 'mb-3 h-32 w-full rounded-lg bg-muted object-cover');
      img.src = place.image_url;
      img.alt = '';
      card.append(img);
    }
    card.append(
      el('h3', 'font-display text-base font-semibold leading-snug', place.name)
    );

    if (place.rating) {
      const rating = el('p', 'mt-1 flex items-center gap-1 text-sm');
      rating.append(
        el('span', 'text-star', '★'),
        el('span', 'font-semibold', place.rating.toFixed(1)),
        el(
          'span',
          'text-muted-foreground',
          interpolate(
            ngettext('(%s avaliação)', '(%s avaliações)', place.review_count),
            [place.review_count]
          )
        )
      );
      card.append(rating);
    }
    if (place.description) {
      card.append(
        el('p', 'mt-2 line-clamp-3 text-sm text-muted-foreground', place.description)
      );
    }
    card.append(
      el(
        'span',
        'mt-3 inline-block text-sm font-semibold text-brand',
        gettext('Ver detalhes')
      )
    );
    return card;
  }

  function mount(L) {
    const map = L.map(container, { scrollWheelZoom: false }).setView(MARICA, 12);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      referrerPolicy: 'strict-origin-when-cross-origin',
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map);

    const brand = window
      .getComputedStyle(document.documentElement)
      .getPropertyValue('--brand')
      .trim();
    const markers = L.layerGroup().addTo(map);

    function showDataError() {
      const template = document.getElementById('map-data-error-template');
      const notice = template.content.firstElementChild.cloneNode(true);
      notice.querySelector('[data-map-data-retry]').addEventListener('click', () => {
        notice.remove();
        loadMarkers();
      });
      container.append(notice);
      // Evita que cliques no aviso movam o mapa
      L.DomEvent.disableClickPropagation(notice);
    }

    async function loadMarkers() {
      container.querySelector('[data-map-data-error]')?.remove();
      try {
        const { data } = await request('/explore/api/map-data/');
        const places = (data.places || []).filter(
          p => Number.isFinite(p.latitude) && Number.isFinite(p.longitude)
        );
        markers.clearLayers();
        const points = places.map(place => {
          const point = [place.latitude, place.longitude];
          L.circleMarker(point, {
            radius: 9,
            color: 'white',
            weight: 3,
            fillColor: brand,
            fillOpacity: 1,
          })
            .addTo(markers)
            .bindTooltip(place.name, { direction: 'top', offset: [0, -8] })
            .bindPopup(popupFor(place), { maxWidth: 260 });
          return point;
        });
        if (points.length > 1) map.fitBounds(points, { padding: [32, 32] });
        else if (points.length === 1) map.setView(points[0], 15);
      } catch (error) {
        console.warn('Dados do mapa indisponíveis:', error.kind || error);
        showDataError();
      }
    }

    window.addEventListener('online', () => {
      if (container.querySelector('[data-map-data-error]')) loadMarkers();
    });
    loadMarkers();
  }

  window.lazyMap(container, mount);
})();
