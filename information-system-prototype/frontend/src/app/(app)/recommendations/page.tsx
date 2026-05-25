import type { Metadata } from "next";
import Link from "next/link";

import { RecoFilters } from "@/components/reco/reco-filters";
import { RecommendationCard } from "@/components/reco/recommendation-card";
import { RecoStatus } from "@/components/reco/reco-status";
import { SparklesIcon } from "@/components/icons";
import { PageHeader } from "@/components/layout/page-header";
import { buttonClasses } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Pagination } from "@/components/ui/pagination";
import { getRecommendations, getRecoStatus } from "@/lib/api/reco";
import type { RecoOrder, RecoSort } from "@/lib/types";

export const metadata: Metadata = { title: "Recommendations" };

const SORTS = new Set<RecoSort>([
  "score",
  "vacancies_local",
  "vacancies_international",
  "avg_salary",
]);

const PAGE_SIZE = 10;

function first(v: string | string[] | undefined): string | undefined {
  return Array.isArray(v) ? v[0] : v;
}

export default async function RecommendationsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = await searchParams;

  const sortRaw = first(sp.sort) as RecoSort | undefined;
  const sort: RecoSort = sortRaw && SORTS.has(sortRaw) ? sortRaw : "score";
  const order: RecoOrder = first(sp.order) === "asc" ? "asc" : "desc";
  const page = Math.max(1, Number(first(sp.page)) || 1);
  const educationLevel = first(sp.education_level)?.trim() || undefined;
  const minVacancies = Number(first(sp.min_vacancies));
  const minSalary = Number(first(sp.min_avg_salary));

  const [status, results] = await Promise.all([
    getRecoStatus(),
    getRecommendations({
      sort,
      order,
      education_level: educationLevel,
      min_vacancies: Number.isFinite(minVacancies) && minVacancies > 0 ? minVacancies : undefined,
      min_avg_salary: Number.isFinite(minSalary) && minSalary > 0 ? minSalary : undefined,
      page,
      page_size: PAGE_SIZE,
    }),
  ]);

  return (
    <>
      <PageHeader
        title="Recommended professions"
        description="Careers ranked by how well they match your experience and skills."
        actions={
          <Link
            href="/recommendations/settings"
            className={buttonClasses({ variant: "outline", size: "sm" })}
          >
            Settings
          </Link>
        }
      />

      <RecoStatus initialReady={status.ready} />

      {status.ready ? (
        <>
          <div className="mb-6">
            <RecoFilters />
          </div>

          {results.items.length === 0 ? (
            <EmptyState
              icon={<SparklesIcon />}
              title="No professions match these filters"
              description="Try relaxing the filters, or add more detail to your profile to broaden your matches."
              action={
                <Link href="/recommendations" className={buttonClasses({ size: "sm" })}>
                  Clear filters
                </Link>
              }
            />
          ) : (
            <>
              <div className="space-y-3">
                {results.items.map((item, i) => (
                  <RecommendationCard
                    key={item.profession_id}
                    item={item}
                    rank={(page - 1) * PAGE_SIZE + i + 1}
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
      ) : (
        <EmptyState
          icon={<SparklesIcon />}
          title="We need a little more to go on"
          description="Add your work experience and skills (or upload a résumé) so we can compute your matches. They'll appear here automatically."
          action={
            <div className="flex flex-wrap justify-center gap-2">
              <Link href="/profile/edit" className={buttonClasses({ size: "sm" })}>
                Complete my profile
              </Link>
              <Link
                href="/professions"
                className={buttonClasses({ variant: "outline", size: "sm" })}
              >
                Browse all professions
              </Link>
            </div>
          }
        />
      )}
    </>
  );
}
