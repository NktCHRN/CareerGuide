"use client";

import { useRouter } from "next/navigation";

import { deleteProfessionAction } from "@/actions/admin";
import { TrashIcon } from "@/components/icons";
import { Button } from "@/components/ui/button";
import { ConfirmButton } from "@/components/ui/confirm-button";

export function DeleteProfessionButton({
  professionId,
  label,
  variant = "icon",
}: {
  professionId: number;
  label: string;
  variant?: "icon" | "button";
}) {
  const router = useRouter();

  return (
    <ConfirmButton
      title="Delete profession"
      message={
        <>
          Delete <span className="font-medium">“{label}”</span>? This removes it
          from the catalogue and from recommendations. This cannot be undone.
        </>
      }
      confirmLabel="Delete profession"
      onConfirm={async () => {
        await deleteProfessionAction(professionId);
        router.push("/admin/professions");
        router.refresh();
      }}
      trigger={(open) =>
        variant === "icon" ? (
          <button
            type="button"
            onClick={open}
            className="rounded-md p-2 text-slate-400 transition-colors hover:bg-red-50 hover:text-red-600"
            aria-label={`Delete ${label}`}
          >
            <TrashIcon className="text-base" />
          </button>
        ) : (
          <Button variant="danger" onClick={open}>
            <TrashIcon /> Delete
          </Button>
        )
      }
    />
  );
}
