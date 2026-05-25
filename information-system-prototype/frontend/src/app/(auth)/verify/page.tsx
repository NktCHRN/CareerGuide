import type { Metadata } from "next";
import Link from "next/link";

import { Alert } from "@/components/ui/alert";
import { buttonClasses } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { verifyEmail } from "@/lib/api/users";

export const metadata: Metadata = { title: "Verify email" };

export default async function VerifyPage({
  searchParams,
}: {
  searchParams: Promise<{ token?: string }>;
}) {
  const { token } = await searchParams;

  let ok = false;
  if (token) {
    try {
      await verifyEmail(token);
      ok = true;
    } catch {
      ok = false;
    }
  }

  return (
    <Card>
      <CardBody className="sm:px-8 sm:py-8">
        <div className="mb-6 text-center">
          <h1 className="text-xl font-semibold text-slate-900">Email verification</h1>
        </div>

        {ok ? (
          <Alert variant="success" title="Email verified">
            Thank you — your email address has been confirmed.
          </Alert>
        ) : (
          <Alert variant="error" title="Verification failed">
            This verification link is missing, invalid, or has expired. You can
            request a new one from your profile after signing in.
          </Alert>
        )}

        <div className="mt-6 flex justify-center gap-2">
          <Link href="/recommendations" className={buttonClasses({})}>
            Go to recommendations
          </Link>
          <Link href="/login" className={buttonClasses({ variant: "outline" })}>
            Sign in
          </Link>
        </div>
      </CardBody>
    </Card>
  );
}
