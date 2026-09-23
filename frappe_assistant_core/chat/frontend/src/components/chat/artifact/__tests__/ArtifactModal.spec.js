import { mount, flushPromises } from "@vue/test-utils";
import { describe, it, expect, vi, beforeEach } from "vitest";
import ArtifactModal from "@/components/chat/artifact/ArtifactModal.vue";

function makeCapture() {
	const node = document.createElement("div");
	node.className = "captured";
	node.textContent = "ART";
	const cleanup = vi.fn();
	return { capture: () => ({ node, cleanup }), cleanup, node };
}

describe("ArtifactModal", () => {
	beforeEach(() => {
		document.body.style.overflow = "";
	});

	it("mounts the captured node into the viewport via appendChild", async () => {
		const { capture, node } = makeCapture();
		const w = mount(ArtifactModal, {
			props: { capture, toPng: async () => "data:image/png;base64,X", title: "d" },
			attachTo: document.body,
		});
		await flushPromises();
		const viewport = document.querySelector('[data-test="viewport-content"]');
		expect(viewport.contains(node)).toBe(true);
		w.unmount();
	});

	it("locks body scroll while open and restores on unmount", async () => {
		const { capture } = makeCapture();
		const w = mount(ArtifactModal, {
			props: { capture, toPng: async () => "x", title: "d" },
			attachTo: document.body,
		});
		await flushPromises();
		expect(document.body.style.overflow).toBe("hidden");
		w.unmount();
		expect(document.body.style.overflow).toBe("");
	});

	it("calls cleanup on unmount", async () => {
		const { capture, cleanup } = makeCapture();
		const w = mount(ArtifactModal, {
			props: { capture, toPng: async () => "x", title: "d" },
			attachTo: document.body,
		});
		await flushPromises();
		w.unmount();
		expect(cleanup).toHaveBeenCalledTimes(1);
	});

	it("emits close on backdrop click and Escape", async () => {
		const { capture } = makeCapture();
		const w = mount(ArtifactModal, {
			props: { capture, toPng: async () => "x", title: "d" },
			attachTo: document.body,
		});
		await flushPromises();
		document.querySelector('[data-test="backdrop"]').click();
		expect(w.emitted("close")).toBeTruthy();
		w.unmount();
	});

	it("download invokes toPng and triggers an anchor download", async () => {
		const { capture } = makeCapture();
		const toPng = vi.fn(async () => "data:image/png;base64,ABC");
		const clickSpy = vi.fn();
		const realCreate = document.createElement.bind(document);
		vi.spyOn(document, "createElement").mockImplementation((tag) => {
			const el = realCreate(tag);
			if (tag === "a") el.click = clickSpy;
			return el;
		});
		const w = mount(ArtifactModal, {
			props: { capture, toPng, title: "myflow" },
			attachTo: document.body,
		});
		await flushPromises();
		await document.querySelector('[data-test="download-btn"]').click();
		await flushPromises();
		expect(toPng).toHaveBeenCalled();
		expect(clickSpy).toHaveBeenCalled();
		vi.restoreAllMocks();
		w.unmount();
	});

	it("download swallows a rejected toPng without creating an anchor", async () => {
		const { capture } = makeCapture();
		const toPng = vi.fn(async () => {
			throw new Error("export boom");
		});
		const clickSpy = vi.fn();
		const realCreate = document.createElement.bind(document);
		vi.spyOn(document, "createElement").mockImplementation((tag) => {
			const el = realCreate(tag);
			if (tag === "a") el.click = clickSpy;
			return el;
		});
		const errSpy = vi.spyOn(console, "error").mockImplementation(() => {});
		const w = mount(ArtifactModal, {
			props: { capture, toPng, title: "myflow" },
			attachTo: document.body,
		});
		await flushPromises();
		await document.querySelector('[data-test="download-btn"]').click();
		await flushPromises();
		expect(toPng).toHaveBeenCalled();
		expect(clickSpy).not.toHaveBeenCalled();
		expect(errSpy).toHaveBeenCalled();
		vi.restoreAllMocks();
		w.unmount();
	});
});
