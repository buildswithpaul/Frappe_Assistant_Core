import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { mount } from "@vue/test-utils";
import { nextTick, ref, h } from "vue";
import { setActivePinia, createPinia } from "pinia";
import InputArea from "../InputArea.vue";
import { useComposerFocus, COMPOSER_FOCUSED_CLASS } from "@/composables/useComposerFocus.js";

// Redmine #34382: on an iPhone the press on Send blurred the composer, the focused phone layout
// (#34380) collapsed under the finger and the click missed, so Send took two taps. jsdom never
// moves focus on mousedown, so the guard is asserted as the cancelled default that stops it.
function pressDown(el) {
	const event = new MouseEvent("mousedown", { bubbles: true, cancelable: true });
	el.dispatchEvent(event);
	return event;
}

describe("InputArea keeps the composer focused while its buttons are pressed", () => {
	let wrapper;

	beforeEach(async () => {
		setActivePinia(createPinia());
		wrapper = mount(InputArea, { attachTo: document.body });
		await wrapper.find("textarea").setValue("hello");
		wrapper.find("textarea").element.focus();
	});

	afterEach(() => {
		wrapper.unmount();
		document.body.innerHTML = "";
	});

	it("on Send, including a press that lands on its icon", () => {
		const send = wrapper.find("button[aria-label='Send message']").element;
		expect(pressDown(send).defaultPrevented).toBe(true);
		expect(pressDown(send.querySelector("path")).defaultPrevented).toBe(true);
	});

	it("on the plus, mic and thinking buttons", () => {
		for (const selector of ["[data-composer-plus-trigger]", ".mic-btn", "[data-thinking-trigger]"]) {
			expect(pressDown(wrapper.find(selector).element).defaultPrevented, selector).toBe(true);
		}
	});

	it("on the plus menu's items", async () => {
		await wrapper.find("[data-composer-plus-trigger]").trigger("click");
		await nextTick();
		const items = wrapper.findAll(".plus-menu button");
		expect(items.length).toBeGreaterThan(0);
		for (const item of items) expect(pressDown(item.element).defaultPrevented).toBe(true);
	});

	it("but leaves presses in the text box alone, so the caret and selection still work", () => {
		expect(pressDown(wrapper.find("textarea").element).defaultPrevented).toBe(false);
	});

	it("and Send still sends on click", async () => {
		await wrapper.find("button[aria-label='Send message']").trigger("click");
		expect(wrapper.emitted("send")).toBeTruthy();
	});
});

// Once Send keeps focus, the first send from the new-chat screen removes the focused welcome
// composer (ChatView swaps it for the docked one), and a removed field fires no blur.
describe("InputArea ends the focused phone layout when it goes away focused", () => {
	afterEach(() => {
		document.body.innerHTML = "";
		document.documentElement.className = "";
	});

	it("drops the page mark when the focused composer is unmounted", async () => {
		setActivePinia(createPinia());
		const shown = ref(true);
		const wrapper = mount(
			{
				setup() {
					useComposerFocus();
					return () => (shown.value ? h(InputArea) : null);
				},
			},
			{ attachTo: document.body }
		);
		wrapper.find("textarea").element.focus();
		expect(document.documentElement.classList.contains(COMPOSER_FOCUSED_CLASS)).toBe(true);
		shown.value = false;
		await nextTick();
		expect(document.documentElement.classList.contains(COMPOSER_FOCUSED_CLASS)).toBe(false);
		wrapper.unmount();
	});
});
