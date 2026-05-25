import type { Metadata } from "next";
import Link from "next/link";

import { LoginForm } from "@/components/auth/login-form";
import { Card, CardBody } from "@/components/ui/card";

export const metadata: Metadata = { title: "Sign in" };

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string }>;
}) {
  const { next } = await searchParams;

  return (
    <Card>
      <CardBody className="sm:px-8 sm:py-8">
        <div className="mb-6 text-center">
          <h1 className="text-xl font-semibold text-slate-900">Welcome back</h1>
          <p className="mt-1 text-sm text-slate-500">
            Sign in to continue to your recommendations.
          </p>
        </div>
        <LoginForm next={next} />
        <p className="mt-6 text-center text-sm text-slate-500">
          New to CareerGuide?{" "}
          <Link href="/register" className="font-medium text-brand-600 hover:text-brand-700">
            Create an account
          </Link>
        </p>
      </CardBody>
    </Card>
  );
}
