// turns.js — pure helpers for the single-column document chat (Quiet Ledger §3.1).
// No Vue, no DOM — kept pure so it is unit-testable.

/**
 * Classify a chat message row into a render "kind".
 * @param {{role?: string, content?: string}} message
 * @returns {"user"|"assistant"|"divider"}
 */
export function turnKind(message) {
  if (!message || typeof message !== "object") return "assistant";
  if (message.role === "divider") return "divider";
  if (message.role === "user") return "user";
  return "assistant";
}

/** Uppercase rail label for a turn. */
export function turnLabel(message) {
  const kind = turnKind(message);
  if (kind === "user") return "YOU";
  if (kind === "assistant") return "FACO";
  return "";
}

/**
 * First uppercase letter for the ink-initial user avatar.
 * Falls back to "U" when no user identifier is available.
 */
export function userInitial(user) {
  if (typeof user === "string" && user.trim()) {
    return user.trim().charAt(0).toUpperCase();
  }
  return "U";
}
