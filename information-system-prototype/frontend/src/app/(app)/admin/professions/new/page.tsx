import type { Metadata } from "next";
import Link from "next/link";

import { ProfessionForm } from "@/components/admin/profession-form";
import { ChevronLeftIcon } from "@/components/icons";
import { PageHeader } from "@/components/layout/page-header";

export const metadata: Metadata = { title: "New profession" };

export default function NewProfessionPage() {
  return (
    <>
      <Link
        href="/admin/professions"
        className="mb-3 inline-flex items-center gap-1 text-sm font-medium text-slate-500 hover:text-slate-700"
      >
        <ChevronLeftIcon /> Manage professions
      </Link>
      <PageHeader
        title="New profession"
        description="Add a profession to the catalogue. Only the preferred label is required; you can add a photo after creating it."
      />
      <ProfessionForm mode="create" />
    </>
  );
}
