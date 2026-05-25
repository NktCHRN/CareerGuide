import Link from "next/link";

import { Logo } from "@/components/brand/logo";
import { MobileNav } from "@/components/layout/mobile-nav";
import { NavLinks, type NavItem } from "@/components/layout/nav-links";
import { UserMenu } from "@/components/layout/user-menu";
import type { Session } from "@/lib/auth/session";

export function Header({ session }: { session: Session }) {
  const items: NavItem[] = [
    { href: "/recommendations", label: "Recommendations", icon: "recommendations" },
    { href: "/professions", label: "Professions", icon: "professions" },
    { href: "/chats", label: "Chats", icon: "chats" },
  ];
  if (session.role === "admin") {
    items.push({ href: "/admin/professions", label: "Admin", icon: "admin" });
  }

  return (
    <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/90 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center gap-4 px-4 sm:px-6">
        <Link href="/recommendations" aria-label="CareerGuide home">
          <Logo />
        </Link>

        <nav className="ml-4 hidden items-center gap-1 md:flex">
          <NavLinks items={items} />
        </nav>

        <div className="ml-auto flex items-center gap-2">
          <UserMenu email={session.email} role={session.role} />
          <MobileNav items={items} />
        </div>
      </div>
    </header>
  );
}
