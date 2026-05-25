"use client";

import Link from "next/link";
import { useActionState } from "react";

import { resetPasswordAction, type ResetPasswordState } from "@/actions/auth";
import { Alert } from "@/components/ui/alert";
import { buttonClasses } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { SubmitButton } from "@/components/ui/submit-button";

export function ResetPasswordForm({ token }: { token: string }) {
  const [state, action] = useActionState<ResetPasswordState, FormData>(
    resetPasswordAction,
    {},
  );

  if (state.ok) {
    return (
      <div className="space-y-5">
        <Alert variant="success" title="Password updated">
          Your password has been changed. You can now sign in with your new
          password.
        </Alert>
        <Link href="/login" className={buttonClasses({ className: "w-full" })}>
          Go to sign in
        </Link>
      </div>
    );
  }

  if (!token) {
    return (
      <Alert variant="error" title="Missing token">
        This reset link is incomplete. Please request a new one from the{" "}
        <Link href="/forgot-password" className="underline">
          forgot password
        </Link>{" "}
        page.
      </Alert>
    );
  }

  return (
    <form action={action} className="space-y-4">
      {state.error && <Alert variant="error">{state.error}</Alert>}
      <input type="hidden" name="token" value={token} />

      <Field label="New password" htmlFor="password" required hint="At least 8 characters.">
        <Input
          id="password"
          name="password"
          type="password"
          autoComplete="new-password"
          required
          minLength={8}
        />
      </Field>

      <Field label="Confirm new password" htmlFor="confirm" required>
        <Input
          id="confirm"
          name="confirm"
          type="password"
          autoComplete="new-password"
          required
          minLength={8}
        />
      </Field>

      <SubmitButton className="w-full" pendingText="Updating…">
        Set new password
      </SubmitButton>
    </form>
  );
}
