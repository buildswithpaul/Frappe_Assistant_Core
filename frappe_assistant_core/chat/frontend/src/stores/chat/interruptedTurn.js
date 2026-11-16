import { logger } from "@/utils/logger";

// A live turn whose relay stopped writing (its worker died) never ends on its own: ask the
// server to end it as interrupted. Resolves the server's answer when it did, else null.
export async function interruptStaleTurn(sessionId, { fetchLiveTurn, markInterrupted }) {
	let live = null;
	try {
		live = await fetchLiveTurn(sessionId);
	} catch {
		return null;
	}
	if (!live?.stale) return null;
	try {
		const result = await markInterrupted(sessionId);
		return result?.interrupted ? result : null;
	} catch (err) {
		logger.warn("Could not mark the turn interrupted:", err);
		return null;
	}
}
