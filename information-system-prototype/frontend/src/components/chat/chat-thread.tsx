"use client";

import { useMutation } from "@tanstack/react-query";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";

import { sendMessageAction } from "@/actions/chat";
import { SendIcon } from "@/components/icons";
import { cn } from "@/lib/cn";
import { formatTime } from "@/lib/format";
import type { ChatMessage } from "@/lib/types";

const SUGGESTIONS = [
  "Is this a good fit for my profile?",
  "What skills should I learn next?",
  "Draft a short learning plan for me.",
];

export function ChatThread({
  chatId,
  initialMessages,
  professionBound,
}: {
  chatId: number;
  initialMessages: ChatMessage[];
  professionBound: boolean;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [pendingUser, setPendingUser] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string>();
  const endRef = useRef<HTMLDivElement>(null);

  const mutation = useMutation({
    mutationFn: (content: string) => sendMessageAction(chatId, content),
    onSuccess: (res, content) => {
      if (res.error || !res.data) {
        setError(res.error ?? "The assistant could not reply.");
        setDraft(content);
        setPendingUser(null);
        return;
      }
      setMessages((prev) => [
        ...prev,
        res.data!.user_message,
        res.data!.assistant_message,
      ]);
      setPendingUser(null);
    },
    onError: (_e, content) => {
      setError("The assistant could not reply. Please try again.");
      setDraft(content);
      setPendingUser(null);
    },
  });

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, pendingUser]);

  const send = (text: string) => {
    const content = text.trim();
    if (!content || mutation.isPending) return;
    setError(undefined);
    setPendingUser(content);
    setDraft("");
    mutation.mutate(content);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(draft);
    }
  };

  const isEmpty = messages.length === 0 && !pendingUser;

  return (
    <div className="flex h-[calc(100vh-13rem)] flex-col rounded-[var(--radius-card)] border border-slate-200 bg-white shadow-[var(--shadow-card)]">
      <div className="scroll-area flex-1 space-y-4 overflow-y-auto p-4 sm:p-6">
        {isEmpty && (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <p className="text-sm text-slate-500">
              Ask anything about{" "}
              {professionBound ? "this profession" : "careers, skills or résumés"}.
            </p>
            <div className="mt-4 flex flex-wrap justify-center gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => send(s)}
                  className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs text-slate-600 hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m) => (
          <Bubble key={m.id} role={m.role} content={m.content} time={m.created_at} />
        ))}

        {pendingUser && (
          <>
            <Bubble role="user" content={pendingUser} />
            <TypingBubble />
          </>
        )}

        {error && (
          <p className="text-center text-xs text-red-600">{error}</p>
        )}
        <div ref={endRef} />
      </div>

      <div className="border-t border-slate-100 p-3 sm:p-4">
        <div className="flex items-end gap-2">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onKeyDown}
            rows={1}
            placeholder="Type your message…"
            className="scroll-area max-h-32 min-h-11 flex-1 resize-none rounded-xl border border-slate-300 px-3.5 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:border-brand-500 focus-visible:ring-2 focus-visible:ring-brand-500"
          />
          <button
            type="button"
            onClick={() => send(draft)}
            disabled={!draft.trim() || mutation.isPending}
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-brand-600 text-white transition-colors hover:bg-brand-700 disabled:opacity-50"
            aria-label="Send message"
          >
            <SendIcon className="text-lg" />
          </button>
        </div>
        <p className="mt-1.5 px-1 text-[11px] text-slate-400">
          Press Enter to send, Shift+Enter for a new line.
        </p>
      </div>
    </div>
  );
}

function Bubble({
  role,
  content,
  time,
}: {
  role: ChatMessage["role"];
  content: string;
  time?: string;
}) {
  const isUser = role === "user";
  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed sm:max-w-[75%]",
          isUser
            ? "rounded-br-md bg-brand-600 text-white"
            : "rounded-bl-md bg-slate-100 text-slate-800",
        )}
      >
        <p className="whitespace-pre-wrap">{content}</p>
        {time && (
          <p
            className={cn(
              "mt-1 text-[10px]",
              isUser ? "text-brand-100" : "text-slate-400",
            )}
          >
            {formatTime(time)}
          </p>
        )}
      </div>
    </div>
  );
}

function TypingBubble() {
  return (
    <div className="flex justify-start">
      <div className="flex items-center gap-1 rounded-2xl rounded-bl-md bg-slate-100 px-4 py-3">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="h-2 w-2 animate-bounce rounded-full bg-slate-400"
            style={{ animationDelay: `${i * 0.15}s` }}
          />
        ))}
      </div>
    </div>
  );
}
