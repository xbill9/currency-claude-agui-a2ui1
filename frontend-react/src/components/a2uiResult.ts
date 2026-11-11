// Kept free of @a2ui imports so it is safe during server rendering.

/** Pulls the A2UI message list out of a tool result (object or JSON string). */
export function extractA2uiMessages(result: unknown): unknown[] | null {
  let value: any = result;
  if (typeof value === "string") {
    try {
      value = JSON.parse(value);
    } catch {
      return null;
    }
  }
  const messages = value?.validated_a2ui_json;
  return Array.isArray(messages) && messages.length > 0 ? messages : null;
}
