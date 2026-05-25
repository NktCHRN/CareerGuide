"use client";

import { useRouter } from "next/navigation";
import { useRef, useState, useTransition } from "react";

import { uploadProfessionPhotoAction } from "@/actions/admin";
import { UploadIcon } from "@/components/icons";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";

export function PhotoUploader({
  professionId,
  currentUrl,
}: {
  professionId: number;
  currentUrl: string | null;
}) {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [result, setResult] = useState<{ ok?: boolean; error?: string }>({});
  const [pending, startTransition] = useTransition();

  const onPick = (f: File | null) => {
    setFile(f);
    setResult({});
    setPreview(f ? URL.createObjectURL(f) : null);
  };

  const upload = () => {
    if (!file) return;
    setResult({});
    startTransition(async () => {
      const fd = new FormData();
      fd.append("file", file);
      const res = await uploadProfessionPhotoAction(professionId, fd);
      setResult(res);
      if (res.ok) {
        setFile(null);
        if (inputRef.current) inputRef.current.value = "";
        router.refresh();
      }
    });
  };

  const shown = preview ?? currentUrl;

  return (
    <div className="space-y-4">
      {result.error && <Alert variant="error">{result.error}</Alert>}
      {result.ok && <Alert variant="success">Photo updated.</Alert>}

      <div className="flex items-center gap-4">
        <div className="h-24 w-24 shrink-0 overflow-hidden rounded-xl bg-slate-100">
          {shown ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={shown} alt="Profession" className="h-full w-full object-cover" />
          ) : (
            <div className="flex h-full w-full items-center justify-center text-slate-300">
              <UploadIcon className="text-2xl" />
            </div>
          )}
        </div>
        <div className="flex-1">
          <input
            ref={inputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            onChange={(e) => onPick(e.target.files?.[0] ?? null)}
            className="block w-full text-sm text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-brand-50 file:px-3 file:py-2 file:text-sm file:font-medium file:text-brand-700 hover:file:bg-brand-100"
          />
          <p className="mt-1 text-xs text-slate-400">JPEG, PNG or WebP, up to 5 MB.</p>
        </div>
      </div>

      <Button onClick={upload} disabled={!file || pending} variant="outline" size="sm">
        {pending && <Spinner />}
        {pending ? "Uploading…" : "Upload photo"}
      </Button>
    </div>
  );
}
