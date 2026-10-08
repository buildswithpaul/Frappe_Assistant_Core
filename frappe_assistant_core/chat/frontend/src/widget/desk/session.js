// Frappe Assistant Copilot - Powered by FAC Cloud
// Copyright (C) 2025 Paul Clinton
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU Affero General Public License for more details.
//
// You should have received a copy of the GNU Affero General Public License
// along with this program.  If not, see <https://www.gnu.org/licenses/>.

/**
 * Session identity for the widget.
 *
 * sessionStorage is COPIED into the new tab by "Duplicate tab", middle-click,
 * and target="_blank" — so a stored session id is not proof that this tab owns
 * it. Before adopting one we ask the other tabs whether a live widget still
 * holds it; a reload has no live owner to answer, a duplicated tab does.
 *
 * It also survives a logout, and carries no user of its own. A stored entry
 * therefore records the user it was minted for, and is adopted only by that
 * user — otherwise the next person to log in continues the last person's
 * conversation. Entries are {id, user}; anything else is not adoptable.
 */
export const CHANNEL_NAME = "faco_widget_session_claims";
const CLAIM_WAIT_MS = 150;
const HANDOFF_KEY = "faco_widget_session";
const PERSISTED_KEY = "faco_widget_persistent_session";
const ACTIVE_KEY = "faco_active_session";

/** Serialize a session id and the user who minted it for storage. */
export function encode(id, user) {
	return JSON.stringify({ id: id, user: user || null });
}

/** Parse a stored value into {id, user}, or null if it is not adoptable. */
export function decode(raw) {
	if (!raw) return null;
	try {
		const parsed = JSON.parse(raw);
		if (parsed && typeof parsed === "object" && parsed.id) {
			return { id: String(parsed.id), user: parsed.user || null };
		}
	} catch {
		// A bare id written by an older build — no owner, so not adoptable.
	}
	return null;
}

/** The id in `entry` if `owner` minted it, else null. */
export function owned(entry, owner) {
	if (!entry || !entry.id || !entry.user || !owner) return null;
	return entry.user === owner ? entry.id : null;
}

export async function resolve({ stored, persisted, owner, isClaimed, generate }) {
	const consumed_handoff = !!stored;
	const candidate = owned(stored, owner) || owned(persisted, owner) || null;

	if (!candidate) {
		return { session_id: generate(), restored: false, consumed_handoff };
	}

	let claimed = false;
	try {
		claimed = await isClaimed(candidate);
	} catch {
		claimed = false;
	}

	if (claimed) {
		return { session_id: generate(), restored: false, consumed_handoff };
	}
	return { session_id: candidate, restored: true, consumed_handoff };
}

export function makeClaimProbe(waitMs = CLAIM_WAIT_MS) {
	return (sessionId) =>
		new Promise((resolve) => {
			let channel;
			try {
				channel = new BroadcastChannel(CHANNEL_NAME);
			} catch {
				resolve(false);
				return;
			}

			let settled = false;
			const finish = (held) => {
				if (settled) return;
				settled = true;
				try {
					channel.close();
				} catch {
					// Channel already closed.
				}
				resolve(held);
			};

			channel.onmessage = (event) => {
				const data = event && event.data;
				if (data && data.type === "claim_held" && data.session_id === sessionId) {
					finish(true);
				}
			};

			channel.postMessage({ type: "claim_check", session_id: sessionId });
			setTimeout(() => finish(false), waitMs);
		});
}

/** Answer other tabs' claim checks for as long as this tab holds the session. */
export function startClaimResponder(getSessionId) {
	let channel;
	try {
		channel = new BroadcastChannel(CHANNEL_NAME);
	} catch {
		return () => {};
	}
	channel.onmessage = (event) => {
		const data = event && event.data;
		const sid = getSessionId();
		if (data && data.type === "claim_check" && sid && data.session_id === sid) {
			channel.postMessage({ type: "claim_held", session_id: sid });
		}
	};
	return () => {
		try {
			channel.close();
		} catch {
			// Already closed.
		}
	};
}

/**
 * A session id names a conversation and is handed between the widget, the SPA
 * and AR, so it should not be predictable from the clock. Unlike
 * crypto.randomUUID, getRandomValues needs no secure context, so this works on
 * an http:// dev bench too.
 */
export function generateSessionId() {
	const bytes = new Uint8Array(9);
	crypto.getRandomValues(bytes);
	const random = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
	return "faco_" + Date.now() + "_" + random;
}

/** The user this tab is currently logged in as, or null. */
export function currentUser() {
	try {
		return (window.frappe && window.frappe.session && window.frappe.session.user) || null;
	} catch {
		return null;
	}
}

function read(key) {
	try {
		return decode(sessionStorage.getItem(key));
	} catch {
		return null;
	}
}

/** Stamped with the current user — a later login must not inherit it. */
export function persistSession(sessionId) {
	try {
		if (sessionId) sessionStorage.setItem(PERSISTED_KEY, encode(sessionId, currentUser()));
	} catch {
		// Storage disabled.
	}
}

export async function resolveWidgetSession({ isClaimed = makeClaimProbe() } = {}) {
	const outcome = await resolve({
		stored: read(HANDOFF_KEY),
		persisted: read(PERSISTED_KEY),
		owner: currentUser(),
		isClaimed,
		generate: generateSessionId,
	});
	if (outcome.consumed_handoff) {
		try {
			sessionStorage.removeItem(HANDOFF_KEY);
			localStorage.removeItem(HANDOFF_KEY); // legacy builds wrote it here
		} catch {
			// Storage disabled.
		}
	}
	persistSession(outcome.session_id);
	return { session_id: outcome.session_id, restored: outcome.restored };
}

/** Same-tab hand-off read by FAC Chat when "Open full assistant" is clicked. */
export function handOffToFullPage(sessionId) {
	try {
		sessionStorage.setItem(ACTIVE_KEY, encode(sessionId, currentUser()));
	} catch {
		// Storage disabled.
	}
}
