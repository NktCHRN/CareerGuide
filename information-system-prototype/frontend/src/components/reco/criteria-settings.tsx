"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { saveCriteriaAction } from "@/actions/profile";
import { CheckIcon } from "@/components/icons";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import {
  ALL_CRITERIA,
  CRITERIA_DESCRIPTIONS,
  CRITERIA_FUNCTIONAL,
  CRITERIA_LABELS,
} from "@/lib/criteria";
import { cn } from "@/lib/cn";
import type { RecommendationCriterion } from "@/lib/types";

export function CriteriaSettings({
  initial,
}: {
  initial: RecommendationCriterion[];
}) {
  const router = useRouter();
  const [selected, setSelected] = useState<Set<RecommendationCriterion>>(
    new Set(initial.length ? initial : ["experience"]),
  );
  const [result, setResult] = useState<{ ok?: boolean; error?: string }>({});
  const [pending, startTransition] = useTransition();

  const toggle = (c: RecommendationCriterion) => {
    setResult({});
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(c)) next.delete(c);
      else next.add(c);
      return next;
    });
  };

  const save = () => {
    const list = Array.from(selected);
    const payload = list.length ? list : (["experience"] as RecommendationCriterion[]);
    startTransition(async () => {
      const res = await saveCriteriaAction(payload);
      setResult(res);
      if (res.ok) router.refresh();
    });
  };

  return (
    <div className="space-y-5">
      {result.error && <Alert variant="error">{result.error}</Alert>}
      {result.ok && (
        <Alert variant="success">
          Your recommendation criteria were updated. Matches are recomputing in
          the background.
        </Alert>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        {ALL_CRITERIA.map((c) => {
          const active = selected.has(c);
          const functional = CRITERIA_FUNCTIONAL.includes(c);
          return (
            <button
              key={c}
              type="button"
              onClick={() => toggle(c)}
              className={cn(
                "flex gap-3 rounded-xl border p-4 text-left transition-colors",
                active
                  ? "border-brand-400 bg-brand-50/60 ring-1 ring-brand-200"
                  : "border-slate-200 bg-white hover:border-slate-300",
              )}
              aria-pressed={active}
            >
              <span
                className={cn(
                  "mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md border",
                  active
                    ? "border-brand-600 bg-brand-600 text-white"
                    : "border-slate-300 bg-white text-transparent",
                )}
              >
                <CheckIcon className="text-xs" />
              </span>
              <span className="min-w-0">
                <span className="flex flex-wrap items-center gap-2">
                  <span className="font-medium text-slate-900">
                    {CRITERIA_LABELS[c]}
                  </span>
                  {functional ? (
                    <Badge tone="success">Active</Badge>
                  ) : (
                    <Badge tone="muted">Needs data</Badge>
                  )}
                </span>
                <span className="mt-1 block text-xs leading-relaxed text-slate-500">
                  {CRITERIA_DESCRIPTIONS[c]}
                </span>
              </span>
            </button>
          );
        })}
      </div>

      <Alert variant="info">
        In this prototype, recommendations are driven by your{" "}
        <strong>previous experience &amp; skills</strong>. The other criteria can
        be selected to express your preference, but don't yet change the ranking.
      </Alert>

      <div className="flex justify-end">
        <Button onClick={save} disabled={pending}>
          {pending && <Spinner />}
          {pending ? "Saving…" : "Save settings"}
        </Button>
      </div>
    </div>
  );
}
