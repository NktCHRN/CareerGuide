"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input, Label, Select } from "@/components/ui/field";
import type { RecoOrder, RecoSort } from "@/lib/types";

const SORT_LABELS: Record<RecoSort, string> = {
  score: "Best match",
  avg_salary: "Average salary",
  vacancies_local: "Local vacancies",
  vacancies_international: "International vacancies",
};

export function RecoFilters() {
  const router = useRouter();
  const params = useSearchParams();

  const [sort, setSort] = useState<RecoSort>(
    (params.get("sort") as RecoSort) || "score",
  );
  const [order, setOrder] = useState<RecoOrder>(
    (params.get("order") as RecoOrder) || "desc",
  );
  const [education, setEducation] = useState(params.get("education_level") ?? "");
  const [minVacancies, setMinVacancies] = useState(params.get("min_vacancies") ?? "");
  const [minSalary, setMinSalary] = useState(params.get("min_avg_salary") ?? "");

  const apply = (overrides?: Partial<Record<string, string>>) => {
    const next = new URLSearchParams();
    const values = {
      sort,
      order,
      education_level: education.trim(),
      min_vacancies: minVacancies,
      min_avg_salary: minSalary,
      ...overrides,
    };
    for (const [k, v] of Object.entries(values)) {
      if (v) next.set(k, String(v));
    }
    router.push(`/recommendations?${next.toString()}`);
  };

  const clear = () => {
    setSort("score");
    setOrder("desc");
    setEducation("");
    setMinVacancies("");
    setMinSalary("");
    router.push("/recommendations");
  };

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        apply();
      }}
      className="rounded-[var(--radius-card)] border border-slate-200 bg-white p-4 shadow-[var(--shadow-card)]"
    >
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <div>
          <Label htmlFor="sort">Sort by</Label>
          <Select
            id="sort"
            value={sort}
            onChange={(e) => {
              const v = e.target.value as RecoSort;
              setSort(v);
              apply({ sort: v });
            }}
          >
            {Object.entries(SORT_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
        </div>
        <div>
          <Label htmlFor="order">Order</Label>
          <Select
            id="order"
            value={order}
            onChange={(e) => {
              const v = e.target.value as RecoOrder;
              setOrder(v);
              apply({ order: v });
            }}
          >
            <option value="desc">Highest first</option>
            <option value="asc">Lowest first</option>
          </Select>
        </div>
        <div>
          <Label htmlFor="education_level">Education level</Label>
          <Input
            id="education_level"
            value={education}
            onChange={(e) => setEducation(e.target.value)}
            placeholder="Any"
          />
        </div>
        <div>
          <Label htmlFor="min_vacancies">Min. vacancies</Label>
          <Input
            id="min_vacancies"
            type="number"
            min={0}
            value={minVacancies}
            onChange={(e) => setMinVacancies(e.target.value)}
            placeholder="Any"
          />
        </div>
        <div>
          <Label htmlFor="min_avg_salary">Min. salary</Label>
          <Input
            id="min_avg_salary"
            type="number"
            min={0}
            value={minSalary}
            onChange={(e) => setMinSalary(e.target.value)}
            placeholder="Any"
          />
        </div>
      </div>
      <div className="mt-3 flex items-center gap-2">
        <Button type="submit" size="sm">
          Apply filters
        </Button>
        <button
          type="button"
          onClick={clear}
          className="text-sm font-medium text-slate-500 hover:text-slate-700"
        >
          Clear
        </button>
      </div>
    </form>
  );
}
