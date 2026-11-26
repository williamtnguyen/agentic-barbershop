import { config } from "@/config";

export interface ChatReply {
  conversationId: string;
  reply: string;
}

export class ChatError extends Error {}

/** Send one message to the front desk. Pass the conversationId from the previous reply. */
export async function sendChat(message: string, conversationId?: string): Promise<ChatReply> {
  let response: Response;
  try {
    response = await fetch(`${config.apiBaseUrl}/chat`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(conversationId ? { message, conversation_id: conversationId } : { message }),
    });
  } catch {
    throw new ChatError("Couldn't reach the front desk. Check your connection and try again.");
  }

  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new ChatError(
      response.status === 422
        ? "That message couldn't be sent. Keep it under 2,000 characters."
        : "The front desk didn't answer. Try again in a moment.",
    );
  }
  return { conversationId: body.conversation_id, reply: body.reply };
}

// --- Booking ----------------------------------------------------------------

export interface Service {
  id: string;
  name: string;
  minutes: number;
  price: string;
  description?: string | null;
}

export interface TimeSlot {
  start: string; // YYYY-MM-DDTHH:MM, shop-local
  label: string;
}

export interface BookingInput {
  serviceId: string;
  start: string;
  phone: string;
  firstName: string;
  lastName?: string;
  note?: string;
}

export interface BookingResult {
  bookingId: string;
  service: string;
  start: string;
  when: string;
  client: string;
}

/** An API failure. `message` is safe to show; `status` is 0 for network failures. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${config.apiBaseUrl}${path}`, init);
  } catch {
    throw new ApiError("Couldn't reach the shop. Check your connection and try again.", 0);
  }
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof body.detail === "string" ? body.detail : null;
    throw new ApiError(
      detail ??
        (response.status === 422
          ? "Check the highlighted details and try again."
          : "Something went wrong on our side. Try again in a moment."),
      response.status,
    );
  }
  return body as T;
}

export async function getServices(): Promise<Service[]> {
  const services = await request<unknown>("/services");
  if (!Array.isArray(services)) {
    throw new ApiError("Something went wrong on our side. Try again in a moment.", 500);
  }
  return services as Service[];
}

export async function getOpenDays(serviceId: string, month: string): Promise<string[]> {
  const q = new URLSearchParams({ service_id: serviceId, month });
  return (await request<{ days: string[] }>(`/availability/days?${q}`)).days;
}

export async function getOpenTimes(serviceId: string, date: string): Promise<TimeSlot[]> {
  const q = new URLSearchParams({ service_id: serviceId, date });
  return (await request<{ slots: TimeSlot[] }>(`/availability?${q}`)).slots;
}

export async function createBooking(input: BookingInput): Promise<BookingResult> {
  const body = await request<{
    booking_id: string;
    service: string;
    start: string;
    when: string;
    client: string;
  }>("/bookings", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      service_id: input.serviceId,
      start: input.start,
      phone: input.phone,
      first_name: input.firstName,
      last_name: input.lastName || undefined,
      note: input.note || undefined,
    }),
  });
  return {
    bookingId: body.booking_id,
    service: body.service,
    start: body.start,
    when: body.when,
    client: body.client,
  };
}
