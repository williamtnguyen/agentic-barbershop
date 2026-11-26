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
