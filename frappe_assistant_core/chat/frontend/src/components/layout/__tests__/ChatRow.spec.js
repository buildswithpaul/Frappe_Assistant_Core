import { describe, it, expect, beforeAll } from "vitest";
import { mount } from "@vue/test-utils";
import ChatRow from "@/components/layout/ChatRow.vue";

beforeAll(() => {
	window.__ = (s) => s;
});

const session = { session_id: "a", title: "Overdue invoices", preview: "Overdue invoices", project: "p1" };
const projects = [
	{ name: "p1", title: "Q3 Close" },
	{ name: "p2", title: "Onboarding" },
];
const mountRow = () =>
	mount(ChatRow, { props: { session, active: false, projects }, global: { mocks: { __: (s) => s } } });

describe("ChatRow", () => {
	it("emits select on click", async () => {
		const w = mountRow();
		await w.find("[data-test=chat-row]").trigger("click");
		expect(w.emitted("select")).toBeTruthy();
	});

	it("Enter saves the trimmed title, Esc cancels", async () => {
		const w = mountRow();
		await w.find("[data-test=row-menu]").trigger("click");
		await w.find("[data-test=menu-rename]").trigger("click");
		const input = w.find("[data-test=rename-input]");
		await input.setValue("  New name ");
		await input.trigger("keydown", { key: "Enter" });
		expect(w.emitted("rename")[0]).toEqual(["New name"]);

		await w.find("[data-test=row-menu]").trigger("click");
		await w.find("[data-test=menu-rename]").trigger("click");
		await w.find("[data-test=rename-input]").setValue("discard");
		await w.find("[data-test=rename-input]").trigger("keydown", { key: "Escape" });
		expect(w.emitted("rename")).toHaveLength(1);
	});

	it("blank rename is emitted as empty so the server restores the auto title", async () => {
		const w = mountRow();
		await w.find("[data-test=row-menu]").trigger("click");
		await w.find("[data-test=menu-rename]").trigger("click");
		await w.find("[data-test=rename-input]").setValue("   ");
		await w.find("[data-test=rename-input]").trigger("keydown", { key: "Enter" });
		expect(w.emitted("rename")[0]).toEqual([""]);
	});

	it("move menu lists projects, marks the current one, and can remove", async () => {
		const w = mountRow();
		await w.find("[data-test=row-menu]").trigger("click");
		await w.find("[data-test=menu-move]").trigger("click");
		expect(w.find("[data-test=move-p1]").text()).toContain("✓");
		await w.find("[data-test=move-p2]").trigger("click");
		expect(w.emitted("move")[0]).toEqual(["p2"]);
		await w.find("[data-test=row-menu]").trigger("click");
		await w.find("[data-test=menu-move]").trigger("click");
		await w.find("[data-test=move-none]").trigger("click");
		expect(w.emitted("move")[1]).toEqual([null]);
	});

	it("archive asks for confirmation first", async () => {
		const w = mountRow();
		await w.find("[data-test=row-menu]").trigger("click");
		await w.find("[data-test=menu-archive]").trigger("click");
		expect(w.emitted("archive")).toBeFalsy();
		await w.find("[data-test=confirm-archive]").trigger("click");
		expect(w.emitted("archive")).toBeTruthy();
	});
});
