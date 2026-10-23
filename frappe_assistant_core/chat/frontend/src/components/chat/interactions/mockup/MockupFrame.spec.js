import { mount } from "@vue/test-utils";
import { afterEach, describe, it, expect, vi } from "vitest";

import MockupFrame from "@/components/chat/interactions/mockup/MockupFrame.vue";

const CSP_META = `<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:">`;

let wrapper;

function mountFrame(props = {}) {
	wrapper = mount(MockupFrame, {
		props: { html: '<div class="mk-card">Hello</div>', title: "Mockup", ...props },
		attachTo: document.body,
	});
	return wrapper;
}

function postHeight(source, height) {
	window.dispatchEvent(new MessageEvent("message", { data: { type: "mk-height", height }, source }));
}

afterEach(() => wrapper?.unmount());

describe("MockupFrame", () => {
	it("sandboxes the frame with scripts only", () => {
		const iframe = mountFrame().find("iframe");
		expect(iframe.attributes("sandbox")).toBe("allow-scripts");
		expect(iframe.attributes("title")).toBe("Mockup");
	});

	it("puts the CSP first, then the kit CSS, then the given HTML", () => {
		const srcdoc = mountFrame().find("iframe").attributes("srcdoc");
		const csp = srcdoc.indexOf(CSP_META);
		const kit = srcdoc.indexOf("--mk-radius");
		const user = srcdoc.indexOf('<div class="mk-card">Hello</div>');
		expect(csp).toBeGreaterThan(-1);
		expect(csp).toBeLessThan(kit);
		expect(kit).toBeLessThan(user);
		expect(srcdoc.indexOf("<body>")).toBeLessThan(user);
		expect(srcdoc.indexOf("<body>")).toBeGreaterThan(csp);
	});

	it("shows a plain message instead of a frame over 200 KB", () => {
		const w = mountFrame({ html: "a".repeat(204801) });
		expect(w.find("iframe").exists()).toBe(false);
		expect(w.text()).toBe("Mockup too large to show");
	});

	it("counts bytes, not characters, against the cap", () => {
		// 3-byte characters: 70000 chars is 210000 bytes
		expect(mountFrame({ html: "€".repeat(70000) }).find("iframe").exists()).toBe(false);
	});

	it("keeps a mockup of exactly 200 KB", () => {
		expect(mountFrame({ html: "a".repeat(204800) }).find("iframe").exists()).toBe(true);
	});

	it("takes the height the frame reports, clamped", async () => {
		const w = mountFrame();
		const win = w.find("iframe").element.contentWindow;
		postHeight(win, 400.2);
		await w.vm.$nextTick();
		expect(w.find("iframe").element.style.height).toBe("401px");
		postHeight(win, 999999);
		await w.vm.$nextTick();
		expect(w.find("iframe").element.style.height).toBe("1200px");
	});

	it("ignores height messages from any other window", async () => {
		const w = mountFrame();
		const before = w.find("iframe").element.style.height;
		postHeight(window, 700);
		await w.vm.$nextTick();
		expect(w.find("iframe").element.style.height).toBe(before);
	});

	it("stops listening once unmounted", () => {
		const add = vi.spyOn(window, "addEventListener");
		const remove = vi.spyOn(window, "removeEventListener");
		const w = mountFrame();
		const handler = add.mock.calls.find(([type]) => type === "message")[1];
		w.unmount();
		expect(remove).toHaveBeenCalledWith("message", handler);
		vi.restoreAllMocks();
	});
});
