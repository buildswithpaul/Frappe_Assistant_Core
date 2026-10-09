import { describe, it, expect, vi, afterEach } from "vitest";
import { mount } from "@vue/test-utils";
import { nextTick } from "vue";
import PromptExpandModal from "@/components/workflows/config/PromptExpandModal.vue";
import OutputFullscreen from "@/components/workflows/runs/OutputFullscreen.vue";
import { useBuilderShortcuts } from "@/composables/useBuilderShortcuts";

/**
 * The builder listens for Escape on `window` to close the node config panel. A
 * modal opened from that panel closes on the same key, and the key must not
 * reach the builder or the panel underneath closes with it. Production reaches
 * this whenever either modal is opened from a selected node.
 */
describe.each([
	["PromptExpandModal", PromptExpandModal, { text: "t", modelValue: "p" }],
	["OutputFullscreen", OutputFullscreen, { text: "output" }],
])("%s Escape", (_name, component, props) => {
	let wrapper;
	let shortcuts;
	afterEach(() => {
		wrapper?.unmount();
		shortcuts?.unmount();
	});

	it("closes the modal without reaching the builder's Escape handler", async () => {
		const onEscape = vi.fn();
		const Host = {
			template: "<div />",
			setup() {
				useBuilderShortcuts({ onEscape });
			},
		};
		shortcuts = mount(Host);
		wrapper = mount(component, { props: { open: false, ...props }, attachTo: document.body });
		await wrapper.setProps({ open: true });
		await nextTick();

		document.body.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));

		expect(wrapper.emitted("update:open")?.[0]).toEqual([false]);
		expect(onEscape).not.toHaveBeenCalled();
	});
});
