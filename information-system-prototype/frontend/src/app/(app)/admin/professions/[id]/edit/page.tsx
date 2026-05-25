import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { DeleteProfessionButton } from "@/components/admin/delete-profession-button";
import { PhotoUploader } from "@/components/admin/photo-uploader";
import { ProfessionForm } from "@/components/admin/profession-form";
import { ChevronLeftIcon } from "@/components/icons";
import { PageHeader } from "@/components/layout/page-header";
import { buttonClasses } from "@/components/ui/button";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { getProfession } from "@/lib/api/career";
import { ApiError } from "@/lib/api/errors";

export const metadata: Metadata = { title: "Edit profession" };

export default async function EditProfessionPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id: idParam } = await params;
  const id = Number(idParam);
  if (!Number.isInteger(id)) notFound();

  let profession;
  try {
    profession = await getProfession(id);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) notFound();
    throw err;
  }

  return (
    <>
      <Link
        href="/admin/professions"
        className="mb-3 inline-flex items-center gap-1 text-sm font-medium text-slate-500 hover:text-slate-700"
      >
        <ChevronLeftIcon /> Manage professions
      </Link>
      <PageHeader
        title={profession.preferred_label}
        description={`Editing profession #${profession.id}.`}
        actions={
          <div className="flex items-center gap-2">
            <Link
              href={`/professions/${profession.id}`}
              className={buttonClasses({ variant: "outline", size: "sm" })}
            >
              View public page
            </Link>
            <DeleteProfessionButton
              professionId={profession.id}
              label={profession.preferred_label}
              variant="button"
            />
          </div>
        }
      />

      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Photo</CardTitle>
        </CardHeader>
        <CardBody>
          <PhotoUploader professionId={profession.id} currentUrl={profession.photo_url} />
        </CardBody>
      </Card>

      <ProfessionForm mode="edit" initial={profession} />
    </>
  );
}
