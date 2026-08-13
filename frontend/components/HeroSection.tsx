"use client";

import Link from "next/link";

export default function HeroSection() {
  return (
    <section className="relative z-10 flex flex-1 overflow-hidden px-5 pt-32">
      <div className="mx-auto max-w-7xl">
        <h1 className="text-center text-7xl font-semibold leading-[0.95] tracking-tight xl:text-8xl">
          The gap between quoted and paid.
          <br />
          Now visible.
        </h1>

        <p className="mx-auto mt-8 max-w-2xl text-center text-lg text-neutral-600">
          WageLens helps workers compare promised wages with actual payments and
          expose discrepancies before they become exploitation.
        </p>

        <div className="mt-10 flex flex-col items-center justify-center gap-4 md:flex-row">
          <Link href="/complaints/new">
            <button
              type="button"
              className="cursor-pointer rounded-full bg-black px-6 py-3 text-white"
            >
              Register a discrepancy
            </button>
          </Link>

          <Link href="/dashboard">
            <button
              type="button"
              className="cursor-pointer rounded-full border border-black px-6 py-3"
            >
              Dashboard
            </button>
          </Link>
        </div>
      </div>
    </section>
  );
}
