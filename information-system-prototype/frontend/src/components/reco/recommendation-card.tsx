import Link from "next/link";

import { GlobeIcon, GraduationIcon, MapPinIcon } from "@/components/icons";
import { Badge } from "@/components/ui/badge";
import { formatCount, formatMatch, formatSalary } from "@/lib/format";
import type { RecommendationItem } from "@/lib/types";

export function RecommendationCard({
  item,
  rank,
}: {
  item: RecommendationItem;
  rank: number;
}) {
  const matchPct = Math.round(Math.max(0, Math.min(1, item.score)) * 100);

  return (
    <Link
      href={`/professions/${item.profession_id}`}
      className="group flex items-center gap-4 rounded-[var(--radius-card)] border border-slate-200 bg-white p-4 shadow-[var(--shadow-card)] transition-all hover:border-brand-300 hover:shadow-[var(--shadow-card-hover)] sm:p-5"
    >
      {/* Match ring */}
      <div className="relative flex h-14 w-14 shrink-0 items-center justify-center">
        <svg viewBox="0 0 36 36" className="h-14 w-14 -rotate-90">
          <circle
            cx="18"
            cy="18"
            r="15.5"
            fill="none"
            className="stroke-slate-100"
            strokeWidth="3"
          />
          <circle
            cx="18"
            cy="18"
            r="15.5"
            fill="none"
            className="stroke-brand-500"
            strokeWidth="3"
            strokeLinecap="round"
            strokeDasharray={`${(matchPct / 100) * 97.4} 97.4`}
          />
        </svg>
        <span className="absolute text-sm font-semibold text-brand-700">
          {formatMatch(item.score)}
        </span>
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-slate-400">#{rank}</span>
          <h3 className="truncate font-semibold text-slate-900 group-hover:text-brand-700">
            {item.preferred_label ?? `Profession #${item.profession_id}`}
          </h3>
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-slate-500">
          {item.education_level && (
            <span className="inline-flex items-center gap-1">
              <GraduationIcon className="text-sm text-slate-400" />
              {item.education_level}
            </span>
          )}
          {item.avg_salary !== null && (
            <span className="inline-flex items-center gap-1">
              💼 {formatSalary(item.avg_salary)}
            </span>
          )}
          {item.vacancies_local !== null && (
            <span className="inline-flex items-center gap-1">
              <MapPinIcon className="text-sm text-slate-400" />
              {formatCount(item.vacancies_local)} local
            </span>
          )}
          {item.vacancies_international !== null && (
            <span className="inline-flex items-center gap-1">
              <GlobeIcon className="text-sm text-slate-400" />
              {formatCount(item.vacancies_international)} intl
            </span>
          )}
        </div>
      </div>

      <Badge tone="brand" className="hidden shrink-0 sm:inline-flex">
        View details →
      </Badge>
    </Link>
  );
}
