"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { createChatAction } from "@/actions/chat";
import { ChatIcon } from "@/components/icons";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";

export function AskAssistantButton({
  professionId,
  label,
}: {
  professionId: number;
  label: string;
}) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string>();

  const start = () => {
    setError(undefined);
    startTransition(async () => {
      const res = await createChatAction({
        profession_id: professionId,
        title: `About ${label}`,
      });
      if (res.chatId) {
        router.push(`/chats/${res.chatId}`);
      } else {
        setError(res.error ?? "Could not start the chat.");
      }
    });
  };

  return (
    <div>
      <Button onClick={start} disabled={pending}>
        {pending ? <Spinner /> : <ChatIcon className="text-base" />}
        Ask the assistant
      </Button>
      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
    </div>
  );
}
