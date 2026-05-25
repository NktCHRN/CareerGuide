"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { XIcon } from "@/components/icons";
import { NavLinks, type NavItem } from "@/components/layout/nav-links";

export function MobileNav({ items }: { items: NavItem[] }) {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();

  // Close the panel whenever navigation happens.
  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  return (
    <div className="md:hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex h-9 w-9 items-center justify-center rounded-lg text-slate-600 hover:bg-slate-100"
        aria-label="Toggle navigation"
        aria-expanded={open}
      >
        {open ? (
          <XIcon className="text-xl" />
        ) : (
          <span className="flex flex-col gap-1">
            <span className="h-0.5 w-5 rounded bg-current" />
            <span className="h-0.5 w-5 rounded bg-current" />
            <span className="h-0.5 w-5 rounded bg-current" />
          </span>
        )}
      </button>

      {open && (
        <div className="absolute inset-x-0 top-16 z-40 border-b border-slate-200 bg-white p-3 shadow-lg">
          <nav className="flex flex-col gap-1">
            <NavLinks items={items} variant="mobile" />
          </nav>
        </div>
      )}
    </div>
  );
}
