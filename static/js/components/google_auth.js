function handleCredentialResponse(response) {
  request('/accounts/google/', { method: 'POST', json: { token: response.credential } })
    .then(data => {
      // Armazenar flag para mostrar toast de sucesso após redirect
      sessionStorage.setItem('loginSuccess', 'true');
      sessionStorage.setItem('loginUsername', data.username);
      window.location.href = '/';
    })
    .catch(error => {
      console.error('Autenticação do Google falhou:', error.kind || error);
      showToast(
        (error.data && error.data.error) ||
          error.userMessage ||
          gettext('Falha ao autenticar com Google. Por favor, tente novamente.'),
        'error'
      );
    });
}

// O SDK do Google (~100 KB + iframe) só é baixado quando o menu "Entrar" é aberto
let googleInitialized = false;
let googleSdkPromise = null;

function loadGoogleSDK() {
  if (!window.GOOGLE_CLIENT_ID) return Promise.resolve(false);
  if (!googleSdkPromise) {
    googleSdkPromise = new Promise(resolve => {
      const script = document.createElement('script');
      script.src = 'https://accounts.google.com/gsi/client';
      script.async = true;
      script.onload = () => resolve(true);
      script.onerror = () => resolve(false);
      document.head.appendChild(script);
    });
  }
  return googleSdkPromise;
}

function initializeGoogleSDK() {
  if (googleInitialized || typeof google === 'undefined' || !google.accounts) return;
  try {
    google.accounts.id.initialize({
      client_id: window.GOOGLE_CLIENT_ID,
      callback: handleCredentialResponse,
    });
    googleInitialized = true;
  } catch (error) {
    console.error('Erro ao inicializar SDK do Google Sign-In:', error);
  }
}

function renderGoogleButton() {
  const googleButton = document.getElementById('google-signin-button');
  if (!googleInitialized || !googleButton || googleButton.hasChildNodes()) return;
  try {
    google.accounts.id.renderButton(googleButton, {
      type: 'standard',
      theme: 'outline',
      size: 'large',
      text: 'signin_with',
      shape: 'rectangular',
      logo_alignment: 'left',
      width: 280,
    });
  } catch (error) {
    console.error('Erro ao renderizar botão do Google Sign-In:', error);
  }
}

function showGoogleButton() {
  loadGoogleSDK().then(loaded => {
    if (!loaded) return;
    initializeGoogleSDK();
    renderGoogleButton();
  });
}

document.addEventListener('DOMContentLoaded', () => {
  const button = document.getElementById('google-signin-button');
  const popover = button && button.closest('.popover');
  if (!popover) return;
  const toggle = popover.querySelector(':scope > button');
  // Começa a baixar ao passar o mouse, para o botão já estar pronto ao abrir
  toggle?.addEventListener('pointerenter', loadGoogleSDK, { once: true });
  toggle?.addEventListener('click', showGoogleButton);
});
