import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createPageFrame, describePageWrite, fetchTransport, readCall } from "./pageFrameHost";

const PAGE = { title: "Sales", html: "<p>Sales</p>", style: "", script: "" };

let frame;
let pageWindow;
let other;
let transport;
let askWrite;
let replies;

// jsdom runs no srcdoc frame, so a real window stands in for the page's frame: the host reads the
// outer frame's first child, as the browser gives it, and posts its replies there.
function mountFrame(options = {}) {
	frame = createPageFrame({ page: PAGE, kitCss: "", user: "avery@example.com", transport, askWrite, ...options });
	Object.defineProperty(frame.element, "contentWindow", { value: { frames: [pageWindow] } });
	return frame;
}

function fromPage(data, source = pageWindow) {
	window.dispatchEvent(new MessageEvent("message", { data: { fac_page: 1, ...data }, source }));
}

const reply = (id) => replies.find((r) => r.op === "reply" && r.id === id);
const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

beforeEach(() => {
	const holders = [document.createElement("iframe"), document.createElement("iframe")];
	holders.forEach((el) => document.body.append(el));
	[pageWindow, other] = holders.map((el) => el.contentWindow);
	replies = [];
	vi.spyOn(pageWindow, "postMessage").mockImplementation((message) => replies.push(message));
	transport = { get: vi.fn(async () => [{ name: "SINV-1" }]), post: vi.fn(async () => ({ ok: 1 })) };
	askWrite = vi.fn(async () => true);
});

afterEach(() => {
	frame?.dispose();
	document.body.innerHTML = "";
	vi.restoreAllMocks();
});

describe("createPageFrame", () => {
	it("builds the outer frame with scripts only", () => {
		const { element } = mountFrame();
		expect(element.getAttribute("sandbox")).toBe("allow-scripts");
		expect(element.getAttribute("referrerpolicy")).toBe("no-referrer");
		expect(element.srcdoc).toContain("fac_page_frame.js");
	});

	it("ignores a message from any window but the page's own frame", async () => {
		mountFrame();
		fromPage({ op: "call", id: 1, method: "frappe.client.get_list", args: {}, type: "GET" }, other);
		fromPage({ op: "call", id: 2, method: "frappe.client.get_list", args: {}, type: "GET" }, window);
		await settle();
		expect(transport.get).not.toHaveBeenCalled();
		expect(replies).toEqual([]);
	});

	it("serves a read as GET, with no prompt, and replies with its message", async () => {
		mountFrame();
		fromPage({ op: "call", id: 1, method: "frappe.client.get_list", args: { doctype: "Sales Invoice" }, type: "GET" });
		await settle();
		expect(transport.get).toHaveBeenCalledWith("frappe.client.get_list", { doctype: "Sales Invoice" });
		expect(askWrite).not.toHaveBeenCalled();
		expect(transport.post).not.toHaveBeenCalled();
		expect(reply(1)).toEqual({ fac_page: 1, op: "reply", id: 1, ok: true, message: [{ name: "SINV-1" }] });
	});

	it("tries a call that names no type as a read first", async () => {
		mountFrame();
		fromPage({ op: "call", id: 1, method: "my_app.api.sales_feed", args: {} });
		await settle();
		expect(transport.get).toHaveBeenCalledOnce();
		expect(askWrite).not.toHaveBeenCalled();
	});

	it("asks before a change, and sends it as POST only once the user allows it", async () => {
		mountFrame();
		fromPage({
			op: "call",
			id: 1,
			method: "frappe.client.set_value",
			args: { doctype: "ToDo", name: "TD-1", fieldname: "status", value: "Closed" },
		});
		await settle();
		expect(askWrite).toHaveBeenCalledWith("This page wants to update ToDo TD-1: status → Closed.");
		expect(transport.get).not.toHaveBeenCalled();
		expect(transport.post).toHaveBeenCalledWith("frappe.client.set_value", expect.objectContaining({ name: "TD-1" }));
		expect(reply(1).ok).toBe(true);
	});

	it("sends nothing when the user does not allow the change", async () => {
		askWrite.mockResolvedValue(false);
		mountFrame();
		fromPage({ op: "call", id: 1, method: "frappe.client.delete", args: { doctype: "ToDo", name: "TD-1" } });
		await settle();
		expect(transport.post).not.toHaveBeenCalled();
		expect(transport.get).not.toHaveBeenCalled();
		expect(reply(1)).toMatchObject({ ok: false, error: { message: "The user did not allow this change." } });
		expect(frame.errors[0]).toMatch(/did not allow/);
	});

	it("asks before a call the script sent as POST", async () => {
		mountFrame();
		fromPage({ op: "call", id: 1, method: "my_app.api.close_invoice", args: {}, type: "POST" });
		await settle();
		expect(askWrite).toHaveBeenCalledWith("This page wants to run my_app.api.close_invoice, which can change data.");
		expect(transport.get).not.toHaveBeenCalled();
	});

	it("asks, then sends as POST, when a call that named no type is refused as GET", async () => {
		transport.get.mockRejectedValue(Object.assign(new Error("Not permitted"), { status: 403 }));
		mountFrame();
		fromPage({ op: "call", id: 1, method: "my_app.api.close_invoice", args: { name: "X" } });
		await settle();
		expect(askWrite).toHaveBeenCalledOnce();
		expect(transport.post).toHaveBeenCalledWith("my_app.api.close_invoice", { name: "X" });
	});

	it("does not turn a refused read the script sent as GET into a change", async () => {
		transport.get.mockRejectedValue(Object.assign(new Error("Not permitted"), { status: 403 }));
		mountFrame();
		fromPage({ op: "call", id: 1, method: "frappe.client.get_list", args: {}, type: "GET" });
		await settle();
		expect(askWrite).not.toHaveBeenCalled();
		expect(reply(1)).toMatchObject({ ok: false, error: { message: "Not permitted", status: 403 } });
	});

	it("refuses a malformed call and an unknown request, sending nothing", async () => {
		mountFrame();
		fromPage({ op: "call", id: 1, method: "../../api/method/logout", args: {} });
		fromPage({ op: "call", id: 2, method: "frappe.client.get_list", args: ["x"] });
		fromPage({ op: "call", id: 3, method: "frappe.client.get_list", args: {}, type: "PUT" });
		fromPage({ op: "eval", id: 4, code: "alert(1)" });
		await settle();
		expect(transport.get).not.toHaveBeenCalled();
		expect(transport.post).not.toHaveBeenCalled();
		expect(reply(1).ok).toBe(false);
		expect(reply(2).ok).toBe(false);
		expect(reply(3).ok).toBe(false);
		expect(reply(4)).toBeUndefined();
	});

	it("keeps what went wrong while the page ran", async () => {
		const onError = vi.fn();
		mountFrame({ onError });
		fromPage({ op: "error", message: "x is not defined" });
		transport.get.mockRejectedValue(Object.assign(new Error("No permission"), { status: 403 }));
		fromPage({ op: "call", id: 1, method: "frappe.client.get_list", args: {}, type: "GET" });
		await settle();
		expect(frame.errors).toEqual(["x is not defined", "frappe.client.get_list failed: No permission"]);
		expect(onError).toHaveBeenCalledTimes(2);
	});

	it("snapshots only once the script has run and its calls are back", async () => {
		vi.useFakeTimers();
		try {
			let finish;
			transport.get.mockReturnValue(new Promise((resolve) => (finish = resolve)));
			mountFrame();
			const snap = frame.snapshot();
			await vi.advanceTimersByTimeAsync(1000);
			expect(replies.find((r) => r.op === "snapshot")).toBeUndefined();
			fromPage({ op: "ready" });
			fromPage({ op: "call", id: 1, method: "frappe.client.get_list", args: {}, type: "GET" });
			await vi.advanceTimersByTimeAsync(1000);
			// The figures the script fetched are still on their way.
			expect(replies.find((r) => r.op === "snapshot")).toBeUndefined();
			finish([]);
			await vi.advanceTimersByTimeAsync(400);
			const ask = replies.find((r) => r.op === "snapshot");
			expect(ask).toBeDefined();
			fromPage({ op: "snapshot_result", id: ask.id, html: "<div>x</div>", wide: false });
			await expect(snap).resolves.toEqual({ html: "<div>x</div>", wide: false });
		} finally {
			vi.useRealTimers();
		}
	});

	it("rejects a snapshot that is not markup", async () => {
		mountFrame();
		fromPage({ op: "ready" });
		const snap = frame.snapshot();
		await vi.waitFor(() => expect(replies.find((r) => r.op === "snapshot")).toBeDefined());
		const { id } = replies.find((r) => r.op === "snapshot");
		fromPage({ op: "snapshot_result", id, html: { toString: () => "<b>x</b>" } });
		await expect(snap).rejects.toThrow(/nothing to print/);
	});

	it("returns the rendered markup for Download PDF", async () => {
		mountFrame();
		fromPage({ op: "ready" });
		const snap = frame.snapshot();
		await vi.waitFor(() => expect(replies.find((r) => r.op === "snapshot")).toBeDefined());
		const { id } = replies.find((r) => r.op === "snapshot");
		fromPage({ op: "snapshot_result", id, html: '<div class="fac-page-root">₹70,29,354</div>', wide: false });
		await expect(snap).resolves.toEqual({ html: '<div class="fac-page-root">₹70,29,354</div>', wide: false });
	});

	it("stops listening once disposed", async () => {
		mountFrame();
		frame.dispose();
		fromPage({ op: "call", id: 1, method: "frappe.client.get_list", args: {}, type: "GET" });
		await settle();
		expect(transport.get).not.toHaveBeenCalled();
	});
});

describe("readCall", () => {
	it("accepts a dotted method, plain args and GET, POST or no type", () => {
		expect(readCall({ id: 1, method: "a.b_c.d", args: { x: [1] } })).toEqual({ id: 1, method: "a.b_c.d", args: { x: [1] }, type: undefined });
		expect(readCall({ id: 2, method: "a.b", type: "POST" }).type).toBe("POST");
	});

	it("refuses anything else", () => {
		expect(readCall({ id: 0, method: "a.b" })).toBe(null);
		expect(readCall({ id: 1, method: "a/b" })).toBe(null);
		expect(readCall({ id: 1, method: "a.b", args: new Date() })).toBe(null);
		expect(readCall({ id: 1, method: "a.b", args: { big: "x".repeat(1024 * 1024 + 1) } })).toBe(null);
	});
});

describe("describePageWrite", () => {
	it("says what a change does in plain words", () => {
		expect(describePageWrite("frappe.client.insert", { doc: JSON.stringify({ doctype: "ToDo" }) })).toBe(
			"This page wants to create a new ToDo.",
		);
		expect(
			describePageWrite("frappe.client.set_value", {
				doctype: "Sales Invoice",
				name: "SINV-1",
				fieldname: { status: "Paid", a: 1, b: 2, c: 3 },
			}),
		).toBe("This page wants to update Sales Invoice SINV-1: status → Paid, a → 1, b → 2 and 1 more.");
		expect(describePageWrite("frappe.client.submit", { doc: { doctype: "Sales Order", name: "SO-1" } })).toBe(
			"This page wants to submit Sales Order SO-1.",
		);
	});
});

describe("fetchTransport", () => {
	afterEach(() => vi.unstubAllGlobals());

	it("sends a read as GET with JSON-encoded args, and a change as POST with the CSRF token", async () => {
		const fetchMock = vi.fn(async () => ({ ok: true, status: 200, json: async () => ({ message: 7 }) }));
		vi.stubGlobal("fetch", fetchMock);
		const t = fetchTransport(() => "csrf-1");
		expect(await t.get("frappe.client.get_count", { doctype: "ToDo", filters: { status: "Open" } })).toBe(7);
		const [url, init] = fetchMock.mock.calls[0];
		expect(url).toBe("/api/method/frappe.client.get_count?doctype=ToDo&filters=%7B%22status%22%3A%22Open%22%7D");
		expect(init.method).toBe("GET");
		await t.post("frappe.client.insert", { doc: {} });
		expect(fetchMock.mock.calls[1][1]).toMatchObject({
			method: "POST",
			headers: expect.objectContaining({ "X-Frappe-CSRF-Token": "csrf-1" }),
		});
	});

	it("rejects with Frappe's message and the HTTP status", async () => {
		const body = { exc: "x", _server_messages: JSON.stringify([JSON.stringify({ message: "<b>Not permitted</b>" })]) };
		vi.stubGlobal("fetch", vi.fn(async () => ({ ok: false, status: 403, json: async () => body })));
		await expect(fetchTransport(() => "").get("a.b", {})).rejects.toMatchObject({ message: "Not permitted", status: 403 });
	});
});
