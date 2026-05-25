"use server";

import { revalidatePath } from "next/cache";

import {
  createProfession,
  deleteProfession,
  getPhotoUploadUrl,
  updateProfession,
} from "@/lib/api/career";
import { friendlyMessage } from "@/lib/api/errors";
import type { ProfessionCreate, ProfessionUpdate } from "@/lib/types";

export interface ProfessionFormResult {
  ok?: boolean;
  error?: string;
  id?: number;
}

export async function createProfessionAction(
  payload: ProfessionCreate,
): Promise<ProfessionFormResult> {
  try {
    const p = await createProfession(payload);
    revalidatePath("/admin/professions");
    return { ok: true, id: p.id };
  } catch (err) {
    return { error: friendlyMessage(err, "Could not create the profession.") };
  }
}

export async function updateProfessionAction(
  id: number,
  payload: ProfessionUpdate,
): Promise<ProfessionFormResult> {
  try {
    await updateProfession(id, payload);
    revalidatePath("/admin/professions");
    revalidatePath(`/professions/${id}`);
    revalidatePath(`/admin/professions/${id}/edit`);
    return { ok: true, id };
  } catch (err) {
    return { error: friendlyMessage(err, "Could not update the profession.") };
  }
}

export async function deleteProfessionAction(id: number): Promise<void> {
  await deleteProfession(id);
  revalidatePath("/admin/professions");
}

/**
 * Fetch a presigned PUT URL from career-service and upload the image to S3/MinIO
 * server-side (avoids browser→MinIO CORS). Per FR13–15 admin photo management.
 */
export async function uploadProfessionPhotoAction(
  id: number,
  formData: FormData,
): Promise<{ ok?: boolean; error?: string }> {
  const file = formData.get("file");
  if (!(file instanceof File) || file.size === 0) {
    return { error: "Please choose an image to upload." };
  }
  const allowed = ["image/jpeg", "image/png", "image/webp"];
  if (!allowed.includes(file.type)) {
    return { error: "Use a JPEG, PNG or WebP image." };
  }
  if (file.size > 5 * 1024 * 1024) {
    return { error: "The image is too large (max 5 MB)." };
  }

  try {
    const presign = await getPhotoUploadUrl(id, file.type);
    const bytes = Buffer.from(await file.arrayBuffer());
    const put = await fetch(presign.url, {
      method: "PUT",
      headers: { "content-type": presign.content_type },
      body: bytes,
    });
    if (!put.ok) {
      return { error: `Upload to storage failed (${put.status}).` };
    }
    revalidatePath(`/professions/${id}`);
    revalidatePath(`/admin/professions/${id}/edit`);
    return { ok: true };
  } catch (err) {
    return { error: friendlyMessage(err, "Could not upload the photo.") };
  }
}
