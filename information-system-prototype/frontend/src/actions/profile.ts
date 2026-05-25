"use server";

import { revalidatePath } from "next/cache";

import { friendlyMessage } from "@/lib/api/errors";
import {
  changePassword,
  getProfile,
  updateCriteria,
  updateProfile,
  uploadResume,
} from "@/lib/api/users";
import type {
  ProfileOut,
  ProfileUpdate,
  RecommendationCriterion,
  ResumeOut,
  RiasecResult,
} from "@/lib/types";

export interface ActionResult {
  ok?: boolean;
  error?: string;
}

/** Re-fetch the profile (used by client polling while a résumé is parsed). */
export async function getProfileAction(): Promise<ProfileOut> {
  return getProfile();
}

/** Save edited profile fields (FR5). Triggers async recompute on the backend. */
export async function saveProfileAction(
  payload: ProfileUpdate,
): Promise<ActionResult> {
  try {
    await updateProfile(payload);
    revalidatePath("/profile");
    revalidatePath("/recommendations");
    return { ok: true };
  } catch (err) {
    return { error: friendlyMessage(err, "Could not save your profile.") };
  }
}

/** Persist a completed RIASEC assessment into the profile (FR6). */
export async function saveRiasecAction(
  result: RiasecResult,
): Promise<ActionResult> {
  try {
    await updateProfile({ riasec_result: result });
    revalidatePath("/profile");
    revalidatePath("/riasec");
    return { ok: true };
  } catch (err) {
    return { error: friendlyMessage(err, "Could not save your results.") };
  }
}

/** Update which recommendation criteria are active (FR8). */
export async function saveCriteriaAction(
  criteria: RecommendationCriterion[],
): Promise<ActionResult> {
  try {
    await updateCriteria(criteria.length ? criteria : ["experience"]);
    revalidatePath("/profile");
    revalidatePath("/recommendations");
    return { ok: true };
  } catch (err) {
    return { error: friendlyMessage(err, "Could not update your settings.") };
  }
}

export interface ResumeUploadResult extends ActionResult {
  resume?: ResumeOut;
}

/** Upload a PDF résumé (FR1/FR5); the worker parses it asynchronously. */
export async function uploadResumeAction(
  formData: FormData,
): Promise<ResumeUploadResult> {
  const file = formData.get("file");
  if (!(file instanceof File) || file.size === 0) {
    return { error: "Please choose a PDF file to upload." };
  }
  if (file.type && file.type !== "application/pdf") {
    return { error: "Only PDF files are supported." };
  }
  if (file.size > 10 * 1024 * 1024) {
    return { error: "The file is too large (max 10 MB)." };
  }

  try {
    const forward = new FormData();
    forward.append("file", file, file.name || "resume.pdf");
    const resume = await uploadResume(forward);
    revalidatePath("/profile");
    return { ok: true, resume };
  } catch (err) {
    return { error: friendlyMessage(err, "Could not upload your résumé.") };
  }
}

export interface ChangePasswordState {
  ok?: boolean;
  error?: string;
}

/** Change password while signed in (FR3). */
export async function changePasswordAction(
  _prev: ChangePasswordState,
  formData: FormData,
): Promise<ChangePasswordState> {
  const oldPassword = String(formData.get("old_password") ?? "");
  const newPassword = String(formData.get("new_password") ?? "");
  const confirm = String(formData.get("confirm") ?? "");

  if (!oldPassword) return { error: "Please enter your current password." };
  if (newPassword.length < 8) {
    return { error: "Your new password must be at least 8 characters long." };
  }
  if (newPassword !== confirm) return { error: "The new passwords do not match." };

  try {
    await changePassword({ old_password: oldPassword, new_password: newPassword });
    return { ok: true };
  } catch (err) {
    return {
      error: friendlyMessage(err, "Could not change your password."),
    };
  }
}
