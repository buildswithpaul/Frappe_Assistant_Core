import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { MSG_GENERIC, friendlyError, isTechnicalMessage } from "./_core.js";

vi.mock("@/utils/logger", () => ({
	logger: { error: vi.fn(), warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
}));

const serverMessagesBody = (message, { excType = "ValidationError", exception = "" } = {}) =>
	JSON.stringify({
		exc_type: excType,
		exception,
		_server_messages: JSON.stringify([
			JSON.stringify({ message, title: "Error", indicator: "red" }),
		]),
	});

describe("friendlyError", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});
	afterEach(() => vi.restoreAllMocks());

	it("maps missing-method Frappe messages to the generic fallback", () => {
		const raw =
			"Failed to get method for command frappe_assistant_core.chat.api.set_user_credit_limit with module 'frappe_assistant_core.chat.api' has no attribute 'set_user_credit_limit'";
		const err = friendlyError(
			{ status: 417 },
			serverMessagesBody(raw, { exception: raw })
		);
		expect(err.message).toBe(MSG_GENERIC);
		expect(err.userMessage).toBe(MSG_GENERIC);
	});

	it("maps AttributeError exc_type to the generic fallback", () => {
		const err = friendlyError(
			{ status: 500 },
			JSON.stringify({
				exc_type: "AttributeError",
				exception: "AttributeError: module has no attribute 'x'",
			})
		);
		expect(err.message).toBe(MSG_GENERIC);
	});

	it("keeps real validation messages for the user", () => {
		const err = friendlyError(
			{ status: 417 },
			serverMessagesBody("Credit limit cannot be negative")
		);
		expect(err.message).toBe("Credit limit cannot be negative");
	});

	it("maps session errors to the refresh prompt", () => {
		const err = friendlyError(
			{ status: 403 },
			JSON.stringify({ exc_type: "CSRFTokenError", exception: "CSRFTokenError" })
		);
		expect(err.message).toMatch(/session has ended/i);
	});
});

describe("friendlyError with a server-authored validation message", () => {
	// Frappe puts the full Python traceback in `exc` on EVERY error response,
	// including deliberate `frappe.throw` validations. Scanning the whole body
	// for "Traceback" therefore discarded the authored message too, and the
	// user saw "Something went wrong" for a plain bad postal code.
	const validationBody = JSON.stringify({
		billing_field: "billing_pincode",
		exc_type: "ValidationError",
		exception:
			"frappe.exceptions.ValidationError: [HTTP_417] Postal code 110001 is not in Karnataka.",
		exc: '["Traceback (most recent call last):\\n  File \\"x.py\\", line 1"]',
		_server_messages: JSON.stringify([
			JSON.stringify({
				message: "[HTTP_417] Postal code 110001 is not in Karnataka.",
			}),
		]),
	});

	it("shows the authored message, not the generic one", () => {
		const err = friendlyError({ status: 417 }, validationBody);
		expect(err.message).toContain("not in Karnataka");
		expect(err.message).not.toBe(MSG_GENERIC);
	});

	it("strips Frappe's [HTTP_nnn] prefix", () => {
		const err = friendlyError({ status: 417 }, validationBody);
		expect(err.message).not.toContain("HTTP_417");
		expect(err.message.startsWith("Postal code")).toBe(true);
	});

	it("carries the field the server named", () => {
		const err = friendlyError({ status: 417 }, validationBody);
		expect(err.field).toBe("billing_pincode");
	});

	it("still hides a genuinely technical exception", () => {
		// An AttributeError is not an authored message, traceback or not.
		const technical = JSON.stringify({
			exc_type: "AttributeError",
			exception: "AttributeError: 'NoneType' object has no attribute 'x'",
			_server_messages: JSON.stringify([
				JSON.stringify({ message: "'NoneType' object has no attribute 'x'" }),
			]),
		});
		expect(friendlyError({ status: 500 }, technical).message).toBe(MSG_GENERIC);
	});
});

describe("isTechnicalMessage", () => {
	it("detects missing-method phrasing", () => {
		expect(
			isTechnicalMessage(
				"Failed to get method for command foo.bar with module 'foo' has no attribute 'bar'"
			)
		).toBe(true);
	});

	it("allows ordinary copy", () => {
		expect(isTechnicalMessage("Only System Managers can access billing features")).toBe(
			false
		);
	});
});
