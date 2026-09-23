// Frappe Assistant Copilot - Browser diagnostics recorder
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
 * Always-on ring buffers for console output and failed requests.
 *
 * The console entry and the failed request happen BEFORE the assistant is asked
 * about them — no API can ask a browser what it logged five seconds ago. So this
 * records continuously from page load and `browser_capture_diagnostics` drains
 * it, rather than being a request/response tool like the others.
 *
 * The load-bearing invariant is that recording is never on the critical path:
 * every hook is `try { record } catch {}` and then ALWAYS calls the original,
 * captured once at install. This file runs on every Desk page for every user,
 * so a bug here must degrade to "no diagnostics", never to "the Desk is broken".
 *
 * Nothing recorded leaves the browser until the tool is called AND the user
 * approves the capture card.
 */
(function () {
	"use strict";

	const MAX_ENTRIES = 100;
	const MAX_MESSAGE_CHARS = 1000;
	const MAX_AGE_MS = 5 * 60 * 1000;
	const STORAGE_KEY = "faco_diag_v1";
	// localStorage, not sessionStorage: this is a tenant-wide setting, and it
	// must be honoured on the very first paint of a brand-new tab, before any
	// per-session state exists.
	const ENABLED_STORAGE_KEY = "faco_diag_enabled_v1";
	const DEFAULT_SINCE_SECONDS = 120;
	const DEFAULT_MAX_RETURNED = 20;

	// Excluded because recording them feeds the recorder its own reflection:
	// the bridge calls fire *because* a capture is in flight, and the upload is
	// the screenshot being posted.
	const SELF_TRAFFIC = [
		"plugins.faco.tools.browser_bridge",
		"chat.api.settings.uploads.upload_message_file",
	];

	// If widget_diagnostics_redact.js is absent or dies at parse, recording must
	// degrade to safe-but-useless, never to unredacted. Every stub below either
	// drops its input or returns a fixed placeholder — never the identity.
	const REDACTION_UNAVAILABLE = "***REDACTION_UNAVAILABLE***";
	const redact = function () {
		return (
			(typeof window !== "undefined" && window.FACODiagnosticsRedact) || {
				maskQueryString: (u) => {
					const raw = String(u || "");
					const q = raw.indexOf("?");
					return q === -1 ? raw : raw.slice(0, q);
				},
				extractFrappeError: () => null,
				truncate: () => "",
				redactSecretKeys: () => REDACTION_UNAVAILABLE,
				redactInlineSecrets: () => REDACTION_UNAVAILABLE,
			}
		);
	};

	const D = {
		MAX_ENTRIES,
		MAX_MESSAGE_CHARS,
		MAX_AGE_MS,
		STORAGE_KEY,
		ENABLED_STORAGE_KEY,

		_installed: false,
		_enabled: true,
		_recording: false,
		_originals: {},
		_buffers: { console: [], network: [] },

		// -- buffer maintenance ------------------------------------------------

		clear() {
			this._buffers.console = [];
			this._buffers.network = [];
			try {
				window.sessionStorage.removeItem(STORAGE_KEY);
			} catch (e) {
				/* storage unavailable — in-memory is still correct */
			}
		},

		_push(kind, entry) {
			const buf = this._buffers[kind];
			buf.push(entry);
			if (buf.length > MAX_ENTRIES) buf.splice(0, buf.length - MAX_ENTRIES);
		},

		/**
		 * Run a recording body with the re-entrancy guard held.
		 *
		 * Without the guard a console.error raised inside recording would be
		 * captured, which would raise again — the buffer fills with itself.
		 */
		_guarded(fn) {
			if (this._recording || !this._enabled) return;
			this._recording = true;
			try {
				fn();
			} catch (e) {
				/* recording must never surface to the page */
			} finally {
				this._recording = false;
			}
		},

		// -- console -----------------------------------------------------------

		_recordConsole(level, args) {
			const R = redact();
			// Object arguments are stringified (a stack trace or a caught
			// exception commonly carries one), so key-based masking runs before
			// JSON.stringify and inline masking runs on the joined text — the
			// same two-pass shape the redact spec uses for response bodies.
			const parts = Array.prototype.slice.call(args).map((a) => {
				if (a instanceof Error) return a.message;
				if (typeof a === "string") return a;
				try {
					return JSON.stringify(R.redactSecretKeys(a));
				} catch (e) {
					return String(a);
				}
			});
			const message = R.truncate(R.redactInlineSecrets(parts.join(" ")), MAX_MESSAGE_CHARS);
			const stack = (function () {
				for (const a of args)
					if (a instanceof Error && a.stack)
						return R.truncate(R.redactInlineSecrets(a.stack), MAX_MESSAGE_CHARS);
				return "";
			})();

			const now = Date.now();
			const buf = this._buffers.console;
			const existing = buf.find((e) => e.level === level && e.message === message);
			if (existing) {
				existing.count += 1;
				existing.last_at = now;
				return;
			}
			this._push("console", {
				level,
				message,
				stack,
				count: 1,
				first_at: now,
				last_at: now,
			});
		},

		// -- network -----------------------------------------------------------

		_isSelfTraffic(url) {
			const u = String(url || "");
			return SELF_TRAFFIC.some((marker) => u.indexOf(marker) !== -1);
		},

		_recordNetwork(method, url, status, startedAt) {
			const R = redact();
			const entry = {
				method: String(method || "GET").toUpperCase(),
				url: R.maskQueryString(url),
				status: status,
				duration_ms: Math.max(0, Date.now() - startedAt),
				at: Date.now(),
				failed: !status || status >= 400,
			};
			this._push("network", entry);
			return entry;
		},

		// Unguarded body: callers already inside a `_guarded` frame (the XHR
		// `loadend` handler) must call this directly. Routing them through the
		// guarded wrapper below would see `_recording` already held and no-op —
		// which is exactly how the XHR path lost every error envelope.
		_attachErrorUnguarded(entry, bodyText) {
			const parsed = redact().extractFrappeError(bodyText);
			if (parsed) entry.error = parsed;
		},

		_attachError(entry, bodyText) {
			this._guarded(() => this._attachErrorUnguarded(entry, bodyText));
		},

		// -- install / uninstall -----------------------------------------------

		install() {
			if (this._installed || !this._enabled) return;
			const self = this;

			try {
				self._originals.consoleError = console.error;
				self._originals.consoleWarn = console.warn;

				console.error = function () {
					self._guarded(() => self._recordConsole("error", arguments));
					return self._originals.consoleError.apply(console, arguments);
				};
				console.warn = function () {
					self._guarded(() => self._recordConsole("warn", arguments));
					return self._originals.consoleWarn.apply(console, arguments);
				};

				self._onError = function (event) {
					self._guarded(() => {
						// A resource-load failure (a broken <img>/<script> src) has no
						// .message at all — fall back to whatever names the failing
						// asset, or the entry is just the useless literal "Uncaught error".
						// The fallback is a URL, so it goes through the same
						// maskQueryString the network path uses — a filter-carrying
						// query string on a broken asset link is exactly the data
						// never meant to be captured.
						const rawFallback =
							(event && event.filename) ||
							(event && event.target && (event.target.src || event.target.href)) ||
							"Uncaught error";
						const fallback = redact().maskQueryString(rawFallback);
						self._recordConsole("error", [
							event && event.message ? event.message : fallback,
							event && event.error ? event.error : "",
						]);
					});
				};
				self._onRejection = function (event) {
					self._guarded(() =>
						self._recordConsole("error", [
							"Unhandled promise rejection:",
							event && event.reason ? event.reason : "",
						])
					);
				};
				window.addEventListener("error", self._onError, true);
				window.addEventListener("unhandledrejection", self._onRejection);

				if (typeof window.fetch === "function") {
					self._originals.fetch = window.fetch;
					window.fetch = function (input, init) {
						// `input` can be a string, a Request (carries its own
						// .url/.method), or a URL (carries neither — String(url)
						// is its href).
						const url =
							typeof input === "string" ? input : (input && input.url) || String(input || "");
						const method = (init && init.method) || (input && input.method) || "GET";
						const startedAt = Date.now();

						if (self._isSelfTraffic(url) || !self._enabled) {
							return self._originals.fetch.apply(window, arguments);
						}

						return self._originals.fetch.apply(window, arguments).then(
							(response) => {
								self._guarded(() => {
									const entry = self._recordNetwork(
										method,
										url,
										response ? response.status : 0,
										startedAt
									);
									// Clone ONLY on failure: cloning a success would
									// buffer bodies we have promised never to keep.
									if (entry.failed && response && response.clone) {
										try {
											const copy = response.clone();
											if (copy && copy.text) {
												copy.text().then(
													(t) => self._attachError(entry, t),
													() => {}
												);
											}
										} catch (e) {
											/* body not cloneable */
										}
									}
								});
								return response;
							},
							(error) => {
								self._guarded(() => self._recordNetwork(method, url, 0, startedAt));
								throw error;
							}
						);
					};
				}

				if (typeof window.XMLHttpRequest === "function") {
					const proto = window.XMLHttpRequest.prototype;
					self._originals.xhrOpen = proto.open;
					self._originals.xhrSend = proto.send;

					proto.open = function (method, url) {
						try {
							this.__faco_method = method;
							this.__faco_url = url;
						} catch (e) {
							/* frozen instance */
						}
						return self._originals.xhrOpen.apply(this, arguments);
					};

					proto.send = function () {
						const xhr = this;
						const startedAt = Date.now();
						try {
							if (!self._isSelfTraffic(xhr.__faco_url) && self._enabled) {
								xhr.addEventListener("loadend", function () {
									self._guarded(() => {
										const entry = self._recordNetwork(
											xhr.__faco_method,
											xhr.__faco_url,
											xhr.status,
											startedAt
										);
										if (entry.failed) {
											let body = "";
											try {
												body = xhr.responseText || "";
											} catch (e) {
												/* responseType is not text */
											}
											// Already inside self._guarded() (this whole
											// callback) — the guarded wrapper would see
											// _recording held and no-op, dropping the error.
											if (body) self._attachErrorUnguarded(entry, body);
										}
									});
								});
							}
						} catch (e) {
							/* listener could not be attached — send anyway */
						}
						return self._originals.xhrSend.apply(this, arguments);
					};
				}

				self._onPageHide = function () {
					self.persist();
				};
				window.addEventListener("pagehide", self._onPageHide);

				self._installed = true;
			} catch (e) {
				// A partially installed recorder is worse than none.
				try {
					self.uninstall();
				} catch (inner) {
					/* nothing further we can do */
				}
			}
		},

		uninstall() {
			const o = this._originals;
			try {
				if (o.consoleError) console.error = o.consoleError;
				if (o.consoleWarn) console.warn = o.consoleWarn;
				if (o.fetch) window.fetch = o.fetch;
				if (o.xhrOpen) window.XMLHttpRequest.prototype.open = o.xhrOpen;
				if (o.xhrSend) window.XMLHttpRequest.prototype.send = o.xhrSend;
				if (this._onError) window.removeEventListener("error", this._onError, true);
				if (this._onRejection)
					window.removeEventListener("unhandledrejection", this._onRejection);
				if (this._onPageHide) window.removeEventListener("pagehide", this._onPageHide);
			} catch (e) {
				/* best effort */
			}
			this._originals = {};
			this._installed = false;
		},

		// setEnabled(false) and applyPersistedEnabled() must not drift apart on
		// what "disabled" means — both route through here so uninstalling
		// without clearing (or vice versa) can't happen from only one of them.
		_forceDisabled() {
			this._enabled = false;
			this.uninstall();
			this.clear();
		},

		// `persist` defaults true: every existing caller wants the decision
		// remembered. A caller passes false only when the enabled value is
		// INFERRED (a fail-open default for a field that didn't come back),
		// not read from an actual server response — writing that inferred
		// value would overwrite a real persisted decision from earlier.
		setEnabled(on, persist = true) {
			const enabling = !!on;
			if (persist) {
				try {
					window.localStorage.setItem(ENABLED_STORAGE_KEY, enabling ? "1" : "0");
				} catch (e) {
					/* storage unavailable — this tab still honours the in-memory value */
				}
			}
			if (!enabling) {
				this._forceDisabled();
			} else {
				this._enabled = true;
				if (!this._installed) this.install();
			}
		},

		/**
		 * Resolve the last enabled/disabled decision this browser knows about,
		 * from localStorage (survives tabs and sessions, unlike the
		 * sessionStorage entry buffer). Called once at script load, BEFORE
		 * rehydrate()/install() — a persisted "off" must win before any
		 * previously-captured buffer is even loaded into memory, or a disabled
		 * recorder would still serve last session's entries via snapshot()
		 * until the next full page reload. Returns the resolved value
		 * (true/false), or null when nothing is persisted yet.
		 */
		applyPersistedEnabled() {
			let persisted = null;
			try {
				const raw = window.localStorage.getItem(ENABLED_STORAGE_KEY);
				if (raw === "0") persisted = false;
				else if (raw === "1") persisted = true;
			} catch (e) {
				/* storage unavailable — nothing to reconcile */
			}
			if (persisted === false) this._forceDisabled();
			return persisted;
		},

		// -- persistence -------------------------------------------------------

		persist() {
			try {
				window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(this._buffers));
			} catch (e) {
				/* quota or disabled storage — in-memory still works */
			}
		},

		rehydrate() {
			try {
				const raw = window.sessionStorage.getItem(STORAGE_KEY);
				if (!raw) return;
				const saved = JSON.parse(raw);
				const cutoff = Date.now() - MAX_AGE_MS;
				this._buffers.console = (saved.console || []).filter((e) => e.last_at >= cutoff);
				this._buffers.network = (saved.network || []).filter((e) => e.at >= cutoff);
			} catch (e) {
				/* corrupt blob — start clean rather than fail to load */
			}
		},

		// -- readers -----------------------------------------------------------

		// Same MAX_AGE_MS cutoff snapshot()/rehydrate() already apply. Without it,
		// one error early in the day would keep hinting "N console error(s)"
		// forever while the drain (capped at 300s by the tool schema) can
		// physically never reach it — the hint fires and the capture returns
		// nothing. Warnings are excluded: they stay visible in snapshot() as
		// context once a capture happens, but must not themselves trigger one.
		counts() {
			const cutoff = Date.now() - MAX_AGE_MS;
			const consoleBuf = this._buffers.console;
			const recentErrors = consoleBuf.filter((e) => e.level === "error" && e.last_at >= cutoff);
			const consoleCount = recentErrors.reduce((n, e) => n + e.count, 0);
			const failed = this._buffers.network.filter((e) => e.failed && e.at >= cutoff);
			const newest = Math.max(0, ...recentErrors.map((e) => e.last_at), ...failed.map((e) => e.at));
			return {
				console: consoleCount,
				failed_requests: failed.length,
				newest_age_s: newest ? Math.round((Date.now() - newest) / 1000) : null,
			};
		},

		snapshot(options) {
			const opts = options || {};
			// `== null` rather than `||`: an explicit 0 (e.g. max_console: 0)
			// must be honoured, not silently replaced by the default.
			const since = (opts.since_seconds == null ? DEFAULT_SINCE_SECONDS : opts.since_seconds) * 1000;
			const cutoff = Date.now() - since;
			const maxConsole = opts.max_console == null ? DEFAULT_MAX_RETURNED : opts.max_console;
			const maxNetwork = opts.max_network == null ? DEFAULT_MAX_RETURNED : opts.max_network;

			const consoleBuf = this._buffers.console;
			const consoleFiltered = consoleBuf.filter((e) => e.last_at >= cutoff);
			// Not `.slice(-maxConsole)`: ToIntegerOrInfinity collapses -0 to +0,
			// so slice(-0) is spec'd to mean "from the start" (the whole array)
			// rather than "the last zero" — silently ignoring an explicit 0.
			const consoleEntries = consoleFiltered.slice(Math.max(consoleFiltered.length - maxConsole, 0));

			// Failures first: a capped list that spent its budget on 200s is
			// a capped list that answered nothing.
			const network = this._buffers.network
				.filter((e) => e.at >= cutoff)
				.sort((a, b) => (b.failed ? 1 : 0) - (a.failed ? 1 : 0) || b.at - a.at)
				.slice(0, maxNetwork);

			return { enabled: this._enabled, console: consoleEntries, network };
		},
	};

	window.FACODiagnostics = D;
	// Persisted state resolves BEFORE rehydrate(): a persisted "off" already
	// clears sessionStorage inside _forceDisabled(), so rehydrating first
	// would load a buffer into memory that's supposed to be gone, and
	// snapshot() would keep serving it until the next full page reload.
	const persistedEnabled = D.applyPersistedEnabled();
	if (persistedEnabled !== false) {
		D.rehydrate();
		D.install();
	}
})();
