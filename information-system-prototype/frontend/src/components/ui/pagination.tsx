"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";

import { ChevronLeftIcon, ChevronRightIcon } from "@/components/icons";
import { cn } from "@/lib/cn";

/**
 * Query-string based pagination. Preserves all existing search params and only
 * swaps the `page` value, so it composes with search / sort / filter state.
 */
export function Pagination({
  page,
  pageSize,
  total,
}: {
  page: number;
  pageSize: number;
  total: number;
}) {
  const pathname = usePathname();
  const params = useSearchParams();
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  if (total === 0 || totalPages <= 1) return null;

  const hrefFor = (p: number) => {
    const next = new URLSearchParams(params.toString());
    next.set("page", String(p));
    return `${pathname}?${next.toString()}`;
  };

  const from = (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);

  return (
    <nav
      className="mt-6 flex items-center justify-between gap-4"
      aria-label="Pagination"
    >
      <p className="text-sm text-slate-500">
        <span className="font-medium text-slate-700">
          {from}–{to}
        </span>{" "}
        of {total}
      </p>
      <div className="flex items-center gap-2">
        <PageLink
          href={hrefFor(page - 1)}
          disabled={page <= 1}
          label="Previous page"
        >
          <ChevronLeftIcon className="text-base" />
        </PageLink>
        <span className="px-2 text-sm text-slate-600">
          Page {page} of {totalPages}
        </span>
        <PageLink
          href={hrefFor(page + 1)}
          disabled={page >= totalPages}
          label="Next page"
        >
          <ChevronRightIcon className="text-base" />
        </PageLink>
      </div>
    </nav>
  );
}

function PageLink({
  href,
  disabled,
  label,
  children,
}: {
  href: string;
  disabled: boolean;
  label: string;
  children: React.ReactNode;
}) {
  const className = cn(
    "inline-flex h-9 w-9 items-center justify-center rounded-lg border text-slate-600",
    disabled
      ? "pointer-events-none border-slate-100 bg-slate-50 text-slate-300"
      : "border-slate-300 bg-white hover:bg-slate-50",
  );
  if (disabled) {
    return (
      <span className={className} aria-disabled aria-label={label}>
        {children}
      </span>
    );
  }
  return (
    <Link href={href} className={className} aria-label={label}>
      {children}
    </Link>
  );
}
