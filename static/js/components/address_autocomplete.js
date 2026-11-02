/**
 * Autocompletar de Locais do Google Maps para Formulário de Local
 * Gerencia autocompletar de endereço e captura automática de latitude/longitude
 * Usa a nova API PlaceAutocompleteElement (recomendada pelo Google desde março de 2025)
 */

let autocompleteInput;
let addressTextarea;
let latitudeField;
let longitudeField;

function initAutocomplete() {
  // Obter campos do formulário
  addressTextarea = document.getElementById('id_address');
  latitudeField = document.getElementById('id_latitude');
  longitudeField = document.getElementById('id_longitude');

  if (!addressTextarea) {
    console.error('Campo de endereço não encontrado');
    return;
  }

  // Ocultar o textarea original temporariamente. A obrigatoriedade passa para o campo
  // visível: um campo oculto obrigatório bloqueia o envio sem nenhum aviso.
  addressTextarea.hidden = true;
  const required = addressTextarea.required;
  addressTextarea.required = false;

  // Criar um input de texto para autocompletar
  autocompleteInput = document.createElement('input');
  autocompleteInput.type = 'text';
  autocompleteInput.className = 'input w-full';
  autocompleteInput.id = 'id_address_search';
  autocompleteInput.autocomplete = 'off';
  autocompleteInput.required = required;
  autocompleteInput.setAttribute(
    'aria-describedby',
    addressTextarea.getAttribute('aria-describedby') || ''
  );
  addressTextarea.labels.forEach(label => (label.htmlFor = autocompleteInput.id));
  autocompleteInput.placeholder = gettext('Comece a digitar o endereço...');
  autocompleteInput.value = addressTextarea.value;

  // Inserir o input de autocompletar antes do textarea
  addressTextarea.parentNode.insertBefore(autocompleteInput, addressTextarea);

  // Criar instância de autocompletar usando a API clássica (ainda suportada)
  const autocomplete = new google.maps.places.Autocomplete(autocompleteInput, {
    types: ['address'],
    componentRestrictions: { country: 'BR' }, // Restringir ao Brasil
    fields: ['formatted_address', 'geometry', 'address_components'],
  });

  // Ouvir seleção de local
  autocomplete.addListener('place_changed', () => {
    const place = autocomplete.getPlace();
    onPlaceChanged(place);
  });

  // Sincronizar entrada manual com textarea oculto
  autocompleteInput.addEventListener('input', function () {
    addressTextarea.value = this.value;
  });

  // Prevenir envio de formulário ao pressionar Enter no campo de endereço
  autocompleteInput.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') {
      e.preventDefault();
    }
  });
}

function onPlaceChanged(place) {
  if (!place.geometry || !place.geometry.location) {
    console.warn('Sem dados de geometria para o local selecionado');
    return;
  }

  // Atualizar input e textarea com endereço formatado
  const formattedAddress = place.formatted_address || '';
  autocompleteInput.value = formattedAddress;
  addressTextarea.value = formattedAddress;

  // Atualizar latitude e longitude
  if (latitudeField && longitudeField) {
    const lat = place.geometry.location.lat();
    const lng = place.geometry.location.lng();

    latitudeField.value = lat.toFixed(6);
    longitudeField.value = lng.toFixed(6);
  }

  // Opcional: Atualizar campos de cidade/estado se existirem
  if (place.address_components) {
    updateAddressComponents(place.address_components);
  }
}

function updateAddressComponents(components) {
  // Esta função pode ser estendida para preencher automaticamente outros campos como cidade, estado, etc.
  // Exemplo: Extrair cidade e estado se necessário
  components.forEach(component => {
    const types = component.types;
    // Pode ser usado para preencher campos de cidade/estado se campos de formulário forem adicionados
    if (types.includes('locality')) {
      // Cidade: component.long_name
    }
    if (types.includes('administrative_area_level_1')) {
      // Estado: component.short_name
    }
  });
}

// O Google desativa o campo quando recusa a chave (cobrança, restrição de domínio):
// volta o campo de texto comum, para o endereço continuar sendo digitado à mão.
window.gm_authFailure = function () {
  if (!autocompleteInput) return;
  autocompleteInput.labels.forEach(label => (label.htmlFor = addressTextarea.id));
  addressTextarea.required = autocompleteInput.required;
  addressTextarea.hidden = false;
  autocompleteInput.remove();
  autocompleteInput = null;
};

// Inicializar quando o script do Google Maps for carregado
window.initAutocomplete = initAutocomplete;
