import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createPageFrame, fetchTransport, readCall } from "./pageFrameHost";

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
		fromPage({ op: "call", id: 1, method: "sales_feed", args: { months: 6 }, type: "GET" });
		await settle();
		expect(askUser).toHaveBeenCalledWith(
			expect.objectContaining({
				message: "This page wants to run sales_feed with these values.",
				fields: [{ name: "months", value: "6" }],
				trustable: true,
			}),
		);
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

	it("remembers Allow for this page for that method, on this version of the page only", async () => {
		askUser.mockResolvedValue("page");
		mountFrame({ pageName: "sales-trust" });
		fromPage({ op: "call", id: 1, method: "sales_feed", args: {} });
		fromPage({ op: "call", id: 2, method: "sales_feed", args: {} });
		await settle();
		await settle();
		expect(askUser).toHaveBeenCalledOnce();
		expect(transport.get).toHaveBeenCalledTimes(2);

		// Another method on the same page still asks.
		fromPage({ op: "call", id: 3, method: "other_feed", args: {} });
		await settle();
		expect(askUser).toHaveBeenCalledTimes(2);

		// A new version of the same page starts afresh: its code has not earned the trust.
		frame.dispose();
		mountFrame({ pageName: "sales-trust", page: { ...PAGE, script: "root_element.textContent = 'v2';" } });
		fromPage({ op: "call", id: 4, method: "sales_feed", args: {} });
		await settle();
		expect(askUser).toHaveBeenCalledTimes(3);

		// And so does another page.
		frame.dispose();
		mountFrame({ pageName: "costs-trust" });
		fromPage({ op: "call", id: 5, method: "sales_feed", args: {} });
		await settle();
		expect(askUser).toHaveBeenCalledTimes(4);
	});

	it("never trusts a dotted method for the page, even when told to", async () => {
		askUser.mockResolvedValue("page");
		mountFrame({ pageName: "sales-dotted" });
		for (const id of [1, 2]) {
			fromPage({ op: "call", id, method: "frappe.desk.form.save.savedocs", args: { doc: "{}", action: "Save" } });
			await settle();
		}
		expect(askUser).toHaveBeenCalledTimes(2);
		expect(askUser.mock.calls[0][0].trustable).toBe(false);
	});

	it("refuses a method the user said no to, without asking again, for this version of the page", async () => {
		askUser.mockResolvedValue(false);
		mountFrame({ pageName: "sales-denied" });
		fromPage({ op: "call", id: 1, method: "sales_feed", args: {} });
		await settle();
		fromPage({ op: "call", id: 2, method: "sales_feed", args: {} });
		await settle();
		expect(askUser).toHaveBeenCalledOnce();
		expect(reply(2)).toMatchObject({ ok: false, error: { message: "The user did not allow this." } });
		frame.dispose();
		mountFrame({ pageName: "sales-denied", page: { ...PAGE, script: "// v2" } });
		fromPage({ op: "call", id: 3, method: "sales_feed", args: {} });
		await settle();
		expect(askUser).toHaveBeenCalledTimes(2);
	});

	it("lets at most five calls wait for the user, and refuses the rest", async () => {
		askUser.mockReturnValue(new Promise(() => {}));
		mountFrame();
		for (let id = 1; id <= 7; id++) fromPage({ op: "call", id, method: `feed_${id}`, args: {} });
		await settle();
		expect(askUser).toHaveBeenCalledTimes(5);
		expect(reply(6)).toMatchObject({ ok: false, error: { message: "Too many requests are waiting for the user." } });
		expect(reply(7).ok).toBe(false);
	});

	it("runs at most eight reads at once", async () => {
		const finishers = [];
		transport.get.mockImplementation(() => new Promise((resolve) => finishers.push(resolve)));
		mountFrame();
		for (let id = 1; id <= 10; id++) fromPage({ op: "call", id, method: "frappe.client.get_count", args: {}, type: "GET" });
		await settle();
		expect(transport.get).toHaveBeenCalledTimes(8);
		finishers[0](1);
		await settle();
		expect(transport.get).toHaveBeenCalledTimes(9);
	});

	it("reads the record before a save, shows the diff, and refuses when it can't read it", async () => {
		transport.get.mockResolvedValueOnce({ doctype: "ToDo", name: "TD-1", docstatus: 0, status: "Open", priority: "High" });
		mountFrame();
		fromPage({ op: "call", id: 1, method: "frappe.client.save", args: { doc: { doctype: "ToDo", name: "TD-1", status: "Closed" } } });
		await settle();
		expect(transport.get).toHaveBeenCalledWith("frappe.client.get", { doctype: "ToDo", name: "TD-1" });
		expect(askUser.mock.calls[0][0].fields).toEqual([
			{ name: "status", value: "Closed", before: "Open", status: "changed" },
			{ name: "priority", value: "", before: "High", beforeRows: undefined, status: "blanked" },
		]);

		transport.get.mockRejectedValueOnce(new Error("No permission"));
		fromPage({ op: "call", id: 2, method: "frappe.client.save", args: { doc: { doctype: "ToDo", name: "TD-2" } } });
		await settle();
		expect(askUser).toHaveBeenCalledOnce();
		expect(reply(2)).toMatchObject({ ok: false, error: { message: "This request is not allowed." } });
	});

	it("refuses a save that would change the record's docstatus, asking nothing", async () => {
		transport.get.mockResolvedValueOnce({ doctype: "ToDo", name: "TD-1", docstatus: 1 });
		mountFrame();
		fromPage({ op: "call", id: 1, method: "frappe.client.save", args: { doc: { doctype: "ToDo", name: "TD-1" } } });
		await settle();
		expect(askUser).not.toHaveBeenCalled();
		expect(transport.post).not.toHaveBeenCalled();
	});

	it("sends set_value the fieldname object it described, not the string the page sent", async () => {
		mountFrame();
		fromPage({
			op: "call",
			id: 1,
			method: "frappe.client.set_value",
			args: { doctype: "ToDo", name: "T1", fieldname: '{"description":"x","allocated_to":"a@x.com"}' },
		});
		await settle();
		expect(askUser.mock.calls[0][0].fields).toEqual([
			{ name: "description", value: "x" },
			{ name: "allocated_to", value: "a@x.com" },
		]);
		expect(transport.post).toHaveBeenCalledWith("frappe.client.set_value", {
			doctype: "ToDo",
			name: "T1",
			fieldname: { description: "x", allocated_to: "a@x.com" },
		});
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
		expect(request.message).toBe("This page wants to create a new ToDo with these fields.");
		expect(request.fields).toEqual([
			{ name: "description", value: "Call Blue Harbor" },
			{ name: "priority", value: "High" },
			{ name: "allocated_to", value: "a@x.com" },
		]);
		expect(request.trustable).toBe(false);
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
		expect(askUser.mock.calls[0][0].fields).toEqual([{ name: "status", value: "Closed" }]);
		expect(transport.post).toHaveBeenCalledWith("frappe.client.set_value", {
			doctype: "ToDo",
			name: "TD-1",
			fieldname: { status: "Closed" },
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
