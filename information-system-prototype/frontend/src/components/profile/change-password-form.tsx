"use client";

import { useActionState } from "react";

import {
  changePasswordAction,
  type ChangePasswordState,
} from "@/actions/profile";
import { Alert } from "@/components/ui/alert";
import { Field, Input } from "@/components/ui/field";
import { SubmitButton } from "@/components/ui/submit-button";

export function ChangePasswordForm() {
  const [state, action] = useActionState<ChangePasswordState, FormData>(
    changePasswordAction,
    {},
  );

  return (
    <form action={action} className="space-y-4">
      {state.error && <Alert variant="error">{state.error}</Alert>}
      {state.ok && (
        <Alert variant="success">Your password has been changed.</Alert>
      )}

      <Field label="Current password" htmlFor="old_password" required>
        <Input
          id="old_password"
          name="old_password"
          type="password"
          autoComplete="current-password"
          required
        />
      </Field>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="New password" htmlFor="new_password" required>
          <Input
            id="new_password"
            name="new_password"
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
      </div>

      <SubmitButton variant="outline" pendingText="Updating…">
        Update password
      </SubmitButton>
    </form>
  );
}
