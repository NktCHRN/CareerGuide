import Link from "next/link";

import { Logo } from "@/components/brand/logo";

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col bg-gradient-to-b from-brand-50/70 via-white to-slate-50">
      <div className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-4 py-12">
        <Link href="/" className="mb-8 flex justify-center" aria-label="CareerGuide home">
          <Logo />
        </Link>
        <div className="animate-fade-in-up">{children}</div>
      </div>
    </div>
  );
}
