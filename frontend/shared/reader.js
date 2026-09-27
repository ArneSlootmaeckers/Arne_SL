/** Wristband reader abstraction.
 *
 * The real reader is not chosen yet, so screens only ever talk to this
 * interface (both classes expose start(onScan) / stop()). Adding e.g. a
 * serial or network reader later means adding one more class here — nothing
 * else on the page changes.
 */

/** A USB NFC/RFID reader that behaves like a keyboard: it types the
 * wristband id followed by Enter. Captures that without needing a focused
 * text field, by listening globally and buffering keystrokes.
 */
export class KeyboardWedgeReader {
  constructor({ minLength = 3, resetAfterMs = 500 } = {}) {
    this.minLength = minLength;
    this.resetAfterMs = resetAfterMs;
    this.buffer = "";
    this.lastKeyTime = 0;
    this.onScan = null;
    this._handleKeydown = this._handleKeydown.bind(this);
  }

  start(onScan) {
    this.onScan = onScan;
    document.addEventListener("keydown", this._handleKeydown);
  }

  stop() {
    document.removeEventListener("keydown", this._handleKeydown);
  }

  _handleKeydown(event) {
    // Don't interfere with someone typing in a real input field (e.g. the
    // simulation panel's own text box handles its own Enter key).
    if (event.target && ["INPUT", "TEXTAREA"].includes(event.target.tagName)) {
      return;
    }

    const now = performance.now();
    if (now - this.lastKeyTime > this.resetAfterMs) {
      this.buffer = "";
    }
    this.lastKeyTime = now;

    if (event.key === "Enter") {
      const scanned = this.buffer;
      this.buffer = "";
      if (scanned.length >= this.minLength && this.onScan) {
        this.onScan(scanned);
      }
      return;
    }

    if (event.key.length === 1) {
      this.buffer += event.key;
    }
  }
}

/** Bridge for the native Android wrapper app (android/webview-app): exposes
 * window.ToelatingNativeBridge.onScan(id), which that app's own NFC-reading
 * code (MainActivity.kt) calls after reading a wristband's hardware UID with
 * the phone's own NFC chip — same effect as a KeyboardWedgeReader scan, just
 * fed in directly instead of via synthetic keystrokes. Inert in a normal
 * browser: nothing ever calls it there.
 */
export class NativeBridgeReader {
  start(onScan) {
    window.ToelatingNativeBridge = { onScan };
  }

  stop() {
    delete window.ToelatingNativeBridge;
  }
}

/** Development/demo stand-in: type an id or pick one from a list of test
 * wristbands. Any id works — an unknown one is simply registered on first use.
 */
export class SimulatedReader {
  constructor(containerEl, testWristbands = []) {
    this.containerEl = containerEl;
    this.testWristbands = testWristbands;
    this.onScan = null;
  }

  start(onScan) {
    this.onScan = onScan;
    this._render();
  }

  stop() {
    this.containerEl.innerHTML = "";
  }

  _render() {
    this.containerEl.innerHTML = "";
    this.containerEl.classList.add("sim-panel");

    const title = document.createElement("div");
    title.className = "sim-panel-title";
    title.textContent = "Simulatiemodus";
    this.containerEl.appendChild(title);

    const quickPicks = document.createElement("div");
    quickPicks.className = "sim-panel-quickpicks";
    for (const id of this.testWristbands) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "sim-panel-btn";
      btn.textContent = id;
      btn.addEventListener("click", () => this._trigger(id));
      quickPicks.appendChild(btn);
    }
    this.containerEl.appendChild(quickPicks);

    const form = document.createElement("form");
    form.className = "sim-panel-form";
    const input = document.createElement("input");
    input.type = "text";
    input.placeholder = "Ander bandje-ID…";
    const submit = document.createElement("button");
    submit.type = "submit";
    submit.textContent = "Scan";
    form.appendChild(input);
    form.appendChild(submit);
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      this._trigger(input.value.trim());
      input.value = "";
    });
    this.containerEl.appendChild(form);
  }

  _trigger(id) {
    if (id && this.onScan) this.onScan(id);
  }
}
