import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createPageFrame, describePageRequest, fetchTransport, readCall } from "./pageFrameHost";

const PAGE = { title: "Sales", html: "<p>Sales</p>", style: "", script: "" };

let frame;
let pageWindow;
let other;
let transport;
let askUser;
let pageCount = 0;
let replies;

// jsdom runs no srcdoc frame, so a real window stands in for the page's frame: the host reads the
// outer frame's first child, as the browser gives it, and posts its replies there.
function mountFrame(options = {}) {
	// Each test gets its own page name, so a method trusted for one page never carries into the next.
	frame = createPageFrame({
		page: PAGE,
		kitCss: "",
		user: "avery@example.com",
		pageName: `sales-${++pageCount}`,
		transport,
		askUser,
		...options,
	});
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
	askUser = vi.fn(async () => "once");
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

	it("serves an allowlisted read as GET, with no prompt, and replies with its message", async () => {
		mountFrame();
		fromPage({ op: "call", id: 1, method: "frappe.client.get_list", args: { doctype: "Sales Invoice" }, type: "GET" });
		await settle();
		expect(transport.get).toHaveBeenCalledWith("frappe.client.get_list", { doctype: "Sales Invoice" });
		expect(askUser).not.toHaveBeenCalled();
		expect(transport.post).not.toHaveBeenCalled();
		expect(reply(1)).toEqual({ fac_page: 1, op: "reply", id: 1, ok: true, message: [{ name: "SINV-1" }] });
	});

	it("keeps an allowlisted read on GET even when the script asked for POST", async () => {
		mountFrame();
		fromPage({ op: "call", id: 1, method: "frappe.client.get_count", args: { doctype: "ToDo" }, type: "POST" });
		await settle();
		expect(transport.get).toHaveBeenCalledOnce();
		expect(transport.post).not.toHaveBeenCalled();
		expect(askUser).not.toHaveBeenCalled();
	});

	it("asks before any other method, even one sent as GET, and runs nothing until allowed", async () => {
		// GET rollback stops database writes, not a queued job, an email or an outbound request.
		askUser.mockResolvedValue(false);
		mountFrame();
		fromPage({ op: "call", id: 1, method: "my_app.api.sales_feed", args: { months: 6 }, type: "GET" });
		await settle();
		expect(askUser).toHaveBeenCalledWith({
			message: "This page wants to run my_app.api.sales_feed.",
			fields: [["months", "6"]],
			trustable: true,
		});
		expect(transport.get).not.toHaveBeenCalled();
		expect(transport.post).not.toHaveBeenCalled();
		expect(reply(1)).toMatchObject({ ok: false, error: { message: "The user did not allow this." } });
	});

	it("asks before an aliased write, whatever its name or type", async () => {
		askUser.mockResolvedValue(false);
		mountFrame();
		for (const [id, method] of [
			[1, "frappe.desk.form.save.savedocs"],
			[2, "frappe.client.insert_many"],
			[3, "run_doc_method"],
		]) {
			fromPage({ op: "call", id, method, args: {}, type: "GET" });
		}
		await settle();
		expect(askUser).toHaveBeenCalledTimes(3);
		expect(transport.get).not.toHaveBeenCalled();
		expect(transport.post).not.toHaveBeenCalled();
	});

	it("sends an allowed method with the type the script asked for, or GET then POST", async () => {
		transport.get.mockRejectedValueOnce(Object.assign(new Error("Not permitted"), { status: 403 }));
		mountFrame();
		fromPage({ op: "call", id: 1, method: "my_app.api.close_invoice", args: { name: "X" } });
		await settle();
		expect(askUser).toHaveBeenCalledOnce();
		expect(transport.get).toHaveBeenCalledWith("my_app.api.close_invoice", { name: "X" });
		expect(transport.post).toHaveBeenCalledWith("my_app.api.close_invoice", { name: "X" });
	});

	it("remembers Allow for this page for that method and that page only", async () => {
		askUser.mockResolvedValue("page");
		mountFrame({ pageName: "sales-trust" });
		fromPage({ op: "call", id: 1, method: "my_app.api.sales_feed", args: {} });
		fromPage({ op: "call", id: 2, method: "my_app.api.sales_feed", args: {} });
		await settle();
		await settle();
		expect(askUser).toHaveBeenCalledOnce();
		expect(transport.get).toHaveBeenCalledTimes(2);

		// Another method on the same page still asks, and so does the same method on another page.
		fromPage({ op: "call", id: 3, method: "my_app.api.other", args: {} });
		await settle();
		expect(askUser).toHaveBeenCalledTimes(2);
		frame.dispose();
		mountFrame({ pageName: "costs-trust" });
		fromPage({ op: "call", id: 4, method: "my_app.api.sales_feed", args: {} });
		await settle();
		expect(askUser).toHaveBeenCalledTimes(3);
	});

	it("never trusts a record write for the page, even when the user says so", async () => {
		askUser.mockResolvedValue("page");
		mountFrame({ pageName: "sales-writes" });
		const args = { doctype: "ToDo", name: "TD-1", fieldname: "status", value: "Closed" };
		fromPage({ op: "call", id: 1, method: "frappe.client.set_value", args });
		await settle();
		fromPage({ op: "call", id: 2, method: "frappe.client.set_value", args });
		await settle();
		expect(askUser).toHaveBeenCalledTimes(2);
		expect(askUser.mock.calls[0][0].trustable).toBe(false);
	});

	it("lists the fields a change sets, and sends exactly the payload it described", async () => {
		mountFrame();
		const doc = { doctype: "ToDo", description: "Call Blue Harbor", priority: "High", allocated_to: "a@x.com" };
		fromPage({ op: "call", id: 1, method: "frappe.client.insert", args: { doc } });
		await settle();
		const request = askUser.mock.calls[0][0];
		expect(request).toEqual({
			message: "This page wants to create a new ToDo.",
			fields: [
				["description", "Call Blue Harbor"],
				["priority", "High"],
				["allocated_to", "a@x.com"],
			],
			trustable: false,
		});
		expect(transport.post).toHaveBeenCalledWith("frappe.client.insert", { doc });
	});

	it("sends the payload the user saw, even if the page's copy changes while they decide", async () => {
		let decide;
		askUser.mockReturnValue(new Promise((resolve) => (decide = resolve)));
		mountFrame();
		const args = { doctype: "ToDo", name: "TD-1", fieldname: "status", value: "Closed" };
		fromPage({ op: "call", id: 1, method: "frappe.client.set_value", args });
		await settle();
		// postMessage gives the host its own copy; the host copies again before it asks.
		args.value = "Cancelled";
		decide("once");
		await settle();
		expect(askUser.mock.calls[0][0].fields).toEqual([["status", "Closed"]]);
		expect(transport.post).toHaveBeenCalledWith("frappe.client.set_value", {
			doctype: "ToDo",
			name: "TD-1",
			fieldname: "status",
			value: "Closed",
		});
	});

	it("refuses a write whose doctype or name disagrees with its doc, asking nothing", async () => {
		mountFrame();
		const doc = { doctype: "ToDo", name: "TD-1", status: "Closed" };
		fromPage({ op: "call", id: 1, method: "frappe.client.save", args: { doc, doctype: "Note" } });
		fromPage({ op: "call", id: 2, method: "frappe.client.save", args: { doc, name: "TD-2" } });
		fromPage({ op: "call", id: 3, method: "frappe.client.insert", args: { doc: { status: "x" } } });
		await settle();
		expect(askUser).not.toHaveBeenCalled();
		expect(transport.post).not.toHaveBeenCalled();
		for (const id of [1, 2, 3]) expect(reply(id)).toMatchObject({ ok: false, error: { message: "This request is not allowed." } });
	});

	it("sends nothing when the user does not allow a change", async () => {
		askUser.mockResolvedValue(false);
		mountFrame();
		fromPage({ op: "call", id: 1, method: "frappe.client.delete", args: { doctype: "ToDo", name: "TD-1" } });
		await settle();
		expect(askUser.mock.calls[0][0].message).toBe("This page wants to delete ToDo TD-1.");
		expect(transport.post).not.toHaveBeenCalled();
		expect(transport.get).not.toHaveBeenCalled();
		expect(frame.errors[0]).toMatch(/did not allow/);
	});

	it("does not turn a refused allowlisted read into a change", async () => {
		transport.get.mockRejectedValue(Object.assign(new Error("Not permitted"), { status: 403 }));
		mountFrame();
		fromPage({ op: "call", id: 1, method: "frappe.client.get_list", args: {}, type: "GET" });
		await settle();
		expect(askUser).not.toHaveBeenCalled();
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

describe("describePageRequest", () => {
	it("says what a change does and lists its fields, with long values cut short", () => {
		expect(describePageRequest("frappe.client.insert", { doc: JSON.stringify({ doctype: "ToDo", description: "x" }) })).toEqual({
			message: "This page wants to create a new ToDo.",
			fields: [["description", "x"]],
			trustable: false,
		});
		const update = describePageRequest("frappe.client.set_value", {
			doctype: "Sales Invoice",
			name: "SINV-1",
			fieldname: { status: "Paid", remarks: "y".repeat(200) },
		});
		expect(update.message).toBe("This page wants to update Sales Invoice SINV-1.");
		expect(update.fields[0]).toEqual(["status", "Paid"]);
		expect(update.fields[1][1]).toHaveLength(78);
		expect(describePageRequest("frappe.client.submit", { doc: { doctype: "Sales Order", name: "SO-1" } }).message).toBe(
			"This page wants to submit Sales Order SO-1.",
		);
	});

	it("names a child table by its row count and folds a long field list", () => {
		const doc = { doctype: "Sales Order", items: [{}, {}] };
		for (let i = 0; i < 10; i++) doc[`f${i}`] = i;
		const { fields } = describePageRequest("frappe.client.insert", { doc });
		expect(fields[0]).toEqual(["items", "2 rows"]);
		expect(fields).toHaveLength(9);
		expect(fields.at(-1)).toEqual(["and 3 more", ""]);
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
