import { Badge } from "@/components/ui/badge";

type Tone = "brand" | "neutral" | "success" | "warning" | "danger" | "muted";

export function ChipList({
  items,
  tone = "neutral",
  empty = "Not provided",
}: {
  items: string[] | null | undefined;
  tone?: Tone;
  empty?: string;
}) {
  if (!items || items.length === 0) {
    return <p className="text-sm text-slate-400">{empty}</p>;
  }
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((item) => (
        <Badge key={item} tone={tone}>
          {item}
        </Badge>
      ))}
    </div>
  );
}
