"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { saveProfileAction } from "@/actions/profile";
import { PlusIcon, TrashIcon } from "@/components/icons";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Label, Select, Textarea } from "@/components/ui/field";
import { Spinner } from "@/components/ui/spinner";
import { TagInput } from "@/components/ui/tag-input";
import {
  MONTH_OPTIONS,
  YEAR_OPTIONS,
  buildMonthYear,
  computeMonths,
  parseMonthYear,
} from "@/lib/experience";
import type { ExperienceIn, IndustryOption, ProfileOut } from "@/lib/types";

interface EditExp {
  key: string;
  title: string;
  industry: string;
  startMonth: number | "";
  startYear: number | "";
  current: boolean;
  endMonth: number | "";
  endYear: number | "";
  description: string;
}

let counter = 0;
const nextKey = () => `exp-${counter++}`;

function toEditExp(e: ProfileOut["experiences"][number]): EditExp {
  const start = parseMonthYear(e.start);
  const isCurrent = (e.end ?? "").toLowerCase() === "current";
  const end = parseMonthYear(e.end);
  return {
    key: nextKey(),
    title: e.title ?? "",
    industry: e.industry ?? "",
    startMonth: start.month,
    startYear: start.year,
    current: isCurrent,
    endMonth: end.month,
    endYear: end.year,
    description: e.description ?? "",
  };
}

export function ProfileEditor({
  profile,
  industries,
}: {
  profile: ProfileOut;
  industries: IndustryOption[];
}) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [result, setResult] = useState<{ ok?: boolean; error?: string }>({});

  const [name, setName] = useState(profile.name ?? "");
  const [summary, setSummary] = useState(profile.summary ?? "");
  const [workStyle, setWorkStyle] = useState(profile.work_style ?? "");
  const [skills, setSkills] = useState<string[]>(profile.skills ?? []);
  const [hobbies, setHobbies] = useState<string[]>(profile.hobbies ?? []);
  const [values, setValues] = useState<string[]>(
    profile.professional_values ?? [],
  );
  const [eduLevel, setEduLevel] = useState(profile.education?.level ?? "");
  const [eduField, setEduField] = useState(profile.education?.field ?? "");
  const [eduYears, setEduYears] = useState(profile.education?.years ?? "");
  const [eduUniversity, setEduUniversity] = useState(
    profile.education?.university ?? "",
  );
  const [experiences, setExperiences] = useState<EditExp[]>(
    profile.experiences.map(toEditExp),
  );

  const updateExp = (key: string, patch: Partial<EditExp>) =>
    setExperiences((prev) =>
      prev.map((e) => (e.key === key ? { ...e, ...patch } : e)),
    );

  const addExp = () =>
    setExperiences((prev) => [
      ...prev,
      {
        key: nextKey(),
        title: "",
        industry: "",
        startMonth: "",
        startYear: "",
        current: false,
        endMonth: "",
        endYear: "",
        description: "",
      },
    ]);

  const removeExp = (key: string) =>
    setExperiences((prev) => prev.filter((e) => e.key !== key));

  const save = () => {
    setResult({});
    const cleanExperiences: ExperienceIn[] = experiences
      .filter((e) => e.title.trim())
      .map((e) => {
        const start = buildMonthYear(e.startMonth, e.startYear) || null;
        const end = e.current
          ? "current"
          : buildMonthYear(e.endMonth, e.endYear) || null;
        return {
          title: e.title.trim(),
          industry: e.industry || null,
          description: e.description.trim() || null,
          start,
          end,
          months_of_experience: computeMonths(start, end),
        };
      });

    const hasEducation =
      eduLevel || eduField || eduYears || eduUniversity;

    startTransition(async () => {
      const res = await saveProfileAction({
        name: name.trim() || null,
        summary: summary.trim() || null,
        work_style: workStyle.trim() || null,
        skills,
        hobbies,
        professional_values: values,
        education: hasEducation
          ? {
              level: eduLevel.trim() || null,
              field: eduField.trim() || null,
              years: eduYears.trim() || null,
              university: eduUniversity.trim() || null,
            }
          : null,
        experiences: cleanExperiences,
      });
      setResult(res);
      if (res.ok) {
        router.refresh();
        window.scrollTo({ top: 0, behavior: "smooth" });
      }
    });
  };

  return (
    <div className="space-y-6">
      {result.error && <Alert variant="error">{result.error}</Alert>}
      {result.ok && (
        <Alert variant="success" title="Profile saved">
          Your changes were saved. Recommendations affected by these fields are
          being recomputed in the background.{" "}
          <Link href="/profile" className="font-medium underline">
            View profile
          </Link>
        </Alert>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Basic information</CardTitle>
        </CardHeader>
        <CardBody className="space-y-4">
          <Field label="Full name" htmlFor="name">
            <Input id="name" value={name} onChange={(e) => setName(e.target.value)} />
          </Field>
          <Field
            label="Professional summary"
            htmlFor="summary"
            hint="A short description of who you are professionally."
          >
            <Textarea
              id="summary"
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
              rows={4}
            />
          </Field>
          <Field label="Work style" htmlFor="work_style">
            <Input
              id="work_style"
              value={workStyle}
              onChange={(e) => setWorkStyle(e.target.value)}
              placeholder="e.g. collaborative, detail-oriented, remote-first"
            />
          </Field>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Skills, interests & values</CardTitle>
        </CardHeader>
        <CardBody className="space-y-4">
          <Field
            label="Skills"
            hint="Press Enter or comma to add. These drive your recommendations."
          >
            <TagInput value={skills} onChange={setSkills} placeholder="Add a skill…" />
          </Field>
          <Field label="Hobbies & interests">
            <TagInput value={hobbies} onChange={setHobbies} placeholder="Add a hobby…" />
          </Field>
          <Field label="Professional values">
            <TagInput value={values} onChange={setValues} placeholder="Add a value…" />
          </Field>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Education</CardTitle>
        </CardHeader>
        <CardBody className="grid gap-4 sm:grid-cols-2">
          <Field label="Level" htmlFor="edu_level">
            <Input
              id="edu_level"
              value={eduLevel}
              onChange={(e) => setEduLevel(e.target.value)}
              placeholder="e.g. Bachelor's"
            />
          </Field>
          <Field label="Field of study" htmlFor="edu_field">
            <Input
              id="edu_field"
              value={eduField}
              onChange={(e) => setEduField(e.target.value)}
              placeholder="e.g. Computer Science"
            />
          </Field>
          <Field label="Institution" htmlFor="edu_university">
            <Input
              id="edu_university"
              value={eduUniversity}
              onChange={(e) => setEduUniversity(e.target.value)}
            />
          </Field>
          <Field label="Years" htmlFor="edu_years">
            <Input
              id="edu_years"
              value={eduYears}
              onChange={(e) => setEduYears(e.target.value)}
              placeholder="e.g. 2016–2020"
            />
          </Field>
        </CardBody>
      </Card>

      <Card>
        <CardHeader className="flex items-center justify-between">
          <CardTitle>Work experience</CardTitle>
          <Button variant="secondary" size="sm" onClick={addExp}>
            <PlusIcon /> Add experience
          </Button>
        </CardHeader>
        <CardBody className="space-y-5">
          {experiences.length === 0 && (
            <p className="text-sm text-slate-400">
              No experience added yet. Add your roles so we can recommend matching
              professions.
            </p>
          )}
          {experiences.map((exp, idx) => (
            <div
              key={exp.key}
              className="rounded-xl border border-slate-200 bg-slate-50/40 p-4"
            >
              <div className="mb-3 flex items-center justify-between">
                <span className="text-sm font-medium text-slate-500">
                  Experience {idx + 1}
                </span>
                <button
                  type="button"
                  onClick={() => removeExp(exp.key)}
                  className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-red-600 hover:bg-red-50"
                >
                  <TrashIcon /> Remove
                </button>
              </div>
              <div className="space-y-4">
                <div className="grid gap-4 sm:grid-cols-2">
                  <Field label="Job title" required>
                    <Input
                      value={exp.title}
                      onChange={(e) => updateExp(exp.key, { title: e.target.value })}
                      placeholder="e.g. Backend Developer"
                    />
                  </Field>
                  <Field label="Industry">
                    <Select
                      value={exp.industry}
                      onChange={(e) => updateExp(exp.key, { industry: e.target.value })}
                    >
                      <option value="">Select industry…</option>
                      {industries.map((opt) => (
                        <option key={opt.key} value={opt.key}>
                          {opt.label}
                        </option>
                      ))}
                    </Select>
                  </Field>
                </div>

                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <Label>Start</Label>
                    <div className="flex gap-2">
                      <Select
                        value={exp.startMonth}
                        onChange={(e) =>
                          updateExp(exp.key, {
                            startMonth: e.target.value ? Number(e.target.value) : "",
                          })
                        }
                        aria-label="Start month"
                      >
                        <option value="">Month</option>
                        {MONTH_OPTIONS.map((m) => (
                          <option key={m.value} value={m.value}>
                            {m.label}
                          </option>
                        ))}
                      </Select>
                      <Select
                        value={exp.startYear}
                        onChange={(e) =>
                          updateExp(exp.key, {
                            startYear: e.target.value ? Number(e.target.value) : "",
                          })
                        }
                        aria-label="Start year"
                      >
                        <option value="">Year</option>
                        {YEAR_OPTIONS.map((y) => (
                          <option key={y} value={y}>
                            {y}
                          </option>
                        ))}
                      </Select>
                    </div>
                  </div>

                  <div>
                    <Label>End</Label>
                    <div className="flex gap-2">
                      <Select
                        value={exp.endMonth}
                        disabled={exp.current}
                        onChange={(e) =>
                          updateExp(exp.key, {
                            endMonth: e.target.value ? Number(e.target.value) : "",
                          })
                        }
                        aria-label="End month"
                      >
                        <option value="">Month</option>
                        {MONTH_OPTIONS.map((m) => (
                          <option key={m.value} value={m.value}>
                            {m.label}
                          </option>
                        ))}
                      </Select>
                      <Select
                        value={exp.endYear}
                        disabled={exp.current}
                        onChange={(e) =>
                          updateExp(exp.key, {
                            endYear: e.target.value ? Number(e.target.value) : "",
                          })
                        }
                        aria-label="End year"
                      >
                        <option value="">Year</option>
                        {YEAR_OPTIONS.map((y) => (
                          <option key={y} value={y}>
                            {y}
                          </option>
                        ))}
                      </Select>
                    </div>
                    <label className="mt-2 inline-flex items-center gap-2 text-sm text-slate-600">
                      <input
                        type="checkbox"
                        checked={exp.current}
                        onChange={(e) =>
                          updateExp(exp.key, { current: e.target.checked })
                        }
                        className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
                      />
                      I currently work here
                    </label>
                  </div>
                </div>

                <Field label="Description">
                  <Textarea
                    value={exp.description}
                    onChange={(e) =>
                      updateExp(exp.key, { description: e.target.value })
                    }
                    rows={3}
                    placeholder="What did you do in this role?"
                  />
                </Field>
              </div>
            </div>
          ))}
        </CardBody>
      </Card>

      <div className="sticky bottom-4 flex items-center justify-end gap-3 rounded-xl border border-slate-200 bg-white/95 p-3 shadow-lg backdrop-blur">
        <Link
          href="/profile"
          className="text-sm font-medium text-slate-500 hover:text-slate-700"
        >
          Cancel
        </Link>
        <Button onClick={save} disabled={pending}>
          {pending && <Spinner />}
          {pending ? "Saving…" : "Save changes"}
        </Button>
      </div>
    </div>
  );
}
