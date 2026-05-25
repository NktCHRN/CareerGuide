import type { Metadata } from "next";
import Link from "next/link";

import { ChangePasswordForm } from "@/components/profile/change-password-form";
import { RiasecBars } from "@/components/profile/riasec-bars";
import {
  BriefcaseIcon,
  CompassIcon,
  GraduationIcon,
} from "@/components/icons";
import { PageHeader } from "@/components/layout/page-header";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { buttonClasses } from "@/components/ui/button";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { ChipList } from "@/components/ui/chip-list";
import { criterionLabel } from "@/lib/criteria";
import {
  formatDate,
  formatExperienceLength,
  formatPeriod,
  initials,
} from "@/lib/format";
import { industryLabel } from "@/lib/industries";
import { getProfile, listResumes } from "@/lib/api/users";
import { RIASEC_NAMES } from "@/lib/riasec";

export const metadata: Metadata = { title: "My profile" };

export default async function ProfilePage() {
  const [profile, resumes] = await Promise.all([getProfile(), listResumes()]);

  const profileSparse =
    !profile.summary &&
    profile.skills.length === 0 &&
    profile.experiences.length === 0;

  return (
    <>
      <PageHeader
        title="My profile"
        description="Everything CareerGuide knows about you. Keep it up to date for sharper recommendations."
        actions={
          <Link href="/profile/edit" className={buttonClasses({ size: "sm" })}>
            Edit profile
          </Link>
        }
      />

      {resumes.length > 0 && profileSparse && (
        <Alert variant="info" title="Your résumé is being processed" className="mb-6">
          We're parsing your uploaded résumé in the background. Your profile will
          fill in shortly — reload this page in a moment.
        </Alert>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Sidebar */}
        <div className="space-y-6 lg:order-last">
          <Card>
            <CardBody className="text-center">
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-brand-600 text-xl font-semibold text-white">
                {initials(profile.name, profile.email)}
              </div>
              <h2 className="mt-3 text-lg font-semibold text-slate-900">
                {profile.name || "Unnamed user"}
              </h2>
              <p className="text-sm text-slate-500">{profile.email}</p>
              <div className="mt-3 flex flex-wrap justify-center gap-1.5">
                {profile.email_verified ? (
                  <Badge tone="success">Email verified</Badge>
                ) : (
                  <Badge tone="warning">Email not verified</Badge>
                )}
                {profile.role === "admin" && <Badge tone="brand">Administrator</Badge>}
              </div>
            </CardBody>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Recommendation criteria</CardTitle>
            </CardHeader>
            <CardBody className="space-y-3">
              <div className="flex flex-wrap gap-1.5">
                {profile.recommendation_criteria.map((c) => (
                  <Badge key={c} tone="brand">
                    {criterionLabel(c)}
                  </Badge>
                ))}
              </div>
              <Link
                href="/recommendations/settings"
                className="inline-block text-sm font-medium text-brand-600 hover:text-brand-700"
              >
                Change criteria →
              </Link>
            </CardBody>
          </Card>

          <Card>
            <CardHeader className="flex items-center justify-between">
              <CardTitle>RIASEC type</CardTitle>
              <Link
                href="/riasec"
                className="text-xs font-medium text-brand-600 hover:text-brand-700"
              >
                {profile.riasec_result ? "Retake" : "Take test"}
              </Link>
            </CardHeader>
            <CardBody>
              {profile.riasec_result ? (
                <>
                  <div className="mb-4 flex items-center gap-3">
                    <span className="flex h-11 items-center rounded-lg bg-brand-50 px-3 font-mono text-lg font-bold tracking-widest text-brand-700">
                      {profile.riasec_result.code}
                    </span>
                    <p className="text-xs text-slate-500">
                      {profile.riasec_result.top
                        .slice(0, 3)
                        .map((l) => RIASEC_NAMES[l])
                        .join(" · ")}
                    </p>
                  </div>
                  <RiasecBars result={profile.riasec_result} />
                </>
              ) : (
                <div className="flex flex-col items-center py-2 text-center">
                  <CompassIcon className="text-2xl text-brand-300" />
                  <p className="mt-2 text-sm text-slate-500">
                    Discover your Holland interest type.
                  </p>
                  <Link
                    href="/riasec"
                    className={buttonClasses({ variant: "secondary", size: "sm", className: "mt-3" })}
                  >
                    Take the RIASEC test
                  </Link>
                </div>
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <GraduationIcon className="text-slate-400" /> Education
              </CardTitle>
            </CardHeader>
            <CardBody>
              {profile.education &&
              (profile.education.level ||
                profile.education.field ||
                profile.education.university) ? (
                <dl className="space-y-2 text-sm">
                  <Row label="Level" value={profile.education.level} />
                  <Row label="Field" value={profile.education.field} />
                  <Row label="Institution" value={profile.education.university} />
                  <Row label="Years" value={profile.education.years} />
                </dl>
              ) : (
                <p className="text-sm text-slate-400">No education details yet.</p>
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Résumés</CardTitle>
            </CardHeader>
            <CardBody>
              {resumes.length === 0 ? (
                <p className="text-sm text-slate-400">No résumé uploaded.</p>
              ) : (
                <ul className="space-y-2">
                  {resumes.map((r) => (
                    <li
                      key={r.id}
                      className="flex items-center justify-between gap-2 text-sm"
                    >
                      <span className="text-slate-600">
                        Uploaded {formatDate(r.uploaded_at)}
                      </span>
                      {r.download_url && (
                        <a
                          href={r.download_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="font-medium text-brand-600 hover:text-brand-700"
                        >
                          Download
                        </a>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </CardBody>
          </Card>
        </div>

        {/* Main */}
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle>About</CardTitle>
            </CardHeader>
            <CardBody className="space-y-4">
              <div>
                <p className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-400">
                  Professional summary
                </p>
                {profile.summary ? (
                  <p className="text-sm leading-relaxed text-slate-700">
                    {profile.summary}
                  </p>
                ) : (
                  <p className="text-sm text-slate-400">No summary yet.</p>
                )}
              </div>
              <div>
                <p className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-400">
                  Work style
                </p>
                <p className="text-sm text-slate-700">
                  {profile.work_style || (
                    <span className="text-slate-400">Not provided</span>
                  )}
                </p>
              </div>
            </CardBody>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BriefcaseIcon className="text-slate-400" /> Experience
              </CardTitle>
            </CardHeader>
            <CardBody>
              {profile.experiences.length === 0 ? (
                <p className="text-sm text-slate-400">
                  No work experience added yet.
                </p>
              ) : (
                <ol className="space-y-5">
                  {profile.experiences.map((exp) => (
                    <li key={exp.id} className="relative border-l-2 border-brand-100 pl-4">
                      <span className="absolute -left-[5px] top-1.5 h-2 w-2 rounded-full bg-brand-500" />
                      <div className="flex flex-wrap items-baseline justify-between gap-2">
                        <h3 className="font-medium text-slate-900">{exp.title}</h3>
                        <span className="text-xs text-slate-400">
                          {formatPeriod(exp.start, exp.end)}
                          {formatExperienceLength(exp.months_of_experience) &&
                            ` · ${formatExperienceLength(exp.months_of_experience)}`}
                        </span>
                      </div>
                      {exp.industry && (
                        <Badge tone="neutral" className="mt-1">
                          {industryLabel(exp.industry)}
                        </Badge>
                      )}
                      {exp.description && (
                        <p className="mt-2 text-sm leading-relaxed text-slate-600">
                          {exp.description}
                        </p>
                      )}
                    </li>
                  ))}
                </ol>
              )}
            </CardBody>
          </Card>

          <div className="grid gap-6 sm:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Skills</CardTitle>
              </CardHeader>
              <CardBody>
                <ChipList items={profile.skills} tone="brand" empty="No skills listed." />
              </CardBody>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>ESCO-mapped skills</CardTitle>
              </CardHeader>
              <CardBody>
                <ChipList
                  items={profile.esco_skills.map((s) => s.label)}
                  tone="neutral"
                  empty="Mapped automatically from your skills."
                />
              </CardBody>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Hobbies & interests</CardTitle>
              </CardHeader>
              <CardBody>
                <ChipList items={profile.hobbies} tone="success" empty="None listed." />
              </CardBody>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Professional values</CardTitle>
              </CardHeader>
              <CardBody>
                <ChipList
                  items={profile.professional_values}
                  tone="warning"
                  empty="None listed."
                />
              </CardBody>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Account &amp; security</CardTitle>
            </CardHeader>
            <CardBody>
              <ChangePasswordForm />
            </CardBody>
          </Card>
        </div>
      </div>
    </>
  );
}

function Row({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-right font-medium text-slate-800">
        {value || <span className="font-normal text-slate-400">—</span>}
      </dd>
    </div>
  );
}
