"use client";

import { useCallback, useRef, useState, useSyncExternalStore } from "react";

const DEFAULT_SPEECH_LANG = "hi-IN";

type SpeechRecognitionInstance = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onresult: ((event: SpeechRecognitionEvent) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
};

function getSpeechRecognitionCtor():
  | (new () => SpeechRecognitionInstance)
  | null {
  if (typeof window === "undefined") return null;
  const w = window as Window & {
    SpeechRecognition?: new () => SpeechRecognitionInstance;
    webkitSpeechRecognition?: new () => SpeechRecognitionInstance;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

function speechRecognitionSupported(): boolean {
  return getSpeechRecognitionCtor() !== null;
}

function subscribeToSpeechSupport() {
  return () => {};
}

export function useSpeechRecognition() {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [interimTranscript, setInterimTranscript] = useState("");
  const [error, setError] = useState<string | null>(null);
  const supported = useSyncExternalStore(
    subscribeToSpeechSupport,
    speechRecognitionSupported,
    () => true,
  );

  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);
  const finalPartsRef = useRef<string[]>([]);

  const resetTranscript = useCallback(() => {
    finalPartsRef.current = [];
    setTranscript("");
    setInterimTranscript("");
    setError(null);
  }, []);

  const stopListening = useCallback(() => {
    recognitionRef.current?.stop();
    setIsListening(false);
  }, []);

  const startListening = useCallback(() => {
    const Ctor = getSpeechRecognitionCtor();
    if (!Ctor) {
      setError("Speech recognition is not supported in this browser. Use Chrome or Edge.");
      return;
    }

    setError(null);
    finalPartsRef.current = [];
    setTranscript("");
    setInterimTranscript("");

    const recognition = new Ctor();
    recognition.lang = DEFAULT_SPEECH_LANG;
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const piece = event.results[i][0]?.transcript ?? "";
        if (event.results[i].isFinal) {
          finalPartsRef.current.push(piece.trim());
        } else {
          interim += piece;
        }
      }
      const finalText = finalPartsRef.current.join(" ").trim();
      setTranscript(finalText);
      setInterimTranscript(interim.trim());
    };

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      if (event.error === "no-speech") {
        setError("No speech detected. Please try again.");
      } else if (event.error === "not-allowed") {
        setError("Microphone permission denied. Allow mic access in your browser.");
      } else if (event.error !== "aborted") {
        setError(event.message || `Speech recognition error: ${event.error}`);
      }
      setIsListening(false);
    };

    recognition.onend = () => {
      setIsListening(false);
      setInterimTranscript("");
      const finalText = finalPartsRef.current.join(" ").trim();
      if (finalText) {
        setTranscript(finalText);
      }
    };

    recognitionRef.current = recognition;
    try {
      recognition.start();
      setIsListening(true);
    } catch {
      setError("Could not start speech recognition. Try again.");
      setIsListening(false);
    }
  }, []);

  const toggleListening = useCallback(() => {
    if (isListening) {
      stopListening();
    } else {
      startListening();
    }
  }, [isListening, startListening, stopListening]);

  const displayTranscript = isListening
    ? [transcript, interimTranscript].filter(Boolean).join(" ")
    : transcript;

  return {
    isListening,
    transcript,
    displayTranscript,
    setTranscript,
    error,
    supported,
    toggleListening,
    stopListening,
    resetTranscript,
  };
}
