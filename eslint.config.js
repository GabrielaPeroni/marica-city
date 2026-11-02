const js = require('@eslint/js');
const prettier = require('eslint-config-prettier');

// Browser globals used across the plain-JS files in static/js/. There is no
// bundler/module system yet: every file below is loaded individually via a
// <script src="..."> tag in a Django template and files share globals by
// attaching to `window` or simply relying on script load order.
const browserGlobals = {
  window: 'readonly',
  document: 'readonly',
  console: 'readonly',
  navigator: 'readonly',
  location: 'readonly',
  localStorage: 'readonly',
  sessionStorage: 'readonly',
  fetch: 'readonly',
  FormData: 'readonly',
  URL: 'readonly',
  URLSearchParams: 'readonly',
  FileReader: 'readonly',
  Promise: 'readonly',
  Set: 'readonly',
  Map: 'readonly',
  setTimeout: 'readonly',
  clearTimeout: 'readonly',
  setInterval: 'readonly',
  clearInterval: 'readonly',
  atob: 'readonly',
  btoa: 'readonly',
  alert: 'readonly',
  confirm: 'readonly',
  module: 'readonly',
  HTMLDialogElement: 'readonly',
  AbortController: 'readonly',
  HTMLFormElement: 'readonly',
  HTMLImageElement: 'readonly',
  Date: 'readonly',
};

// Third-party libraries loaded from <script> tags in templates/base.html
// and templates/core/landing.html (Swiper, Google Maps / Sign-In SDK).
const thirdPartyGlobals = {
  basecoat: 'readonly',
  Swiper: 'readonly',
  google: 'readonly',
  // Django JavaScriptCatalog (/jsi18n/), loaded first in base.html
  gettext: 'readonly',
  ngettext: 'readonly',
  interpolate: 'readonly',
};

module.exports = [
  js.configs.recommended,
  {
    files: ['static/js/**/*.js'],
    languageOptions: {
      ecmaVersion: 2021,
      sourceType: 'script',
      globals: {
        ...browserGlobals,
        ...thirdPartyGlobals,
      },
    },
    rules: {
      'no-unused-vars': ['warn', { args: 'none', caughtErrors: 'none' }],
      'no-undef': 'error',
      'no-console': 'off',
    },
  },
  {
    // getCookie()/cloneIcon()/request() (services/utils.js) and showToast() (toasts.js) load first
    // in base.html, so every other file can use them.
    files: ['static/js/**/*.js'],
    ignores: ['static/js/services/utils.js', 'static/js/components/toasts.js'],
    languageOptions: {
      globals: {
        getCookie: 'readonly',
        cloneIcon: 'readonly',
        showToast: 'readonly',
        request: 'readonly',
        whenActive: 'readonly',
        RequestError: 'readonly',
      },
    },
  },
  {
    // favoritesService is the singleton exported by favorites_service.js,
    // which base.html loads before favorites_ui.js.
    files: ['static/js/components/favorites_ui.js'],
    languageOptions: {
      globals: { favoritesService: 'readonly' },
    },
  },
  {
    ignores: ['static/vendor/**', 'node_modules/**', 'staticfiles/**'],
  },
  prettier,
];
