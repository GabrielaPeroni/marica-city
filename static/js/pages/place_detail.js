// Detalhe do lugar: diálogo de avaliação (criar/editar), exclusão de avaliação e lightbox da galeria.
// Os botões são links para as páginas de avaliação; com JS o dialogs.js abre o <dialog> no lugar.
(function () {
  const reviewForm = document.getElementById('reviewForm');
  const deleteReviewForm = document.getElementById('deleteReviewForm');

  function setReviewMode(trigger) {
    const editUrl = trigger.dataset.reviewEdit;
    const title = document.getElementById('review-dialog-title');
    const submitText = document.getElementById('submitButtonText');
    reviewForm.reset();
    reviewForm.action = editUrl || reviewForm.dataset.createUrl;
    if (title)
      title.textContent = editUrl
        ? gettext('Editar avaliação')
        : gettext('Escrever avaliação');
    if (submitText) {
      submitText.textContent = editUrl
        ? gettext('Atualizar avaliação')
        : gettext('Enviar avaliação');
    }
    if (editUrl) {
      const star = reviewForm.querySelector(
        `input[name="rating"][value="${trigger.dataset.rating}"]`
      );
      if (star) star.checked = true;
      reviewForm.querySelector('[name="comment"]').value =
        trigger.dataset.comment || '';
    }
  }

  document.addEventListener('click', event => {
    const reviewTrigger = event.target.closest('[data-review-edit], [data-review-new]');
    if (reviewTrigger && reviewForm) {
      setReviewMode(reviewTrigger);
      return;
    }
    const deleteTrigger = event.target.closest('[data-review-delete]');
    if (deleteTrigger && deleteReviewForm) {
      deleteReviewForm.action = deleteTrigger.dataset.reviewDelete;
    }
  });

  const lightbox = document.getElementById('gallery-lightbox');
  if (!lightbox) return;
  const items = [...lightbox.querySelectorAll('[data-lightbox-item]')];
  let current = 0;

  function show(index) {
    current = (index + items.length) % items.length;
    items.forEach((item, i) => (item.hidden = i !== current));
  }

  document.addEventListener('click', event => {
    const opener = event.target.closest('[data-lightbox-open]');
    if (opener) {
      show(Number(opener.dataset.lightboxOpen));
      lightbox.showModal();
      return;
    }
    const step = event.target.closest('[data-lightbox-step]');
    if (step) show(current + Number(step.dataset.lightboxStep));
  });

  lightbox.addEventListener('keydown', event => {
    if (event.key === 'ArrowLeft') show(current - 1);
    if (event.key === 'ArrowRight') show(current + 1);
  });

  // Clicar no fundo escuro (fora da foto e dos botões) fecha
  lightbox.addEventListener('click', event => {
    if (event.target.matches('figure')) lightbox.close();
  });
})();
