import type { Metadata } from "next";

import { ProfessionListCard } from "@/components/professions/profession-list-card";
import { SearchBar } from "@/components/professions/search-bar";
import { SearchIcon } from "@/components/icons";
import { PageHeader } from "@/components/layout/page-header";
import { EmptyState } from "@/components/ui/empty-state";
import { Pagination } from "@/components/ui/pagination";
import { searchProfessions } from "@/lib/api/career";
import { getScores } from "@/lib/api/reco";

export const metadata: Metadata = { title: "Professions" };

const PAGE_SIZE = 12;

function first(v: string | string[] | undefined): string | undefined {
  return Array.isArray(v) ? v[0] : v;
}

export default async function ProfessionsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = await searchParams;
  const query = first(sp.query)?.trim() || undefined;
  const page = Math.max(1, Number(first(sp.page)) || 1);

  const results = await searchProfessions({ query, page, page_size: PAGE_SIZE });

  // FR9: float recommended professions to the top of the current results.
  let scores: Record<string, number> = {};
  if (results.items.length) {
    try {
      const res = await getScores(results.items.map((p) => p.id));
      if (res.ready) scores = res.scores;
    } catch {
      /* scoring is best-effort; ignore failures */
    }
  }

  const items = [...results.items].sort((a, b) => {
    const sa = scores[a.id];
    const sb = scores[b.id];
    if (sa != null && sb != null) return sb - sa;
    if (sa != null) return -1;
    if (sb != null) return 1;
    return 0;
  });

  return (
    <>
      <PageHeader
        title="Explore professions"
        description="Search the ESCO occupation catalogue. Professions recommended for you appear first."
      />

      <div className="mb-6">
        <SearchBar />
      </div>

      {results.items.length === 0 ? (
        <EmptyState
          icon={<SearchIcon />}
          title={query ? `No professions match “${query}”` : "No professions found"}
          description={
            query
              ? "Try a different or shorter search term."
              : "The catalogue appears to be empty."
          }
        />
      ) : (
        <>
          {query && (
            <p className="mb-4 text-sm text-slate-500">
              {results.total} result{results.total === 1 ? "" : "s"} for{" "}
              <span className="font-medium text-slate-700">“{query}”</span>
            </p>
          )}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {items.map((p) => (
              <ProfessionListCard
                key={p.id}
                profession={p}
                matchScore={scores[p.id]}
              />
            ))}
          </div>
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
