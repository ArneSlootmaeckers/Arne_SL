/** Simple confirmation tones via the Web Audio API — no audio files needed,
 * so the screens keep working fully offline on the local server.
 */

let audioCtx = null;

function getAudioContext() {
  if (!audioCtx) {
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  }
  return audioCtx;
}

function beep(frequency, durationMs, type = "sine") {
  try {
    const ctx = getAudioContext();
    const oscillator = ctx.createOscillator();
    const gain = ctx.createGain();
    oscillator.type = type;
    oscillator.frequency.value = frequency;
    gain.gain.value = 0.2;
    oscillator.connect(gain);
    gain.connect(ctx.destination);
    oscillator.start();
    oscillator.stop(ctx.currentTime + durationMs / 1000);
  } catch {
    // Web Audio not (yet) available in this browser context — fail silently.
  }
}

export function playSuccessSound() {
  beep(880, 150);
  setTimeout(() => beep(1175, 200), 150);
}

export function playFailureSound() {
  beep(220, 300, "sawtooth");
}

export function playNeutralSound() {
  beep(440, 120);
}
