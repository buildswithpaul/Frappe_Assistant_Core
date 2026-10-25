// Script approval for the fac-pages Desk page. Keep this first line a comment: fac_pages.js inlines
// the file through Frappe's render_include from a line that starts with "//".
//
// Which version of a personal FAC Page's script the user has seen and chosen to run. FACO writes
// that code, so a new version waits in the page until the user clicks Run new version. The chat
// panel has an ES-module copy in chat/frontend/src/utils/facPageApproval.js; both are tested
// against the cases in chat/frontend/src/utils/__tests__/facPageApprovalCases.js, run by
// chat/frontend/src/widget/desk/facPageApproval.spec.js.
//
// Desk and the chat share an origin, so one approval in either counts in both. When storage is
// unavailable nothing is remembered, and every open asks again.
// eslint-disable-next-line no-unused-vars
function fac_page_approval_key(user, name) {
	return `fac_page_approved:${encodeURIComponent(user)}:${encodeURIComponent(name)}`;
}

// FNV-1a, for a browser without crypto.subtle (an insecure http origin). The stored script is
// compared as well, so a collision cannot approve different code.
function fnv1a(text) {
	let hash = 0x811c9dc5;
	for (let i = 0; i < text.length; i++) {
		hash ^= text.charCodeAt(i);
		hash = Math.imul(hash, 0x01000193) >>> 0;
	}
	return `fnv1a:${hash.toString(16).padStart(8, "0")}`;
}

// eslint-disable-next-line no-unused-vars
async function fac_page_script_hash(script) {
	const text = script || "";
	const subtle = globalThis.crypto && globalThis.crypto.subtle;
	if (!subtle) return fnv1a(text);
	const digest = await subtle.digest("SHA-256", new TextEncoder().encode(text));
	return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

/** The approved {hash, script}, or null when there is none or storage cannot be read. */
// eslint-disable-next-line no-unused-vars
function fac_page_approved_script(user, name) {
	if (!user || !name) return null;
	try {
		const record = JSON.parse(window.localStorage.getItem(fac_page_approval_key(user, name)));
		if (record && typeof record.hash === "string" && typeof record.script === "string") return record;
	} catch {
		// Unreadable storage approves nothing.
	}
	return null;
}

/** Remember `script` as approved; resolves false when it could not be stored. */
// eslint-disable-next-line no-unused-vars
async function fac_page_approve_script(user, name, script) {
	if (!user || !name) return false;
	const record = { hash: await fac_page_script_hash(script), script: script || "" };
	try {
		window.localStorage.setItem(fac_page_approval_key(user, name), JSON.stringify(record));
		return true;
	} catch {
		return false;
	}
}

// A shared page's code was approved on its publish card, and a draft runs no script at all.
// Every other page with a script is held, so a response with a missing field fails closed.
// eslint-disable-next-line no-unused-vars
function fac_page_needs_review(page) {
	return Boolean(page && page.draft !== true && page.visibility !== "Shared" && (page.script || "").trim());
}

/**
 * Null when the page's script may run now; otherwise why it waits: {state: "first"} for a page
 * whose script was never approved, {state: "changed"} for one FACO changed since, and the
 * approved script ("" on first open) for View changes.
 */
// eslint-disable-next-line no-unused-vars
async function fac_page_script_review(user, name, page) {
	if (!fac_page_needs_review(page)) return null;
	const approved = fac_page_approved_script(user, name);
	if (approved && approved.script === page.script) {
		try {
			if ((await fac_page_script_hash(page.script)) === approved.hash) return null;
		} catch {
			// A hash that cannot be taken approves nothing.
		}
	}
	return approved ? { state: "changed", approved: approved.script } : { state: "first", approved: "" };
}

// Past this many line pairs the diff's table grows too large to build; View changes then shows
// the whole new script.
const LINE_DIFF_MAX_CELLS = 1000000;

/** A line diff of `before` against `after`: [{type: "same" | "removed" | "added", text}]. */
// eslint-disable-next-line no-unused-vars
function fac_page_line_diff(before, after) {
	const a = before ? before.split("\n") : [];
	const b = after ? after.split("\n") : [];
	if (a.length * b.length > LINE_DIFF_MAX_CELLS) return b.map((text) => ({ type: "added", text }));
	// common[i][j]: the longest common subsequence of a[i..] and b[j..].
	const common = Array.from({ length: a.length + 1 }, () => new Array(b.length + 1).fill(0));
	for (let i = a.length - 1; i >= 0; i--) {
		for (let j = b.length - 1; j >= 0; j--) {
			common[i][j] = a[i] === b[j] ? common[i + 1][j + 1] + 1 : Math.max(common[i + 1][j], common[i][j + 1]);
		}
	}
	const lines = [];
	let i = 0;
	let j = 0;
	while (i < a.length && j < b.length) {
		if (a[i] === b[j]) {
			lines.push({ type: "same", text: a[i] });
			i++;
			j++;
		} else if (common[i + 1][j] >= common[i][j + 1]) {
			lines.push({ type: "removed", text: a[i++] });
		} else {
			lines.push({ type: "added", text: b[j++] });
		}
	}
	while (i < a.length) lines.push({ type: "removed", text: a[i++] });
	while (j < b.length) lines.push({ type: "added", text: b[j++] });
	return lines;
}
