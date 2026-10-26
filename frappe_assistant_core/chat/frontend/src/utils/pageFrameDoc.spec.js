import { describe, expect, it } from "vitest";

import { PAGE_FRAME_SANDBOX, makeNonce, pageFrameCsp, pageFrameSrcdoc } from "./pageFrameDoc";

const ORIGIN = "https://erp.example.com";
const NONCE = "abc123";

const parts = (extra = {}) => ({
	html: '<div class="mk-card">Sales</div>',
	style: ".mk-card { color: teal; }",
	script: "root_element.textContent = 'ran';",
	kitCss: ".mk-kit { }",
	user: "avery@example.com",
	origin: ORIGIN,
	nonce: NONCE,
	...extra,
});

// The inner frame's document, as the browser reads it out of the outer frame's srcdoc attribute.
function innerDoc(outer) {
	const doc = new DOMParser().parseFromString(outer, "text/html");
	return { outer: doc, inner: new DOMParser().parseFromString(doc.querySelector("iframe").getAttribute("srcdoc"), "text/html") };
}

describe("pageFrameDoc", () => {
	it("gives both frames scripts and nothing else: no same origin, forms, popups or navigation", () => {
		expect(PAGE_FRAME_SANDBOX).toBe("allow-scripts");
		const { outer } = innerDoc(pageFrameSrcdoc(parts()));
		expect(outer.querySelector("iframe").getAttribute("sandbox")).toBe("allow-scripts");
	});

	it("lets the page reach no server itself, and stops it navigating its frame away", () => {
		const csp = pageFrameCsp(ORIGIN, NONCE);
		expect(csp).toContain("default-src 'none'");
		expect(csp).toContain("connect-src 'none'");
		// The outer frame's policy is what blocks the inner frame navigating with data in the URL.
		expect(csp).toContain("frame-src 'none'");
		expect(csp).toContain("form-action 'none'");
		expect(csp).toContain(`script-src 'nonce-${NONCE}' ${ORIGIN}/assets/frappe_assistant_core/js/`);
		expect(csp).not.toContain("unsafe-eval");
		expect(csp).not.toMatch(/script-src[^;]*unsafe-inline/);
	});

	it("puts the policy first in both frames' documents", () => {
		const { outer, inner } = innerDoc(pageFrameSrcdoc(parts()));
		for (const doc of [outer, inner]) {
			const first = doc.head.firstElementChild;
			expect(first.getAttribute("http-equiv")).toBe("Content-Security-Policy");
			expect(first.getAttribute("content")).toBe(pageFrameCsp(ORIGIN, NONCE));
		}
	});

	it("loads the runtime, then runs the script with this render's nonce, with no click", () => {
		const { inner } = innerDoc(pageFrameSrcdoc(parts()));
		const scripts = [...inner.querySelectorAll("script:not([type])")];
		expect(scripts[0].getAttribute("src")).toBe(`${ORIGIN}/assets/frappe_assistant_core/js/fac_page_frame.js?v=`);
		const run = scripts.at(-1);
		expect(run.getAttribute("nonce")).toBe(NONCE);
		expect(run.textContent).toContain("root_element.textContent = 'ran';");
		expect(scripts.every((s) => s.getAttribute("nonce") === NONCE)).toBe(true);
		expect(inner.querySelector(".fac-page-root > .mk-card").textContent).toBe("Sales");
	});

	it("loads the chart bundle only for a script that names fac", () => {
		const charts = (script) =>
			[...innerDoc(pageFrameSrcdoc(parts({ script }))).inner.querySelectorAll("script[src]")].some((s) =>
				s.getAttribute("src").includes("fac_page_charts.js"),
			);
		expect(charts("fac.chart(root_element, {})")).toBe(true);
		expect(charts("root_element.textContent = 'x';")).toBe(false);
	});

	it("keeps a script or style that closes its own tag inside its element", () => {
		const script = "const s = '</script><img src=x onerror=alert(1)>';";
		const style = "</style><script>alert(2)</script>";
		const { inner } = innerDoc(pageFrameSrcdoc(parts({ script, style })));
		expect(inner.querySelector("img")).toBeNull();
		expect([...inner.querySelectorAll("script:not([src]):not([type])")]).toHaveLength(1);
	});

	it("passes the user as JSON no tag can close", () => {
		const { inner } = innerDoc(pageFrameSrcdoc(parts({ user: "</script><b>x" })));
		expect(JSON.parse(inner.getElementById("fac-page-config").textContent)).toEqual({ user: "</script><b>x" });
		expect(inner.querySelector("b")).toBeNull();
	});

	it("makes a fresh nonce each render", () => {
		expect(makeNonce()).toMatch(/^[0-9a-f]{32}$/);
		expect(makeNonce()).not.toBe(makeNonce());
	});
});
