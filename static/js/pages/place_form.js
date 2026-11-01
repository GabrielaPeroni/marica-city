// Formulário de lugar: galeria em cards sobre o formset (prévia, foto principal, remover).
// A ordem dos cards vira display_order; o primeiro card é a foto principal.
document.addEventListener('DOMContentLoaded', function () {
  const grid = document.getElementById('image-preview-grid');
  const addButton = document.getElementById('add-image-btn');
  const template = document.getElementById('image-card-template');
  const forms = [...document.querySelectorAll('#formset-container .formset-form')];
  const MAX_IMAGES = 3;

  const cards = () => [...grid.querySelectorAll('[data-image-card]')];
  const field = (formDiv, name) => formDiv.querySelector(`input[name$="-${name}"]`);

  function refresh() {
    cards().forEach((card, index) => {
      card.querySelector('[data-primary-badge]').hidden = index !== 0;
      card.querySelector('[data-make-primary]').hidden = index === 0;
    });
    addButton.hidden = cards().length >= MAX_IMAGES;
  }

  function addCard(src, formIndex) {
    const card = template.content.firstElementChild.cloneNode(true);
    card.dataset.formIndex = formIndex;
    card.querySelector('img').src = src;
    card.querySelector('[data-remove-image]').addEventListener('click', () => {
      const formDiv = forms[formIndex];
      // Foto já salva é apagada no envio; a recém-escolhida só libera o slot
      if (formDiv.dataset.existingImageUrl) field(formDiv, 'DELETE').checked = true;
      field(formDiv, 'image').value = '';
      card.remove();
      refresh();
      addButton.focus();
    });
    card.querySelector('[data-make-primary]').addEventListener('click', () => {
      grid.prepend(card);
      refresh();
      card.querySelector('[data-remove-image]').focus();
      grid.dispatchEvent(new window.Event('change', { bubbles: true }));
    });
    grid.insertBefore(card, addButton);
  }

  forms
    .map((formDiv, index) => ({ formDiv, index }))
    .filter(
      ({ formDiv }) =>
        formDiv.dataset.existingImageUrl && !field(formDiv, 'DELETE').checked
    )
    .sort((a, b) => ('primary' in b.formDiv.dataset) - ('primary' in a.formDiv.dataset))
    .forEach(({ formDiv, index }) => addCard(formDiv.dataset.existingImageUrl, index));

  addButton.addEventListener('click', () => {
    const index = forms.findIndex(
      formDiv =>
        !formDiv.dataset.existingImageUrl && !field(formDiv, 'image').files.length
    );
    if (index === -1 || cards().length >= MAX_IMAGES) return;
    const input = field(forms[index], 'image');
    input.onchange = () => {
      const file = input.files[0];
      if (file && file.type.startsWith('image/')) {
        addCard(window.URL.createObjectURL(file), index);
        refresh();
      }
    };
    input.click();
  });

  document.getElementById('place-form').addEventListener('submit', () => {
    cards().forEach((card, position) => {
      const formDiv = forms[card.dataset.formIndex];
      field(formDiv, 'display_order').value = position;
      field(formDiv, 'is_primary').checked = position === 0;
    });
  });

  refresh();
});
