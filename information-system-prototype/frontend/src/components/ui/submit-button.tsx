"use client";

import { useFormStatus } from "react-dom";

import { Button, type ButtonProps } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";

/**
 * Submit button bound to the enclosing <form>'s pending state (Server Actions).
 * Shows a spinner and disables itself while the action runs.
 */
export function SubmitButton({
  children,
  pendingText,
  disabled,
  ...props
}: ButtonProps & { pendingText?: string }) {
  const { pending } = useFormStatus();
  return (
    <Button type="submit" disabled={pending || disabled} {...props}>
      {pending && <Spinner />}
      {pending ? (pendingText ?? children) : children}
    </Button>
  );
}
