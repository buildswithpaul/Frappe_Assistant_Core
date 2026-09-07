import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const DIR = resolve(process.cwd(), "../../public/chat/widget");
const load = (f) => new Function(readFileSync(resolve(DIR, f), "utf8"))();

// The recorder IIFE installs itself on load, and a test may load it more than
// once. Capturing the pristine functions here and restoring them after every
// test is what keeps one test's wrapper out of the next test's assertions.
const PRISTINE = { error: console.error, warn: console.warn, fetch: window.fetch };

let D;
// Set by a test that monkey-patches window.FACODiagnosticsRedact so a
// mid-test failure can't leak the patch into the next test — afterEach
// restores it unconditionally rather than relying on each test's own
// happy-path cleanup line.
let restoreRedactPatch = null;

beforeEach(() => {
	window.sessionStorage.clear();
	window.localStorage.clear();
	load("widget_diagnostics_redact.js");
	load("widget_diagnostics_recorder.js");
	D = window.FACODiagnostics;
	// Auto-installed by the IIFE; tests opt in explicitly so they can assert on
	// what install() actually does.
	D.uninstall();
	D.clear();
});

afterEach(() => {
	if (restoreRedactPatch) {
		try {
			restoreRedactPatch();
		} catch (e) {
			/* ignore */
		}
		restoreRedactPatch = null;
	}
	try {
		if (window.FACODiagnostics) window.FACODiagnostics.uninstall();
	} catch (e) {
		/* ignore */
	}
	console.error = PRISTINE.error;
	console.warn = PRISTINE.warn;
	window.fetch = PRISTINE.fetch;
	window.sessionStorage.clear();
	window.localStorage.clear();
});

describe("pass-through is unconditional", () => {
	it("still calls the original console.error when recording throws", () => {
		const original = vi.fn();
		console.error = original;
		D.install();
		// Force the record path to throw on every call — via a genuine failure
		// in a helper it calls, not a production backdoor flag.
		const originalTruncate = window.FACODiagnosticsRedact.truncate;
		restoreRedactPatch = () => {
			window.FACODiagnosticsRedact.truncate = originalTruncate;
		};
		window.FACODiagnosticsRedact.truncate = () => {
			throw new Error("boom in recording");
		};

		expect(() => console.error("boom")).not.toThrow();
		expect(original).toHaveBeenCalledWith("boom");
	});

	it("restores the exact original functions on uninstall", () => {
		const original = console.error;
		D.install();
		expect(console.error).not.toBe(original);
		D.uninstall();
		expect(console.error).toBe(original);
	});

	it("install is idempotent — double install does not double-wrap", () => {
		const original = console.error;
		D.install();
		const wrapped = console.error;
		D.install();
		expect(console.error).toBe(wrapped);
		D.uninstall();
		expect(console.error).toBe(original);
	});

	it("installs even when fetch is absent", () => {
		const saved = window.fetch;
		delete window.fetch;
		expect(() => D.install()).not.toThrow();
		window.fetch = saved;
	});
});

describe("console buffer", () => {
	it("records errors and warnings", () => {
		D.install();
		console.error("first failure");
		console.warn("a warning");
		const snap = D.snapshot({});
		expect(snap.console).toHaveLength(2);
		expect(snap.console[0].level).toBe("error");
		expect(snap.console[0].message).toContain("first failure");
	});

	it("dedupes identical messages into a count", () => {
		D.install();
		for (let i = 0; i < 5; i++) console.error("same failure");
		const snap = D.snapshot({});
		expect(snap.console).toHaveLength(1);
		expect(snap.console[0].count).toBe(5);
		expect(snap.console[0].last_at).toBeGreaterThanOrEqual(snap.console[0].first_at);
	});

	it("does not record its own recording — no re-entrancy loop", () => {
		D.install();
		// A helper the recording path calls (truncate) itself logs — the
		// re-entrancy guard must stop that nested call from being recorded,
		// and must stop it from re-entering _recordConsole at all.
		const originalTruncate = window.FACODiagnosticsRedact.truncate;
		restoreRedactPatch = () => {
			window.FACODiagnosticsRedact.truncate = originalTruncate;
		};
		window.FACODiagnosticsRedact.truncate = function (...args) {
			console.error("nested logging from inside recording");
			return originalTruncate.apply(this, args);
		};

		console.error("trigger");

		const entries = D.snapshot({}).console;
		expect(entries).toHaveLength(1);
		expect(entries[0].message).toContain("trigger");
	});

	it("caps the buffer and keeps the newest", () => {
		D.install();
		for (let i = 0; i < 150; i++) console.error("failure " + i);
		expect(D._buffers.console.length).toBeLessThanOrEqual(D.MAX_ENTRIES);
		const messages = D._buffers.console.map((e) => e.message).join("|");
		expect(messages).toContain("failure 149");
		expect(messages).not.toContain("failure 0|");
	});

	it("truncates a very long message", () => {
		D.install();
		console.error("y".repeat(5000));
		expect(D.snapshot({}).console[0].message.length).toBeLessThanOrEqual(D.MAX_MESSAGE_CHARS);
	});
});

describe("redaction", () => {
	it("does not leak an object argument's secret keys into the console buffer", () => {
		D.install();
		console.error("auth failed", { api_key: "sk-live-123" });
		const [entry] = D.snapshot({}).console;
		expect(entry.message).not.toContain("sk-live-123");
	});

	it("does not leak an inline key=value secret in the joined message", () => {
		D.install();
		console.error("request failed token=sk-live-999 while saving");
		const [entry] = D.snapshot({}).console;
		expect(entry.message).not.toContain("sk-live-999");
	});
});

describe("network buffer", () => {
	it("records a failed request with the Frappe error envelope", async () => {
		window.fetch = vi.fn(async () => ({
			ok: false,
			status: 417,
			clone: () => ({
				text: async () =>
					JSON.stringify({ exc_type: "ValidationError", exc: "traceback here" }),
			}),
		}));
		D.install();

		await window.fetch("/api/method/frappe.client.save?token=secret");
		await new Promise((r) => setTimeout(r, 0));

		const [entry] = D.snapshot({}).network;
		expect(entry.status).toBe(417);
		expect(entry.failed).toBe(true);
		expect(entry.url).toContain("token=***");
		expect(entry.url).not.toContain("secret");
		expect(entry.error.exc_type).toBe("ValidationError");
	});

	it("does not clone the response body on a successful request", async () => {
		const cloneSpy = vi.fn();
		window.fetch = vi.fn(async () => ({ ok: true, status: 200, clone: cloneSpy }));
		D.install();

		await window.fetch("/api/method/frappe.client.get_list");
		await new Promise((r) => setTimeout(r, 0));

		expect(cloneSpy).not.toHaveBeenCalled();
		const [entry] = D.snapshot({}).network;
		expect(entry.status).toBe(200);
		expect(entry.failed).toBe(false);
		expect(entry.error).toBeUndefined();
	});

	it("ignores its own bridge traffic", async () => {
		window.fetch = vi.fn(async () => ({ ok: true, status: 200, clone: () => ({}) }));
		D.install();

		await window.fetch(
			"/api/method/frappe_assistant_core.plugins.faco.tools.browser_bridge.submit_browser_tool_ack"
		);
		await new Promise((r) => setTimeout(r, 0));

		expect(D.snapshot({}).network).toHaveLength(0);
	});

	it("records a thrown network error as status 0 and rethrows", async () => {
		window.fetch = vi.fn(async () => {
			throw new TypeError("Failed to fetch");
		});
		D.install();

		await expect(window.fetch("/api/method/x")).rejects.toThrow("Failed to fetch");
		const [entry] = D.snapshot({}).network;
		expect(entry.status).toBe(0);
		expect(entry.failed).toBe(true);
	});

	it("derives method from a Request-like object and url from a URL object", async () => {
		window.fetch = vi.fn(async () => ({ ok: true, status: 200, clone: () => ({}) }));
		D.install();

		await window.fetch({ url: "/api/method/x", method: "POST" });
		await window.fetch(new URL("http://localhost/api/method/y"));
		await new Promise((r) => setTimeout(r, 0));

		const entries = D.snapshot({}).network;
		expect(entries.find((e) => e.method === "POST" && e.url.includes("/api/method/x"))).toBeTruthy();
		expect(entries.some((e) => e.url.includes("/api/method/y"))).toBe(true);
	});
});

describe("XMLHttpRequest", () => {
	const REAL_XHR = window.XMLHttpRequest;

	function makeFakeXHRClass() {
		return class FakeXHR {
			constructor() {
				this._listeners = {};
			}
			addEventListener(type, cb) {
				(this._listeners[type] = this._listeners[type] || []).push(cb);
			}
			open(method, url) {
				this.method = method;
				this.url = url;
			}
			send() {}
			_dispatch(type) {
				(this._listeners[type] || []).forEach((cb) => cb.call(this));
			}
		};
	}

	afterEach(() => {
		window.XMLHttpRequest = REAL_XHR;
	});

	it("wraps open/send and records a failed request with its Frappe error envelope", () => {
		window.XMLHttpRequest = makeFakeXHRClass();
		D.install();

		const xhr = new window.XMLHttpRequest();
		xhr.open("POST", "/api/method/frappe.client.save?token=secret");
		xhr.send();
		xhr.status = 417;
		xhr.responseText = JSON.stringify({ exc_type: "ValidationError", exc: "traceback here" });
		xhr._dispatch("loadend");

		const [entry] = D.snapshot({}).network;
		expect(entry.method).toBe("POST");
		expect(entry.status).toBe(417);
		expect(entry.failed).toBe(true);
		expect(entry.url).toContain("token=***");
		expect(entry.error.exc_type).toBe("ValidationError");
	});

	it("records a successful XHR request without an error", () => {
		window.XMLHttpRequest = makeFakeXHRClass();
		D.install();

		const xhr = new window.XMLHttpRequest();
		xhr.open("GET", "/api/method/frappe.client.get_list");
		xhr.send();
		xhr.status = 200;
		xhr._dispatch("loadend");

		const [entry] = D.snapshot({}).network;
		expect(entry.status).toBe(200);
		expect(entry.failed).toBe(false);
		expect(entry.error).toBeUndefined();
	});

	it("restores XMLHttpRequest.prototype.open/send on uninstall", () => {
		const FakeXHR = makeFakeXHRClass();
		window.XMLHttpRequest = FakeXHR;
		const originalOpen = FakeXHR.prototype.open;
		const originalSend = FakeXHR.prototype.send;

		D.install();
		expect(FakeXHR.prototype.open).not.toBe(originalOpen);
		expect(FakeXHR.prototype.send).not.toBe(originalSend);

		D.uninstall();
		expect(FakeXHR.prototype.open).toBe(originalOpen);
		expect(FakeXHR.prototype.send).toBe(originalSend);
	});
});

describe("snapshot shaping", () => {
	it("drops entries older than since_seconds", () => {
		D.install();
		console.error("old one");
		D._buffers.console[0].last_at = Date.now() - 600000;
		expect(D.snapshot({ since_seconds: 120 }).console).toHaveLength(0);
	});

	it("caps returned entries and puts failures first", async () => {
		window.fetch = vi.fn(async (url) => ({
			ok: !String(url).includes("bad"),
			status: String(url).includes("bad") ? 500 : 200,
			clone: () => ({ text: async () => "{}" }),
		}));
		D.install();
		for (let i = 0; i < 5; i++) await window.fetch("/api/method/ok" + i);
		await window.fetch("/api/method/bad");
		await new Promise((r) => setTimeout(r, 0));

		const out = D.snapshot({ max_network: 3 }).network;
		expect(out).toHaveLength(3);
		expect(out[0].failed).toBe(true);
	});

	it("honours an explicit zero for max_console and max_network", () => {
		D.install();
		console.error("a");
		expect(D.snapshot({ max_console: 0 }).console).toHaveLength(0);

		D._buffers.network.push({ status: 500, failed: true, at: Date.now(), method: "GET", url: "/x" });
		expect(D.snapshot({ max_network: 0 }).network).toHaveLength(0);
	});
});

describe("counts", () => {
	it("reports console errors, failed requests and the newest age", () => {
		D.install();
		console.error("a");
		console.warn("b");
		D._buffers.network.push({ status: 500, failed: true, at: Date.now() });

		const c = D.counts();
		// Only the error counts — the warning stays in the buffer for
		// snapshot() but must not drive the hint (FIX 2a).
		expect(c.console).toBe(1);
		expect(c.failed_requests).toBe(1);
		expect(c.newest_age_s).toBeGreaterThanOrEqual(0);
	});

	it("reports zeroes and a null age on an empty buffer", () => {
		expect(D.counts()).toEqual({ console: 0, failed_requests: 0, newest_age_s: null });
	});

	it("does not count a console entry older than MAX_AGE_MS", () => {
		D.install();
		console.error("stale");
		D._buffers.console[0].last_at = Date.now() - (D.MAX_AGE_MS + 1000);

		expect(D.counts().console).toBe(0);
	});

	it("does not count a failed request older than MAX_AGE_MS", () => {
		D._buffers.network.push({
			status: 500,
			failed: true,
			at: Date.now() - (D.MAX_AGE_MS + 1000),
		});

		expect(D.counts().failed_requests).toBe(0);
	});

	it("still counts an entry inside the MAX_AGE_MS window", () => {
		D.install();
		console.error("fresh");
		D._buffers.console[0].last_at = Date.now() - (D.MAX_AGE_MS - 1000);
		D._buffers.network.push({ status: 500, failed: true, at: Date.now() - (D.MAX_AGE_MS - 1000) });

		const c = D.counts();
		expect(c.console).toBe(1);
		expect(c.failed_requests).toBe(1);
	});

	it("does not count a console.warn even when it is the only entry", () => {
		D.install();
		console.warn("just a warning");

		expect(D.counts().console).toBe(0);
		expect(D.snapshot({}).console).toHaveLength(1);
	});
});

describe("resource-load errors", () => {
	it("names the failing filename when the error event carries no message", () => {
		D.install();
		D._onError({ message: "", filename: "https://example.com/broken.js", error: null });

		const [entry] = D.snapshot({}).console;
		expect(entry.message).toContain("broken.js");
		expect(entry.message).not.toBe("Uncaught error");
	});

	it("names the failing target src when filename is also absent", () => {
		D.install();
		D._onError({ message: "", target: { src: "https://example.com/missing.png" } });

		const [entry] = D.snapshot({}).console;
		expect(entry.message).toContain("missing.png");
	});

	it("masks query string values in the fallback URL, same as the network path", () => {
		D.install();
		D._onError({
			message: "",
			target: { src: "https://example.com/api/method/download?doctype=Sales%20Invoice&name=SINV-0001" },
		});

		const [entry] = D.snapshot({}).console;
		expect(entry.message).not.toContain("SINV-0001");
		expect(entry.message).not.toContain("Sales%20Invoice");
		expect(entry.message).toContain("/api/method/download");
	});
});

describe("redaction fallback when the redact module is absent", () => {
	it("does not leak the original console message text", () => {
		D.install();
		delete window.FACODiagnosticsRedact;

		console.error("request failed token=super-secret-value while saving");

		const [entry] = D.snapshot({}).console;
		expect(entry.message).not.toContain("super-secret-value");
		expect(entry.message).not.toContain("request failed token=super-secret-value while saving");
	});

	it("drops the query string entirely from a recorded network entry", async () => {
		window.fetch = vi.fn(async () => ({
			ok: false,
			status: 500,
			clone: () => ({ text: async () => "{}" }),
		}));
		D.install();
		delete window.FACODiagnosticsRedact;

		await window.fetch("/api/method/x?token=super-secret-value&doctype=Sales%20Invoice");
		await new Promise((r) => setTimeout(r, 0));

		const [entry] = D.snapshot({}).network;
		expect(entry.url).not.toContain("super-secret-value");
		expect(entry.url).not.toContain("?");
	});
});

describe("persistence", () => {
	it("rehydrates across a reload", () => {
		D.install();
		console.error("survives navigation");
		D.persist();

		load("widget_diagnostics_recorder.js");
		const fresh = window.FACODiagnostics;
		expect(fresh.snapshot({}).console[0].message).toContain("survives navigation");
	});

	it("drops rehydrated entries older than the max age", () => {
		D.install();
		console.error("ancient");
		D._buffers.console[0].last_at = Date.now() - (D.MAX_AGE_MS + 1000);
		D.persist();

		load("widget_diagnostics_recorder.js");
		expect(window.FACODiagnostics.snapshot({}).console).toHaveLength(0);
	});
});

describe("kill switch", () => {
	it("uninstalls and clears when disabled", () => {
		const original = console.error;
		D.install();
		console.error("recorded");
		D.setEnabled(false);

		expect(console.error).toBe(original);
		expect(D.snapshot({}).console).toHaveLength(0);
		expect(D.snapshot({}).enabled).toBe(false);
		expect(window.sessionStorage.getItem(D.STORAGE_KEY)).toBeNull();
	});
});

describe("persisted kill switch", () => {
	it("setEnabled persists the decision to localStorage", () => {
		D.install();
		D.setEnabled(false);
		expect(window.localStorage.getItem(D.ENABLED_STORAGE_KEY)).toBe("0");

		D.setEnabled(true);
		expect(window.localStorage.getItem(D.ENABLED_STORAGE_KEY)).toBe("1");
	});

	it("does not install, and clears any previously-captured buffer, when a persisted disabled state exists from a prior page load", () => {
		D.install();
		console.error("customer PII: user@example.com failed to save");
		D.persist();
		// A real navigation never carries page 1's console.error wrapper into
		// page 2 — the JS realm is torn down. Uninstalling here simulates that
		// teardown so the assertions below are about the NEXT page's bootstrap
		// decision, not a leftover wrapper from this test's own setup.
		D.uninstall();

		// Simulates the operator's decision reaching this browser (e.g. via a
		// different tab that already reconciled) without page 1 having known
		// about it — sessionStorage still holds the buffer from persist()
		// above, exactly as it would after a real pagehide. The fix must
		// check this BEFORE rehydrating that buffer.
		window.localStorage.setItem(D.ENABLED_STORAGE_KEY, "0");

		// A fresh load simulates the next Desk page load / navigation, where
		// the recorder's bootstrap is the only thing that runs — no widget.js
		// orchestration involved.
		load("widget_diagnostics_recorder.js");
		const fresh = window.FACODiagnostics;

		expect(console.error).toBe(PRISTINE.error);
		expect(fresh.snapshot({}).enabled).toBe(false);
		expect(fresh.snapshot({}).console).toHaveLength(0);
		expect(window.sessionStorage.getItem(D.STORAGE_KEY)).toBeNull();
	});

	it("applyPersistedEnabled uninstalls and clears a live recorder when disabled elsewhere", () => {
		D.install();
		console.error("still here");
		expect(console.error).not.toBe(PRISTINE.error);

		window.localStorage.setItem(D.ENABLED_STORAGE_KEY, "0");
		D.applyPersistedEnabled();

		expect(console.error).toBe(PRISTINE.error);
		expect(D.snapshot({}).enabled).toBe(false);
		expect(D.snapshot({}).console).toHaveLength(0);
	});
});

describe("check_access integration contract", () => {
	// widget.js calls exactly this shape right after check_access() resolves,
	// ahead of its early returns:
	//   const present = access.enable_browser_diagnostics !== undefined;
	//   window.FACODiagnostics.setEnabled(access.enable_browser_diagnostics !== false, present);
	// This mirrors that call site so the field's wire contract (a real
	// `false`, not merely falsy; persistence gated on the field having
	// actually been present) is covered without mounting the whole
	// FACOWidget class.
	function callAsWidgetJsWould(access) {
		const present = access.enable_browser_diagnostics !== undefined;
		D.setEnabled(access.enable_browser_diagnostics !== false, present);
	}

	it("a disabled value from check_access's response uninstalls the recorder", () => {
		D.install();
		expect(console.error).not.toBe(PRISTINE.error);

		callAsWidgetJsWould({ enable_browser_diagnostics: false });

		expect(console.error).toBe(PRISTINE.error);
		expect(D.snapshot({}).enabled).toBe(false);
	});

	it("a missing field (exception-fallback response) fails open", () => {
		D.install();
		callAsWidgetJsWould({}); // enable_browser_diagnostics is undefined here

		expect(console.error).not.toBe(PRISTINE.error);
		expect(D.snapshot({}).enabled).toBe(true);
	});

	it("a fail-open write from a missing field does not overwrite a pre-existing persisted disabled state", () => {
		// Page 1: the operator's decision was "off", and that persisted.
		window.localStorage.setItem(D.ENABLED_STORAGE_KEY, "0");

		// Page 2: check_access()'s own catch block returns {can_use:false,
		// reason} with no enable_browser_diagnostics field at all — a
		// transient RPC failure, not a real answer from the server.
		callAsWidgetJsWould({ can_use: false, reason: "Error checking access" });

		// The fail-open VALUE is correct — this tab still gets diagnostics for
		// its own session. But the WRITE must not happen: the persisted "0"
		// from before this RPC even ran has to survive for the NEXT load.
		expect(D.snapshot({}).enabled).toBe(true);
		expect(window.localStorage.getItem(D.ENABLED_STORAGE_KEY)).toBe("0");
	});
});
