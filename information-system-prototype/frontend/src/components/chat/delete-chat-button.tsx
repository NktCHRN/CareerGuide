"use client";

import { useRouter } from "next/navigation";

import { deleteChatAction } from "@/actions/chat";
import { TrashIcon } from "@/components/icons";
import { ConfirmButton } from "@/components/ui/confirm-button";

export function DeleteChatButton({
  chatId,
  title,
  redirectTo,
}: {
  chatId: number;
  title: string;
  redirectTo?: string;
}) {
  const router = useRouter();

  return (
    <ConfirmButton
      title="Delete chat"
      message={
        <>
          Delete <span className="font-medium">“{title}”</span>? This permanently
          removes the conversation and its messages.
        </>
      }
      confirmLabel="Delete chat"
      onConfirm={async () => {
        await deleteChatAction(chatId);
        if (redirectTo) router.push(redirectTo);
        else router.refresh();
      }}
      trigger={(open) => (
        <button
          type="button"
          onClick={open}
          className="rounded-md p-2 text-slate-400 transition-colors hover:bg-red-50 hover:text-red-600"
          aria-label={`Delete chat ${title}`}
        >
          <TrashIcon className="text-base" />
        </button>
      )}
    />
  );
}
