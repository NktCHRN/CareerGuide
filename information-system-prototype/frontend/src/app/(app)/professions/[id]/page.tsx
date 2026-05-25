import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { AskAssistantButton } from "@/components/professions/ask-assistant-button";
import {
  ChevronLeftIcon,
  ExternalLinkIcon,
  GlobeIcon,
  GraduationIcon,
  MapPinIcon,
} from "@/components/icons";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api/errors";
import { getProfession } from "@/lib/api/career";
import { getScores } from "@/lib/api/reco";
import { getProfile } from "@/lib/api/users";
import { cn } from "@/lib/cn";
import { formatCount, formatMatch, formatSalary } from "@/lib/format";
import type { ProfileOut } from "@/lib/types";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  try {
    const p = await getProfession(Number(id));
    return { title: p.preferred_label };
  } catch {
    return { title: "Profession" };
  }
}

export default async function ProfessionDetailPage({
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

  // Best-effort: the user's profile (skill highlighting) and match score.
  let profile: ProfileOut | null = null;
  let matchScore: number | undefined;
  try {
    [profile] = await Promise.all([getProfile()]);
  } catch {
    /* ignore */
  }
  try {
    const res = await getScores([id]);
    if (res.ready && res.scores[id] != null) matchScore = res.scores[id];
  } catch {
    /* ignore */
  }

  const userSkillLabels = new Set(
    (profile?.skills ?? []).map((s) => s.toLowerCase()),
  );
  const userEscoUris = new Set((profile?.esco_skills ?? []).map((s) => s.skill_uri));
  const hasSkill = (uri: string, label: string) =>
    userEscoUris.has(uri) || userSkillLabels.has(label.toLowerCase());

  const essential = profession.knowledge_skills.filter(
    (s) => s.relation_type === "essential",
  );
  const optional = profession.knowledge_skills.filter(
    (s) => s.relation_type !== "essential",
  );

  return (
    <>
      <Link
        href="/professions"
        className="mb-4 inline-flex items-center gap-1 text-sm font-medium text-slate-500 hover:text-slate-700"
      >
        <ChevronLeftIcon /> All professions
      </Link>

      {/* Hero */}
      <Card className="mb-6 overflow-hidden">
        <div className="flex flex-col sm:flex-row">
          <div className="relative h-44 w-full shrink-0 bg-gradient-to-br from-brand-500 to-brand-700 sm:h-auto sm:w-56">
            {profession.photo_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={profession.photo_url}
                alt={profession.preferred_label}
                className="h-full w-full object-cover"
              />
            ) : (
              <div className="flex h-full w-full items-center justify-center text-5xl font-bold text-white/30">
                {profession.preferred_label.charAt(0).toUpperCase()}
              </div>
            )}
          </div>
          <div className="flex-1 p-5 sm:p-6">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
                  {profession.preferred_label}
                </h1>
                {profession.alt_labels.length > 0 && (
                  <p className="mt-1 text-sm text-slate-500">
                    {profession.alt_labels.slice(0, 4).join(" · ")}
                  </p>
                )}
              </div>
              {matchScore !== undefined && (
                <Badge tone="brand" className="text-sm">
                  {formatMatch(matchScore)} match
                </Badge>
              )}
            </div>

            <div className="mt-3 flex flex-wrap items-center gap-2">
              {profession.riasec_type && (
                <Badge tone="neutral">RIASEC · {profession.riasec_type}</Badge>
              )}
              {profession.esco_code && (
                <Badge tone="muted">ESCO {profession.esco_code}</Badge>
              )}
              {profession.esco_uri && (
                <a
                  href={profession.esco_uri}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-xs font-medium text-brand-600 hover:text-brand-700"
                >
                  View on ESCO <ExternalLinkIcon />
                </a>
              )}
            </div>

            <div className="mt-5">
              <AskAssistantButton
                professionId={profession.id}
                label={profession.preferred_label}
              />
            </div>
          </div>
        </div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Main */}
        <div className="space-y-6 lg:col-span-2">
          {profession.description && (
            <Card>
              <CardHeader>
                <CardTitle>Overview</CardTitle>
              </CardHeader>
              <CardBody>
                <p className="text-sm leading-relaxed text-slate-700">
                  {profession.description}
                </p>
              </CardBody>
            </Card>
          )}

          {profession.responsibilities &&
            profession.responsibilities.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle>Typical responsibilities</CardTitle>
                </CardHeader>
                <CardBody>
                  <ul className="space-y-2">
                    {profession.responsibilities.map((r, i) => (
                      <li key={i} className="flex gap-2.5 text-sm text-slate-700">
                        <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-500" />
                        {r}
                      </li>
                    ))}
                  </ul>
                </CardBody>
              </Card>
            )}

          {profession.knowledge_skills.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Skills &amp; knowledge</CardTitle>
              </CardHeader>
              <CardBody className="space-y-5">
                {profile && (
                  <p className="text-xs text-slate-500">
                    Highlighted skills are ones already on your profile.
                  </p>
                )}
                {essential.length > 0 && (
                  <SkillGroup
                    title="Essential"
                    skills={essential}
                    hasSkill={hasSkill}
                  />
                )}
                {optional.length > 0 && (
                  <SkillGroup
                    title="Optional"
                    skills={optional}
                    hasSkill={hasSkill}
                  />
                )}
              </CardBody>
            </Card>
          )}

          {profession.professional_values &&
            profession.professional_values.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle>Typical values</CardTitle>
                </CardHeader>
                <CardBody>
                  <div className="flex flex-wrap gap-1.5">
                    {profession.professional_values.map((v) => (
                      <Badge key={v} tone="warning">
                        {v}
                      </Badge>
                    ))}
                  </div>
                </CardBody>
              </Card>
            )}
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Quick facts</CardTitle>
            </CardHeader>
            <CardBody>
              <dl className="space-y-3 text-sm">
                <Fact
                  icon={<GraduationIcon className="text-slate-400" />}
                  label="Education"
                  value={profession.education_level}
                />
                <Fact icon={<span>💼</span>} label="Average salary" value={formatSalary(profession.avg_salary)} />
                <Fact
                  icon={<MapPinIcon className="text-slate-400" />}
                  label="Local vacancies"
                  value={formatCount(profession.vacancies_local)}
                />
                <Fact
                  icon={<GlobeIcon className="text-slate-400" />}
                  label="International vacancies"
                  value={formatCount(profession.vacancies_international)}
                />
                <Fact label="Work style" value={profession.work_style} />
              </dl>
            </CardBody>
          </Card>

          {!profile?.riasec_result && profession.riasec_type && (
            <Alert variant="info">
              This profession suits a{" "}
              <strong>{profession.riasec_type}</strong> RIASEC type.{" "}
              <Link href="/riasec" className="font-medium underline">
                Take the test
              </Link>{" "}
              to see how you compare.
            </Alert>
          )}
        </div>
      </div>
    </>
  );
}

function SkillGroup({
  title,
  skills,
  hasSkill,
}: {
  title: string;
  skills: { skill_uri: string; label: string }[];
  hasSkill: (uri: string, label: string) => boolean;
}) {
  return (
    <div>
      <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-400">
        {title}
      </p>
      <div className="flex flex-wrap gap-1.5">
        {skills.map((s) => {
          const have = hasSkill(s.skill_uri, s.label);
          return (
            <span
              key={s.skill_uri + s.label}
              className={cn(
                "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset",
                have
                  ? "bg-emerald-50 text-emerald-700 ring-emerald-200"
                  : "bg-slate-100 text-slate-600 ring-slate-200",
              )}
            >
              {have && <span aria-hidden>✓</span>}
              {s.label}
            </span>
          );
        })}
      </div>
    </div>
  );
}

function Fact({
  icon,
  label,
  value,
}: {
  icon?: React.ReactNode;
  label: string;
  value: string | null | undefined;
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="inline-flex items-center gap-1.5 text-slate-500">
        {icon}
        {label}
      </dt>
      <dd className="text-right font-medium text-slate-800">
        {value || <span className="font-normal text-slate-400">—</span>}
      </dd>
    </div>
  );
}
