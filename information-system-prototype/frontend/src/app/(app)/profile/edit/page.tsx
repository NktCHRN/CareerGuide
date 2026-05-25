import type { Metadata } from "next";
import Link from "next/link";

import { ProfileEditor } from "@/components/profile/profile-editor";
import { ResumeUploader } from "@/components/profile/resume-uploader";
import { PageHeader } from "@/components/layout/page-header";
import { buttonClasses } from "@/components/ui/button";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { getIndustries, getProfile } from "@/lib/api/users";
import { INDUSTRY_OPTIONS } from "@/lib/industries";
import type { IndustryOption } from "@/lib/types";

export const metadata: Metadata = { title: "Edit profile" };

export default async function EditProfilePage() {
  const profile = await getProfile();

  let industries: IndustryOption[] = INDUSTRY_OPTIONS;
  try {
    industries = (await getIndustries()).items;
  } catch {
    /* fall back to the bundled list */
  }

  return (
    <>
      <PageHeader
        title="Edit profile"
        description="Update your details manually, or upload a résumé to fill them in automatically."
        actions={
          <Link href="/profile" className={buttonClasses({ variant: "outline", size: "sm" })}>
            Back to profile
          </Link>
        }
      />

      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Upload a résumé</CardTitle>
        </CardHeader>
        <CardBody>
          <p className="mb-4 text-sm text-slate-500">
            Upload a PDF and we'll parse your experience and skills with AI. Parsing
            runs in the background — your profile updates automatically when it's
            done. You can always fine-tune the fields below afterwards.
          </p>
          <ResumeUploader />
        </CardBody>
      </Card>

      <ProfileEditor profile={profile} industries={industries} />
    </>
  );
}
