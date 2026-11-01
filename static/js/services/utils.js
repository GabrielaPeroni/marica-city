/**
 * MaricaCity - Utilitários Compartilhados
 * Funções comuns usadas em toda a aplicação
 */

/**
 * Obter token CSRF do cookie
 * @param {string} name - Nome do cookie
 * @returns {string|null} Valor do cookie
 */
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === name + '=') {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

/**
 * Cópia de um ícone Lucide de <template id="js-icons"> (includes/js_icons.html)
 * @param {string} name - Nome do ícone, ex. "check"
 * @returns {SVGElement|null}
 */
function cloneIcon(name) {
  const template = document.getElementById('js-icons');
  const svg = template && template.content.querySelector(`[data-icon="${name}"]`);
  return svg ? svg.cloneNode(true) : null;
}

const SLOW_AFTER_MS = 4000;
const SLOW_NOTICE_GAP_MS = 60000;
let lastSlowNotice = 0;

/** Falha de request já classificada; `userMessage` diz o que houve e o que fazer */
class RequestError extends Error {
  constructor(kind, userMessage, { status = 0, data = null, retryAfter = 0 } = {}) {
    super(userMessage);
    this.name = 'RequestError';
    this.kind = kind;
    this.userMessage = userMessage;
    this.status = status;
    this.data = data;
    this.retryAfter = retryAfter;
  }
}

function failureFor(status, retryAfter) {
  if (status === 429) {
    const waitText = gettext(
      'Muitas tentativas em pouco tempo. Aguarde %s s e tente de novo.'
    );
    const genericText = gettext(
      'Muitas tentativas em pouco tempo. Aguarde um momento e tente de novo.'
    );
    return [
      'ratelimit',
      retryAfter ? interpolate(waitText, [retryAfter]) : genericText,
    ];
  }
  if (status === 403) {
    return [
      'forbidden',
      gettext('Sua sessão expirou. Recarregue a página e tente de novo.'),
    ];
  }
  if (status >= 500) {
    return [
      'server',
      gettext(
        'O servidor está com problemas agora. Tente novamente em alguns minutos.'
      ),
    ];
  }
  return ['http', gettext('Não foi possível concluir a ação. Tente novamente.')];
}

/**
 * fetch com tempo limite e falhas classificadas. Nunca repete sozinho:
 * quem chama decide (POST não é idempotente).
 * @param {string} url
 * @param {{method?: string, headers?: object, body?: any, json?: any, timeout?: number,
 *   keepalive?: boolean, as?: 'json'|'text'}} [options]
 * @returns {Promise<{status: number, data: any}>} rejeita com RequestError
 */
async function request(url, options = {}) {
  const { timeout = 10000, as = 'json', json, headers = {}, ...init } = options;
  const method = (init.method || 'GET').toUpperCase();
  const finalHeaders = { 'X-Requested-With': 'XMLHttpRequest', ...headers };
  if (as === 'json') finalHeaders.Accept = 'application/json';
  if (method !== 'GET' && !finalHeaders['X-CSRFToken']) {
    finalHeaders['X-CSRFToken'] = getCookie('csrftoken') || '';
  }
  if (json !== undefined) {
    finalHeaders['Content-Type'] = 'application/json';
    init.body = JSON.stringify(json);
  }

  const controller = new AbortController();
  let timedOut = false;
  const killTimer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeout);
  const slowTimer = setTimeout(() => {
    const now = Date.now();
    if (now - lastSlowNotice < SLOW_NOTICE_GAP_MS) return;
    lastSlowNotice = now;
    if (window.showToast) {
      window.showToast(
        gettext('A conexão está lenta. Ainda estamos tentando, aguarde um pouco.'),
        'info'
      );
    }
  }, SLOW_AFTER_MS);

  try {
    let response;
    try {
      response = await fetch(url, {
        ...init,
        method,
        headers: finalHeaders,
        signal: controller.signal,
      });
    } catch (error) {
      if (timedOut) {
        throw new RequestError(
          'timeout',
          gettext('O servidor demorou demais para responder. Tente novamente.')
        );
      }
      if (navigator.onLine === false) {
        throw new RequestError(
          'offline',
          gettext('Você está sem conexão. Verifique a internet e tente de novo.')
        );
      }
      throw new RequestError(
        'network',
        gettext(
          'Não foi possível falar com o servidor. Verifique sua conexão e tente de novo.'
        )
      );
    }

    let data = null;
    try {
      data = as === 'text' ? await response.text() : await response.json();
    } catch (error) {
      if (timedOut) {
        throw new RequestError(
          'timeout',
          gettext('O servidor demorou demais para responder. Tente novamente.')
        );
      }
    }
    if (!response.ok) {
      const retryAfter = parseInt(response.headers.get('Retry-After'), 10) || 0;
      const [kind, message] = failureFor(response.status, retryAfter);
      throw new RequestError(kind, message, {
        status: response.status,
        data,
        retryAfter,
      });
    }
    return { status: response.status, data };
  } finally {
    clearTimeout(killTimer);
    clearTimeout(slowTimer);
  }
}

// Exportar para uso em outros scripts
if (typeof window !== 'undefined') {
  window.getCookie = getCookie;
  window.cloneIcon = cloneIcon;
  window.request = request;
  window.RequestError = RequestError;
}
