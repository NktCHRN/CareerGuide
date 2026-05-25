"use server";

import { revalidatePath } from "next/cache";

import { createChat, deleteChat, getChat, sendMessage } from "@/lib/api/chat";
import { friendlyMessage } from "@/lib/api/errors";
import type { ChatDetail, SendMessageResponse } from "@/lib/types";

export async function createChatAction(input: {
  title?: string | null;
  profession_id?: number | null;
}): Promise<{ chatId?: number; error?: string }> {
  try {
    const chat = await createChat(input);
    revalidatePath("/chats");
    return { chatId: chat.id };
  } catch (err) {
    return { error: friendlyMessage(err, "Could not start the chat.") };
  }
}

export async function sendMessageAction(
  chatId: number,
  content: string,
): Promise<{ ok?: boolean; error?: string; data?: SendMessageResponse }> {
  const text = content.trim();
  if (!text) return { error: "Please type a message." };
  try {
    const data = await sendMessage(chatId, text);
    return { ok: true, data };
  } catch (err) {
    return {
      error: friendlyMessage(err, "The assistant could not reply. Please try again."),
    };
  }
}

export async function deleteChatAction(chatId: number): Promise<void> {
  await deleteChat(chatId);
  revalidatePath("/chats");
}

export async function getChatAction(chatId: number): Promise<ChatDetail> {
  return getChat(chatId);
}
