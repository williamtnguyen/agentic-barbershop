import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ChatPage } from "./ChatPage";
import { GREETING } from "./useChat";

type Reply = { status?: number; body?: unknown } | Error;

function mockApi(...replies: Reply[]) {
  const fetchMock = vi.fn(async (_url: string, _init: RequestInit) => {
    const next = replies.shift();
    if (!next) throw new Error("no more scripted replies");
    if (next instanceof Error) throw next;
    return new Response(JSON.stringify(next.body ?? {}), { status: next.status ?? 200 });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function sentBodies(fetchMock: ReturnType<typeof mockApi>) {
  return fetchMock.mock.calls.map(([, init]) => JSON.parse(init.body as string));
}

async function type(text: string) {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Message"), text);
  await user.click(screen.getByRole("button", { name: "Send" }));
}

describe("ChatPage", () => {
  beforeEach(() => vi.unstubAllGlobals());
  afterEach(() => vi.unstubAllGlobals());

  it("opens with a greeting and quick replies", () => {
    render(<ChatPage />);
    expect(screen.getByText(GREETING)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Any openings this Saturday?" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  });

  it("sends messages and keeps the same conversation", async () => {
    const fetchMock = mockApi(
      { body: { conversation_id: "c1", reply: "Saturday I have 10:00 or 11:30." } },
      { body: { conversation_id: "c1", reply: "Booked for 11:30." } },
    );
    render(<ChatPage />);

    await type("any openings saturday?");
    expect(await screen.findByText("Saturday I have 10:00 or 11:30.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Book a haircut" })).not.toBeInTheDocument();

    await type("11:30");
    expect(await screen.findByText("Booked for 11:30.")).toBeInTheDocument();

    expect(fetchMock.mock.calls[0][0]).toBe("/api/chat");
    expect(sentBodies(fetchMock)).toEqual([
      { message: "any openings saturday?" },
      { message: "11:30", conversation_id: "c1" },
    ]);
  });

  it("sends a quick reply when tapped", async () => {
    const fetchMock = mockApi({ body: { conversation_id: "c1", reply: "Full Service, Clipper Cut, Beard Trim." } });
    render(<ChatPage />);

    await userEvent.setup().click(screen.getByRole("button", { name: "What do you offer?" }));

    expect(await screen.findByText("Full Service, Clipper Cut, Beard Trim.")).toBeInTheDocument();
    expect(sentBodies(fetchMock)).toEqual([{ message: "What do you offer?" }]);
  });

  it("shows a connection error and retries the same message", async () => {
    const fetchMock = mockApi(new TypeError("network down"), {
      body: { conversation_id: "c1", reply: "Hey! What can I do for you?" },
    });
    render(<ChatPage />);

    await type("hello");
    expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't reach the front desk");

    await userEvent.setup().click(screen.getByRole("button", { name: "Try again" }));

    expect(await screen.findByText("Hey! What can I do for you?")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
    expect(sentBodies(fetchMock)).toEqual([{ message: "hello" }, { message: "hello" }]);
    expect(screen.getAllByText("hello")).toHaveLength(1);
  });

  it("explains a server failure", async () => {
    mockApi({ status: 502, body: { detail: "The assistant couldn't respond. Try again." } });
    render(<ChatPage />);

    await type("hi");

    expect(await screen.findByRole("alert")).toHaveTextContent("The front desk didn't answer");
  });
});

describe("ChatPage composer and new chat", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("sends on Enter and adds a line on Shift+Enter", async () => {
    const fetchMock = mockApi({ body: { conversation_id: "c1", reply: "Got it." } });
    render(<ChatPage />);
    const user = userEvent.setup();
    const box = screen.getByLabelText("Message");

    await user.type(box, "fade{Shift>}{Enter}{/Shift}low on the sides");
    expect(box).toHaveValue("fade\nlow on the sides");
    expect(fetchMock).not.toHaveBeenCalled();

    await user.type(box, "{Enter}");
    expect(await screen.findByText("Got it.")).toBeInTheDocument();
    expect(sentBodies(fetchMock)).toEqual([{ message: "fade\nlow on the sides" }]);
    expect(box).toHaveValue("");
  });

  it("starts a fresh conversation with New chat", async () => {
    const fetchMock = mockApi(
      { body: { conversation_id: "c1", reply: "Sure, which day?" } },
      { body: { conversation_id: "c2", reply: "Hey again!" } },
    );
    render(<ChatPage />);
    const user = userEvent.setup();
    expect(screen.getByRole("button", { name: "New chat" })).toBeDisabled();

    await type("book me in");
    await screen.findByText("Sure, which day?");
    await user.click(screen.getByRole("button", { name: "New chat" }));

    expect(screen.queryByText("Sure, which day?")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Book a haircut" })).toBeInTheDocument();

    await type("hi");
    await screen.findByText("Hey again!");
    expect(sentBodies(fetchMock)).toEqual([{ message: "book me in" }, { message: "hi" }]);
  });
});
