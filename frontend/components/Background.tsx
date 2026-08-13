type BackgroundVariant = "hero" | "page";

type BackgroundProps = {
  variant?: BackgroundVariant;
};

export function Background({ variant = "page" }: BackgroundProps) {
  const isHero = variant === "hero";

  return (
    <div
      className={
        isHero
          ? "absolute inset-0 overflow-hidden"
          : "pointer-events-none absolute inset-0 overflow-hidden"
      }
    >
      {isHero ? (
        <>
          <div className="absolute -left-40 top-0 h-[500px] w-[500px] rounded-full bg-emerald-300/40 blur-[120px]" />
          <div className="absolute -right-40 top-0 h-[500px] w-[500px] rounded-full bg-violet-300/40 blur-[120px]" />
          <div className="absolute left-1/2 top-1/3 h-[600px] w-[600px] -translate-x-1/2 rounded-full bg-sky-300/30 blur-[140px]" />
          <div className="absolute inset-0 bg-grid-hero opacity-50" />
        </>
      ) : (
        <>
          <div className="absolute -left-32 top-0 h-72 w-72 rounded-full bg-emerald-100/60 blur-3xl" />
          <div className="absolute -right-32 top-24 h-72 w-72 rounded-full bg-violet-100/50 blur-3xl" />
          <div className="absolute inset-0 bg-grid-page opacity-[0.35]" />
        </>
      )}
    </div>
  );
}
