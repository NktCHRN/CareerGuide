import type { Metadata } from "next";

import { ResetPasswordForm } from "@/components/auth/reset-password-form";
import { Card, CardBody } from "@/components/ui/card";

export const metadata: Metadata = { title: "Set new password" };

export default async function ResetPasswordPage({
  searchParams,
}: {
  searchParams: Promise<{ token?: string }>;
}) {
  const { token } = await searchParams;

  return (
    <Card>
      <CardBody className="sm:px-8 sm:py-8">
        <div className="mb-6 text-center">
          <h1 className="text-xl font-semibold text-slate-900">
            Choose a new password
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Enter a new password for your account.
          </p>
        </div>
        <ResetPasswordForm token={token ?? ""} />
      </CardBody>
    </Card>
  );
}
