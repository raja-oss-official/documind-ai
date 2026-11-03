// ============================================================
// VOICE INPUT AND READ ALOUD (BROWSER SPEECH APIS)
// ============================================================
// Both features use built-in browser APIs and need no backend.
// Buttons are hidden in browsers that do not support them.

const Recognition =
  typeof window !== "undefined" ? window.SpeechRecognition || window.webkitSpeechRecognition : null;

export const voiceInputSupported = Boolean(Recognition);

export const readAloudSupported = typeof window !== "undefined" && "speechSynthesis" in window;

// ============================================================
// VOICE INPUT (DICTATION)
// ============================================================
// Calls onText with the transcript so far (interim results included).
// Returns a function that stops listening.
export function startDictation({ onText, onEnd, onError }) {
  const recognition = new Recognition();
  recognition.lang = navigator.language || "en-US";
  recognition.interimResults = true;
  recognition.continuous = false;

  recognition.onresult = (event) => {
    const transcript = Array.from(event.results)
      .map((result) => result[0].transcript)
      .join("");
    onText(transcript);
  };

  recognition.onerror = (event) => {
    const messages = {
      "not-allowed": "Microphone access was blocked. Allow it in your browser settings to use voice input.",
      "no-speech": "No speech was heard. Try again and speak after the beep.",
      "audio-capture": "No microphone was found.",
    };

    if (event.error !== "aborted") {
      onError(messages[event.error] || "Voice input stopped unexpectedly.");
    }
  };

  recognition.onend = onEnd;
  recognition.start();

  return () => recognition.stop();
}

// ============================================================
// READ ALOUD
// ============================================================
// Long text is spoken in sentence-sized pieces: some browsers stop a
// single long utterance after about 15 seconds.
function splitForSpeech(text, maxLength = 220) {
  const sentences = text.match(/[^.!?]+[.!?]*\s*/g) || [text];
  const pieces = [];
  let current = "";

  for (const sentence of sentences) {
    if ((current + sentence).length > maxLength && current) {
      pieces.push(current.trim());
      current = "";
    }

    current += sentence;
  }

  if (current.trim()) {
    pieces.push(current.trim());
  }

  return pieces;
}

export function speak(text, { onEnd } = {}) {
  const synth = window.speechSynthesis;
  synth.cancel();

  const pieces = splitForSpeech(text);

  pieces.forEach((piece, index) => {
    const utterance = new SpeechSynthesisUtterance(piece);
    utterance.lang = navigator.language || "en-US";

    if (index === pieces.length - 1) {
      utterance.onend = () => onEnd?.();
    }

    utterance.onerror = () => onEnd?.();
    synth.speak(utterance);
  });
}

export function stopSpeaking() {
  if (readAloudSupported) {
    window.speechSynthesis.cancel();
  }
}
