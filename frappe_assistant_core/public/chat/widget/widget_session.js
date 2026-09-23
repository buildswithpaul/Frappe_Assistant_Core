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
window.FACOWidgetSession = {
	CHANNEL_NAME: "faco_widget_session_claims",
	CLAIM_WAIT_MS: 150,

	/** Serialize a session id and the user who minted it for storage. */
	encode(id, user) {
		return JSON.stringify({ id: id, user: user || null });
	},

	/** Parse a stored value into {id, user}, or null if it is not adoptable. */
	decode(raw) {
		if (!raw) return null;
		try {
			const parsed = JSON.parse(raw);
			if (parsed && typeof parsed === "object" && parsed.id) {
				return { id: String(parsed.id), user: parsed.user || null };
			}
		} catch (e) {
			// A bare id written by an older build — no owner, so not adoptable.
		}
		return null;
	},

	/** The id in `entry` if `owner` minted it, else null. */
	owned(entry, owner) {
		if (!entry || !entry.id || !entry.user || !owner) return null;
		return entry.user === owner ? entry.id : null;
	},

	async resolve({ stored, persisted, owner, isClaimed, generate }) {
		const consumed_handoff = !!stored;
		const candidate =
			this.owned(stored, owner) || this.owned(persisted, owner) || null;

		if (!candidate) {
			return { session_id: generate(), restored: false, consumed_handoff };
		}

		let claimed = false;
		try {
			claimed = await isClaimed(candidate);
		} catch (e) {
			claimed = false;
		}

		if (claimed) {
			return { session_id: generate(), restored: false, consumed_handoff };
		}
		return { session_id: candidate, restored: true, consumed_handoff };
	},

	make_claim_probe() {
		const channelName = this.CHANNEL_NAME;
		const waitMs = this.CLAIM_WAIT_MS;

		return (sessionId) =>
			new Promise((resolve) => {
				let channel;
				try {
					channel = new BroadcastChannel(channelName);
				} catch (e) {
					resolve(false);
					return;
				}

				let settled = false;
				const finish = (held) => {
					if (settled) return;
					settled = true;
					try {
						channel.close();
					} catch (e) {
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
	},

	start_claim_responder(widget) {
		try {
			widget._claimChannel = new BroadcastChannel(this.CHANNEL_NAME);
		} catch (e) {
			widget._claimChannel = null;
			return;
		}
		widget._claimChannel.onmessage = (event) => {
			const data = event && event.data;
			if (data && data.type === "claim_check" && data.session_id === widget.session_id) {
				widget._claimChannel.postMessage({
					type: "claim_held",
					session_id: widget.session_id,
				});
			}
		};
	},

	stop_claim_responder(widget) {
		if (!widget._claimChannel) return;
		try {
			widget._claimChannel.close();
		} catch (e) {
			// Already closed.
		}
		widget._claimChannel = null;
	},
};
