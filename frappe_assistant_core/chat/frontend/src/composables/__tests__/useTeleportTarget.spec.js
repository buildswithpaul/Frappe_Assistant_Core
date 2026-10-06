import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import { defineComponent, h } from "vue";
import { TELEPORT_TARGET_KEY, useTeleportTarget } from "@/composables/useTeleportTarget";

const Probe = defineComponent({
	setup() {
		const target = useTeleportTarget();
		return () => h("span", typeof target === "string" ? target : target.id);
	},
});

describe("useTeleportTarget", () => {
	it("is body in FAC Chat", () => {
		expect(mount(Probe).text()).toBe("body");
	});

	it("is the provided shadow overlay in the widget", () => {
		const overlay = document.createElement("div");
		overlay.id = "fac-overlay";
		const wrapper = mount(Probe, { global: { provide: { [TELEPORT_TARGET_KEY]: overlay } } });
		expect(wrapper.text()).toBe("fac-overlay");
	});
});
