import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { BookPanel } from "./BookPanel";

const SERVICES = [
  { id: "SV_FULL", name: "Full Service", minutes: 80, price: "$40.00", description: "Scissor cut." },
  { id: "SV_CLIPPER", name: "Clipper Cut", minutes: 55, price: "$30.00", description: null },
];
const SLOTS = [
  { start: "2026-11-19T12:00", label: "12:00 PM" },
  { start: "2026-11-19T12:30", label: "12:30 PM" },
];

type Handler = (url: URL, init?: RequestInit) => { status?: number; body: unknown } | Error;

function mockApi(overrides: Partial<Record<"services" | "days" | "times" | "book", Handler>> = {}) {
  const routes: Record<string, Handler> = {
    services: () => ({ body: SERVICES }),
    days: () => ({ body: { days: ["2026-11-19", "2026-11-21"] } }),
    times: () => ({ body: { slots: SLOTS } }),
    book: () => ({
      status: 201,
      body: {
        booking_id: "BK_1",
        service: "Clipper Cut",
        start: "2026-11-19T12:00",
        when: "Thursday, November 19 at 12:00 PM",
        client: "Sam",
      },
    }),
    ...overrides,
  };
  const fetchMock = vi.fn(async (input: string, init?: RequestInit) => {
    const url = new URL(input, "http://test");
    const route = url.pathname.endsWith("/services")
      ? "services"
      : url.pathname.endsWith("/availability/days")
        ? "days"
        : url.pathname.endsWith("/availability")
          ? "times"
          : "book";
    const result = routes[route](url, init);
    if (result instanceof Error) throw result;
    return new Response(JSON.stringify(result.body), { status: result.status ?? 200 });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function calls(fetchMock: ReturnType<typeof mockApi>, path: string) {
  return fetchMock.mock.calls.filter(([input]) => new URL(input, "http://test").pathname.endsWith(path));
}

async function pickClipperThursdayNoon() {
  const user = userEvent.setup();
  await user.click(await screen.findByRole("radio", { name: /Clipper Cut/ }));
  await user.click(await screen.findByRole("button", { name: "Thursday, November 19" }));
  await user.click(await screen.findByRole("radio", { name: "12:00 PM" }));
  return user;
}

describe("BookPanel", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 10, 18, 12, 0)); // Wed Nov 18, 2026
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("books a service, day and time", async () => {
    const fetchMock = mockApi();
    render(<BookPanel />);

    const user = await pickClipperThursdayNoon();
    expect(screen.getByRole("button", { name: "Friday, November 20, no openings" })).toBeDisabled();
    expect(calls(fetchMock, "/availability/days")[0][0]).toContain("service_id=SV_CLIPPER&month=2026-11");

    await user.type(screen.getByLabelText("First name"), "Sam");
    await user.type(screen.getByLabelText("Mobile number"), "(408) 555-0123");
    await user.type(screen.getByLabelText(/Note for the barber/), "low fade");
    await user.click(screen.getByRole("button", { name: "Book Thursday, Nov 19 at 12:00 PM" }));

    expect(await screen.findByRole("heading", { name: "You're booked, Sam" })).toBeInTheDocument();
    expect(screen.getByText("Clipper Cut on Thursday, November 19 at 12:00 PM")).toBeInTheDocument();
    const [, init] = calls(fetchMock, "/bookings")[0];
    expect(JSON.parse(init!.body as string)).toEqual({
      service_id: "SV_CLIPPER",
      start: "2026-11-19T12:00",
      phone: "(408) 555-0123",
      first_name: "Sam",
      note: "low fade",
    });
  });

  it("asks for a valid phone number before booking", async () => {
    const fetchMock = mockApi();
    render(<BookPanel />);
    const user = await pickClipperThursdayNoon();

    await user.type(screen.getByLabelText("First name"), "Sam");
    await user.type(screen.getByLabelText("Mobile number"), "555");
    await user.click(screen.getByRole("button", { name: /^Book Thursday/ }));

    expect(screen.getByText("Enter a 10-digit US number.")).toBeInTheDocument();
    expect(calls(fetchMock, "/bookings")).toHaveLength(0);
  });

  it("refreshes the times when the chosen one was just taken", async () => {
    const fetchMock = mockApi({
      book: () => ({ status: 409, body: { detail: "That time was just taken. Pick another time." } }),
    });
    render(<BookPanel />);
    const user = await pickClipperThursdayNoon();

    await user.type(screen.getByLabelText("First name"), "Sam");
    await user.type(screen.getByLabelText("Mobile number"), "4085550123");
    await user.click(screen.getByRole("button", { name: /^Book Thursday/ }));

    expect(await screen.findByRole("alert")).toHaveTextContent("That time was just taken");
    expect(screen.queryByLabelText("First name")).not.toBeInTheDocument();
    await waitFor(() => expect(calls(fetchMock, "/availability")).toHaveLength(2));
  });

  it("lets the client retry when services fail to load", async () => {
    let fail = true;
    mockApi({ services: () => (fail ? new TypeError("offline") : { body: SERVICES }) });
    render(<BookPanel />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't reach the shop");
    fail = false;
    await userEvent.setup().click(screen.getByRole("button", { name: "Try again" }));

    expect(await screen.findByRole("radio", { name: /Full Service/ })).toBeInTheDocument();
  });

  it("starts over after booking", async () => {
    mockApi();
    render(<BookPanel />);
    const user = await pickClipperThursdayNoon();
    await user.type(screen.getByLabelText("First name"), "Sam");
    await user.type(screen.getByLabelText("Mobile number"), "4085550123");
    await user.click(screen.getByRole("button", { name: /^Book Thursday/ }));

    await user.click(await screen.findByRole("button", { name: "Book another appointment" }));

    expect(screen.getByRole("radio", { name: /Clipper Cut/ })).toHaveAttribute("aria-checked", "false");
    expect(screen.queryByText(/^Time on/)).not.toBeInTheDocument();
  });
});
