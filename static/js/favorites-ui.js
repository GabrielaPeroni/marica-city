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
  if (isLoggedIn) {
    favoritesService.loadFromBackend().then(() => {
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

/**
 * Gerenciar clique no botão de favorito
 * @param {Event} e - Evento de clique
 */
async function handleFavoriteClick(e) {
  e.preventDefault();
  e.stopPropagation();

  const button = e.currentTarget;
  const placeId = button.dataset.placeId;

  if (!placeId) {
    console.error('ID do local não encontrado');
    return;
  }

  // Sem `disabled`: ele esmaecia o botão e tirava o hover/foco a cada clique
  if (button.dataset.busy) return;
  button.dataset.busy = 'true';

  try {
    // Alternar no localStorage
    const isNowFavorited = favoritesService.toggleFavorite(placeId);

    // Atualizar UI
    updateFavoriteButton(button, isNowFavorited);
    updateFavoritesCount(placeId, isNowFavorited ? 1 : -1);
    updateNavbarFavoritesCount();

    // Mostrar animação de feedback
    button.removeAttribute('data-pop');
    void button.offsetWidth;
    button.setAttribute('data-pop', '');

    // Se logado, também sincronizar com backend (opcional - dispara e esquece)
    const isLoggedIn = document.body.dataset.userAuthenticated === 'true';
    if (isLoggedIn) {
      const csrfToken = getCookie('csrftoken');

      // Opcional: chamar endpoint do backend para salvar favorito
      try {
        await fetch(`/explore/place/${placeId}/favorite/toggle/`, {
          method: 'POST',
          headers: {
            'X-CSRFToken': csrfToken,
            'Content-Type': 'application/json',
          },
        });
      } catch (error) {
        // Sincronização com backend falhou mas o armazenamento local ainda funciona
        console.warn('Sincronização com backend falhou:', error);
      }
    }
  } catch (error) {
    console.error('Erro ao alternar favorito:', error);
    alert(gettext('Erro ao atualizar favorito. Tente novamente.'));
  } finally {
    delete button.dataset.busy;
  }
}

/**
 * Gerenciar remoção de favorito da página de favoritos
 * @param {Event} e - Evento de clique
 */
async function handleRemoveFavorite(e) {
  e.preventDefault();
  e.stopPropagation();

  const button = e.currentTarget;
  const placeId = button.dataset.placeId;

  if (!placeId) return;

  // Remover do localStorage
  favoritesService.removeFavorite(placeId);

  // Remover cartão com animação
  const card = button.closest('[data-favorite-item]');
  if (card) {
    card.classList.add('transition', 'duration-300', 'opacity-0', 'scale-95');

    setTimeout(() => {
      card.remove();

      // Verificar se não há mais favoritos
      const remainingCards = document.querySelectorAll('.favorite-btn').length;
      if (remainingCards === 0) {
        location.reload(); // Recarregar para mostrar estado vazio
      }
    }, 300);
  }

  // Atualizar contagem da navbar
  updateNavbarFavoritesCount();

  // Sincronizar com backend se logado
  const isLoggedIn = document.body.dataset.userAuthenticated === 'true';
  if (isLoggedIn) {
    const csrfToken = getCookie('csrftoken');
    try {
      await fetch(`/explore/place/${placeId}/favorite/toggle/`, {
        method: 'POST',
        headers: {
          'X-CSRFToken': csrfToken,
          'Content-Type': 'application/json',
        },
      });
    } catch (error) {
      console.warn('Sincronização com backend falhou:', error);
    }
  }
}

// Inicializar quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', function () {
  // Inicializar UI
  initializeFavoritesUI();

  // Adicionar manipuladores de clique a todos os botões de favorito
  const favoriteButtons = document.querySelectorAll(
    '.favorite-btn:not([data-remove-mode])'
  );
  favoriteButtons.forEach(button => {
    button.addEventListener('click', handleFavoriteClick);
  });

  // Adicionar manipuladores de clique para botões de remover na página de favoritos
  const removeButtons = document.querySelectorAll('.favorite-btn[data-remove-mode]');
  removeButtons.forEach(button => {
    button.addEventListener('click', handleRemoveFavorite);
  });

  // Ouvir mudanças de armazenamento de outras abas
  window.addEventListener('storage', function (e) {
    if (e.key === 'marica_favorites') {
      initializeFavoritesUI();
    }
  });
});
