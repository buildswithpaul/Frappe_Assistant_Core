import { describe, it, expect, beforeEach } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const SRC = resolve(process.cwd(), "../../public/chat/widget/widget_diagnostics_redact.js");

function load() {
	const win = {};
	new Function("window", readFileSync(SRC, "utf8"))(win);
	return win.FACODiagnosticsRedact;
}

let R;
beforeEach(() => {
	R = load();
});

describe("truncate", () => {
	it("returns an empty string instead of throwing when the value cannot be stringified", () => {
		const hostile = {
			toString() {
				throw new Error("x");
			},
		};
		expect(() => R.truncate(hostile, 5)).not.toThrow();
		expect(R.truncate(hostile, 5)).toBe("");
	});
});

describe("maskQueryString", () => {
	it("keeps keys and masks values", () => {
		expect(R.maskQueryString("/api/method/x?token=abc123&doctype=Sales%20Invoice")).toBe(
			"/api/method/x?token=***&doctype=***"
		);
	});

	it("leaves a url without a query string alone", () => {
		expect(R.maskQueryString("/api/method/frappe.client.save")).toBe(
			"/api/method/frappe.client.save"
		);
	});

	it("does not throw on a malformed url", () => {
		expect(() => R.maskQueryString("::::?a=b")).not.toThrow();
	});
});

describe("redactSecretKeys", () => {
	it("masks secret-ish keys at any depth, case-insensitively", () => {
		const out = R.redactSecretKeys({
			customer: "Acme",
			API_Key: "live_123",
			nested: { password: "hunter2", sid: "abc", note: "keep" },
		});
		expect(out.customer).toBe("Acme");
		expect(out.API_Key).toBe("***REDACTED***");
		expect(out.nested.password).toBe("***REDACTED***");
		expect(out.nested.sid).toBe("***REDACTED***");
		expect(out.nested.note).toBe("keep");
	});

	it("redacts a compound key ending in Key, not just an exact 'key' match", () => {
		const out = R.redactSecretKeys({ signingKey: "abc", plain: "keep" });
		expect(out.signingKey).toBe("***REDACTED***");
		expect(out.plain).toBe("keep");
	});

	it("survives a cyclic object instead of blowing the stack", () => {
		const a = { name: "a" };
		a.self = a;
		expect(() => R.redactSecretKeys(a)).not.toThrow();
	});
});

describe("redactInlineSecrets", () => {
	it("redacts a quoted key even though the separator follows a closing quote", () => {
		const out = R.redactInlineSecrets('{"password": "hunter2", "sid": "abc123XYZ"}');
		expect(out).not.toContain("hunter2");
		expect(out).not.toContain("abc123XYZ");
	});

	it("masks an unquoted multi-word value through to the terminator, not just the first token", () => {
		const out = R.redactInlineSecrets("password: My Secret Passphrase");
		expect(out).not.toContain("My Secret Passphrase");
		expect(out).not.toContain("Secret Passphrase");
	});
});

describe("extractFrappeError", () => {
	it("pulls exc_type, server messages and a truncated traceback", () => {
		const body = JSON.stringify({
			exc_type: "ValidationError",
			_server_messages: JSON.stringify([
				JSON.stringify({ message: "Customer is required" }),
			]),
			exc: "x".repeat(5000),
		});
		const out = R.extractFrappeError(body);
		expect(out.exc_type).toBe("ValidationError");
		expect(out.server_messages[0]).toContain("Customer is required");
		expect(out.exc.length).toBe(R.MAX_EXC_CHARS);
	});

	it("caps the number of server messages", () => {
		const body = JSON.stringify({
			exc_type: "ValidationError",
			_server_messages: JSON.stringify(["a", "b", "c", "d", "e"]),
		});
		expect(R.extractFrappeError(body).server_messages.length).toBe(R.MAX_SERVER_MESSAGES);
	});

	it("returns null for a body that is not a Frappe error envelope", () => {
		expect(R.extractFrappeError(JSON.stringify({ message: "fine" }))).toBeNull();
		expect(R.extractFrappeError("<html>502 Bad Gateway</html>")).toBeNull();
		expect(R.extractFrappeError("")).toBeNull();
	});

	it("redacts secrets that appear inside the error envelope", () => {
		const body = JSON.stringify({ exc_type: "AuthError", exc: "token=SHOULD_NOT_LEAK" });
		const out = R.extractFrappeError(body);
		expect(out.exc).toContain("token=");
		expect(out.exc).not.toContain("SHOULD_NOT_LEAK");
	});

	it("normalizes exc from Frappe's real wire shape — a JSON-encoded array of strings", () => {
		// frappe.utils.response.report_error: orjson.dumps([...]).decode()
		const traceback = 'Traceback (most recent call last):\n  File "app.py", line 1\nValidationError: bad';
		const body = JSON.stringify({
			exc_type: "ValidationError",
			exc: JSON.stringify([traceback]),
		});
		const out = R.extractFrappeError(body);
		expect(out.exc).toContain("Traceback (most recent call last):");
		expect(out.exc).toContain('File "app.py", line 1');
		expect(out.exc).not.toContain("\\n");
	});

	it("joins multiple array entries with a newline", () => {
		const body = JSON.stringify({
			exc_type: "ValidationError",
			exc: JSON.stringify(["first entry", "second entry"]),
		});
		const out = R.extractFrappeError(body).exc;
		expect(out).toBe("first entry\nsecond entry");
	});

	it("still handles a plain-string exc unchanged", () => {
		const body = JSON.stringify({ exc_type: "ValidationError", exc: "plain traceback text" });
		expect(R.extractFrappeError(body).exc).toBe("plain traceback text");
	});

	it("does not throw when exc is neither JSON nor a normal string shape", () => {
		const body = JSON.stringify({ exc_type: "ValidationError", exc: "5 > 3" });
		expect(() => R.extractFrappeError(body)).not.toThrow();
	});
});
