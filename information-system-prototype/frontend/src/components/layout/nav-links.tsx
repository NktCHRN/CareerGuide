"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import {
  ChatIcon,
  SearchIcon,
  SettingsIcon,
  SparklesIcon,
} from "@/components/icons";
import { cn } from "@/lib/cn";

const ICONS = {
  recommendations: SparklesIcon,
  professions: SearchIcon,
  chats: ChatIcon,
  admin: SettingsIcon,
} as const;

export interface NavItem {
  href: string;
  label: string;
  icon: keyof typeof ICONS;
}

export function NavLinks({
  items,
  variant = "desktop",
}: {
  items: NavItem[];
  variant?: "desktop" | "mobile";
}) {
  const pathname = usePathname();

  return (
    <>
      {items.map((item) => {
        const Icon = ICONS[item.icon];
        const active =
          pathname === item.href || pathname.startsWith(`${item.href}/`);
        return (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "inline-flex items-center gap-2 rounded-lg text-sm font-medium transition-colors",
              variant === "desktop" ? "px-3 py-2" : "px-3 py-2.5",
              active
                ? "bg-brand-50 text-brand-700"
                : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
            )}
            aria-current={active ? "page" : undefined}
          >
            <Icon className="text-base" />
            {item.label}
          </Link>
        );
      })}
    </>
  );
}
