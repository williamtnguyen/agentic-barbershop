import { AlertCircle, ArrowUp } from "lucide-react";
import { type FormEvent, type KeyboardEvent, useEffect, useRef } from "react";

import { DeskAvatar } from "@/components/brand";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

import type { Message, useChat } from "./useChat";

const QUICK_REPLIES = ["Book a haircut", "What do you offer?", "Any openings this Saturday?"];
const timeFormat = new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" });

function Bubble({ message, lastInRun }: { message: Message; lastInRun: boolean }) {
  const mine = message.from === "client";
  return (
    <li className={cn("flex flex-col gap-1", mine ? "items-end" : "items-start")}>
      <div className={cn("flex max-w-[85%] items-end gap-2", mine && "flex-row-reverse")}>
        {!mine &&
          (lastInRun ? <DeskAvatar className="size-7" /> : <span className="w-7 shrink-0" />)}
        <div
          className={cn(
            "rounded-2xl px-3.5 py-2 text-sm leading-relaxed whitespace-pre-wrap [overflow-wrap:anywhere]",
            mine ? "bg-primary text-primary-foreground" : "bg-muted text-foreground",
            lastInRun && (mine ? "rounded-br-sm" : "rounded-bl-sm"),
          )}
        >
          <span className="sr-only">{mine ? "You: " : "Front desk: "}</span>
          {message.text}
        </div>
      </div>
      {lastInRun && (
        <time
          className={cn("text-[11px] text-muted-foreground", mine ? "pr-1" : "pl-10")}
          dateTime={message.at.toISOString()}
        >
          {timeFormat.format(message.at)}
        </time>
      )}
    </li>
  );
}

/** The conversation and composer. Chat state lives in the parent so it survives tab switches. */
export function ChatPanel({
  chat,
  draft,
  setDraft,
  inputRef,
}: {
  chat: ReturnType<typeof useChat>;
  draft: string;
  setDraft: (value: string) => void;
  inputRef: React.RefObject<HTMLTextAreaElement | null>;
}) {
  const { messages, pending, error, send, retry } = chat;
  const threadEnd = useRef<HTMLDivElement>(null);
  const started = messages.some((m) => m.from === "client");

  useEffect(() => {
    threadEnd.current?.scrollIntoView?.({ block: "end" });
  }, [messages, pending, error]);

  function submit(event?: FormEvent) {
    event?.preventDefault();
    if (!draft.trim() || pending) return;
    send(draft);
    setDraft("");
    inputRef.current?.focus();
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      submit();
    }
  }

  return (
    <div className="flex h-full flex-col">
      <section
        aria-label="Conversation"
        aria-live="polite"
        aria-busy={pending}
        className="flex-1 overflow-y-auto px-4 py-5"
      >
        <ol className="flex flex-col gap-1.5">
          {messages.map((m, i) => (
            <Bubble
              key={m.id}
              message={m}
              lastInRun={i === messages.length - 1 || messages[i + 1].from !== m.from}
            />
          ))}
          {pending && (
            <li className="mt-1.5 flex items-end gap-2" aria-label="Front desk is typing">
              <DeskAvatar className="size-7" />
              <div className="flex gap-1 rounded-2xl rounded-bl-sm bg-muted px-3.5 py-3">
                {[0, 1, 2].map((i) => (
                  <span key={i} className="typing-dot size-1.5 rounded-full bg-muted-foreground" />
                ))}
              </div>
            </li>
          )}
        </ol>

        {!started && !pending && (
          <div className="mt-4 flex flex-wrap gap-2 pl-9" aria-label="Suggestions">
            {QUICK_REPLIES.map((text) => (
              <Button
                key={text}
                variant="outline"
                size="sm"
                className="rounded-full"
                onClick={() => send(text)}
              >
                {text}
              </Button>
            ))}
          </div>
        )}

        {error && (
          <div
            role="alert"
            className="mt-4 flex items-center gap-3 rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2.5 text-sm text-destructive"
          >
            <AlertCircle className="size-4 shrink-0" aria-hidden />
            <span className="flex-1">{error}</span>
            <Button variant="outline" size="sm" onClick={retry}>
              Try again
            </Button>
          </div>
        )}
        <div ref={threadEnd} />
      </section>

      <form onSubmit={submit} className="border-t p-3">
        <div className="relative">
          <label htmlFor="message" className="sr-only">
            Message
          </label>
          <Textarea
            id="message"
            ref={inputRef}
            rows={1}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onKeyDown}
            maxLength={2000}
            placeholder="Message the front desk"
            className="max-h-36 min-h-11 resize-none rounded-xl py-2.5 pr-12"
          />
          <Button
            type="submit"
            size="icon"
            aria-label="Send"
            disabled={!draft.trim() || pending}
            className="absolute right-1.5 bottom-1.5 size-8 rounded-lg"
          >
            <ArrowUp />
          </Button>
        </div>
        <p className="mt-2 hidden text-center text-[11px] text-muted-foreground sm:block">
          Press Enter to send, Shift + Enter for a new line
        </p>
      </form>
    </div>
  );
}
