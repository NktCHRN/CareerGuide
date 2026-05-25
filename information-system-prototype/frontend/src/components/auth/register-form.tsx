"use client";

import Link from "next/link";
import { useActionState } from "react";

import { registerAction, type RegisterState } from "@/actions/auth";
import { BriefcaseIcon, UploadIcon } from "@/components/icons";
import { Alert } from "@/components/ui/alert";
import { buttonClasses } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { SubmitButton } from "@/components/ui/submit-button";

export function RegisterForm() {
  const [state, action] = useActionState<RegisterState, FormData>(
    registerAction,
    {},
  );

  if (state.ok) {
    return <RegisterSuccess state={state} />;
  }

  return (
    <form action={action} className="space-y-4">
      {state.error && <Alert variant="error">{state.error}</Alert>}

      <Field label="Full name" htmlFor="name" hint="Optional — you can add this later.">
        <Input id="name" name="name" autoComplete="name" placeholder="Jane Doe" />
      </Field>

      <Field label="Email" htmlFor="email" required>
        <Input
          id="email"
          name="email"
          type="email"
          autoComplete="email"
          required
          placeholder="you@example.com"
        />
      </Field>

      <Field
        label="Password"
        htmlFor="password"
        required
        hint="At least 8 characters."
      >
        <Input
          id="password"
          name="password"
          type="password"
          autoComplete="new-password"
          required
          minLength={8}
        />
      </Field>

      <Field label="Confirm password" htmlFor="confirm" required>
        <Input
          id="confirm"
          name="confirm"
          type="password"
          autoComplete="new-password"
          required
          minLength={8}
        />
      </Field>

      <SubmitButton className="w-full" pendingText="Creating account…">
        Create account
      </SubmitButton>
    </form>
  );
}

function RegisterSuccess({ state }: { state: RegisterState }) {
  return (
    <div className="space-y-5">
      <Alert variant="success" title="Your account is ready">
        You can start using CareerGuide right away — confirming your email is
        recommended but not required.
      </Alert>

      {state.verificationToken ? (
        <Alert variant="info" title="Verify your email">
          <p className="mb-2">
            A verification link was generated (development mode):
          </p>
          <Link
            href={`/verify?token=${encodeURIComponent(state.verificationToken)}`}
            className={buttonClasses({ variant: "secondary", size: "sm" })}
          >
            Verify my email now
          </Link>
        </Alert>
      ) : (
        <Alert variant="info" title="Check your inbox">
          We sent a verification link to{" "}
          <span className="font-medium">{state.email}</span>.
        </Alert>
      )}

      <div>
        <p className="mb-3 text-sm font-medium text-slate-700">
          Next, set up your profile so we can recommend professions:
        </p>
        <div className="grid gap-3 sm:grid-cols-2">
          <NextStep
            href="/profile/edit"
            icon={<BriefcaseIcon className="text-lg" />}
            title="Fill in your profile"
            body="Add your experience, skills and interests manually."
          />
          <NextStep
            href="/profile/edit?upload=1"
            icon={<UploadIcon className="text-lg" />}
            title="Upload your CV"
            body="We'll parse your PDF résumé and pre-fill your profile."
          />
        </div>
      </div>

      <div className="text-center">
        <Link
          href="/recommendations"
          className="text-sm font-medium text-slate-500 hover:text-slate-700"
        >
          Skip for now
        </Link>
      </div>
    </div>
  );
}

function NextStep({
  href,
  icon,
  title,
  body,
}: {
  href: string;
  icon: React.ReactNode;
  title: string;
  body: string;
}) {
  return (
    <Link
      href={href}
      className="group rounded-xl border border-slate-200 bg-white p-4 transition-colors hover:border-brand-300 hover:bg-brand-50/40"
    >
      <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50 text-brand-600 group-hover:bg-brand-100">
        {icon}
      </span>
      <span className="mt-3 block text-sm font-semibold text-slate-900">
        {title}
      </span>
      <span className="mt-1 block text-xs text-slate-500">{body}</span>
    </Link>
  );
}
