import { Logo } from "@/components/brand/logo";

export function Footer() {
  return (
    <footer className="border-t border-slate-200 bg-white">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-3 px-4 py-6 sm:flex-row sm:px-6">
        <Logo />
        <p className="text-xs text-slate-500">
          A career-orientation recommender prototype. © {new Date().getFullYear()}{" "}
          CareerGuide.
        </p>
      </div>
    </footer>
  );
}
