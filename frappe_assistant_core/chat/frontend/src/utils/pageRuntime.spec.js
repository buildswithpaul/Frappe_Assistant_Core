import { beforeEach, describe, expect, it, vi } from "vitest";

import { makeFrappeStandIn, runPageScript } from "./pageRuntime";

let api;
let root;

beforeEach(() => {
	api = {
		baseCall: vi.fn().mockResolvedValue({ ok: true }),
		getCall: vi.fn().mockResolvedValue([{ name: "INV-1" }]),
		user: "avery@example.com",
	};
	root = document.createElement("div");
});

const run = (script, onUnsupported) => runPageScript(script, root, makeFrappeStandIn(api, { onUnsupported }));

describe("runPageScript", () => {
	it("runs the script with root_element, frappe, __ and fac in scope", () => {
		const result = runPageScript(
			"root_element.textContent = [frappe.session.user, __('Hi'), typeof fac].join(' ');",
			root,
			makeFrappeStandIn(api),
		);
		expect(result).toEqual({ ok: true });
		expect(root.textContent).toBe("avery@example.com Hi object");
	});

	it("hands the script the fac it is given", () => {
		const chart = vi.fn();
		const result = runPageScript("fac.chart(root_element, {series: []});", root, makeFrappeStandIn(api), { chart });
		expect(result).toEqual({ ok: true });
		expect(chart).toHaveBeenCalledWith(root, { series: [] });
	});

	it("sends frappe.db.get_list through frappe.client.get_list on the stand-in API", async () => {
		await run(
			"window.__pageRows = frappe.db.get_list('Sales Invoice', {fields: ['name'], filters: {status: 'Paid'}, limit: 5});",
		);
		await expect(window.__pageRows).resolves.toEqual([{ name: "INV-1" }]);
		expect(api.getCall).toHaveBeenCalledWith("frappe.client.get_list", {
			doctype: "Sales Invoice",
			fields: '["name"]',
			filters: '{"status":"Paid"}',
			order_by: undefined,
			limit_start: undefined,
			limit_page_length: 5,
		});
		delete window.__pageRows;
	});

	it("gives {ok: false} with the error when the script throws", () => {
		const result = run("throw new Error('boom');");
		expect(result.ok).toBe(false);
		expect(result.error.message).toBe("boom");
	});

	it("names the unsupported member a script reaches for", () => {
		const onUnsupported = vi.fn();
		const result = run("frappe.ui.form.on('Sales Invoice', {});", onUnsupported);
		expect(result).toMatchObject({ ok: false, unsupported: "ui" });
		expect(onUnsupported).toHaveBeenCalledWith("ui");
	});
});

describe("makeFrappeStandIn", () => {
	it("escapes html as Desk's frappe.utils.escape_html does, and reports any other utils member", () => {
		const onUnsupported = vi.fn();
		const frappe = makeFrappeStandIn(api, { onUnsupported });
		expect(frappe.utils.escape_html(`<a href="x" title='y'>\`1=1\` & co</a>`)).toBe(
			"&lt;a href&#x3D;&quot;x&quot; title&#x3D;&#39;y&#39;&gt;&#x60;1&#x3D;1&#x60; &amp; co&lt;/a&gt;",
		);
		expect(frappe.utils.escape_html(null)).toBe("");
		expect(frappe.utils.escape_html(undefined)).toBe("");
		expect(frappe.utils.escape_html(0)).toBe("0");
		expect(frappe.utils.escape_html(false)).toBe("false");
		expect(frappe.utils.get_url).toBeUndefined();
		expect(onUnsupported).toHaveBeenCalledWith("utils.get_url");
	});

	it("calls back and resolves frappe.call with the response, GET by type", async () => {
		const callback = vi.fn();
		const frappe = makeFrappeStandIn(api);
		const r = await frappe.call({ method: "x.y.z", type: "GET", args: { a: 1, b: { c: 2 } }, callback });
		expect(api.getCall).toHaveBeenCalledWith("x.y.z", { a: 1, b: '{"c":2}' });
		expect(r).toEqual({ message: [{ name: "INV-1" }] });
		expect(callback).toHaveBeenCalledWith({ message: [{ name: "INV-1" }] });
	});

	it("posts frappe.call by default and accepts the (method, args) form", async () => {
		await makeFrappeStandIn(api).call("x.y.z", { a: 1 });
		expect(api.baseCall).toHaveBeenCalledWith("x.y.z", { a: 1 });
	});

	it("hands a failure to the error callback", async () => {
		api.baseCall.mockRejectedValue(new Error("denied"));
		const error = vi.fn();
		await makeFrappeStandIn(api)
			.call({ method: "x.y.z", error })
			.catch(() => {});
		expect(error).toHaveBeenCalledWith(expect.objectContaining({ message: "denied" }));
	});

	it("maps the frappe.db writes to frappe.client", async () => {
		const frappe = makeFrappeStandIn(api);
		await frappe.db.insert({ doctype: "ToDo", description: "x" });
		await frappe.db.set_value("ToDo", "T-1", "status", "Closed");
		await frappe.db.delete_doc("ToDo", "T-1");
		expect(api.baseCall.mock.calls.map((c) => c[0])).toEqual([
			"frappe.client.insert",
			"frappe.client.set_value",
			"frappe.client.delete",
		]);
	});

	it("maps get_value and get_doc to GET reads", async () => {
		const frappe = makeFrappeStandIn(api);
		await frappe.db.get_value("Customer", "C-1", "customer_name");
		await frappe.db.get_doc("Customer", "C-1");
		expect(api.getCall.mock.calls.map((c) => c[0])).toEqual(["frappe.client.get_value", "frappe.client.get"]);
	});

	it("formats as Desk does with the site's settings (pageFormat.parity.spec.js has the rest)", () => {
		const formatSettings = {
			number_format: "#,##,###.##",
			currency: "INR",
			float_precision: "3",
			date_format: "dd-mm-yyyy",
			currencies: { INR: { symbol: "₹", number_format: "#,##,###.##", fraction_units: 100 } },
		};
		const frappe = makeFrappeStandIn(api, { formatSettings });
		expect(frappe.format(123456.5, { fieldtype: "Currency" })).toBe("₹ 1,23,456.50");
		expect(frappe.format(1234.5, { fieldtype: "Float" })).toBe("1,234.500");
		expect(frappe.format(1234.4, { fieldtype: "Int" })).toBe("1234");
		expect(frappe.format("2026-10-29", { fieldtype: "Date" })).toBe("29-10-2026");
		expect(frappe.format("plain", { fieldtype: "Data" })).toBe("plain");
		// A record's text is never unescaped: Frappe saved it escaped, and Desk returns it so.
		expect(frappe.format("&lt;img src=x onerror=alert(1)&gt;", { fieldtype: "Data" })).toBe(
			"&lt;img src=x onerror=alert(1)&gt;",
		);
		expect(frappe.format(null, { fieldtype: "Data" })).toBe("");
		expect(frappe.datetime.str_to_user("2026-10-29")).toBe("29-10-2026");
	});

	it("gives today's date as YYYY-MM-DD", () => {
		expect(makeFrappeStandIn(api).datetime.get_today()).toMatch(/^\d{4}-\d{2}-\d{2}$/);
	});

	it("records an unknown member below a known one by its path", () => {
		const onUnsupported = vi.fn();
		const frappe = makeFrappeStandIn(api, { onUnsupported });
		expect(frappe.db.get_single_value).toBeUndefined();
		expect(onUnsupported).toHaveBeenCalledWith("db.get_single_value");
	});

	it("reports a failed call the script gave no error callback for", async () => {
		api.baseCall.mockRejectedValue(new Error("denied"));
		const onError = vi.fn();
		const frappe = makeFrappeStandIn(api, { onError });
		await frappe.db.insert({ doctype: "ToDo" }).catch(() => {});
		expect(onError).toHaveBeenCalledWith(expect.objectContaining({ message: "denied" }));
	});

	it("leaves a failure to the script's own error callback", async () => {
		api.baseCall.mockRejectedValue(new Error("denied"));
		const onError = vi.fn();
		await makeFrappeStandIn(api, { onError })
			.call({ method: "x.y.z", error: () => {} })
			.catch(() => {});
		expect(onError).not.toHaveBeenCalled();
	});
});
