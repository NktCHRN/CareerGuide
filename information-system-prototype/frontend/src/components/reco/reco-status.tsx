"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useRef } from "react";

import { getRecoStatusAction } from "@/actions/reco";
import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";

/**
 * Polls the recommendation readiness while the worker computes the user's
 * vector. Shows a banner until ready, then refreshes the page so the ranked
 * list streams in. Only polls while `ready` is false.
 */
export function RecoStatus({ initialReady }: { initialReady: boolean }) {
  const router = useRouter();
  const wasReady = useRef(initialReady);

  const { data } = useQuery({
    queryKey: ["reco-status"],
    queryFn: getRecoStatusAction,
    initialData: { ready: initialReady, updated_at: null },
    refetchInterval: (query) => (query.state.data?.ready ? false : 5000),
  });

  const ready = data?.ready ?? initialReady;

  useEffect(() => {
    if (ready && !wasReady.current) {
      wasReady.current = true;
      router.refresh();
    }
  }, [ready, router]);

  if (ready) return null;

  return (
    <Alert variant="warning" title="Preparing your recommendations" className="mb-6">
      <span className="inline-flex items-center gap-2">
        <Spinner />
        We're analysing your profile to compute your matches. This updates
        automatically — it usually takes under a minute after you change your
        profile.
      </span>
    </Alert>
  );
}
