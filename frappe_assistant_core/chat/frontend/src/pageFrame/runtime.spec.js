import { EXAMPLE_SITE } from "@/utils/__tests__/pageFormatCases";
import { makeBlocks } from "@/utils/pageBlocks";
import { report } from "@/utils/pageReport";

// The frame's config, as pageFrameDoc.js writes it from get_page's response.
beforeAll(async () => {
	const config = document.createElement("script");
	config.type = "application/json";
	config.id = "fac-page-config";
	config.textContent = JSON.stringify({ user: "avery@example.com", format_settings: EXAMPLE_SITE });
	document.head.append(config);
	document.body.innerHTML = '<div class="fac-page-root"></div>';
	// jsdom has no ResizeObserver; the runtime only reports the page's height with it.
	globalThis.ResizeObserver = class {
		observe() {}
	};
	await import("./runtime");
});

describe("the personal page frame's runtime", () => {
	it("gives the page a frappe.format with the site's settings from its config", () => {
		let frappe;
		window.__fac_page.run((root_element, pageFrappe) => (frappe = pageFrappe));
		expect(frappe.format(79360, { fieldtype: "Currency" })).toBe("₹ 79,360.00");
		expect(frappe.session.user).toBe("avery@example.com");
	});

	it("gives the page fac.report, which asks the host which reports the viewer may run", async () => {
		// The frame loads the bundle that sets window.fac_page_charts before the page runs.
		window.fac_page_charts = { report };
		const posted = vi.spyOn(window, "postMessage");
		let fac;
		window.__fac_page.run((root_element, pageFrappe, translate, pageFac) => (fac = pageFac));
		fac.report("Profit and Loss Statement", { company: "C" });
		await Promise.resolve();
		const call = posted.mock.calls.map(([message]) => message).find((message) => message.op === "call");
		expect(call).toMatchObject({
			method: "frappe_assistant_core.api.fac_page.report_access",
			args: { reports: ["Profit and Loss Statement"] },
		});
		posted.mockRestore();
	});

	it("gives the page fac.canWrite, which asks the host about the viewer's permission", async () => {
		window.fac_page_charts = { report, makeBlocks };
		const posted = vi.spyOn(window, "postMessage");
		let fac;
		window.__fac_page.run((root_element, pageFrappe, translate, pageFac) => (fac = pageFac));
		fac.canWrite("ToDo", "T-1");
		await Promise.resolve();
		const call = posted.mock.calls.map(([message]) => message).find((message) => message.op === "call");
		expect(call).toMatchObject({ method: "frappe.client.has_permission", args: { doctype: "ToDo", docname: "T-1", perm_type: "write" } });
		posted.mockRestore();
	});
});
