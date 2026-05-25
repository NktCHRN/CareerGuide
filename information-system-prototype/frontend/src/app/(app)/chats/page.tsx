import type { Metadata } from "next";
import Link from "next/link";

import { DeleteChatButton } from "@/components/chat/delete-chat-button";
import { NewChatButton } from "@/components/chat/new-chat-button";
import { ChatIcon } from "@/components/icons";
import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Pagination } from "@/components/ui/pagination";
import { listChats } from "@/lib/api/chat";
import { formatDate } from "@/lib/format";

export const metadata: Metadata = { title: "Chats" };

const PAGE_SIZE = 15;

function first(v: string | string[] | undefined): string | undefined {
  return Array.isArray(v) ? v[0] : v;
}

export default async function ChatsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = await searchParams;
  const page = Math.max(1, Number(first(sp.page)) || 1);
  const chats = await listChats({ page, page_size: PAGE_SIZE });

  return (
    <>
      <PageHeader
        title="Your chats"
        description="Ask the assistant about professions, your fit, learning plans or your résumé."
        actions={<NewChatButton />}
      />

      {chats.items.length === 0 ? (
        <EmptyState
          icon={<ChatIcon />}
          title="No chats yet"
          description="Start a new conversation, or open a profession and tap “Ask the assistant”."
          action={<NewChatButton />}
        />
      ) : (
        <>
          <Card className="divide-y divide-slate-100">
            {chats.items.map((chat) => (
              <div
                key={chat.id}
                className="flex items-center gap-3 px-4 py-3.5 transition-colors hover:bg-slate-50/70 sm:px-5"
              >
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
                  <ChatIcon className="text-lg" />
                </span>
                <Link href={`/chats/${chat.id}`} className="min-w-0 flex-1">
                  <p className="truncate font-medium text-slate-900">{chat.title}</p>
                  <p className="mt-0.5 flex items-center gap-2 text-xs text-slate-400">
                    Updated {formatDate(chat.updated_at)}
                    {chat.profession_id !== null && (
                      <Badge tone="brand">Profession</Badge>
                    )}
                  </p>
                </Link>
                <DeleteChatButton chatId={chat.id} title={chat.title} />
              </div>
            ))}
          </Card>
          <Pagination
            page={chats.page}
            pageSize={chats.page_size}
            total={chats.total}
          />
        </>
      )}
    </>
  );
}
