import { Mic } from "lucide-react";
import { MicPulseVariant } from "@/lib/enums";

const MIC_SHELL = "h-36 w-36";
const MIC_BUTTON = "h-20 w-20";

type MicPulseProps = {
  variant?: MicPulseVariant;
  active?: boolean;
};

export function MicPulse({ variant = MicPulseVariant.Idle, active = false }: MicPulseProps) {
  const isListening = variant === MicPulseVariant.Listening;
  const isFeedback = variant === MicPulseVariant.Feedback;
  const showPulse = active && (isListening || isFeedback);

  const gradientClass = isFeedback
    ? "mic-gemini-gradient-feedback"
    : "mic-gemini-gradient-listening";

  const buttonClass = isFeedback
    ? "bg-emerald-500 shadow-[0_4px_16px_rgba(16,185,129,0.35)]"
    : isListening
      ? "bg-red-500 shadow-[0_4px_16px_rgba(239,68,68,0.32)]"
      : "bg-neutral-900 shadow-[0_6px_18px_rgba(0,0,0,0.12)]";

  return (
    <div className={`relative flex ${MIC_SHELL} items-center justify-center`}>
      <div className="absolute inset-0 overflow-hidden rounded-full">
        {showPulse && (
          <>
            <div
              className={`pointer-events-none absolute inset-0 rounded-full ${gradientClass} mic-gemini-wave`}
            />
            <div
              className={`pointer-events-none absolute inset-0 rounded-full ${gradientClass} mic-gemini-wave mic-gemini-wave-delay`}
            />
          </>
        )}
      </div>
      <div
        className={`relative z-10 flex ${MIC_BUTTON} items-center justify-center rounded-full text-white ${buttonClass}`}
      >
        <Mic className="h-9 w-9" strokeWidth={1.5} />
      </div>
    </div>
  );
}
