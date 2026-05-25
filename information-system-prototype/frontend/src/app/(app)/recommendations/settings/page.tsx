import type { Metadata } from "next";
import Link from "next/link";

import { CriteriaSettings } from "@/components/reco/criteria-settings";
import { PageHeader } from "@/components/layout/page-header";
import { buttonClasses } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { getProfile } from "@/lib/api/users";

export const metadata: Metadata = { title: "Recommendation settings" };

export default async function RecommendationSettingsPage() {
  const profile = await getProfile();

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title="Recommendation settings"
        description="Choose which aspects of your profile should shape your recommendations (FR8)."
        actions={
          <Link
            href="/recommendations"
            className={buttonClasses({ variant: "outline", size: "sm" })}
          >
            Back
          </Link>
        }
      />
      <Card>
        <CardBody>
          <CriteriaSettings initial={profile.recommendation_criteria} />
        </CardBody>
      </Card>
    </div>
  );
}
