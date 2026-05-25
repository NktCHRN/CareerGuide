import Link from "next/link";
import { redirect } from "next/navigation";

import { Logo } from "@/components/brand/logo";
import {
  ChatIcon,
  CompassIcon,
  GraduationIcon,
  SparklesIcon,
} from "@/components/icons";
import { buttonClasses } from "@/components/ui/button";
import { getSession } from "@/lib/auth/session";

const FEATURES = [
  {
    icon: SparklesIcon,
    title: "Personalised recommendations",
    body: "A machine-learning model ranks professions against your experience and skills.",
  },
  {
    icon: CompassIcon,
    title: "Know your type",
    body: "Take a RIASEC assessment and see how your interests map to careers.",
  },
  {
    icon: GraduationIcon,
    title: "Rich profession data",
    body: "Explore ESCO occupations: skills, salaries, vacancies and education needs.",
  },
  {
    icon: ChatIcon,
    title: "Ask the assistant",
    body: "Chat about a profession, your fit, or a learning plan — grounded in your profile.",
  },
];

export default async function LandingPage() {
  const session = await getSession();
  if (session) redirect("/recommendations");

  return (
    <div className="flex min-h-screen flex-col bg-white">
      <header className="border-b border-slate-100">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
          <Logo />
          <div className="flex items-center gap-2">
            <Link href="/login" className={buttonClasses({ variant: "ghost", size: "sm" })}>
              Sign in
            </Link>
            <Link href="/register" className={buttonClasses({ size: "sm" })}>
              Get started
            </Link>
          </div>
        </div>
      </header>

      <main className="flex-1">
        <section className="relative overflow-hidden">
          <div className="absolute inset-0 -z-10 bg-gradient-to-b from-brand-50/80 to-white" />
          <div className="mx-auto max-w-6xl px-4 py-20 text-center sm:px-6 sm:py-28">
            <span className="inline-flex items-center gap-2 rounded-full bg-brand-100 px-3 py-1 text-xs font-medium text-brand-700">
              <SparklesIcon /> Career orientation, guided by data
            </span>
            <h1 className="mx-auto mt-6 max-w-3xl text-4xl font-bold tracking-tight text-slate-900 sm:text-5xl">
              Find the profession that fits{" "}
              <span className="text-brand-600">who you are</span>
            </h1>
            <p className="mx-auto mt-5 max-w-2xl text-lg text-slate-600">
              CareerGuide analyses your experience, skills and interests to
              recommend careers from the European ESCO catalogue — and helps you
              plan your next step.
            </p>
            <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
              <Link href="/register" className={buttonClasses({ size: "lg" })}>
                Create your profile
              </Link>
              <Link
                href="/login"
                className={buttonClasses({ variant: "outline", size: "lg" })}
              >
                I already have an account
              </Link>
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-4 pb-24 sm:px-6">
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {FEATURES.map((f) => (
              <div
                key={f.title}
                className="rounded-[var(--radius-card)] border border-slate-200 bg-white p-6 shadow-[var(--shadow-card)] transition-shadow hover:shadow-[var(--shadow-card-hover)]"
              >
                <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-xl text-brand-600">
                  <f.icon />
                </div>
                <h3 className="mt-4 font-semibold text-slate-900">{f.title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-slate-500">
                  {f.body}
                </p>
              </div>
            ))}
          </div>
        </section>
      </main>

      <footer className="border-t border-slate-100 py-8">
        <p className="text-center text-xs text-slate-400">
          A career-orientation recommender prototype. © {new Date().getFullYear()}{" "}
          CareerGuide.
        </p>
      </footer>
    </div>
  );
}
