import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { ChatThread } from "@/components/chat/chat-thread";
import { DeleteChatButton } from "@/components/chat/delete-chat-button";
import { ChevronLeftIcon, ExternalLinkIcon } from "@/components/icons";
import { Badge } from "@/components/ui/badge";
import { getChat } from "@/lib/api/chat";
import { ApiError } from "@/lib/api/errors";

export const metadata: Metadata = { title: "Chat" };

export default async function ChatPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id: idParam } = await params;
  const id = Number(idParam);
  if (!Number.isInteger(id)) notFound();

  let chat;
  try {
    chat = await getChat(id);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) notFound();
    throw err;
  }

  return (
    <div className="mx-auto max-w-3xl">
      <Link
        href="/chats"
        className="mb-3 inline-flex items-center gap-1 text-sm font-medium text-slate-500 hover:text-slate-700"
      >
        <ChevronLeftIcon /> All chats
      </Link>

      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="min-w-0">
          <h1 className="truncate text-xl font-semibold tracking-tight text-slate-900">
            {chat.title}
          </h1>
          {chat.profession_id !== null && (
            <Link
              href={`/professions/${chat.profession_id}`}
              className="mt-1 inline-flex items-center gap-1 text-xs font-medium text-brand-600 hover:text-brand-700"
            >
              <Badge tone="brand">Linked profession</Badge>
              View profession <ExternalLinkIcon />
            </Link>
          )}
        </div>
        <DeleteChatButton chatId={chat.id} title={chat.title} redirectTo="/chats" />
      </div>

      <ChatThread
        chatId={chat.id}
        initialMessages={chat.messages}
        professionBound={chat.profession_id !== null}
      />
    </div>
  );
}
