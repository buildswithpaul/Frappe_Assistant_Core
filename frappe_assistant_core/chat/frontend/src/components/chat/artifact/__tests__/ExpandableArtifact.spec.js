import { mount } from "@vue/test-utils";
import { describe, it, expect, vi } from "vitest";
import ExpandableArtifact from "@/components/chat/artifact/ExpandableArtifact.vue";

const ModalStub = {
	name: "ArtifactModal",
	props: ["capture", "toPng", "title"],
	template: `<div class="modal-stub" />`,
};

function mountWrapper(props = {}) {
	return mount(ExpandableArtifact, {
		props: {
			capture: () => ({ node: document.createElement("div"), cleanup: () => {} }),
			canCapture: () => true,
			toPng: async () => "data:image/png;base64,X",
			title: "diagram",
			disabled: false,
			...props,
		},
		slots: { default: '<div class="art">ARTIFACT</div>' },
		global: { stubs: { ArtifactModal: ModalStub } },
	});
}

describe("ExpandableArtifact", () => {
	it("renders the slotted artifact", () => {
		const w = mountWrapper();
		expect(w.find(".art").exists()).toBe(true);
		expect(w.text()).toContain("ARTIFACT");
	});

	it("shows the expand button by default", () => {
		const w = mountWrapper();
		expect(w.find('[data-test="expand-btn"]').exists()).toBe(true);
	});

	it("hides the expand button when disabled", () => {
		const w = mountWrapper({ disabled: true });
		expect(w.find('[data-test="expand-btn"]').exists()).toBe(false);
	});

	it("hides the expand button when canCapture returns false", () => {
		const w = mountWrapper({ canCapture: () => false });
		expect(w.find('[data-test="expand-btn"]').exists()).toBe(false);
	});

	it("does not call capture() for visibility (only canCapture)", () => {
		const capture = vi.fn(() => ({ node: document.createElement("div"), cleanup: () => {} }));
		mountWrapper({ capture, canCapture: () => true });
		expect(capture).not.toHaveBeenCalled();
	});

	it("opens the modal on expand click and forwards title", async () => {
		const w = mountWrapper();
		expect(w.findComponent(ModalStub).exists()).toBe(false);
		await w.find('[data-test="expand-btn"]').trigger("click");
		const modal = w.findComponent(ModalStub);
		expect(modal.exists()).toBe(true);
		expect(modal.props("title")).toBe("diagram");
	});
});
