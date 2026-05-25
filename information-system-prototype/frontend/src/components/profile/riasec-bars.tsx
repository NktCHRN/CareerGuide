import { cn } from "@/lib/cn";
import { RIASEC_DIMENSIONS, RIASEC_MAX_PER_DIM } from "@/lib/riasec";
import type { RiasecResult } from "@/lib/types";

export function RiasecBars({ result }: { result: RiasecResult }) {
  const top = result.top.slice(0, 3);
  return (
    <div className="space-y-3">
      {RIASEC_DIMENSIONS.map((d) => {
        const score = result.scores[d.letter] ?? 0;
        const pct = Math.round((score / RIASEC_MAX_PER_DIM) * 100);
        const isTop = top.includes(d.letter);
        return (
          <div key={d.letter}>
            <div className="mb-1 flex items-center justify-between text-xs">
              <span
                className={cn(
                  isTop ? "font-semibold text-slate-800" : "text-slate-600",
                )}
              >
                <span className="font-mono">{d.letter}</span> · {d.name}
              </span>
              <span className="text-slate-400">{pct}%</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-slate-100">
              <div
                className={cn(
                  "h-full rounded-full transition-all",
                  isTop ? "bg-brand-600" : "bg-brand-300",
                )}
                style={{ width: `${Math.max(pct, 2)}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
