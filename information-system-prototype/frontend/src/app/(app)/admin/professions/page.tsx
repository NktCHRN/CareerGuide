import type { Metadata } from "next";
import Link from "next/link";

import { DeleteProfessionButton } from "@/components/admin/delete-profession-button";
import { PlusIcon, SearchIcon } from "@/components/icons";
import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { buttonClasses } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Pagination } from "@/components/ui/pagination";
import { searchProfessions } from "@/lib/api/career";

export const metadata: Metadata = { title: "Manage professions" };

const PAGE_SIZE = 20;

function first(v: string | string[] | undefined): string | undefined {
  return Array.isArray(v) ? v[0] : v;
}

export default async function AdminProfessionsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = await searchParams;
  const query = first(sp.query)?.trim() || undefined;
  const page = Math.max(1, Number(first(sp.page)) || 1);

  const results = await searchProfessions({ query, page, page_size: PAGE_SIZE });

  return (
    <>
      <PageHeader
        title="Manage professions"
        description="Create, edit and remove professions in the catalogue (FR13–FR15)."
        actions={
          <Link href="/admin/professions/new" className={buttonClasses({ size: "sm" })}>
            <PlusIcon /> New profession
          </Link>
        }
      />

      <form method="get" className="relative mb-6 max-w-md">
        <SearchIcon className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-lg text-slate-400" />
        <input
          type="search"
          name="query"
          defaultValue={query ?? ""}
          placeholder="Search professions…"
          className="h-11 w-full rounded-lg border border-slate-300 bg-white pl-11 pr-3 text-sm text-slate-900 placeholder:text-slate-400 focus:border-brand-500 focus-visible:ring-2 focus-visible:ring-brand-500"
        />
      </form>

      {results.items.length === 0 ? (
        <EmptyState
          icon={<SearchIcon />}
          title="No professions found"
          description={query ? `Nothing matches “${query}”.` : "Create the first profession to get started."}
          action={
            <Link href="/admin/professions/new" className={buttonClasses({ size: "sm" })}>
              <PlusIcon /> New profession
            </Link>
          }
        />
      ) : (
        <>
          <Card className="divide-y divide-slate-100">
            {results.items.map((p) => (
              <div
                key={p.id}
                className="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-slate-50/70 sm:px-5"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium text-slate-900">
                    {p.preferred_label}
                  </p>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-400">
                    <span>#{p.id}</span>
                    {p.esco_code && <Badge tone="muted">ESCO {p.esco_code}</Badge>}
                    {p.isco_group != null && <span>ISCO {p.isco_group}</span>}
                  </div>
                </div>
                <Link
                  href={`/admin/professions/${p.id}/edit`}
                  className={buttonClasses({ variant: "outline", size: "sm" })}
                >
                  Edit
                </Link>
                <DeleteProfessionButton professionId={p.id} label={p.preferred_label} />
              </div>
            ))}
          </Card>
          <Pagination
            page={results.page}
            pageSize={results.page_size}
            total={results.total}
          />
        </>
      )}
    </>
  );
}
