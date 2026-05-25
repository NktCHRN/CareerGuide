"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import {
  createProfessionAction,
  updateProfessionAction,
} from "@/actions/admin";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Textarea } from "@/components/ui/field";
import { Spinner } from "@/components/ui/spinner";
import { TagInput } from "@/components/ui/tag-input";
import type { ProfessionCreate, ProfessionDetail } from "@/lib/types";

function numberOrNull(v: string): number | null {
  const t = v.trim();
  if (!t) return null;
  const n = Number(t);
  return Number.isFinite(n) ? n : null;
}

export function ProfessionForm({
  mode,
  initial,
}: {
  mode: "create" | "edit";
  initial?: ProfessionDetail;
}) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [result, setResult] = useState<{ ok?: boolean; error?: string }>({});

  const [preferredLabel, setPreferredLabel] = useState(initial?.preferred_label ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [escoCode, setEscoCode] = useState(initial?.esco_code ?? "");
  const [escoUri, setEscoUri] = useState(initial?.esco_uri ?? "");
  const [iscoGroup, setIscoGroup] = useState(
    initial?.isco_group != null ? String(initial.isco_group) : "",
  );
  const [riasecType, setRiasecType] = useState(initial?.riasec_type ?? "");
  const [educationLevel, setEducationLevel] = useState(
    initial?.education_level ?? "",
  );
  const [avgSalary, setAvgSalary] = useState(
    initial?.avg_salary != null ? String(initial.avg_salary) : "",
  );
  const [vacLocal, setVacLocal] = useState(
    initial?.vacancies_local != null ? String(initial.vacancies_local) : "",
  );
  const [vacIntl, setVacIntl] = useState(
    initial?.vacancies_international != null
      ? String(initial.vacancies_international)
      : "",
  );
  const [workStyle, setWorkStyle] = useState(initial?.work_style ?? "");
  const [altLabels, setAltLabels] = useState<string[]>(initial?.alt_labels ?? []);
  const [values, setValues] = useState<string[]>(
    initial?.professional_values ?? [],
  );
  const [responsibilities, setResponsibilities] = useState(
    (initial?.responsibilities ?? []).join("\n"),
  );

  const submit = () => {
    setResult({});
    if (!preferredLabel.trim()) {
      setResult({ error: "A preferred label is required." });
      return;
    }
    const payload: ProfessionCreate = {
      preferred_label: preferredLabel.trim(),
      description: description.trim() || null,
      esco_code: escoCode.trim() || null,
      esco_uri: escoUri.trim() || null,
      isco_group: numberOrNull(iscoGroup),
      riasec_type: riasecType.trim() || null,
      education_level: educationLevel.trim() || null,
      avg_salary: numberOrNull(avgSalary),
      vacancies_local: numberOrNull(vacLocal),
      vacancies_international: numberOrNull(vacIntl),
      work_style: workStyle.trim() || null,
      alt_labels: altLabels,
      professional_values: values,
      responsibilities: responsibilities
        .split("\n")
        .map((r) => r.trim())
        .filter(Boolean),
    };

    startTransition(async () => {
      const res =
        mode === "create"
          ? await createProfessionAction(payload)
          : await updateProfessionAction(initial!.id, payload);
      setResult(res);
      if (res.ok) {
        if (mode === "create" && res.id) {
          router.push(`/admin/professions/${res.id}/edit`);
        } else {
          router.refresh();
          window.scrollTo({ top: 0, behavior: "smooth" });
        }
      }
    });
  };

  return (
    <div className="space-y-6">
      {result.error && <Alert variant="error">{result.error}</Alert>}
      {result.ok && mode === "edit" && (
        <Alert variant="success" title="Saved">
          The profession was updated.{" "}
          <Link href={`/professions/${initial!.id}`} className="font-medium underline">
            View public page
          </Link>
        </Alert>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Core details</CardTitle>
        </CardHeader>
        <CardBody className="space-y-4">
          <Field label="Preferred label" required>
            <Input
              value={preferredLabel}
              onChange={(e) => setPreferredLabel(e.target.value)}
              placeholder="e.g. Software Developer"
            />
          </Field>
          <Field label="Description">
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={5}
            />
          </Field>
          <Field label="Alternative labels" hint="Press Enter to add each one.">
            <TagInput value={altLabels} onChange={setAltLabels} placeholder="Add a synonym…" />
          </Field>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>ESCO &amp; classification</CardTitle>
        </CardHeader>
        <CardBody className="grid gap-4 sm:grid-cols-2">
          <Field label="ESCO code">
            <Input value={escoCode} onChange={(e) => setEscoCode(e.target.value)} />
          </Field>
          <Field label="ISCO group">
            <Input
              type="number"
              value={iscoGroup}
              onChange={(e) => setIscoGroup(e.target.value)}
            />
          </Field>
          <Field label="ESCO URI" >
            <Input
              value={escoUri}
              onChange={(e) => setEscoUri(e.target.value)}
              placeholder="http://data.europa.eu/esco/occupation/…"
            />
          </Field>
          <Field label="RIASEC type">
            <Input
              value={riasecType}
              onChange={(e) => setRiasecType(e.target.value)}
              placeholder="e.g. IRC"
              maxLength={16}
            />
          </Field>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Labour-market data</CardTitle>
        </CardHeader>
        <CardBody className="grid gap-4 sm:grid-cols-2">
          <Field label="Education level">
            <Input
              value={educationLevel}
              onChange={(e) => setEducationLevel(e.target.value)}
              placeholder="e.g. Bachelor's degree"
            />
          </Field>
          <Field label="Work style">
            <Input value={workStyle} onChange={(e) => setWorkStyle(e.target.value)} />
          </Field>
          <Field label="Average salary (USD)">
            <Input
              type="number"
              min={0}
              value={avgSalary}
              onChange={(e) => setAvgSalary(e.target.value)}
            />
          </Field>
          <Field label="Local vacancies">
            <Input
              type="number"
              min={0}
              value={vacLocal}
              onChange={(e) => setVacLocal(e.target.value)}
            />
          </Field>
          <Field label="International vacancies">
            <Input
              type="number"
              min={0}
              value={vacIntl}
              onChange={(e) => setVacIntl(e.target.value)}
            />
          </Field>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Qualitative profile</CardTitle>
        </CardHeader>
        <CardBody className="space-y-4">
          <Field label="Typical professional values">
            <TagInput value={values} onChange={setValues} placeholder="Add a value…" />
          </Field>
          <Field
            label="Responsibilities"
            hint="One responsibility per line."
          >
            <Textarea
              value={responsibilities}
              onChange={(e) => setResponsibilities(e.target.value)}
              rows={5}
            />
          </Field>
        </CardBody>
      </Card>

      <div className="sticky bottom-4 flex items-center justify-end gap-3 rounded-xl border border-slate-200 bg-white/95 p-3 shadow-lg backdrop-blur">
        <Link
          href="/admin/professions"
          className="text-sm font-medium text-slate-500 hover:text-slate-700"
        >
          Cancel
        </Link>
        <Button onClick={submit} disabled={pending}>
          {pending && <Spinner />}
          {mode === "create" ? "Create profession" : "Save changes"}
        </Button>
      </div>
    </div>
  );
}
