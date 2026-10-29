import { EXAMPLE_SITE } from "@/utils/__tests__/pageFormatCases";

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
});
