import type { Metadata } from "next";

import { RequestResetForm } from "@/components/auth/request-reset-form";
import { Card, CardBody } from "@/components/ui/card";

export const metadata: Metadata = { title: "Forgot password" };

export default function ForgotPasswordPage() {
  return (
    <Card>
      <CardBody className="sm:px-8 sm:py-8">
        <div className="mb-6 text-center">
          <h1 className="text-xl font-semibold text-slate-900">
            Reset your password
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Enter your email and we'll send you a reset link.
          </p>
        </div>
        <RequestResetForm />
      </CardBody>
    </Card>
  );
}
