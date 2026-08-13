import { instrumentSerif } from "@/lib/fonts";

export function PageHeader({ title }: { title: string }) {
  return (
    <h1
      className={`${instrumentSerif.className} text-3xl font-normal tracking-tight text-neutral-900 sm:text-4xl`}
    >
      {title}
    </h1>
  );
}
