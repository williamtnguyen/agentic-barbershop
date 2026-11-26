import { CalendarDays, MessageCircle, RotateCcw } from "lucide-react";
import { useRef, useState } from "react";

import { DeskAvatar } from "@/components/brand";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { config } from "@/config";
import { BookPanel } from "@/features/booking/BookPanel";
import { ChatPanel } from "@/features/chat/ChatPanel";
import { useChat } from "@/features/chat/useChat";
import { cn } from "@/lib/utils";

type Tab = "book" | "chat";

function initialTab(): Tab {
  return window.location.hash === "#chat" ? "chat" : "book";
}

export function App() {
  const [tab, setTab] = useState<Tab>(initialTab);
  const chat = useChat();
  const [draft, setDraft] = useState("");
  const input = useRef<HTMLTextAreaElement>(null);
  const chatStarted = chat.messages.some((m) => m.from === "client");

  function changeTab(next: string) {
    setTab(next as Tab);
    window.history.replaceState(null, "", next === "chat" ? "#chat" : window.location.pathname);
  }

  function newChat() {
    chat.reset();
    setDraft("");
    input.current?.focus();
  }

  return (
    <div className="flex min-h-dvh justify-center bg-muted/50 sm:items-center sm:p-6">
      <Card className="relative h-dvh w-full gap-0 overflow-hidden rounded-none border-0 py-0 shadow-none sm:h-[min(52rem,calc(100dvh-3rem))] sm:max-w-xl sm:rounded-xl sm:border sm:shadow-sm">
        <Tabs value={tab} onValueChange={changeTab} className="h-full min-h-0 gap-0">
          <header className="relative border-b px-4 pt-3 pb-3">
            <div className="flex items-center gap-3">
              <DeskAvatar className="size-10" />
              <div className="min-w-0 flex-1">
                <CardTitle className="truncate text-base">{config.businessName}</CardTitle>
                <CardDescription className="mt-1 flex items-center gap-1.5 text-xs">
                  <span className="size-1.5 rounded-full bg-success" aria-hidden />
                  Open for online booking
                </CardDescription>
              </div>
              {tab === "chat" && (
                <Button variant="ghost" size="sm" onClick={newChat} disabled={!chatStarted}>
                  <RotateCcw />
                  New chat
                </Button>
              )}
            </div>
            <TabsList className="mt-3 w-full">
              <TabsTrigger value="book">
                <CalendarDays />
                Book
              </TabsTrigger>
              <TabsTrigger value="chat">
                <MessageCircle />
                Chat
              </TabsTrigger>
            </TabsList>
            <div
              className={cn(
                "absolute inset-x-0 -bottom-px h-0.5 transition-opacity",
                chat.pending ? "pole-progress opacity-100" : "opacity-0",
              )}
              aria-hidden
            />
          </header>

          <TabsContent
            value="book"
            forceMount
            className="min-h-0 overflow-y-auto data-[state=inactive]:hidden"
          >
            <BookPanel />
          </TabsContent>
          <TabsContent
            value="chat"
            forceMount
            className="min-h-0 data-[state=inactive]:hidden"
          >
            <ChatPanel chat={chat} draft={draft} setDraft={setDraft} inputRef={input} />
          </TabsContent>
        </Tabs>
      </Card>
    </div>
  );
}
