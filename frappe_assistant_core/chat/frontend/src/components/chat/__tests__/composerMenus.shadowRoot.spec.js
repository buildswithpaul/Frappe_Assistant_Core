/**
 * The composer menus as the Desk widget renders them: inside a shadow root.
 *
 * Their click-outside listener sits on `document`, and a click from inside a
 * shadow root reaches `document` with `event.target` retargeted to the shadow
 * host. Reading the target made every click — on the ⊕ trigger, on Attach —
 * look like a click outside, so the menu closed on the gesture that opened it.
 */
import { describe, it, expect, beforeEach } from "vitest";
import { mount } from "@vue/test-utils";
import { defineComponent, nextTick, ref } from "vue";
import ComposerPlusMenu from "../ComposerPlusMenu.vue";
import ThinkingLevelMenu from "../ThinkingLevelMenu.vue";
import InputToolbar from "../InputToolbar.vue";

const PLUS_TRIGGER = 'button[aria-label="Attach or toggle composer modes"]';

const PlusHarness = defineComponent({
	components: { ComposerPlusMenu, InputToolbar },
	setup: () => ({ plusOpen: ref(true) }),
	template: `
		<div>
			<ComposerPlusMenu :open="plusOpen" :web-search-available="true" @close="plusOpen = false" />
			<InputToolbar :plus-open="plusOpen" :web-search-available="true" @toggle-plus="plusOpen = !plusOpen" />
			<div class="elsewhere">elsewhere</div>
		</div>`,
});

/**
 * A click as a user makes one. test-utils' trigger() dispatches a non-composed event, which
 * stops at the shadow root, so the document listener under test would never see it.
 */
async function userClick(wrapper) {
	wrapper.element.dispatchEvent(new MouseEvent("click", { bubbles: true, composed: true }));
	await nextTick();
}

/** Mount into a shadow root, as widget/panel/main.js does. */
function mountInShadow(component, options = {}) {
	const host = document.createElement("div");
	document.body.appendChild(host);
	const mountEl = document.createElement("div");
	host.attachShadow({ mode: "open" }).appendChild(mountEl);
	return mount(component, { attachTo: mountEl, global: { stubs: { MicButton: true } }, ...options });
}

describe("composer menus inside a shadow root", () => {
	beforeEach(() => {
		document.body.innerHTML = "";
	});

	it("the ⊕ trigger's own click is not a click outside", async () => {
		const wrapper = mountInShadow(PlusHarness);

		await userClick(wrapper.find(PLUS_TRIGGER));

		expect(wrapper.findComponent(ComposerPlusMenu).emitted("close")).toBeFalsy();
		wrapper.unmount();
	});

	it("a click inside the ⊕ menu keeps it open", async () => {
		const wrapper = mountInShadow(PlusHarness);

		await userClick(wrapper.find(".menu-thinking"));

		expect(wrapper.find(".plus-menu").exists()).toBe(true);
		wrapper.unmount();
	});

	it("a click elsewhere in the shadow root still closes the ⊕ menu", async () => {
		const wrapper = mountInShadow(PlusHarness);

		await userClick(wrapper.find(".elsewhere"));

		expect(wrapper.find(".plus-menu").exists()).toBe(false);
		wrapper.unmount();
	});

	it("a click inside the thinking menu keeps it open", async () => {
		const wrapper = mountInShadow(ThinkingLevelMenu, {
			props: { open: true, levels: ["off", "high"], selected: "off", hintFor: () => null },
		});

		await userClick(wrapper.find(".thinking-menu"));

		expect(wrapper.emitted("close")).toBeFalsy();
		wrapper.unmount();
	});
});
