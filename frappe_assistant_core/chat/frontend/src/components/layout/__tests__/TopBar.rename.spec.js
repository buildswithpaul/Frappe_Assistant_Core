import { describe, it, expect, beforeAll, vi } from "vitest";
import { mount } from "@vue/test-utils";
import { createPinia } from "pinia";
import TopBar from "@/components/layout/TopBar.vue";

beforeAll(() => {
	window.__ = (s) => s;
});

vi.mock("@/composables/useNavToggle", () => ({ useNavToggle: () => ({ onHamburger: (f) => f() }) }));

const mountBar = (props = {}) =>
	mount(TopBar, {
		props: { title: "Overdue invoices", showActions: false, ...props },
		attachTo: document.body,
		global: {
			plugins: [createPinia()],
			stubs: { RouterLink: { template: "<a><slot/></a>" } },
		},
	});

describe("TopBar rename and breadcrumb", () => {
	it("shows the project crumb", () => {
		const w = mountBar({ project: { name: "p1", title: "Q3 Close" }, renamable: true });
		expect(w.find("[data-test=crumb-project]").text()).toContain("Q3 Close");
	});

	it("has no crumb without a project", () => {
		expect(mountBar().find("[data-test=crumb-project]").exists()).toBe(false);
	});

	it("Enter emits the whitespace-collapsed title", async () => {
		const w = mountBar({ renamable: true });
		await w.find("[data-test=chat-title]").trigger("click");
		const input = w.find("[data-test=title-input]");
		await input.setValue("  New   name ");
		await input.trigger("keydown", { key: "Enter" });
		expect(w.emitted("rename")[0]).toEqual(["New name"]);
	});

	it("not renamable: click opens no input", async () => {
		const w = mountBar({ renamable: false });
		await w.find("[data-test=chat-title]").trigger("click");
		expect(w.find("[data-test=title-input]").exists()).toBe(false);
	});

	it("Escape discards even though the unmounting input blurs", async () => {
		const w = mountBar({ renamable: true });
		await w.find("[data-test=chat-title]").trigger("click");
		const input = w.find("[data-test=title-input]");
		await input.setValue("discard");
		// Synchronous: the blur fired by removing the input must not commit.
		input.trigger("keydown", { key: "Escape" });
		input.trigger("blur");
		await w.vm.$nextTick();
		expect(w.emitted("rename")).toBeUndefined();
	});

	it("Escape inside the editor does not reach window listeners", async () => {
		const w = mountBar({ renamable: true });
		await w.find("[data-test=chat-title]").trigger("click");
		const seen = vi.fn();
		window.addEventListener("keydown", seen);
		await w.find("[data-test=title-input]").trigger("keydown", { key: "Escape" });
		window.removeEventListener("keydown", seen);
		expect(seen).not.toHaveBeenCalled();
	});
});
