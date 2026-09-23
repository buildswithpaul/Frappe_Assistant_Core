import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import ToolVisibilityModal from "@/components/settings/connections/ToolVisibilityModal.vue";

const DETAILS = [
	{ name: "search", description: "Find documents", read_only: true },
	{ name: "send", description: "Send a message", read_only: false },
	{ name: "delete", description: "Delete a document", read_only: false },
];

const props = {
	serverName: "Acme",
	toolDetails: DETAILS,
	blocked: ["delete"],
	managed: true,
};

const mountModal = (overrides = {}) =>
	mount(ToolVisibilityModal, { props: { ...props, ...overrides } });

const choiceOf = (row) =>
	["always", "ask", "blocked"].find((v) =>
		row.find(`[data-test="choice-${v}"]`).classes().includes("is-selected")
	);

describe("ToolVisibilityModal", () => {
	it("renders one row per tool", () => {
		expect(mountModal().findAll('[data-test="tool-row"]')).toHaveLength(3);
	});

	it("separates tools that only read from tools that change things", () => {
		const text = mountModal().text();
		expect(text).toMatch(/reads only/i);
		expect(text).toMatch(/can make changes/i);
	});

	it("starts a blocked tool on blocked", () => {
		const rows = mountModal().findAll('[data-test="tool-row"]');
		const deleteRow = rows.find((r) => r.text().includes("delete"));
		expect(choiceOf(deleteRow)).toBe("blocked");
	});

	it("auto-allows a read-only tool on the managed connection, matching what AR does", () => {
		const rows = mountModal().findAll('[data-test="tool-row"]');
		const searchRow = rows.find((r) => r.text().includes("search"));
		expect(choiceOf(searchRow)).toBe("always");
	});

	it("auto-allows a read-only tool on a bring-your-own server too", () => {
		// Stopping to ask before every lookup is friction with no decision
		// behind it. AR seeds these preferences when the connection is made;
		// this default is what the picker shows for older connections.
		const rows = mountModal({ managed: false, slug: "acme" }).findAll(
			'[data-test="tool-row"]'
		);
		const searchRow = rows.find((r) => r.text().includes("search"));
		expect(choiceOf(searchRow)).toBe("always");
	});

	it("still asks for anything that can make changes", () => {
		const rows = mountModal({ managed: false, slug: "acme" }).findAll(
			'[data-test="tool-row"]'
		);
		const sendRow = rows.find((r) => r.text().includes("send"));
		expect(choiceOf(sendRow)).toBe("ask");
	});

	it("honours a stored preference over the default", () => {
		const rows = mountModal({
			preferences: { send: "always_allow" },
		}).findAll('[data-test="tool-row"]');
		const sendRow = rows.find((r) => r.text().includes("send"));
		expect(choiceOf(sendRow)).toBe("always");
	});

	it("keys stored preferences by the prefixed name the model sees", () => {
		const rows = mountModal({
			managed: false,
			slug: "acme",
			preferences: { acme_send: "always_allow" },
		}).findAll('[data-test="tool-row"]');
		const sendRow = rows.find((r) => r.text().includes("send"));
		expect(choiceOf(sendRow)).toBe("always");
	});

	it("emits the blocked list, not the allowed list", async () => {
		const w = mountModal();
		const rows = w.findAll('[data-test="tool-row"]');
		const sendRow = rows.find((r) => r.text().includes("send"));
		await sendRow.find('[data-test="choice-blocked"]').trigger("click");
		await w.find('[data-test="save"]').trigger("click");
		expect(w.emitted("save")[0][0].blocked_tools.sort()).toEqual(["delete", "send"]);
	});

	it("emits only the preferences that changed", async () => {
		const w = mountModal();
		const rows = w.findAll('[data-test="tool-row"]');
		const sendRow = rows.find((r) => r.text().includes("send"));
		await sendRow.find('[data-test="choice-always"]').trigger("click");
		await w.find('[data-test="save"]').trigger("click");
		expect(w.emitted("save")[0][0].preferences).toEqual([
			{ tool_name: "send", preference: "always_allow" },
		]);
	});

	it("writes no preference for a tool it is blocking", async () => {
		const w = mountModal();
		const rows = w.findAll('[data-test="tool-row"]');
		const searchRow = rows.find((r) => r.text().includes("search"));
		await searchRow.find('[data-test="choice-blocked"]').trigger("click");
		await w.find('[data-test="save"]').trigger("click");
		const emitted = w.emitted("save")[0][0];
		expect(emitted.blocked_tools).toContain("search");
		expect(emitted.preferences.map((p) => p.tool_name)).not.toContain("search");
	});

	it("sets a whole group at once", async () => {
		const w = mountModal();
		await w.find('[data-test="bulk-write"]').trigger("click");
		await w.find('[data-test="save"]').trigger("click");
		// "delete" started blocked; asking for the whole write group unblocks it.
		expect(w.emitted("save")[0][0].blocked_tools).toEqual([]);
	});

	it("says plainly that read-only tools run without asking, and whose word that is", () => {
		expect(mountModal({ managed: false, slug: "acme" }).text()).toMatch(
			/server’s own description/i
		);
		expect(mountModal().text()).not.toMatch(/server’s own description/i);
	});

	it("falls back to a plain name list when no details are supplied", () => {
		const w = mount(ToolVisibilityModal, {
			props: { serverName: "Acme", tools: ["a", "b"], blocked: [] },
		});
		expect(w.findAll('[data-test="tool-row"]')).toHaveLength(2);
	});

	it("shows an empty state when the server exposes no tools", () => {
		const w = mount(ToolVisibilityModal, {
			props: { serverName: "Acme", tools: [], toolDetails: [] },
		});
		expect(w.text()).toMatch(/no tools/i);
	});
});
