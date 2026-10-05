import { describe, it, expect, vi, afterEach } from "vitest";
import { mount } from "@vue/test-utils";
import SpotlightModal from "./SpotlightModal.vue";

const content = {
	kind: "announcement", id: "n1", eyebrow: "New", title: "Agents", body: "Build **agents**",
	highlights: ["One", "Two"], media: { url: "https://x/a.gif", type: "image", alt: "Demo" },
	primary: { label: "Try it", route: "/agents" }, secondary: { label: "Not now" },
};

function mountModal(props = {}) {
	return mount(SpotlightModal, { props: { content, ...props }, attachTo: document.body, global: { stubs: { teleport: true } } });
}

describe("SpotlightModal", () => {
	afterEach(() => vi.unstubAllGlobals());

	it("renders eyebrow, title, markdown body, highlights and both buttons", () => {
		const w = mountModal();
		expect(w.text()).toContain("New");
		expect(w.find("h2").text()).toBe("Agents");
		expect(w.html()).toContain("<strong>agents</strong>");
		expect(w.findAll("[data-test='spotlight-highlight']")).toHaveLength(2);
		expect(w.find("[data-test='spotlight-primary']").text()).toBe("Try it");
		expect(w.find("[data-test='spotlight-secondary']").text()).toBe("Not now");
		w.unmount();
	});

	it("renders nothing without content", () => {
		const w = mountModal({ content: null });
		expect(w.find("[role='dialog']").exists()).toBe(false);
	});

	it("emits primary, secondary and dismiss", async () => {
		const w = mountModal();
		await w.find("[data-test='spotlight-primary']").trigger("click");
		await w.find("[data-test='spotlight-secondary']").trigger("click");
		await w.find("[aria-label='Close']").trigger("click");
		expect(w.emitted("primary")).toHaveLength(1);
		expect(w.emitted("secondary")).toHaveLength(1);
		expect(w.emitted("dismiss")).toHaveLength(1);
		w.unmount();
	});

	it("backdrop and Escape defer instead of dismissing", async () => {
		const w = mountModal();
		await w.find("[data-test='spotlight-overlay']").trigger("click");
		await w.find("[role='dialog']").trigger("keydown", { key: "Escape" });
		expect(w.emitted("close")).toHaveLength(2);
		expect(w.emitted("dismiss")).toBeUndefined();
		w.unmount();
	});

	it("single-column card when there is no media", () => {
		const w = mountModal({ content: { ...content, media: null } });
		expect(w.find("[data-test='spotlight-card']").classes()).toContain("is-text-only");
		w.unmount();
	});

	it("collapses to text-only when the media fails to load", async () => {
		const w = mountModal();
		await w.find("img").trigger("error");
		expect(w.find("[data-test='spotlight-card']").classes()).toContain("is-text-only");
		w.unmount();
	});

	it("video respects reduced motion", () => {
		vi.stubGlobal("matchMedia", vi.fn().mockImplementation((q) => ({ matches: q.includes("reduce"), addEventListener() {}, removeEventListener() {} })));
		const w = mountModal({ content: { ...content, media: { url: "https://x/a.mp4", type: "video", alt: "Demo" } } });
		const video = w.find("video");
		expect(video.attributes("autoplay")).toBeUndefined();
		expect(video.attributes("controls")).toBeDefined();
		w.unmount();
	});

	it("renders quota art for art:'quota' media and focuses the primary button", async () => {
		const w = mountModal({ content: { ...content, media: { art: "quota" }, threshold: 100 } });
		expect(w.find(".spot-art").exists()).toBe(true);
		expect(w.find("img").exists()).toBe(false);
		await new Promise((r) => setTimeout(r, 0));
		expect(document.activeElement).toBe(w.find("[data-test='spotlight-primary']").element);
		w.unmount();
	});

	it("traps Tab between the last and first focusable elements", async () => {
		const w = mountModal({ content: { ...content, media: null } });
		const close = w.find("[aria-label='Close']").element;
		const primary = w.find("[data-test='spotlight-primary']").element;
		close.focus();
		await w.find("[role='dialog']").trigger("keydown", { key: "Tab" });
		expect(document.activeElement).toBe(primary);
		await w.find("[role='dialog']").trigger("keydown", { key: "Tab", shiftKey: true });
		expect(document.activeElement).toBe(close);
		w.unmount();
	});

	it("defers on Escape when focus is on the card itself", async () => {
		const w = mountModal();
		const card = w.find("[role='dialog']");
		expect(card.attributes("tabindex")).toBe("-1");
		card.element.focus();
		await card.trigger("keydown", { key: "Escape" });
		expect(w.emitted("close")).toHaveLength(1);
		expect(w.emitted("dismiss")).toBeUndefined();
		w.unmount();
	});

	it("restores focus to the opener when closed", async () => {
		const opener = document.createElement("button");
		document.body.appendChild(opener);
		opener.focus();
		const w = mountModal();
		await new Promise((r) => setTimeout(r, 0));
		expect(document.activeElement).not.toBe(opener);
		await w.setProps({ content: null });
		expect(document.activeElement).toBe(opener);
		w.unmount();
		opener.remove();
	});
});
