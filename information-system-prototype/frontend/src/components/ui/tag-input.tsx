"use client";

import { useState, type KeyboardEvent } from "react";

import { XIcon } from "@/components/icons";

/**
 * Controlled multi-value input rendering chips. Enter or comma commits the
 * current text; Backspace on an empty field removes the last chip.
 */
export function TagInput({
  value,
  onChange,
  placeholder,
  id,
}: {
  value: string[];
  onChange: (next: string[]) => void;
  placeholder?: string;
  id?: string;
}) {
  const [draft, setDraft] = useState("");

  const commit = (raw: string) => {
    const text = raw.trim().replace(/,$/, "").trim();
    if (!text) return;
    if (!value.some((v) => v.toLowerCase() === text.toLowerCase())) {
      onChange([...value, text]);
    }
    setDraft("");
  };

  const handleKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      commit(draft);
    } else if (e.key === "Backspace" && !draft && value.length) {
      onChange(value.slice(0, -1));
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-2 py-1.5 focus-within:border-brand-500 focus-within:ring-2 focus-within:ring-brand-500 focus-within:ring-offset-1">
      {value.map((tag) => (
        <span
          key={tag}
          className="inline-flex items-center gap-1 rounded-md bg-brand-50 py-1 pl-2.5 pr-1 text-sm text-brand-700"
        >
          {tag}
          <button
            type="button"
            onClick={() => onChange(value.filter((v) => v !== tag))}
            className="rounded p-0.5 text-brand-500 hover:bg-brand-100 hover:text-brand-700"
            aria-label={`Remove ${tag}`}
          >
            <XIcon className="text-xs" />
          </button>
        </span>
      ))}
      <input
        id={id}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={handleKey}
        onBlur={() => commit(draft)}
        placeholder={value.length ? "" : placeholder}
        className="min-w-32 flex-1 bg-transparent px-1.5 py-1 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none"
      />
    </div>
  );
}
