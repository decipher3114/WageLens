"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { instrumentSerif } from "@/lib/fonts";

export default function Navbar() {
  const pathname = usePathname();
  const onRegister = pathname === "/complaints/new";
  const onDashboard = pathname === "/dashboard";

  return (
    <div className="relative z-10 flex items-center justify-between border-b border-black/30 px-5 py-4 xl:px-18 xl:py-4">
      <Link href="/" className="group">
        <span
          className={`${instrumentSerif.className} text-[36px] font-normal leading-none tracking-tight text-neutral-900 transition group-hover:opacity-80 sm:text-[42px]`}
        >
          WageLens
        </span>
      </Link>
      <div className="flex items-center justify-between md:gap-3">
        {!onRegister && (
          <Link href="/complaints/new">
            <button
              type="button"
              className="cursor-pointer rounded-full border border-black bg-black px-3 py-2 text-sm font-medium text-white"
            >
              Register
            </button>
          </Link>
        )}
        {!onDashboard && (
          <Link href="/dashboard">
            <button
              type="button"
              className="cursor-pointer rounded-full border border-black px-3 py-2 text-sm font-medium"
            >
              Dashboard
            </button>
          </Link>
        )}
      </div>
    </div>
  );
}
