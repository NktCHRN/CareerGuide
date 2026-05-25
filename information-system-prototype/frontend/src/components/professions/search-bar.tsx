"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { SearchIcon, XIcon } from "@/components/icons";

export function SearchBar() {
  const router = useRouter();
  const params = useSearchParams();
  const [value, setValue] = useState(params.get("query") ?? "");

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const q = value.trim();
    router.push(q ? `/professions?query=${encodeURIComponent(q)}` : "/professions");
  };

  return (
    <form onSubmit={submit} className="relative">
      <SearchIcon className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-lg text-slate-400" />
      <input
        type="search"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Search professions by name…"
        aria-label="Search professions"
        className="h-12 w-full rounded-xl border border-slate-300 bg-white pl-11 pr-24 text-sm text-slate-900 placeholder:text-slate-400 focus:border-brand-500 focus-visible:ring-2 focus-visible:ring-brand-500"
      />
      {value && (
        <button
          type="button"
          onClick={() => {
            setValue("");
            router.push("/professions");
          }}
          className="absolute right-[88px] top-1/2 -translate-y-1/2 rounded-md p-1 text-slate-400 hover:bg-slate-100"
          aria-label="Clear search"
        >
          <XIcon />
        </button>
      )}
      <button
        type="submit"
        className="absolute right-2 top-1/2 h-8 -translate-y-1/2 rounded-lg bg-brand-600 px-3.5 text-sm font-medium text-white hover:bg-brand-700"
      >
        Search
      </button>
    </form>
  );
}
