import { describe, it, expect, afterEach } from "vitest";
import { mount } from "@vue/test-utils";
import NodePalette from "./NodePalette.vue";
import { getDefaultLabel } from "./graphUtils";

afterEach(() => {
	delete window.__;
});

describe("NodePalette translation", () => {
	it("translates labels and descriptions at render time", () => {
		// Frappe installs window.__ after module load; production reaches this state the same way.
		window.__ = (text) => `T:${text}`;
		const w = mount(NodePalette);
		expect(w.text()).toContain("T:For each");
		expect(w.text()).toContain("T:Call one tool directly, no AI, no credits");
	});

	it("translates the default label of a new node", () => {
		window.__ = (text) => `T:${text}`;
		expect(getDefaultLabel("tool")).toBe("T:Tool");
		expect(getDefaultLabel("loop")).toBe("T:For each");
	});
});
