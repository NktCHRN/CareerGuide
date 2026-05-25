"use client";

import { useEffect } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";

export default function AppError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="mx-auto max-w-md py-10">
      <Card>
        <CardBody className="text-center sm:px-8 sm:py-8">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-red-50 text-xl text-red-600">
            !
          </div>
          <h1 className="text-lg font-semibold text-slate-900">
            Something went wrong
          </h1>
          <p className="mt-1.5 text-sm text-slate-500">
            We couldn't load this page. This can happen if a service is briefly
            unavailable.
          </p>
          <div className="mt-6 flex justify-center">
            <Button onClick={reset}>Try again</Button>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
