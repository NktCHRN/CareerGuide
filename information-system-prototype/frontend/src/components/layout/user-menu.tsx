"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { logoutAction } from "@/actions/auth";
import {
  CompassIcon,
  LogoutIcon,
  SettingsIcon,
  UserIcon,
} from "@/components/icons";
import { Badge } from "@/components/ui/badge";
import { initials } from "@/lib/format";

export function UserMenu({
  email,
  role,
}: {
  email: string;
  role: "user" | "admin";
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-600 text-sm font-semibold text-white transition-transform hover:scale-105"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Account menu"
      >
        {initials(null, email)}
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 z-50 mt-2 w-60 animate-fade-in-up rounded-xl border border-slate-200 bg-white p-1.5 shadow-lg"
        >
          <div className="px-3 py-2">
            <p className="truncate text-sm font-medium text-slate-900">{email}</p>
            {role === "admin" && (
              <Badge tone="brand" className="mt-1">
                Administrator
              </Badge>
            )}
          </div>
          <div className="my-1 h-px bg-slate-100" />
          <MenuLink href="/profile" onClick={() => setOpen(false)}>
            <UserIcon className="text-base text-slate-400" />
            My profile
          </MenuLink>
          <MenuLink href="/riasec" onClick={() => setOpen(false)}>
            <CompassIcon className="text-base text-slate-400" />
            RIASEC test
          </MenuLink>
          <MenuLink href="/recommendations/settings" onClick={() => setOpen(false)}>
            <SettingsIcon className="text-base text-slate-400" />
            Recommendation settings
          </MenuLink>
          <div className="my-1 h-px bg-slate-100" />
          <form action={logoutAction}>
            <button
              type="submit"
              role="menuitem"
              className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-100"
            >
              <LogoutIcon className="text-base text-slate-400" />
              Log out
            </button>
          </form>
        </div>
      )}
    </div>
  );
}

function MenuLink({
  href,
  onClick,
  children,
}: {
  href: string;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      role="menuitem"
      onClick={onClick}
      className="flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-slate-700 hover:bg-slate-100"
    >
      {children}
    </Link>
  );
}
