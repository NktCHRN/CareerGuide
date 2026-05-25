"use server";

import { getRecoStatus } from "@/lib/api/reco";
import type { RecoStatus } from "@/lib/types";

/** Lightweight status poll for the client (is the user's vector ready yet?). */
export async function getRecoStatusAction(): Promise<RecoStatus> {
  return getRecoStatus();
}
