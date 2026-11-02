/**
 * MaricaCity - Gerenciador de UI de Favoritos
 * Gerencia interações de UI para favoritos usando o FavoritesService
 */

/**
 * Atualizar UI do botão de favorito
 * @param {HTMLElement} button - Elemento do botão de favorito
 * @param {boolean} isFavorited - Status atual de favoritado
 */
function updateFavoriteButton(button, isFavorited) {
  const label = isFavorited
    ? gettext('Remover dos favoritos')
    : gettext('Adicionar aos favoritos');
  button.setAttribute('aria-pressed', isFavorited ? 'true' : 'false');
  button.setAttribute('title', label);
  button.setAttribute('aria-label', label);
}

/**
 * Atualizar exibição da contagem de favoritos
 * @param {number} placeId - ID do local
 * @param {number} delta - Mudança na contagem (+1 ou -1)
 */
function updateFavoritesCount(placeId, delta) {
  const countElements = document.querySelectorAll(
    `[data-favorites-count-for="${placeId}"]`
  );

  countElements.forEach(element => {
    const currentCount = parseInt(element.textContent) || 0;
    const newCount = Math.max(0, currentCount + delta);
    element.textContent = newCount;
  });
}

/**
 * Inicializar UI de favoritos ao carregar a página
 */
function initializeFavoritesUI() {
  // Atualizar todos os botões de favorito com base no localStorage
  const buttons = document.querySelectorAll('.favorite-btn');

  buttons.forEach(button => {
    const placeId = button.dataset.placeId;
    if (placeId) {
      const isFavorited = favoritesService.isFavorited(placeId);
      updateFavoriteButton(button, isFavorited);
    }
  });

  // Atualizar contagem de favoritos na navbar/header se existir
  updateNavbarFavoritesCount();

  // Se o usuário estiver logado, sincronizar com backend
  const isLoggedIn = document.body.dataset.userAuthenticated === 'true';
  if (!isLoggedIn) favoritesService.forgetSync();
  if (isLoggedIn) {
    whenActive()
      .then(() => favoritesService.loadFromBackend())
      .then(() => {
        // Atualizar UI após carregar do backend
        buttons.forEach(button => {
          const placeId = button.dataset.placeId;
          if (placeId) {
            const isFavorited = favoritesService.isFavorited(placeId);
            updateFavoriteButton(button, isFavorited);
          }
        });
        updateNavbarFavoritesCount();
      });
  }
}

/**
 * Atualizar contagem de favoritos na navbar
 */
function updateNavbarFavoritesCount() {
  const navbarCount = document.querySelector('.favorites-count');
  if (navbarCount) {
    const count = favoritesService.getCount();
    navbarCount.textContent = count;

    navbarCount.hidden = count === 0;
  }
}

const SYNC_DELAY_MS = 300;
const SYNC_MAX_ROUNDS = 4;
// placeId -> { server: último estado confirmado, timer, running }
const syncState = new Map();

function isLoggedIn() {
  return document.body.dataset.userAuthenticated === 'true';
}

/** Aplica o estado a todos os corações do mesmo lugar, contagens e navbar */
function applyFavorite(placeId, wanted) {
  const was = favoritesService.isFavorited(placeId);
  if (wanted && !was) favoritesService.addFavorite(placeId);
  if (!wanted && was) favoritesService.removeFavorite(placeId);
  document.querySelectorAll('.favorite-btn').forEach(button => {
    if (button.dataset.placeId === String(placeId)) {
      updateFavoriteButton(button, wanted);
    }
  });
  if (was !== wanted) updateFavoritesCount(placeId, wanted ? 1 : -1);
  updateNavbarFavoritesCount();
}

function popButton(button) {
  button.removeAttribute('data-pop');
  void button.offsetWidth;
  button.setAttribute('data-pop', '');
}

/**
 * Envia o estado final desejado ao servidor. Cliques rápidos viram um pedido só:
 * o estado local é a verdade, o servidor é reconciliado com `is_favorited`.
 * @returns {Promise<boolean>} true se o servidor ficou igual ao local
 */
function scheduleSync(placeId, { immediate = false } = {}) {
  if (!isLoggedIn()) return Promise.resolve(true);
  let state = syncState.get(placeId);
  if (!state) {
    // Primeiro clique: o servidor ainda está como o cliente estava antes dele
    state = {
      server: !favoritesService.isFavorited(placeId),
      timer: null,
      waiters: [],
    };
    syncState.set(placeId, state);
  }
  return new Promise(resolve => {
    state.waiters.push(resolve);
    if (state.running) return;
    clearTimeout(state.timer);
    state.timer = setTimeout(() => runSync(placeId), immediate ? 0 : SYNC_DELAY_MS);
  });
}

async function runSync(placeId) {
  const state = syncState.get(placeId);
  state.running = true;
  state.timer = null;
  let failure = null;
  for (let round = 0; round < SYNC_MAX_ROUNDS; round++) {
    if (favoritesService.isFavorited(placeId) === state.server) break;
    try {
      const { data } = await request(`/explore/place/${placeId}/favorite/toggle/`, {
        method: 'POST',
        timeout: 8000,
        keepalive: true,
      });
      if (typeof data.is_favorited === 'boolean') state.server = data.is_favorited;
      else state.server = !state.server;
    } catch (error) {
      failure = error;
      break;
    }
  }
  state.running = false;
  const ok = !failure && favoritesService.isFavorited(placeId) === state.server;
  if (!ok) {
    applyFavorite(placeId, state.server);
    const reason = failure ? failure.userMessage : '';
    const text = gettext('Não foi possível atualizar o favorito. %s');
    showToast(interpolate(text, [reason]).trim(), 'error');
  }
  const waiters = state.waiters.splice(0);
  waiters.forEach(resolve => resolve(ok));
}

/** Cliques em corações: troca na hora, servidor em segundo plano */
function handleFavoriteClick(e) {
  const button = e.target.closest('.favorite-btn');
  if (!button) return;
  e.preventDefault();
  e.stopPropagation();

  const placeId = button.dataset.placeId;
  if (!placeId) return;

  if (button.hasAttribute('data-remove-mode')) {
    removeFromFavoritesPage(button, placeId);
    return;
  }
  applyFavorite(placeId, !favoritesService.isFavorited(placeId));
  popButton(button);
  scheduleSync(placeId);
}

async function removeFromFavoritesPage(button, placeId) {
  const card = button.closest('[data-favorite-item]');
  if (card && card.hidden) return;
  applyFavorite(placeId, false);
  if (card) {
    card.classList.add('transition', 'duration-300', 'opacity-0', 'scale-95');
    setTimeout(() => {
      if (!favoritesService.isFavorited(placeId)) card.hidden = true;
    }, 300);
  }
  const ok = await scheduleSync(placeId, { immediate: true });
  if (!ok && card) {
    card.hidden = false;
    card.classList.remove('transition', 'duration-300', 'opacity-0', 'scale-95');
  }
  const remaining = [...document.querySelectorAll('[data-favorite-item]')].filter(
    item => !item.hidden
  );
  if (remaining.length === 0) location.reload();
}

// Fecha o que ficou pendente antes de a aba sumir
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState !== 'hidden') return;
  syncState.forEach((state, placeId) => {
    if (state.timer && !state.running) {
      clearTimeout(state.timer);
      runSync(placeId);
    }
  });
});

// Um só ouvinte: vale para cartões de qualquer lugar, inclusive os inseridos depois
document.addEventListener('click', handleFavoriteClick);

document.addEventListener('DOMContentLoaded', function () {
  initializeFavoritesUI();
  window.addEventListener('storage', function (e) {
    if (e.key === 'marica_favorites') initializeFavoritesUI();
  });
  window.addEventListener('pageshow', e => {
    if (e.persisted) initializeFavoritesUI();
  });
});
