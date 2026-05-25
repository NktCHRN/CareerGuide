import type { Metadata } from "next";

import { RiasecTest } from "@/components/profile/riasec-test";
import { PageHeader } from "@/components/layout/page-header";
import { getProfile } from "@/lib/api/users";

export const metadata: Metadata = { title: "RIASEC test" };

export default async function RiasecPage() {
  const profile = await getProfile();

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title="RIASEC interest assessment"
        description="Discover your Holland interest type and how it relates to careers."
      />
      <RiasecTest existing={profile.riasec_result} />
    </div>
  );
}
