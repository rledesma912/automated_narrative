/**
 * Wizard Client (extraído de wizard.ejs siguiendo el patrón de Spec-318 §9.C).
 *
 * Maneja:
 *  - Narrador (Spec-440 §5): el <select> storyteller_id lista solo personajes con nombre.
 *  - Modal de eliminación con confirmación (closeDeleteModal global).
 *  - Listas dinámicas: addPersonaje/addScenario/addRule + askDelete* para cada uno.
 *  - Auto-save por campo (Spec-220): PATCH a /generar/paso/<step>/guardar en blur/change.
 *  - Combos Género → Subgénero desde el catálogo embebido (Spec-440 §2).
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
    updateStoryteller();

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

  // ── Narrador: solo personajes visibles y con nombre (Spec-440 §5) ────────
  // Mismo criterio que el render del servidor (wizard.ejs). Si el elegido deja
  // de existir → "Seleccioná..."; con un único personaje se preselecciona.
  // Cada cambio de valor se guarda en sesión.
  function namedPersonajes() {
    return getVisiblePersonajes()
      .map(function (i) {
        var input = document.querySelector('[name="protagonista_' + i + '_name"]');
        return { value: "protagonista_" + i, label: input ? input.value.trim() : "" };
      })
      .filter(function (c) {
        return c.label !== "";
      });
  }

  function updateStoryteller() {
    var sel = document.querySelector("select[data-characters-field]");
    if (!sel) return;
    var chars = namedPersonajes();
    var current = sel.value;

    sel.innerHTML = "";
    var placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.disabled = true;
    placeholder.textContent = chars.length ? "Seleccioná..." : "Primero nombrá un personaje";
    sel.appendChild(placeholder);
    chars.forEach(function (c) {
      var opt = document.createElement("option");
      opt.value = c.value;
      opt.textContent = c.label;
      sel.appendChild(opt);
    });

    var keep = chars.some(function (c) {
      return c.value === current;
    });
    var next = keep ? current : chars.length === 1 ? chars[0].value : "";
    sel.value = next;
    if (!next) placeholder.selected = true;
    sel.disabled = chars.length === 0;
    if (next !== current) autoSaveField(sel.name, next, "select");
  }

  document.querySelectorAll('[name^="protagonista_"][name$="_name"]').forEach(function (el) {
    el.addEventListener("input", updateStoryteller);
  });

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

  // ── Listas dinámicas genéricas ───────────────────────────────────────────
  // Mismo comportamiento que personajes/escenarios/reglas, parametrizado.
  function cardList(opts) {
    function card(i) {
      return document.getElementById(opts.cardPrefix + i);
    }
    function visibleCount() {
      var n = 0;
      for (var i = 1; i <= opts.max; i++) if (card(i) && !card(i).classList.contains("hidden")) n++;
      return n;
    }
    function toggleMax() {
      var msg = document.getElementById(opts.msgMaxId);
      if (msg) msg.classList.toggle("hidden", visibleCount() < opts.max);
    }
    return {
      add: function () {
        for (var i = 1; i <= opts.max; i++) {
          if (card(i) && card(i).classList.contains("hidden")) {
            card(i).classList.remove("hidden");
            var delBtn = document.getElementById(opts.deleteBtnPrefix + i);
            if (delBtn) delBtn.classList.remove("invisible");
            if (typeof lucide !== "undefined") lucide.createIcons();
            break;
          }
        }
        toggleMax();
      },
      askDelete: function (idx) {
        var label = opts.describe(idx);
        openDeleteModal("Se borrará " + label + " definitivamente.", function () {
          if (!card(idx)) return;
          card(idx).querySelectorAll("input, textarea, select").forEach(function (el) {
            if (el.type === "checkbox" || el.type === "radio") {
              el.checked = false;
              el.dispatchEvent(new Event("change"));
            } else {
              el.value = "";
              el.dispatchEvent(new Event("blur"));
            }
          });
          card(idx).classList.add("hidden");
          toggleMax();
        });
      },
    };
  }

  // ── Listas dinámicas: Entidades (Spec-450 §4) ────────────────────────────
  var entidades = cardList({
    max: 3,
    cardPrefix: "entity-card-",
    deleteBtnPrefix: "entity-delete-btn-",
    msgMaxId: "msg-max-entidades",
    describe: function (idx) {
      var nameInput = document.querySelector('[name="entity_' + idx + '_name"]');
      var name = nameInput ? nameInput.value.trim() : "";
      return name ? '"' + name + '"' : "la Entidad " + idx;
    },
  });
  window.addEntidad = entidades.add;
  window.askDeleteEntidad = entidades.askDelete;

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

  // ── Género → Subgénero (Spec-440 §2) ─────────────────────────────────────
  // Al cambiar el género se repuebla el subgénero con los suyos; si el valor
  // actual no pertenece al nuevo género, vuelve a "Seleccioná..." y se guardan
  // ambos campos en sesión.
  var catalogEl = document.getElementById("genre-catalog");
  var genreCatalog = [];
  try {
    genreCatalog = catalogEl ? JSON.parse(catalogEl.textContent || "[]") : [];
  } catch (e) {
    genreCatalog = [];
  }

  function fillSubgenres(sub, genreId) {
    var genre = genreCatalog.find(function (g) {
      return g.id === genreId;
    });
    var subgenres = genre ? genre.subgenres : [];
    var current = sub.value;
    var keep = subgenres.some(function (s) {
      return s.id === current;
    });
    sub.innerHTML = "";
    var placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.disabled = true;
    placeholder.textContent = genre ? "Seleccioná..." : "Elegí primero el tipo de horror";
    sub.appendChild(placeholder);
    subgenres.forEach(function (s) {
      var opt = document.createElement("option");
      opt.value = s.id;
      opt.textContent = s.label;
      sub.appendChild(opt);
    });
    sub.disabled = subgenres.length === 0;
    sub.value = keep ? current : "";
    if (!keep) placeholder.selected = true;
    return keep;
  }

  document.querySelectorAll("select[data-depends-on]").forEach(function (sub) {
    var parent = document.querySelector('[name="' + sub.dataset.dependsOn + '"]');
    if (!parent) return;
    parent.addEventListener("change", function () {
      autoSaveField(parent.name, parent.value, "select");
      if (!fillSubgenres(sub, parent.value)) autoSaveField(sub.name, "", "select");
    });
    sub.addEventListener("change", function () {
      autoSaveField(sub.name, sub.value, "select");
    });
  });

  updateStoryteller();

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
