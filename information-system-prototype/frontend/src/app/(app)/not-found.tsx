import Link from "next/link";

import { buttonClasses } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-md py-10">
      <Card>
        <CardBody className="text-center sm:px-8 sm:py-8">
          <p className="text-4xl font-bold text-brand-600">404</p>
          <h1 className="mt-2 text-lg font-semibold text-slate-900">
            Page not found
          </h1>
          <p className="mt-1.5 text-sm text-slate-500">
            The page or item you're looking for doesn't exist or may have been
            removed.
          </p>
          <div className="mt-6 flex justify-center gap-2">
            <Link href="/recommendations" className={buttonClasses({})}>
              Go to recommendations
            </Link>
            <Link
              href="/professions"
              className={buttonClasses({ variant: "outline" })}
            >
              Browse professions
            </Link>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
