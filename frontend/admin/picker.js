/** Vervangt het keuzevenster van een <select> door een eigen popup in de
 * Sparkx-stijl. Op Android (WebView) en in veel browsers opent een <select>
 * het eigen, grijze systeemvenster van het toestel, en dat laat zich niet met
 * CSS opmaken.
 *
 * De <select> blijft (verborgen) de bron van de waarde: bestaande code die
 * `select.value` leest of zet, en formulieren die hem versturen of resetten,
 * werken dus ongewijzigd verder.
 */

const CHEVRON_SVG =
  '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" ' +
  'stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
  '<polyline points="6 9 12 15 18 9"></polyline></svg>';

export function enhanceSelect(select) {
  const trigger = document.createElement("button");
  trigger.type = "button";
  trigger.className = "picker-trigger";
  trigger.setAttribute("aria-haspopup", "listbox");
  const label = document.createElement("span");
  label.className = "picker-label";
  trigger.append(label);
  trigger.insertAdjacentHTML("beforeend", CHEVRON_SVG);

  select.classList.add("picker-native");
  select.after(trigger);

  function refresh() {
    const option = select.options[select.selectedIndex];
    label.textContent = option ? option.textContent : "";
  }

  // Code die `select.value = ...` zet (bv. de status van een opgezocht
  // bandje) moet ook het zichtbare label bijwerken, zonder dat die code de
  // popup hoeft te kennen.
  const nativeValue = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value");
  Object.defineProperty(select, "value", {
    configurable: true,
    get() {
      return nativeValue.get.call(select);
    },
    set(newValue) {
      nativeValue.set.call(select, newValue);
      refresh();
    },
  });
  // Een form-reset zet de <select> pas terug ná dit event.
  select.form?.addEventListener("reset", () => setTimeout(refresh));

  trigger.addEventListener("click", () => openPopup(select, trigger));
  refresh();
}

function openPopup(select, trigger) {
  const overlay = document.createElement("div");
  overlay.className = "picker-overlay";

  const panel = document.createElement("div");
  panel.className = "picker-panel";
  panel.setAttribute("role", "listbox");

  if (select.dataset.title) {
    const title = document.createElement("div");
    title.className = "picker-title";
    title.textContent = select.dataset.title;
    panel.append(title);
  }

  function close() {
    overlay.remove();
    document.removeEventListener("keydown", onKeydown);
    trigger.focus();
  }

  function onKeydown(event) {
    if (event.key === "Escape") close();
  }

  let selectedButton = null;
  for (const option of select.options) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "picker-option";
    button.setAttribute("role", "option");
    button.textContent = option.textContent;
    const isSelected = option.value === select.value;
    button.setAttribute("aria-selected", String(isSelected));
    if (isSelected) {
      button.classList.add("selected");
      selectedButton = button;
    }
    button.addEventListener("click", () => {
      const changed = select.value !== option.value;
      select.value = option.value;
      close();
      if (changed) select.dispatchEvent(new Event("change", { bubbles: true }));
    });
    panel.append(button);
  }

  overlay.addEventListener("click", (event) => {
    if (event.target === overlay) close();
  });
  document.addEventListener("keydown", onKeydown);

  overlay.append(panel);
  document.body.append(overlay);
  (selectedButton || panel.querySelector(".picker-option"))?.focus();
}
