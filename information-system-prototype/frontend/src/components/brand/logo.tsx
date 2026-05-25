import { CompassIcon } from "@/components/icons";
import { cn } from "@/lib/cn";

export function Logo({
  withText = true,
  className,
}: {
  withText?: boolean;
  className?: string;
}) {
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-white shadow-sm">
        <CompassIcon className="text-lg" />
      </span>
      {withText && (
        <span className="text-lg font-semibold tracking-tight text-slate-900">
          Career<span className="text-brand-600">Guide</span>
        </span>
      )}
    </span>
  );
}
