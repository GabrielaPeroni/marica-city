// Formulários não-GET: ao enviar, o botão vira "Enviando…" com spinner e um segundo envio é barrado.
// Um só ouvinte no document (depois dos ouvintes dos próprios formulários, então envios
// cancelados por validação ou por AJAX, como o login, passam em branco).
// Rótulo próprio: data-pending-label no botão. Sem proteção: data-no-guard no formulário.
(function () {
  const RESTORE_AFTER_MS = 60000;
  const locked = new Map();

  function submitButtons(form) {
    return [...form.elements].filter(
      el => el.tagName === 'BUTTON' && (el.type === 'submit' || el.type === '')
    );
  }

  function lock(form, submitter) {
    const saved = [];
    submitButtons(form).forEach(button => {
      saved.push({ button, nodes: [...button.childNodes], disabled: button.disabled });
      button.disabled = true;
    });
    if (submitter) {
      const spinner = cloneIcon('loader-circle');
      const hasText = submitter.textContent.trim() !== '';
      const label = submitter.dataset.pendingLabel || gettext('Enviando…');
      submitter.setAttribute('aria-busy', 'true');
      submitter.replaceChildren(
        ...(spinner ? [spinner] : []),
        ...(hasText ? [document.createTextNode(label)] : [])
      );
    }
    form.dataset.submitting = 'true';
    const timer = setTimeout(() => unlock(form), RESTORE_AFTER_MS);
    locked.set(form, { saved, timer });
  }

  function unlock(form) {
    const entry = locked.get(form);
    if (!entry) return;
    clearTimeout(entry.timer);
    entry.saved.forEach(({ button, nodes, disabled }) => {
      button.disabled = disabled;
      button.removeAttribute('aria-busy');
      button.replaceChildren(...nodes);
    });
    delete form.dataset.submitting;
    locked.delete(form);
  }

  // Captura: barra o segundo envio antes dos ouvintes do formulário
  document.addEventListener(
    'submit',
    event => {
      const form = event.target;
      if (form.dataset && form.dataset.submitting) {
        event.preventDefault();
        event.stopImmediatePropagation();
      }
    },
    true
  );

  document.addEventListener('submit', event => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || event.defaultPrevented) return;
    if (form.hasAttribute('data-no-guard') || locked.has(form)) return;
    const method = (
      (event.submitter && event.submitter.getAttribute('formmethod')) ||
      form.method
    ).toLowerCase();
    if (method !== 'post') return;
    const target = (event.submitter && event.submitter.formTarget) || form.target;
    if (target && target !== '_self') return;
    // O navegador monta os dados depois deste evento: desabilitar agora perderia name/value do botão
    const submitter = event.submitter;
    setTimeout(() => lock(form, submitter), 0);
    form.dataset.submitting = 'true';
  });

  // Volta pelo botão "voltar" (cache de páginas): nada pode ficar travado
  window.addEventListener('pageshow', () => {
    document.querySelectorAll('form[data-submitting]').forEach(form => {
      if (locked.has(form)) unlock(form);
      else delete form.dataset.submitting;
    });
  });
})();
