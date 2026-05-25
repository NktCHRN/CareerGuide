"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { createChatAction } from "@/actions/chat";
import { PlusIcon } from "@/components/icons";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";

export function NewChatButton() {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string>();

  const start = () => {
    setError(undefined);
    startTransition(async () => {
      const res = await createChatAction({});
      if (res.chatId) router.push(`/chats/${res.chatId}`);
      else setError(res.error ?? "Could not start a chat.");
    });
  };

  return (
    <div className="flex flex-col items-end">
      <Button size="sm" onClick={start} disabled={pending}>
        {pending ? <Spinner /> : <PlusIcon />}
        New chat
      </Button>
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
    </div>
  );
}
