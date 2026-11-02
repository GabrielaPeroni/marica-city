/**
 * MaricaCity - Serviço de Favoritos
 * Gerencia favoritos usando localStorage para todos os usuários
 * Sincronização opcional com backend para usuários logados
 */

// Trocas feitas aqui já vão ao servidor; só outro aparelho muda a lista por fora
const SYNCED_AT_KEY = 'marica_favorites_synced_at';
const SYNC_TTL_MS = 5 * 60 * 1000;

class FavoritesService {
  constructor() {
    this.storageKey = 'marica_favorites';
    this.listeners = [];
  }

  /**
   * Obter todos os favoritos do localStorage
   * @returns {number[]} Array de IDs de locais
   */
  getFavorites() {
    try {
      const stored = localStorage.getItem(this.storageKey);
      return stored ? JSON.parse(stored) : [];
    } catch (error) {
      console.error('Erro ao ler favoritos do localStorage:', error);
      return [];
    }
  }

  /**
   * Salvar favoritos no localStorage
   * @param {number[]} favorites - Array de IDs de locais
   */
  saveFavorites(favorites) {
    try {
      localStorage.setItem(this.storageKey, JSON.stringify(favorites));
      this.notifyListeners();
    } catch (error) {
      console.error('Erro ao salvar favoritos no localStorage:', error);
    }
  }

  /**
   * Verificar se um local está favoritado
   * @param {number} placeId - ID do local para verificar
   * @returns {boolean}
   */
  isFavorited(placeId) {
    const favorites = this.getFavorites();
    return favorites.includes(parseInt(placeId));
  }

  /**
   * Adicionar um local aos favoritos
   * @param {number} placeId - ID do local para adicionar
   * @returns {boolean} Status de sucesso
   */
  addFavorite(placeId) {
    const favorites = this.getFavorites();
    const id = parseInt(placeId);

    if (!favorites.includes(id)) {
      favorites.push(id);
      this.saveFavorites(favorites);
      return true;
    }
    return false;
  }

  /**
   * Remover um local dos favoritos
   * @param {number} placeId - ID do local para remover
   * @returns {boolean} Status de sucesso
   */
  removeFavorite(placeId) {
    const favorites = this.getFavorites();
    const id = parseInt(placeId);
    const index = favorites.indexOf(id);

    if (index > -1) {
      favorites.splice(index, 1);
      this.saveFavorites(favorites);
      return true;
    }
    return false;
  }

  /**
   * Alternar status de favorito
   * @param {number} placeId - ID do local para alternar
   * @returns {boolean} Novo status de favoritado
   */
  toggleFavorite(placeId) {
    if (this.isFavorited(placeId)) {
      this.removeFavorite(placeId);
      return false;
    } else {
      this.addFavorite(placeId);
      return true;
    }
  }

  /**
   * Obter contagem de favoritos
   * @returns {number}
   */
  getCount() {
    return this.getFavorites().length;
  }

  /**
   * Limpar todos os favoritos
   */
  clearAll() {
    this.saveFavorites([]);
  }

  /**
   * Registrar um ouvinte para mudanças nos favoritos
   * @param {Function} callback - Função de callback
   */
  addListener(callback) {
    this.listeners.push(callback);
  }

  /**
   * Notificar todos os ouvintes sobre mudanças
   */
  notifyListeners() {
    const favorites = this.getFavorites();
    this.listeners.forEach(callback => callback(favorites));
  }

  /**
   * Sincronizar favoritos com backend (para usuários logados)
   * @returns {Promise<void>}
   */
  async syncWithBackend() {
    try {
      const { data } = await request('/explore/favorites/sync/', {
        method: 'POST',
        json: { favorites: this.getFavorites() },
      });
      if (data && data.favorites) this.saveFavorites(data.favorites);
    } catch (error) {
      console.warn('Sincronização de favoritos falhou:', error.kind || error);
    }
  }

  syncedRecently() {
    try {
      const at = Number(window.sessionStorage.getItem(SYNCED_AT_KEY));
      return Boolean(at) && Date.now() - at < SYNC_TTL_MS;
    } catch {
      return false;
    }
  }

  markSynced() {
    try {
      window.sessionStorage.setItem(SYNCED_AT_KEY, String(Date.now()));
    } catch {
      // Sem sessionStorage, só busca de novo na próxima página
    }
  }

  forgetSync() {
    try {
      window.sessionStorage.removeItem(SYNCED_AT_KEY);
    } catch {
      // Nada a limpar
    }
  }

  /**
   * Carregar favoritos do backend (para usuários logados no carregamento da página)
   * @returns {Promise<number[]>}
   */
  async loadFromBackend() {
    if (this.syncedRecently()) return this.getFavorites();
    try {
      const { data } = await request('/explore/favorites/list/', { timeout: 8000 });
      if (data && data.favorites) {
        this.markSynced();
        const merged = [...new Set([...this.getFavorites(), ...data.favorites])];
        this.saveFavorites(merged);
        return merged;
      }
    } catch (error) {
      console.warn('Carregar favoritos falhou:', error.kind || error);
    }
    return this.getFavorites();
  }
}

// Criar instância singleton
const favoritesService = new FavoritesService();

// Exportar para uso em outros scripts
if (typeof module !== 'undefined' && module.exports) {
  module.exports = favoritesService;
}
