"use client";

import Link from "next/link";
import { useActionState } from "react";

import { requestResetAction, type ResetRequestState } from "@/actions/auth";
import { Alert } from "@/components/ui/alert";
import { buttonClasses } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { SubmitButton } from "@/components/ui/submit-button";

export function RequestResetForm() {
  const [state, action] = useActionState<ResetRequestState, FormData>(
    requestResetAction,
    {},
  );

  if (state.ok) {
    return (
      <div className="space-y-5">
        <Alert variant="success" title="Check your inbox">
          If an account exists for that email, we've sent a link to reset your
          password.
        </Alert>
        {state.devToken && (
          <Alert variant="info" title="Development mode">
            <p className="mb-2">Use this link to set a new password:</p>
            <Link
              href={`/reset-password?token=${encodeURIComponent(state.devToken)}`}
              className={buttonClasses({ variant: "secondary", size: "sm" })}
            >
              Reset password
            </Link>
          </Alert>
        )}
        <div className="text-center">
          <Link
            href="/login"
            className="text-sm font-medium text-brand-600 hover:text-brand-700"
          >
            Back to sign in
          </Link>
        </div>
      </div>
    );
  }

  return (
    <form action={action} className="space-y-4">
      {state.error && <Alert variant="error">{state.error}</Alert>}
      <Field
        label="Email"
        htmlFor="email"
        hint="We'll send a reset link to this address."
      >
        <Input
          id="email"
          name="email"
          type="email"
          autoComplete="email"
          required
          placeholder="you@example.com"
        />
      </Field>
      <SubmitButton className="w-full" pendingText="Sending…">
        Send reset link
      </SubmitButton>
      <div className="text-center">
        <Link
          href="/login"
          className="text-sm font-medium text-slate-500 hover:text-slate-700"
        >
          Back to sign in
        </Link>
      </div>
    </form>
  );
}
