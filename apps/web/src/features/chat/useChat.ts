import { useCallback, useRef, useState } from "react";

import { ChatError, sendChat } from "@/lib/api";

export interface Message {
  id: number;
  from: "client" | "desk";
  text: string;
  at: Date;
}

export const GREETING =
  "Hey! I can book you in or answer questions about cuts, prices and hours. What do you need?";

const greeting = (): Message => ({ id: 0, from: "desk", text: GREETING, at: new Date() });

/** Conversation state for one chat with the front desk. */
export function useChat() {
  const [messages, setMessages] = useState<Message[]>(() => [greeting()]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const conversationId = useRef<string | undefined>(undefined);
  const nextId = useRef(1);
  const lastFailed = useRef<string | null>(null);
  // Bumped on reset, so a reply to an abandoned conversation is ignored.
  const generation = useRef(0);

  const deliver = useCallback(async (text: string) => {
    const gen = generation.current;
    setPending(true);
    setError(null);
    try {
      const { conversationId: id, reply } = await sendChat(text, conversationId.current);
      if (gen !== generation.current) return;
      conversationId.current = id;
      lastFailed.current = null;
      setMessages((all) => [
        ...all,
        { id: nextId.current++, from: "desk", text: reply, at: new Date() },
      ]);
    } catch (err) {
      if (gen !== generation.current) return;
      lastFailed.current = text;
      setError(err instanceof ChatError ? err.message : "Something went wrong. Try again.");
    } finally {
      if (gen === generation.current) setPending(false);
    }
  }, []);

  const send = useCallback(
    (raw: string) => {
      const text = raw.trim();
      if (!text || pending) return;
      setMessages((all) => [
        ...all,
        { id: nextId.current++, from: "client", text, at: new Date() },
      ]);
      void deliver(text);
    },
    [deliver, pending],
  );

  const retry = useCallback(() => {
    if (lastFailed.current && !pending) void deliver(lastFailed.current);
  }, [deliver, pending]);

  const reset = useCallback(() => {
    generation.current += 1;
    conversationId.current = undefined;
    lastFailed.current = null;
    setPending(false);
    setError(null);
    setMessages([greeting()]);
  }, []);

  return { messages, pending, error, send, retry, reset };
}
