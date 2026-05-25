"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, useTransition } from "react";

import { getProfileAction, uploadResumeAction } from "@/actions/profile";
import { UploadIcon } from "@/components/icons";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";

type Status = "idle" | "uploading" | "processing" | "done" | "error";

export function ResumeUploader() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string>();
  const [, startTransition] = useTransition();

  // Poll the profile while the worker parses the PDF in the background.
  useEffect(() => {
    if (status !== "processing") return;
    let attempts = 0;
    const id = setInterval(async () => {
      attempts += 1;
      try {
        const p = await getProfileAction();
        const filled =
          !!p.summary || p.skills.length > 0 || p.experiences.length > 0;
        if (filled) {
          clearInterval(id);
          setStatus("done");
          router.refresh();
          return;
        }
      } catch {
        /* keep polling */
      }
      if (attempts >= 20) {
        clearInterval(id);
        setStatus("done");
        router.refresh();
      }
    }, 4000);
    return () => clearInterval(id);
  }, [status, router]);

  const handleUpload = () => {
    if (!file) return;
    setError(undefined);
    setStatus("uploading");
    startTransition(async () => {
      const fd = new FormData();
      fd.append("file", file);
      const res = await uploadResumeAction(fd);
      if (res.error) {
        setError(res.error);
        setStatus("error");
        return;
      }
      setFile(null);
      if (inputRef.current) inputRef.current.value = "";
      setStatus("processing");
    });
  };

  return (
    <div className="space-y-4">
      {error && <Alert variant="error">{error}</Alert>}

      {status === "processing" && (
        <Alert variant="info" title="Parsing your résumé">
          <span className="inline-flex items-center gap-2">
            <Spinner /> This usually takes under a minute. Your profile will
            update automatically.
          </span>
        </Alert>
      )}
      {status === "done" && (
        <Alert variant="success" title="Résumé processed">
          We've updated your profile from your résumé. Review the fields below
          and adjust anything that needs a tweak.
        </Alert>
      )}

      <label
        htmlFor="resume-file"
        className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-slate-300 bg-slate-50/60 px-6 py-8 text-center transition-colors hover:border-brand-300 hover:bg-brand-50/40"
      >
        <UploadIcon className="text-2xl text-brand-500" />
        <span className="text-sm font-medium text-slate-700">
          {file ? file.name : "Choose a PDF résumé"}
        </span>
        <span className="text-xs text-slate-400">PDF only, up to 10 MB</span>
        <input
          id="resume-file"
          ref={inputRef}
          type="file"
          accept="application/pdf,.pdf"
          className="sr-only"
          onChange={(e) => {
            setFile(e.target.files?.[0] ?? null);
            setStatus("idle");
            setError(undefined);
          }}
        />
      </label>

      <Button
        onClick={handleUpload}
        disabled={!file || status === "uploading" || status === "processing"}
      >
        {(status === "uploading" || status === "processing") && <Spinner />}
        {status === "uploading"
          ? "Uploading…"
          : status === "processing"
            ? "Processing…"
            : "Upload & parse résumé"}
      </Button>
    </div>
  );
}
