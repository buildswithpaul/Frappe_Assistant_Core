// Frappe Assistant Copilot - Diagnostics redaction helpers
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
 * Pure redaction helpers for the diagnostics recorder.
 *
 * Kept free of DOM and network access so the security-critical logic can be
 * unit-tested on its own. Nothing here may throw: a redaction failure must
 * never propagate into the page's own console or fetch call.
 */
(function (global) {
	"use strict";

	const MAX_EXC_CHARS = 2000;
	const MAX_SERVER_MESSAGES = 3;
	const MAX_SERVER_MESSAGE_CHARS = 500;
	const REDACTED = "***REDACTED***";

	const SECRET_KEY = /(password|secret|token|api[_-]?key|key$|otp|pwd|sid|csrf)/i;
	// Query values are masked wholesale rather than by key: a Frappe filter
	// string carries document names and field values, which are exactly the
	// data we have promised not to capture.
	const MASKED_VALUE = "***";

	function truncate(text, max) {
		try {
			const s = String(text == null ? "" : text);
			return s.length > max ? s.slice(0, max) : s;
		} catch (e) {
			return "";
		}
	}

	function maskQueryString(url) {
		try {
			const raw = String(url || "");
			const q = raw.indexOf("?");
			if (q === -1) return raw;
			const base = raw.slice(0, q);
			const masked = raw
				.slice(q + 1)
				.split("&")
				.filter(Boolean)
				.map((pair) => {
					const eq = pair.indexOf("=");
					const key = eq === -1 ? pair : pair.slice(0, eq);
					return key + "=" + MASKED_VALUE;
				})
				.join("&");
			return masked ? base + "?" + masked : base;
		} catch (e) {
			return "";
		}
	}

	function redactSecretKeys(value) {
		const seen = new Set();

		function walk(node) {
			if (node === null || typeof node !== "object") return node;
			if (seen.has(node)) return "[Circular]";
			seen.add(node);

			if (Array.isArray(node)) return node.map(walk);

			const out = {};
			for (const key of Object.keys(node)) {
				out[key] = SECRET_KEY.test(key) ? REDACTED : walk(node[key]);
			}
			return out;
		}

		try {
			return walk(value);
		} catch (e) {
			return null;
		}
	}

	// Masks `key=value` pairs inside free text (tracebacks, error strings),
	// where structural key redaction cannot reach. The key may itself be
	// quoted (a stringified dict), and an unquoted value runs to a real
	// terminator rather than the first space — secrets are rarely one token.
	const INLINE_SECRET =
		/((?:password|secret|token|api[_-]?key|otp|pwd|sid|csrf)["']?\s*[=:]\s*)("[^"]*"|'[^']*'|[^,})\r\n]*)/gi;

	function redactInlineSecrets(text) {
		try {
			return String(text || "").replace(INLINE_SECRET, (match, prefix, value) => {
				if (!value) return match;
				const quote = value[0] === '"' || value[0] === "'" ? value[0] : "";
				return prefix + quote + REDACTED + quote;
			});
		} catch (e) {
			return "";
		}
	}

	function parseServerMessages(raw) {
		let list = raw;
		if (typeof list === "string") {
			try {
				list = JSON.parse(list);
			} catch (e) {
				return [truncate(redactInlineSecrets(raw), MAX_SERVER_MESSAGE_CHARS)];
			}
		}
		if (!Array.isArray(list)) return [];
		return list.slice(0, MAX_SERVER_MESSAGES).map((entry) => {
			let text = entry;
			if (typeof entry === "string") {
				try {
					const parsed = JSON.parse(entry);
					text = parsed && parsed.message ? parsed.message : entry;
				} catch (e) {
					text = entry;
				}
			}
			return truncate(redactInlineSecrets(text), MAX_SERVER_MESSAGE_CHARS);
		});
	}

	// frappe.utils.response.report_error sets `exc` to
	// orjson.dumps([...]).decode() — a JSON-encoded array of traceback
	// strings, not a plain string. Left unparsed it arrives as literal `\n`
	// escapes that also eat into the truncation cap below.
	function normalizeExc(raw) {
		if (!raw || typeof raw !== "string") return raw || "";
		try {
			const parsed = JSON.parse(raw);
			if (Array.isArray(parsed)) return parsed.join("\n");
		} catch (e) {
			/* not JSON — a plain traceback string, use as-is */
		}
		return raw;
	}

	/**
	 * Pull the Frappe error envelope out of a response body.
	 *
	 * Returns null for anything that is not one — a proxy's HTML 502 page has
	 * no structure worth shipping, and guessing at it is how bodies leak.
	 */
	function extractFrappeError(bodyText) {
		if (!bodyText) return null;
		let data;
		try {
			data = JSON.parse(bodyText);
		} catch (e) {
			return null;
		}
		if (!data || typeof data !== "object") return null;

		const hasEnvelope =
			"exc_type" in data || "exc" in data || "_server_messages" in data;
		if (!hasEnvelope) return null;

		return {
			exc_type: truncate(data.exc_type || "", 200),
			server_messages: parseServerMessages(data._server_messages),
			exc: truncate(redactInlineSecrets(normalizeExc(data.exc)), MAX_EXC_CHARS),
		};
	}

	global.FACODiagnosticsRedact = {
		MAX_EXC_CHARS,
		MAX_SERVER_MESSAGES,
		MAX_SERVER_MESSAGE_CHARS,
		REDACTED,
		truncate,
		maskQueryString,
		redactSecretKeys,
		redactInlineSecrets,
		extractFrappeError,
	};
})(typeof window !== "undefined" ? window : this);
