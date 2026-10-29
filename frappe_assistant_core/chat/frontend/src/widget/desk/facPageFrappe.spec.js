import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { EXAMPLE_DF, EXAMPLE_ROWS, EXAMPLE_SITE, exampleTitle } from "@/utils/__tests__/pageFormatCases";
import { makeFrappeStandIn, runPageScript } from "@/utils/pageRuntime";

import { facPagesSource } from "./facPagesSource";

const APP_ROOT = resolve(import.meta.dirname, "../../../../..");
// What Desk's own frappe.format returned for the example's rows (pageFormat.parity.spec.js).
const DESK_HTML = JSON.parse(readFileSync(resolve(import.meta.dirname, "../../utils/__tests__/pageFormatCases.desk.json"), "utf-8"));

// The script of the pages-in-chat skill's example, as FACO reads it and writes pages from it.
const SKILL = readFileSync(resolve(APP_ROOT, "../docs/skills/pages_in_chat.md"), "utf-8");
const EXAMPLE = [...SKILL.matchAll(/```js\n([\s\S]*?)```/g)].map((m) => m[1]).find((js) => js.includes("frappe.format"));
const EXAMPLE_HTML = '<table><tbody id="rows"></tbody></table>';

// Desk's frappe.utils.escape_html (frappe/public/js/frappe/utils/utils.js).
const ESCAPE = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;", "`": "&#x60;", "=": "&#x3D;" };
const escapeHtml = (text) => (text == null ? "" : String(text).replace(/[&<>"'`=]/g, (c) => ESCAPE[c]));

// fac_page_frappe.js as fac_pages.js inlines it.
const WRAPPER = readFileSync(resolve(APP_ROOT, "assistant_core/page/fac_pages/fac_page_frappe.js"), "utf-8");
const fac_page_frappe = new Function(`${WRAPPER}\nreturn fac_page_frappe;`)();

// The members of Desk's frappe a page relies on, and a format that answers as Desk's does: with
// the html Frappe's formatter gave for the example's rows.
function deskLikeFrappe(page) {
	const frappe = {
		pages: { "fac-pages": {} },
		ui: { make_app_page: () => ({ main: page.main, set_title: vi.fn() }), Dialog: vi.fn() },
		get_route: () => ["fac-pages", "outstanding"],
		call: vi.fn(({ callback }) => callback({ message: page.data })),
		create_shadow_element: vi.fn(),
		db: { get_list: vi.fn(async () => EXAMPLE_ROWS.map((row) => ({ ...row }))) },
		utils: { escape_html: escapeHtml },
		datetime: { get_today: () => "2026-10-29", str_to_user: vi.fn() },
		session: { user: "avery@example.com" },
		format: vi.fn((value, df, options, doc) => {
			const row = EXAMPLE_ROWS.find((r) => r.name === doc?.name);
			expect([value, df, options]).toEqual([row.outstanding_amount, EXAMPLE_DF, null]);
			return DESK_HTML[exampleTitle(row)];
		}),
	};
	return frappe;
}

const cells = (root) => [...root.querySelectorAll("#rows tr")].map((tr) => [...tr.cells].map((td) => td.textContent));

// The example opened as a Shared page in Desk: fac_pages.js, run as Desk serves it, hands the
// script to create_shadow_element, which runs it as a global script with root_element its root.
async function renderInDesk() {
	const main = { el: document.createElement("div") };
	Object.assign(main, { empty: () => main, append: (el) => main.el.append(el) });
	const page = { main, data: { title: "Outstanding", html: EXAMPLE_HTML, style: "", script: EXAMPLE, draft: false, visibility: "Shared" } };
	const frappe = deskLikeFrappe(page);
	new Function("frappe", "__", "$", facPagesSource())(frappe, (s) => s, vi.fn());
	const wrapper = {};
	frappe.pages["fac-pages"].on_page_load(wrapper);
	frappe.pages["fac-pages"].on_page_show(wrapper);
	await vi.waitFor(() => expect(frappe.create_shadow_element).toHaveBeenCalledOnce());
	const [, html, , js] = frappe.create_shadow_element.mock.calls[0];
	const root = document.createElement("div");
	root.innerHTML = html;
	new Function("ROOT", "frappe", `(function () { let root_element = ROOT; ${js} })();`)(root, frappe);
	await vi.waitFor(() => expect(cells(root)).toHaveLength(EXAMPLE_ROWS.length));
	return { root, frappe };
}

// The same page in the chat panel: the stand-in frappe, with the settings get_page serves.
async function renderInPanel() {
	const api = { getCall: vi.fn(async () => EXAMPLE_ROWS.map((row) => ({ ...row }))), baseCall: vi.fn(), user: "avery@example.com" };
	const root = document.createElement("div");
	root.innerHTML = `<div class="fac-page-root">${EXAMPLE_HTML}</div>`;
	const result = runPageScript(EXAMPLE, root, makeFrappeStandIn(api, { formatSettings: EXAMPLE_SITE }));
	expect(result).toEqual({ ok: true });
	await vi.waitFor(() => expect(cells(root)).toHaveLength(EXAMPLE_ROWS.length));
	return root;
}

describe("the pages-in-chat skill example in Desk and in the chat panel", () => {
	it("is in the skill and formats a currency with frappe.format", () => {
		expect(EXAMPLE).toContain("esc(frappe.format(");
	});

	it("shows the same plain amounts in both, with no markup", async () => {
		const desk = cells((await renderInDesk()).root);
		const panel = cells(await renderInPanel());

		expect(desk).toEqual(panel);
		expect(desk.map((row) => row[2])).toEqual(["₹ 79,360.00", "$ 12,34,567.50", "Fr 0.50"]);
		expect(desk[1][1]).toBe("Globex <Ltd>");
		expect(JSON.stringify(desk)).not.toContain("<div");
	});

	it("gave Desk's frappe.format the call the page made, and its html", async () => {
		const { frappe } = await renderInDesk();
		expect(frappe.format).toHaveBeenCalledTimes(EXAMPLE_ROWS.length);
		expect(frappe.format.mock.results[0].value).toBe("<div style='text-align: right'>₹ 79,360.00</div>");
	});
});

describe("fac_page_frappe, the frappe a Shared page gets in Desk", () => {
	const desk = () => {
		const frappe = deskLikeFrappe({ main: {}, data: {} });
		frappe.format = vi.fn(() => "<div style='text-align: right'>₹ 79,360.00</div>");
		return frappe;
	};

	it("returns the text of Desk's formatted html, from the same arguments", () => {
		const frappe = desk();
		const doc = { currency: "INR" };
		expect(fac_page_frappe(frappe).format(79360, { fieldtype: "Currency" }, { inline: 1 }, doc)).toBe("₹ 79,360.00");
		expect(frappe.format).toHaveBeenCalledWith(79360, { fieldtype: "Currency" }, { inline: 1 }, doc);
	});

	it("returns text for what Desk's format returns that is not html", () => {
		const frappe = desk();
		const page = fac_page_frappe(frappe);
		frappe.format.mockReturnValueOnce(42).mockReturnValueOnce(null).mockReturnValueOnce("A &amp; B");
		expect([page.format(42), page.format(null), page.format("A & B")]).toEqual(["42", "", "A & B"]);
	});

	it("never runs or loads what the formatted html holds", () => {
		const frappe = desk();
		frappe.format = () => '<img src="x" onerror="window.__ran = 1"><script>window.__ran = 2</script>ok';
		expect(fac_page_frappe(frappe).format("x")).toBe("window.__ran = 2ok");
		expect(window.__ran).toBeUndefined();
	});

	it("leaves every other member Desk's own", () => {
		const frappe = desk();
		const page = fac_page_frappe(frappe);
		for (const key of ["call", "db", "utils", "datetime", "session", "ui", "pages"]) expect(page[key]).toBe(frappe[key]);
		expect(page.db.get_list).toBe(frappe.db.get_list);
		expect("call" in page).toBe(true);
	});

	it("writes through to Desk's frappe, as a script that sets a member did before", () => {
		const frappe = desk();
		fac_page_frappe(frappe).page_flag = 1;
		expect(frappe.page_flag).toBe(1);
	});
});
