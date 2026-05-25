import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { formatMatch } from "@/lib/format";
import type { ProfessionListItem } from "@/lib/types";

export function ProfessionListCard({
  profession,
  matchScore,
}: {
  profession: ProfessionListItem;
  matchScore?: number;
}) {
  return (
    <Link
      href={`/professions/${profession.id}`}
      className="group flex h-full flex-col rounded-[var(--radius-card)] border border-slate-200 bg-white p-5 shadow-[var(--shadow-card)] transition-all hover:border-brand-300 hover:shadow-[var(--shadow-card-hover)]"
    >
      <div className="flex items-start justify-between gap-2">
        <h3 className="font-semibold text-slate-900 group-hover:text-brand-700">
          {profession.preferred_label}
        </h3>
        {matchScore !== undefined && (
          <Badge tone="brand" className="shrink-0">
            {formatMatch(matchScore)} match
          </Badge>
        )}
      </div>

      {profession.description && (
        <p className="mt-2 line-clamp-3 text-sm leading-relaxed text-slate-500">
          {profession.description}
        </p>
      )}

      {profession.alt_labels.length > 0 && (
        <p className="mt-3 line-clamp-1 text-xs text-slate-400">
          Also known as: {profession.alt_labels.slice(0, 3).join(", ")}
        </p>
      )}

      <span className="mt-auto pt-4 text-sm font-medium text-brand-600 group-hover:text-brand-700">
        View details →
      </span>
    </Link>
  );
}
