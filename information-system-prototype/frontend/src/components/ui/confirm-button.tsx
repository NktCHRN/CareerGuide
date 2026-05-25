"use client";

import { useState, useTransition, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { Spinner } from "@/components/ui/spinner";

/**
 * Renders a trigger button that asks for confirmation in a modal before
 * running `onConfirm` (typically a Server Action). Used for destructive
 * actions such as deleting a profession or a chat (FR14/FR19).
 */
export function ConfirmButton({
  onConfirm,
  title,
  message,
  confirmLabel = "Delete",
  trigger,
}: {
  onConfirm: () => Promise<void> | void;
  title: string;
  message: ReactNode;
  confirmLabel?: string;
  trigger: (open: () => void) => ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const [pending, startTransition] = useTransition();

  const confirm = () => {
    startTransition(async () => {
      await onConfirm();
      setOpen(false);
    });
  };

  return (
    <>
      {trigger(() => setOpen(true))}
      <Modal
        open={open}
        onClose={() => !pending && setOpen(false)}
        title={title}
        footer={
          <>
            <Button
              variant="outline"
              onClick={() => setOpen(false)}
              disabled={pending}
            >
              Cancel
            </Button>
            <Button variant="danger" onClick={confirm} disabled={pending}>
              {pending && <Spinner />}
              {confirmLabel}
            </Button>
          </>
        }
      >
        {message}
      </Modal>
    </>
  );
}
