/**
 * MaricaCity - Login no popover da navbar
 * Envia o formulário por AJAX e mostra o erro dentro do próprio popover
 */

document.addEventListener('DOMContentLoaded', function () {
  const loginForms = document.querySelectorAll('form[action*="accounts/login"]');

  loginForms.forEach(form => {
    form.addEventListener('submit', async function (e) {
      e.preventDefault();
      if (form.dataset.loginBusy) return;

      const submitButton = form.querySelector('button[type="submit"]');
      const originalNodes = [...submitButton.childNodes];

      const restore = () => {
        delete form.dataset.loginBusy;
        submitButton.disabled = false;
        submitButton.replaceChildren(...originalNodes);
      };

      form.dataset.loginBusy = 'true';
      submitButton.disabled = true;
      submitButton.replaceChildren(
        cloneIcon('loader-circle') || '',
        document.createTextNode(gettext('Entrando...'))
      );
      form.querySelector('[data-login-error]')?.remove();

      try {
        const { data } = await request(form.action, {
          method: 'POST',
          body: new FormData(form),
        });

        if (data.success) {
          submitButton.replaceChildren(
            cloneIcon('check') || '',
            document.createTextNode(gettext('Sucesso!'))
          );
          sessionStorage.setItem('loginSuccess', 'true');
          sessionStorage.setItem('loginUsername', data.username || gettext('usuário'));
          setTimeout(() => location.reload(), 500);
        } else {
          showErrorInForm(form, data.error || gettext('Erro ao fazer login.'));
          restore();
        }
      } catch (error) {
        // Senha errada volta como JSON com erro; o resto é falha de rede/servidor
        const message =
          (error.data && error.data.error) ||
          error.userMessage ||
          gettext('Erro ao conectar com o servidor. Tente novamente.');
        showErrorInForm(form, message);
        restore();
      }
    });

    // Voltou pelo cache de páginas no meio do envio
    window.addEventListener('pageshow', e => {
      if (!e.persisted || !form.dataset.loginBusy) return;
      delete form.dataset.loginBusy;
      const button = form.querySelector('button[type="submit"]');
      button.disabled = false;
      button.textContent = gettext('Entrar');
    });
  });
});

/**
 * Exibir mensagem de erro dentro do formulário
 * @param {HTMLFormElement} form - O elemento do formulário
 * @param {string} message - Mensagem de erro para exibir
 */
function showErrorInForm(form, message) {
  form.querySelector('[data-login-error]')?.remove();

  const alert = document.createElement('div');
  alert.className = 'alert';
  alert.dataset.variant = 'destructive';
  alert.dataset.loginError = '';
  alert.setAttribute('role', 'alert');
  const text = document.createElement('section');
  text.textContent = message;
  alert.append(cloneIcon('circle-alert') || '', text);
  form.prepend(alert);

  form.classList.remove('animate-shake');
  void form.offsetWidth;
  form.classList.add('animate-shake');
}
