/**
 * Session hand-off between the SPA and the desk widget.
 *
 * The two pass a session id through sessionStorage. That storage survives a
 * logout and is cloned into duplicated tabs, and a session id names no user of
 * its own — so an id stored by one user could be picked up and continued by the
 * next person to log in. Every stored id therefore carries the user who minted
 * it, and is only ever handed back to that same user.
 *
 * The widget half of this shape lives in public/chat/widget/widget_session.js
 * (FACOWidgetSession.encode / decode); the two must stay byte-compatible.
 */

/** Read the id at `key` if `user` is the one who stored it, else null. */
export function readHandoff(key, user) {
	if (!user) return null;
	try {
		const raw = sessionStorage.getItem(key);
		if (!raw) return null;
		const parsed = JSON.parse(raw);
		if (parsed && typeof parsed === "object" && parsed.id && parsed.user === user) {
			return String(parsed.id);
		}
	} catch (e) {
		// A bare id written by an older build — no owner, so not adoptable.
	}
	return null;
}

/** Store `id` at `key`, stamped with the user handing it off. */
export function writeHandoff(key, id, user) {
	if (!id) return;
	try {
		sessionStorage.setItem(key, JSON.stringify({ id: id, user: user || null }));
	} catch (e) {
		// Storage disabled — the hand-off is a convenience, not a requirement.
	}
}
