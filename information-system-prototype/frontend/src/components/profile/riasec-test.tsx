"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { saveRiasecAction } from "@/actions/profile";
import { RiasecBars } from "@/components/profile/riasec-bars";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { buttonClasses } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/cn";
import {
  RIASEC_DIMENSIONS,
  RIASEC_QUESTIONS,
  RIASEC_SCALE,
  scoreRiasec,
} from "@/lib/riasec";
import type { RiasecResult } from "@/lib/types";

export function RiasecTest({ existing }: { existing: RiasecResult | null }) {
  const router = useRouter();
  const [started, setStarted] = useState(false);
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [result, setResult] = useState<RiasecResult | null>(existing);
  const [error, setError] = useState<string>();
  const [pending, startTransition] = useTransition();

  const answeredCount = Object.keys(answers).length;
  const total = RIASEC_QUESTIONS.length;
  const complete = answeredCount === total;

  // Showing a previously saved result (not mid-test).
  if (result && !started) {
    return (
      <ResultView
        result={result}
        onRetake={() => {
          setStarted(true);
          setResult(null);
          setAnswers({});
        }}
      />
    );
  }

  if (!started) {
    return (
      <Card>
        <CardBody className="space-y-4 sm:px-8 sm:py-8">
          <p className="text-sm leading-relaxed text-slate-600">
            The RIASEC assessment maps your interests onto six themes —{" "}
            <strong>Realistic, Investigative, Artistic, Social, Enterprising</strong>{" "}
            and <strong>Conventional</strong>. Rate how much you agree with each of{" "}
            {total} short statements. It takes about three minutes, and there are no
            right or wrong answers.
          </p>
          <Button onClick={() => setStarted(true)}>Start the test</Button>
        </CardBody>
      </Card>
    );
  }

  const submit = () => {
    setError(undefined);
    const computed = scoreRiasec(answers);
    startTransition(async () => {
      const res = await saveRiasecAction(computed);
      if (res.error) {
        setError(res.error);
        return;
      }
      setResult(computed);
      setStarted(false);
      router.refresh();
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  };

  return (
    <div className="space-y-5">
      {error && <Alert variant="error">{error}</Alert>}

      <div className="sticky top-16 z-10 rounded-xl border border-slate-200 bg-white/95 px-4 py-3 shadow-sm backdrop-blur">
        <div className="flex items-center justify-between text-sm">
          <span className="font-medium text-slate-700">
            {answeredCount} / {total} answered
          </span>
          <span className="text-slate-400">
            {Math.round((answeredCount / total) * 100)}%
          </span>
        </div>
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-100">
          <div
            className="h-full rounded-full bg-brand-600 transition-all"
            style={{ width: `${(answeredCount / total) * 100}%` }}
          />
        </div>
      </div>

      <ol className="space-y-3">
        {RIASEC_QUESTIONS.map((q, i) => (
          <li key={q.id}>
            <Card>
              <CardBody className="space-y-3">
                <p className="text-sm font-medium text-slate-800">
                  <span className="mr-2 text-slate-400">{i + 1}.</span>
                  {q.text}
                </p>
                <div className="flex flex-wrap gap-2">
                  {RIASEC_SCALE.map((opt) => {
                    const selected = answers[q.id] === opt.value;
                    return (
                      <button
                        key={opt.value}
                        type="button"
                        onClick={() =>
                          setAnswers((prev) => ({ ...prev, [q.id]: opt.value }))
                        }
                        className={cn(
                          "rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors",
                          selected
                            ? "border-brand-600 bg-brand-600 text-white"
                            : "border-slate-200 bg-white text-slate-600 hover:border-brand-300 hover:bg-brand-50",
                        )}
                        aria-pressed={selected}
                      >
                        {opt.label}
                      </button>
                    );
                  })}
                </div>
              </CardBody>
            </Card>
          </li>
        ))}
      </ol>

      <div className="sticky bottom-4 flex items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white/95 p-3 shadow-lg backdrop-blur">
        <span className="text-sm text-slate-500">
          {complete ? "All set — submit your answers." : "Answer every statement to finish."}
        </span>
        <Button onClick={submit} disabled={!complete || pending}>
          {pending && <Spinner />}
          {pending ? "Saving…" : "See my result"}
        </Button>
      </div>
    </div>
  );
}

function ResultView({
  result,
  onRetake,
}: {
  result: RiasecResult;
  onRetake: () => void;
}) {
  const topDims = result.top
    .slice(0, 3)
    .map((l) => RIASEC_DIMENSIONS.find((d) => d.letter === l))
    .filter(Boolean);

  return (
    <div className="space-y-6">
      <Card>
        <CardBody className="sm:px-8 sm:py-8">
          <div className="flex flex-col items-center text-center">
            <p className="text-sm font-medium uppercase tracking-wide text-slate-400">
              Your Holland code
            </p>
            <span className="mt-2 rounded-xl bg-brand-50 px-5 py-2 font-mono text-3xl font-bold tracking-widest text-brand-700">
              {result.code}
            </span>
          </div>
          <div className="mt-6 grid gap-3 sm:grid-cols-3">
            {topDims.map(
              (d) =>
                d && (
                  <div
                    key={d.letter}
                    className="rounded-xl border border-slate-200 bg-slate-50/50 p-4"
                  >
                    <p className="font-semibold text-slate-900">
                      <span className="font-mono text-brand-600">{d.letter}</span> ·{" "}
                      {d.name}
                    </p>
                    <p className="mt-1 text-xs leading-relaxed text-slate-500">
                      {d.blurb}
                    </p>
                  </div>
                ),
            )}
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardBody>
          <h3 className="mb-4 text-sm font-semibold text-slate-900">
            Full breakdown
          </h3>
          <RiasecBars result={result} />
        </CardBody>
      </Card>

      <div className="flex flex-wrap gap-3">
        <Link href="/recommendations" className={buttonClasses({})}>
          See my recommendations
        </Link>
        <Button variant="outline" onClick={onRetake}>
          Retake the test
        </Button>
      </div>
    </div>
  );
}
