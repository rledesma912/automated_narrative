/**
 * Wizard Client (extraído de wizard.ejs siguiendo el patrón de Spec-318 §9.C).
 *
 * Maneja:
 *  - Storyteller labels: refleja nombres de personajes en el <select> storyteller_id.
 *  - Modal de eliminación con confirmación (closeDeleteModal global).
 *  - Listas dinámicas: addPersonaje/addScenario/addRule + askDelete* para cada uno.
 *  - Auto-save por campo (Spec-220): PATCH a /generar/paso/<step>/guardar en blur/change.
 *
 * Lee `window.STEP_NUM` (inyectado por un <script> inline previo en wizard.ejs).
 *
 * Las funciones invocadas desde onclick="..." en el HTML (closeDeleteModal,
 * addPersonaje, addScenario, addRule, askDeletePersonaje, askDeleteScenario,
 * askDeleteRule) quedan expuestas como `window.X = ...`.
 */
(function () {
  "use strict";

  const STEP_NUM = window.STEP_NUM;

  // ── Storyteller: actualizar labels con nombres escritos ──────────────────
  function updateStoryteller() {
    var sel = document.querySelector('[name="storyteller_id"]');
    if (!sel) return;
    [1, 2, 3, 4, 5].forEach(function (n) {
      var nameInput = document.querySelector('[name="protagonista_' + n + '_name"]');
      var opt = sel.querySelector('option[value="protagonista_' + n + '"]');
      if (opt && nameInput) {
        var name = nameInput.value.trim();
        opt.textContent = name || "Personaje " + n + " (sin nombre)";
      }
    });
  }
  document.querySelectorAll('[name$="_name"]').forEach(function (el) {
    el.addEventListener("input", updateStoryteller);
  });
  updateStoryteller();

  // ── Modal de eliminación ─────────────────────────────────────────────────
  var pendingDelete = null;

  window.closeDeleteModal = function () {
    pendingDelete = null;
    var modal = document.getElementById("delete-modal");
    if (modal) modal.classList.add("hidden");
  };

  function openDeleteModal(msg, onConfirm) {
    document.getElementById("delete-modal-msg").textContent = msg;
    document.getElementById("delete-modal-confirm").onclick = function () {
      onConfirm();
      window.closeDeleteModal();
    };
    document.getElementById("delete-modal").classList.remove("hidden");
  }

  var deleteModal = document.getElementById("delete-modal");
  if (deleteModal) {
    deleteModal.addEventListener("click", function (e) {
      if (e.target === this) window.closeDeleteModal();
    });
  }

  // ── Listas dinámicas: Protagonistas ──────────────────────────────────────
  var MAX_PROTAGONISTAS = 5;

  function getVisiblePersonajes() {
    var visible = [];
    for (var i = 1; i <= MAX_PROTAGONISTAS; i++) {
      var card = document.getElementById("personaje-card-" + i);
      if (card && !card.classList.contains("hidden")) visible.push(i);
    }
    return visible;
  }

  window.addPersonaje = function () {
    var visible = getVisiblePersonajes();
    if (visible.length >= MAX_PROTAGONISTAS) {
      document.getElementById("msg-max-personajes").classList.remove("hidden");
      return;
    }
    document.getElementById("msg-max-personajes").classList.add("hidden");

    for (var i = 1; i <= MAX_PROTAGONISTAS; i++) {
      var card = document.getElementById("personaje-card-" + i);
      if (card && card.classList.contains("hidden")) {
        card.classList.remove("hidden");
        var delBtn = document.getElementById("personaje-delete-btn-" + i);
        if (delBtn) delBtn.classList.remove("invisible");
        if (typeof lucide !== "undefined") lucide.createIcons();
        break;
      }
    }

    var newVisible = getVisiblePersonajes();
    if (newVisible.length >= MAX_PROTAGONISTAS) {
      document.getElementById("msg-max-personajes").classList.remove("hidden");
    }
  };

  window.askDeletePersonaje = function (idx) {
    var nameInput = document.querySelector('[name="protagonista_' + idx + '_name"]');
    var name = nameInput ? nameInput.value.trim() : "";
    var msg = name
      ? 'Se borrará "' + name + '" definitivamente.'
      : "Se borrará el Personaje " + idx + " definitivamente.";

    openDeleteModal(msg, function () {
      var card = document.getElementById("personaje-card-" + idx);
      if (!card) return;

      card.querySelectorAll("input, textarea, select").forEach(function (el) {
        if (el.type === "checkbox" || el.type === "radio") {
          el.checked = false;
          el.dispatchEvent(new Event("change"));
        } else {
          el.value = "";
          el.dispatchEvent(new Event("blur"));
        }
      });

      card.classList.add("hidden");
      document.getElementById("msg-max-personajes").classList.add("hidden");

      updateStoryteller();
    });
  };

  // ── Listas dinámicas: Escenarios ─────────────────────────────────────────
  var MAX_ESCENARIOS = 4;

  function getVisibleScenarios() {
    var visible = [];
    for (var i = 1; i <= MAX_ESCENARIOS; i++) {
      var card = document.getElementById("scenario-card-" + i);
      if (card && !card.classList.contains("hidden")) visible.push(i);
    }
    return visible;
  }

  window.addScenario = function () {
    var visible = getVisibleScenarios();
    if (visible.length >= MAX_ESCENARIOS) {
      document.getElementById("msg-max-escenarios").classList.remove("hidden");
      return;
    }
    document.getElementById("msg-max-escenarios").classList.add("hidden");

    for (var i = 1; i <= MAX_ESCENARIOS; i++) {
      var card = document.getElementById("scenario-card-" + i);
      if (card && card.classList.contains("hidden")) {
        card.classList.remove("hidden");
        var delBtn = document.getElementById("scenario-delete-btn-" + i);
        if (delBtn) delBtn.classList.remove("invisible");
        if (typeof lucide !== "undefined") lucide.createIcons();
        break;
      }
    }

    var newVisible = getVisibleScenarios();
    if (newVisible.length >= MAX_ESCENARIOS) {
      document.getElementById("msg-max-escenarios").classList.remove("hidden");
    }
  };

  window.askDeleteScenario = function (idx) {
    var nameInput = document.querySelector('[name="scenario_' + idx + '_name"]');
    var name = nameInput ? nameInput.value.trim() : "";
    var msg = name
      ? 'Se borrará "' + name + '" definitivamente.'
      : "Se borrará el Escenario " + idx + " definitivamente.";

    openDeleteModal(msg, function () {
      var card = document.getElementById("scenario-card-" + idx);
      if (!card) return;

      card.querySelectorAll("input, textarea, select").forEach(function (el) {
        if (el.type === "checkbox" || el.type === "radio") {
          el.checked = false;
          el.dispatchEvent(new Event("change"));
        } else {
          el.value = "";
          el.dispatchEvent(new Event("blur"));
        }
      });

      card.classList.add("hidden");
      document.getElementById("msg-max-escenarios").classList.add("hidden");
    });
  };

  // ── Listas dinámicas: Reglas ─────────────────────────────────────────────
  var MAX_REGLAS = 7;

  function getVisibleRules() {
    var visible = [];
    for (var i = 1; i <= MAX_REGLAS; i++) {
      var card = document.getElementById("rule-card-" + i);
      if (card && !card.classList.contains("hidden")) visible.push(i);
    }
    return visible;
  }

  window.addRule = function () {
    var visible = getVisibleRules();
    if (visible.length >= MAX_REGLAS) {
      document.getElementById("msg-max-reglas").classList.remove("hidden");
      return;
    }
    document.getElementById("msg-max-reglas").classList.add("hidden");

    for (var i = 1; i <= MAX_REGLAS; i++) {
      var card = document.getElementById("rule-card-" + i);
      if (card && card.classList.contains("hidden")) {
        card.classList.remove("hidden");
        var delBtn = document.getElementById("rule-delete-btn-" + i);
        if (delBtn) delBtn.classList.remove("invisible");
        if (typeof lucide !== "undefined") lucide.createIcons();
        break;
      }
    }

    var newVisible = getVisibleRules();
    if (newVisible.length >= MAX_REGLAS) {
      document.getElementById("msg-max-reglas").classList.remove("hidden");
    }
  };

  window.askDeleteRule = function (idx) {
    var textInput = document.querySelector('[name="rule_' + idx + '_text"]');
    var text = textInput ? textInput.value.trim() : "";
    var msg = text
      ? 'Se borrará la regla "' + (text.length > 30 ? text.substring(0, 30) + "..." : text) + '" definitivamente.'
      : "Se borrará la Regla " + idx + " definitivamente.";

    openDeleteModal(msg, function () {
      var card = document.getElementById("rule-card-" + idx);
      if (!card) return;

      card.querySelectorAll("input, textarea, select").forEach(function (el) {
        if (el.type === "checkbox" || el.type === "radio") {
          el.checked = false;
          el.dispatchEvent(new Event("change"));
        } else {
          el.value = "";
          el.dispatchEvent(new Event("blur"));
        }
      });

      card.classList.add("hidden");
      document.getElementById("msg-max-reglas").classList.add("hidden");
    });
  };

  // Render lucide icons iniciales
  if (typeof lucide !== "undefined") lucide.createIcons();

  // ── Auto-save por campo (Spec-220) ───────────────────────────────────────
  // El botón "Anterior" es <a href> (sin submit) → sin auto-save los campos
  // se perdían al navegar atrás. Persistimos a sesión en cada blur/change
  // contra PATCH /generar/paso/<step>/guardar.
  var formEl = document.querySelector('form[action="/generar/paso/' + STEP_NUM + '"]');

  function autoSaveField(fieldName, fieldValue, fieldType) {
    if (!fieldName) return;
    fetch("/generar/paso/" + STEP_NUM + "/guardar", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fieldName: fieldName, fieldValue: fieldValue, fieldType: fieldType }),
    }).catch(function () {
      /* fallo silencioso: el submit del paso es la red de seguridad */
    });
  }

  function readMultiSelect(name) {
    return Array.prototype.slice
      .call(formEl.querySelectorAll('input[type="checkbox"][name="' + name + '"]:checked'))
      .map(function (el) {
        return el.value;
      });
  }

  function handleFieldEvent(el) {
    var name = el.name;
    if (!name) return;
    var siblings = formEl.querySelectorAll('input[type="checkbox"][name="' + name + '"]');
    if (el.type === "checkbox" && siblings.length > 1) {
      autoSaveField(name, readMultiSelect(name), "multi-select");
    } else if (el.type === "checkbox" || el.type === "radio") {
      autoSaveField(name, el.checked ? el.value : "", el.type);
    } else {
      autoSaveField(name, el.value, el.type);
    }
  }

  if (formEl) {
    formEl.querySelectorAll("input, textarea, select").forEach(function (el) {
      if (el.type === "submit" || el.type === "button" || el.type === "hidden") return;
      if (el.type === "checkbox" || el.type === "radio") {
        el.addEventListener("change", function () {
          handleFieldEvent(el);
        });
      } else {
        el.addEventListener("blur", function () {
          handleFieldEvent(el);
        });
      }
    });
  }
})();
