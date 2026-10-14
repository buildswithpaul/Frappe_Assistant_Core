import { describe, it, expect, beforeAll, vi } from "vitest";
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

	it("opening another row's menu closes this one", async () => {
		const mk = (id) =>
			mount(ChatRow, {
				props: { session: { ...session, session_id: id }, active: false, projects },
				attachTo: document.body,
			});
		const a = mk("a");
		const b = mk("b");
		await a.find("[data-test=row-menu]").trigger("click");
		expect(a.find("[data-test=menu-rename]").exists()).toBe(true);
		await b.find("[data-test=row-menu]").trigger("click");
		expect(a.find("[data-test=menu-rename]").exists()).toBe(false);
		expect(b.find("[data-test=menu-rename]").exists()).toBe(true);
		a.unmount();
		b.unmount();
	});

	it("an archive confirm closes when another row is clicked", async () => {
		const mk = (id) =>
			mount(ChatRow, {
				props: { session: { ...session, session_id: id }, active: false, projects },
				attachTo: document.body,
			});
		const a = mk("a");
		const b = mk("b");
		await a.find("[data-test=row-menu]").trigger("click");
		await a.find("[data-test=menu-archive]").trigger("click");
		expect(a.find("[data-test=confirm-archive]").exists()).toBe(true);
		await b.find("[data-test=row-menu]").trigger("click");
		expect(a.find("[data-test=confirm-archive]").exists()).toBe(false);
		a.unmount();
		b.unmount();
	});

	it("Escape then the unmount blur does not save the discarded draft", async () => {
		const w = mountRow();
		await w.find("[data-test=row-menu]").trigger("click");
		await w.find("[data-test=menu-rename]").trigger("click");
		const input = w.find("[data-test=rename-input]");
		await input.setValue("discard");
		input.element.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
		input.element.dispatchEvent(new FocusEvent("blur"));
		expect(w.emitted("rename")).toBeFalsy();
	});

	it("Escape inside the rename input does not reach window listeners", async () => {
		const w = mount(ChatRow, {
			props: { session, active: false, projects },
			attachTo: document.body,
			global: { mocks: { __: (s) => s } },
		});
		await w.find("[data-test=row-menu]").trigger("click");
		await w.find("[data-test=menu-rename]").trigger("click");
		const seen = vi.fn();
		window.addEventListener("keydown", seen);
		await w.find("[data-test=rename-input]").trigger("keydown", { key: "Escape" });
		window.removeEventListener("keydown", seen);
		w.unmount();
		expect(seen).not.toHaveBeenCalled();
	});

	it("Enter then the unmount blur saves exactly once", async () => {
		const w = mountRow();
		await w.find("[data-test=row-menu]").trigger("click");
		await w.find("[data-test=menu-rename]").trigger("click");
		const input = w.find("[data-test=rename-input]");
		await input.setValue("Kept");
		input.element.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
		input.element.dispatchEvent(new FocusEvent("blur"));
		expect(w.emitted("rename")).toEqual([["Kept"]]);
	});

	it("allowNewProject=false hides New project", async () => {
		const w = mount(ChatRow, {
			props: { session, active: false, projects, allowNewProject: false },
			global: { mocks: { __: (s) => s } },
		});
		await w.find("[data-test=row-menu]").trigger("click");
		await w.find("[data-test=menu-move]").trigger("click");
		expect(w.find("[data-test=move-new]").exists()).toBe(false);
	});

	it("shows a dot titled with the project name for a project chat", () => {
		const w = mount(ChatRow, {
			props: { session: { ...session, project_title: "Q3 Close" }, projects },
			global: { mocks: { __: (s) => s } },
		});
		const dot = w.find('[data-test="project-dot"]');
		expect(dot.exists()).toBe(true);
		expect(dot.attributes("title")).toBe("Q3 Close");
		expect(dot.attributes("aria-label")).toBe("Q3 Close");
	});

	it("shows no dot for a chat outside a project", () => {
		const w = mount(ChatRow, {
			props: { session: { ...session, project: null, project_title: null }, projects },
			global: { mocks: { __: (s) => s } },
		});
		expect(w.find('[data-test="project-dot"]').exists()).toBe(false);
	});

	it("showProject=false hides the dot", () => {
		const w = mount(ChatRow, {
			props: { session: { ...session, project_title: "Q3 Close" }, projects, showProject: false },
			global: { mocks: { __: (s) => s } },
		});
		expect(w.find('[data-test="project-dot"]').exists()).toBe(false);
	});

	it("keeps the time out of the visible row and puts it in the title tooltip", () => {
		const w = mount(ChatRow, {
			props: { session: { ...session, last_activity: "2026-06-15 09:00:00" }, projects },
			global: { mocks: { __: (s) => s } },
		});
		expect(w.find(".conversation-time").exists()).toBe(false);
		expect(w.find('[data-test="chat-row"]').attributes("title")).toMatch(/^Overdue invoices · .+/);
	});

	it("showTime renders the time under the title", () => {
		const w = mount(ChatRow, {
			props: { session: { ...session, last_activity: "2026-06-15 09:00:00" }, projects, showTime: true },
			global: { mocks: { __: (s) => s } },
		});
		expect(w.find(".conversation-time").exists()).toBe(true);
	});
});
