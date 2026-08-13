"use client";

import { useEffect, useRef, useState } from "react";
import { Background } from "@/components/Background";
import { MicPulse } from "@/components/MicPulse";
import Navbar from "@/components/Navbar";
import { PageHeader } from "@/components/PageHeader";
import { useSpeechRecognition } from "@/hooks/useSpeechRecognition";
import { feedbackAudioSrc, submitTextComplaint } from "@/lib/api";
import {
  ExtractionField,
  MicCardMode,
  MicPulseVariant,
} from "@/lib/enums";
import { VoiceComplaintResponse } from "@/lib/types";

const MIC_CARD_HEIGHT = "h-[280px]";

type MicActivityCardProps = {
  mode: MicCardMode;
  supported: boolean;
  onToggle?: () => void;
};

function ProcessingCard() {
  return (
    <div
      className={`surface-card mx-auto flex max-w-2xl ${MIC_CARD_HEIGHT} flex-col items-center justify-center px-6 text-center sm:px-10`}
    >
      <div className="relative flex h-24 w-24 items-center justify-center">
        <div className="absolute inset-0 animate-spin rounded-full border-4 border-neutral-100 border-t-emerald-500" />
      </div>
      <div className="mt-6 space-y-2">
        <p className="text-lg font-medium text-neutral-900">Processing your statement</p>
        <p className="animate-pulse text-sm italic text-neutral-500">
          Extracting facts · Checking patterns · Generating feedback...
        </p>
      </div>
    </div>
  );
}

function MicActivityCard({ mode, supported, onToggle }: MicActivityCardProps) {
  const isListening = mode === MicCardMode.Listening;
  const isSpeaking = mode === MicCardMode.Speaking;

  const title = isListening
    ? "Listening... Tap to stop"
    : isSpeaking
      ? "Playing voice feedback"
      : "Tap to start speaking in Hindi";

  const pulseVariant = isListening
    ? MicPulseVariant.Listening
    : isSpeaking
      ? MicPulseVariant.Feedback
      : MicPulseVariant.Idle;

  return (
    <div
      className={`surface-card mx-auto flex max-w-2xl ${MIC_CARD_HEIGHT} flex-col items-center justify-center px-6 text-center transition-colors sm:px-10 ${
        isListening
          ? "cursor-pointer border-red-200/80"
          : isSpeaking
            ? "cursor-default border-emerald-200/80"
            : "cursor-pointer hover:border-neutral-300"
      }`}
      onClick={!isSpeaking && supported ? onToggle : undefined}
    >
      <div className="relative flex h-36 w-36 shrink-0 items-center justify-center">
        <MicPulse
          variant={pulseVariant}
          active={isListening || isSpeaking}
        />
      </div>

      <div className="mt-6 min-h-[52px]">
        <p className="text-lg font-medium text-neutral-900">{title}</p>
      </div>
    </div>
  );
}

const EXTRACTION_FIELDS = [
  { label: "Platform", key: ExtractionField.Platform },
  { label: "Trip time", key: ExtractionField.TripTime },
  { label: "Pickup", key: ExtractionField.PickupLocation },
  { label: "Drop", key: ExtractionField.DropLocation },
  { label: "Quoted", key: ExtractionField.QuotedAmount },
  { label: "Paid", key: ExtractionField.PaidAmount },
] as const;

function formatExtractedValue(
  key: ExtractionField,
  value: string | number | undefined,
  missingFields: string[],
): string {
  if (missingFields.includes(key) || value === undefined) {
    return "Missing";
  }
  return String(value);
}

export default function ComplaintPage() {
  const {
    isListening,
    displayTranscript,
    transcript,
    setTranscript,
    error: speechError,
    supported,
    toggleListening,
    stopListening,
    resetTranscript,
  } = useSpeechRecognition();

  const [result, setResult] = useState<VoiceComplaintResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isPlayingFeedback, setIsPlayingFeedback] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    if (!result?.audio_base64) {
      return;
    }

    const audio = new Audio(
      feedbackAudioSrc(result.audio_base64, result.audio_mime ?? "audio/mpeg"),
    );
    audioRef.current = audio;

    audio.onended = () => setIsPlayingFeedback(false);
    audio.onerror = () => setIsPlayingFeedback(false);

    void audio
      .play()
      .then(() => setIsPlayingFeedback(true))
      .catch(() => setIsPlayingFeedback(false));

    return () => {
      audio.pause();
      setIsPlayingFeedback(false);
      audioRef.current = null;
    };
  }, [result?.audio_base64, result?.audio_mime]);

  async function handleSubmit() {
    if (submitting) return;

    if (isListening) {
      stopListening();
    }

    const text = (transcript || displayTranscript).trim();
    if (text.length < 3) {
      setSubmitError("Please speak or type your complaint before submitting.");
      return;
    }

    setSubmitting(true);
    setSubmitError(null);
    setIsPlayingFeedback(false);

    try {
      const data = await submitTextComplaint(text);
      setResult(data);
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : "Failed to process complaint.";
      setSubmitError(message);
    } finally {
      setSubmitting(false);
    }
  }

  function handleResetAll() {
    audioRef.current?.pause();
    setIsPlayingFeedback(false);
    setResult(null);
    setSubmitError(null);
    resetTranscript();
  }

  const missingFields = result?.missing_fields ?? [];
  const showFeedback = Boolean(result && !submitting);

  const micMode = isPlayingFeedback
    ? MicCardMode.Speaking
    : isListening
      ? MicCardMode.Listening
      : MicCardMode.Idle;

  const ext = result?.extraction;
  const quoted = ext?.quoted_amount;
  const paid = ext?.paid_amount;
  const amountsComplete =
    !missingFields.includes(ExtractionField.QuotedAmount) &&
    !missingFields.includes(ExtractionField.PaidAmount) &&
    quoted !== undefined &&
    paid !== undefined;
  const discrepancy = amountsComplete ? (paid - quoted).toFixed(2) : null;

  return (
    <div className="relative flex min-h-screen flex-col bg-neutral-50">
      <Background />
      <Navbar />

      <section className="relative mx-auto w-full max-w-4xl flex-1 px-6 py-10 lg:py-12">
        <div className="space-y-8">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <PageHeader title="Register complaint" />
            {showFeedback && (
              <button
                type="button"
                onClick={handleResetAll}
                className="shrink-0 cursor-pointer self-start rounded-full border border-neutral-200 bg-neutral-900 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-black"
              >
                Register new complaint
              </button>
            )}
          </div>

          {!supported && !submitting && !showFeedback && (
            <p className="text-xs text-amber-700">
              Browser speech recognition requires Chrome or Edge. You can still type your complaint below.
            </p>
          )}

          {submitting ? (
            <ProcessingCard />
          ) : !showFeedback ? (
            <MicActivityCard
              mode={micMode}
              supported={supported}
              onToggle={toggleListening}
            />
          ) : null}

          {(speechError || submitError) && (
            <div className="mx-auto max-w-2xl rounded-xl border border-amber-200/80 bg-amber-50/80 p-3 text-xs font-medium text-amber-800">
              {speechError || submitError}
            </div>
          )}

          {!showFeedback && !submitting && (
            <div className="mx-auto max-w-2xl space-y-3">
              <label className="block text-sm font-medium text-neutral-700">Transcript</label>
              <textarea
                value={displayTranscript}
                onChange={(e) => setTranscript(e.target.value)}
                rows={5}
                placeholder="Your spoken complaint will appear here. You can edit it before submitting."
                className="surface-card w-full resize-none bg-white px-5 py-4 text-sm text-neutral-900 focus:outline-none focus:ring-2 focus:ring-neutral-200/80"
              />
              <button
                type="button"
                onClick={handleSubmit}
                disabled={!(transcript || displayTranscript).trim()}
                className="w-full cursor-pointer rounded-full bg-neutral-900 px-8 py-3 text-sm font-medium text-white transition hover:bg-black disabled:opacity-50"
              >
                Submit complaint
              </button>
            </div>
          )}

          {showFeedback && result && (
            <div className="animate-in fade-in slide-in-from-bottom-4 mx-auto max-w-2xl space-y-6 duration-500">
              <div className="space-y-2">
                <label className="block text-sm font-medium text-neutral-700">Your statement</label>
                <div className="surface-card bg-white px-5 py-4 text-sm leading-relaxed text-neutral-900">
                  {result.transcript}
                </div>
              </div>

              <div className="surface-card p-8 sm:p-10">
                <p className="text-lg leading-relaxed text-neutral-900 sm:text-xl">
                  {result.feedback}
                </p>
              </div>

              <div className="surface-card space-y-6 p-8 sm:p-10">
                <div className="text-xs font-bold uppercase tracking-wider text-neutral-400">
                  Extracted facts
                </div>
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
                  {EXTRACTION_FIELDS.map(({ label, key }) => {
                    const value = ext?.[key as keyof typeof ext];
                    const isMissing = missingFields.includes(key);
                    const text = formatExtractedValue(key, value, missingFields);
                    return (
                      <div key={key} className="surface-card-inset p-5">
                        <span className="mb-2 block text-xs font-semibold uppercase text-neutral-400">
                          {label}
                        </span>
                        <span
                          className={`text-base font-medium ${
                            isMissing ? "italic text-amber-600" : "text-neutral-900"
                          }`}
                        >
                          {text}
                        </span>
                      </div>
                    );
                  })}
                </div>
                {discrepancy !== null && (
                  <div className="flex items-center justify-between rounded-2xl border border-red-100 bg-red-50/80 p-5 text-sm">
                    <span className="text-xs font-bold uppercase tracking-wider text-red-900">
                      Discrepancy detected
                    </span>
                    <span className="text-lg font-bold tabular-nums text-red-700 sm:text-xl">
                      {Number(discrepancy) > 0 ? `+₹${discrepancy}` : `₹${discrepancy}`}
                    </span>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
