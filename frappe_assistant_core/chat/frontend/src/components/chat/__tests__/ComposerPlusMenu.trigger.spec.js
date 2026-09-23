/**
 * The ⊕ menu driven the way a user drives it: a real DOM click on the real
 * toolbar button, with the button and the menu in the same relationship
 * InputArea gives them (siblings — the trigger is NOT inside the menu).
 *
 * The original specs forced `open` through a prop and never touched the
 * trigger, which is exactly how a menu that could not be opened at all shipped.
 *
 * One caveat worth knowing when reading these: jsdom dispatches an entire event
 * on a single JS stack, so Vue never flushes mid-dispatch the way a browser
 * does between listener invocations. The visible browser symptom (menu appears
 * and vanishes inside one click) therefore cannot be reproduced here directly —
 * it shows up instead as the emit in "never treated as a click outside".
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { mount } from "@vue/test-utils";
import { defineComponent, ref } from "vue";
import ComposerPlusMenu from "../ComposerPlusMenu.vue";
import InputToolbar from "../InputToolbar.vue";

const TRIGGER = 'button[aria-label="Attach or toggle composer modes"]';

function makeHarness(initiallyOpen, onAttach) {
	return defineComponent({
		components: { ComposerPlusMenu, InputToolbar },
		setup() {
			const plusOpen = ref(initiallyOpen);
			return { plusOpen, onAttach };
		},
		template: `
			<div>
				<ComposerPlusMenu
					:open="plusOpen"
					:web-search-available="true"
					@attach="onAttach"
					@close="plusOpen = false"
				/>
				<InputToolbar
					:plus-open="plusOpen"
					:web-search-available="true"
					@toggle-plus="plusOpen = !plusOpen"
				/>
				<div class="elsewhere">elsewhere</div>
			</div>`,
	});
}

function mountHarness({ open = false, onAttach = () => {} } = {}) {
	return mount(makeHarness(open, onAttach), {
		attachTo: document.body,
		global: { stubs: { MicButton: true } },
	});
}

describe("ComposerPlusMenu — opening it", () => {
	beforeEach(() => {
		document.body.innerHTML = "";
	});

	it("opens on a real click of the toolbar trigger", async () => {
		const wrapper = mountHarness();

		await wrapper.find(TRIGGER).trigger("click");

		expect(wrapper.find(".plus-menu").exists()).toBe(true);
		wrapper.unmount();
	});

	it("never treats the trigger's own click as a click outside", async () => {
		// The regression. The trigger lives outside the menu, so its click
		// reaches the document listener; in a browser the DOM has already
		// flushed by then and the opening click read as "outside" and closed
		// the menu again. The trigger owns the toggle in both directions, so
		// this handler must ignore it entirely.
		const wrapper = mountHarness({ open: true });

		await wrapper.find(TRIGGER).trigger("click");

		expect(wrapper.findComponent(ComposerPlusMenu).emitted("close")).toBeFalsy();
		// ...and the trigger's own toggle still closed it.
		expect(wrapper.find(".plus-menu").exists()).toBe(false);
		wrapper.unmount();
	});

	it("closes on a click anywhere else", async () => {
		const wrapper = mountHarness({ open: true });

		await wrapper.find(".elsewhere").trigger("click");

		expect(wrapper.find(".plus-menu").exists()).toBe(false);
		wrapper.unmount();
	});

	it("closes on Escape", async () => {
		const wrapper = mountHarness({ open: true });

		document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
		await wrapper.vm.$nextTick();

		expect(wrapper.find(".plus-menu").exists()).toBe(false);
		wrapper.unmount();
	});

	it("stays open when a click lands inside the menu", async () => {
		const wrapper = mountHarness({ open: true });

		await wrapper.find(".menu-thinking").trigger("click");

		expect(wrapper.find(".plus-menu").exists()).toBe(true);
		wrapper.unmount();
	});

	it("runs Attach inside the click, so the file dialog keeps its user gesture", () => {
		// Deferring to nextTick would lose the gesture and the browser would
		// reject the programmatic .click() on the hidden file input.
		const onAttach = vi.fn();
		const wrapper = mountHarness({ open: true, onAttach });

		wrapper.find(".menu-attach").element.click();

		expect(onAttach).toHaveBeenCalledTimes(1); // no await — same tick
		wrapper.unmount();
	});
});
