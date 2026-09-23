import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";
import ConnectionsSettings from "@/components/settings/ConnectionsSettings.vue";
import ConnectionForm from "@/components/settings/connections/ConnectionForm.vue";
import ToolVisibilityModal from "@/components/settings/connections/ToolVisibilityModal.vue";

vi.mock("@/api/client", () => ({
	default: {
		connections: {
			list: vi.fn(),
			add: vi.fn().mockResolvedValue({ success: true }),
			remove: vi.fn().mockResolvedValue({ success: true }),
			setEnabled: vi.fn().mockResolvedValue({ success: true }),
			test: vi.fn().mockResolvedValue({ success: true, tools: ["a"], tool_count: 1 }),
			setToolVisibility: vi.fn().mockResolvedValue({ success: true }),
		},
		tools: {
			listPreferences: vi.fn().mockResolvedValue({ preferences: {} }),
			setPreference: vi.fn().mockResolvedValue({ success: true }),
		},
	},
}));

// ConnectionsSettings now reads the ?connect= deep link on mount (Part 4 task
// 10 wires ConnectWizard in), so it needs a router even in tests that never
// touch that path.
vi.mock("vue-router", () => ({
	useRoute: () => ({ query: {} }),
	useRouter: () => ({ replace: vi.fn() }),
}));

import api from "@/api/client";

const rows = [
	{ server_name: "Main Frappe Site", managed: true, status: "Active" },
	{ server_name: "Acme CRM", managed: false, status: "Active", auth_type: "APIKey" },
];

describe("ConnectionsSettings", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		vi.clearAllMocks();
	});

	it("loads connections on mount", async () => {
		api.connections.list.mockResolvedValue({ connections: rows, ar_unreachable: false });
		const w = mount(ConnectionsSettings);
		await flushPromises();
		expect(api.connections.list).toHaveBeenCalled();
		expect(w.findAll('[data-test="connection-card"]')).toHaveLength(2);
	});

	it("distinguishes AR unreachable from having no connections", async () => {
		api.connections.list.mockResolvedValue({ connections: [], ar_unreachable: true });
		const w = mount(ConnectionsSettings);
		await flushPromises();
		expect(w.text()).toMatch(/couldn't reach|unavailable/i);
		expect(w.text()).not.toMatch(/no connections yet/i);
	});

	it("shows an empty state when there are genuinely none", async () => {
		api.connections.list.mockResolvedValue({ connections: [], ar_unreachable: false });
		const w = mount(ConnectionsSettings);
		await flushPromises();
		expect(w.text()).toMatch(/nothing connected yet/i);
	});

	it("reloads after a successful removal, once confirmed", async () => {
		api.connections.list.mockResolvedValue({ connections: rows, ar_unreachable: false });
		const w = mount(ConnectionsSettings);
		await flushPromises();

		const cards = w.findAll('[data-test="connection-card"]');
		await cards[1].find('[data-test="remove"]').trigger("click");
		await flushPromises();

		// ConfirmModal Teleports to document.body, so it isn't inside `w`'s own
		// mounted subtree — query the real DOM directly, matching this codebase's
		// established convention for every other Teleported modal's tests.
		expect(api.connections.remove).not.toHaveBeenCalled();
		const confirmButton = document.querySelector(".btn-primary");
		expect(confirmButton).toBeTruthy();
		confirmButton.click();
		await flushPromises();

		expect(api.connections.remove).toHaveBeenCalledWith("Acme CRM");
		expect(api.connections.list).toHaveBeenCalledTimes(2);
	});

	// Regression test for CONTROLLER NOTE requirement 1: ConnectionForm has no
	// self-exclusion for the connection being edited, so the caller must strip
	// it from existingNames or every no-rename edit falsely reads as a dupe.
	it("excludes the connection being edited from existingNames", async () => {
		api.connections.list.mockResolvedValue({ connections: rows, ar_unreachable: false });
		const w = mount(ConnectionsSettings);
		await flushPromises();
		await w
			.findAll('[data-test="connection-card"]')[1]
			.find('[data-test="edit"]')
			.trigger("click");
		await flushPromises();

		const form = w.findComponent(ConnectionForm);
		expect(form.exists()).toBe(true);
		expect(form.props("existingNames")).not.toContain("Acme CRM");
	});

	// Regression test for CONTROLLER NOTE requirements 2 & 3: ToolVisibilityModal
	// seeds its checkbox state once at mount with no watch on props, so opening
	// it for a second, different server must produce a fresh mount rather than
	// prop-updating a stale instance.
	it("reflects the newly opened server's tools, not a stale server's", async () => {
		api.connections.list.mockResolvedValue({ connections: rows, ar_unreachable: false });
		api.connections.test.mockResolvedValueOnce({
			success: true,
			tools: ["alpha", "beta"],
			tool_count: 2,
		});
		const w = mount(ConnectionsSettings);
		await flushPromises();

		await w
			.findAll('[data-test="connection-card"]')[0]
			.find('[data-test="tools"]')
			.trigger("click");
		await flushPromises();
		let modal = w.findComponent(ToolVisibilityModal);
		expect(modal.exists()).toBe(true);
		expect(modal.props("tools")).toEqual(["alpha", "beta"]);

		await modal.vm.$emit("close");
		await flushPromises();
		expect(w.findComponent(ToolVisibilityModal).exists()).toBe(false);

		api.connections.test.mockResolvedValueOnce({
			success: true,
			tools: ["gamma"],
			tool_count: 1,
		});
		await w
			.findAll('[data-test="connection-card"]')[1]
			.find('[data-test="tools"]')
			.trigger("click");
		await flushPromises();
		modal = w.findComponent(ToolVisibilityModal);
		expect(modal.exists()).toBe(true);
		expect(modal.props("tools")).toEqual(["gamma"]);
		expect(modal.props("tools")).not.toContain("alpha");
	});

	it("seeds the tools modal from the connection's real blocked_tools, not always empty", async () => {
		const rowsWithBlocked = [
			{ server_name: "Main Frappe Site", managed: true, status: "Active", blocked_tools: [] },
			{
				server_name: "Acme CRM",
				managed: false,
				status: "Active",
				blocked_tools: ["delete_record"],
			},
		];
		api.connections.list.mockResolvedValue({ connections: rowsWithBlocked, ar_unreachable: false });
		api.connections.test.mockResolvedValueOnce({
			success: true,
			tools: ["delete_record", "send_email"],
			tool_count: 2,
		});
		const w = mount(ConnectionsSettings);
		await flushPromises();

		await w
			.findAll('[data-test="connection-card"]')[1]
			.find('[data-test="tools"]')
			.trigger("click");
		await flushPromises();

		const modal = w.findComponent(ToolVisibilityModal);
		expect(modal.exists()).toBe(true);
		expect(modal.props("blocked")).toEqual(["delete_record"]);
	});

	it("reloads after saving tool visibility, so a same-session reopen reflects the new state", async () => {
		const initialRows = [
			{ server_name: "Main Frappe Site", managed: true, status: "Active", blocked_tools: [] },
			{ server_name: "Acme CRM", managed: false, status: "Active", blocked_tools: [] },
		];
		const updatedRows = [
			{ server_name: "Main Frappe Site", managed: true, status: "Active", blocked_tools: [] },
			{
				server_name: "Acme CRM",
				managed: false,
				status: "Active",
				blocked_tools: ["delete_record"],
			},
		];
		api.connections.list
			.mockResolvedValueOnce({ connections: initialRows, ar_unreachable: false })
			.mockResolvedValueOnce({ connections: updatedRows, ar_unreachable: false });
		api.connections.test.mockResolvedValue({
			success: true,
			tools: ["delete_record", "send_email"],
			tool_count: 2,
		});

		const w = mount(ConnectionsSettings);
		await flushPromises();

		await w
			.findAll('[data-test="connection-card"]')[1]
			.find('[data-test="tools"]')
			.trigger("click");
		await flushPromises();

		let modal = w.findComponent(ToolVisibilityModal);
		modal.vm.$emit("save", { server_name: "Acme CRM", blocked_tools: ["delete_record"] });
		await flushPromises();

		expect(api.connections.setToolVisibility).toHaveBeenCalledWith("Acme CRM", [
			"delete_record",
		]);
		expect(api.connections.list).toHaveBeenCalledTimes(2);

		await w
			.findAll('[data-test="connection-card"]')[1]
			.find('[data-test="tools"]')
			.trigger("click");
		await flushPromises();

		modal = w.findComponent(ToolVisibilityModal);
		expect(modal.props("blocked")).toEqual(["delete_record"]);
	});

	it("saves approval preferences alongside visibility", async () => {
		// Visibility and approval are two different stores in AR — what the
		// model is shown, and what happens when it calls. One picker writes
		// both, so a save that only reached one of them is a half-applied rule.
		api.connections.list.mockResolvedValue({ connections: rows, ar_unreachable: false });
		const w = mount(ConnectionsSettings);
		await flushPromises();

		await w
			.findAll('[data-test="connection-card"]')[0]
			.find('[data-test="tools"]')
			.trigger("click");
		await flushPromises();

		w.findComponent(ToolVisibilityModal).vm.$emit("save", {
			server_name: "Main Frappe Site",
			blocked_tools: ["drop_table"],
			preferences: [{ tool_name: "search", preference: "always_allow" }],
		});
		await flushPromises();

		expect(api.connections.setToolVisibility).toHaveBeenCalledWith("Main Frappe Site", [
			"drop_table",
		]);
		expect(api.tools.setPreference).toHaveBeenCalledWith("search", "always_allow");
	});

	it("hands the picker the slug and managed flag it needs to name a tool", async () => {
		// A non-managed server's tools reach the model prefixed with its slug,
		// and preferences are stored under that name. Without the slug the
		// picker would look up — and write — the wrong key.
		api.connections.list.mockResolvedValue({
			connections: [
				{ server_name: "Acme CRM", managed: false, status: "Active", slug: "acme" },
			],
			ar_unreachable: false,
		});
		api.connections.test.mockResolvedValueOnce({
			success: true,
			tools: ["search"],
			tool_details: [{ name: "search", description: "Find", read_only: true }],
			tool_count: 1,
		});
		const w = mount(ConnectionsSettings);
		await flushPromises();

		await w.find('[data-test="connection-card"]').find('[data-test="tools"]').trigger("click");
		await flushPromises();

		const modal = w.findComponent(ToolVisibilityModal);
		expect(modal.props("slug")).toBe("acme");
		expect(modal.props("managed")).toBe(false);
		expect(modal.props("toolDetails")).toEqual([
			{ name: "search", description: "Find", read_only: true },
		]);
	});

	it("still opens the picker when the preferences call fails", async () => {
		api.connections.list.mockResolvedValue({ connections: rows, ar_unreachable: false });
		api.tools.listPreferences.mockRejectedValueOnce(new Error("AR unreachable"));
		const w = mount(ConnectionsSettings);
		await flushPromises();

		await w
			.findAll('[data-test="connection-card"]')[0]
			.find('[data-test="tools"]')
			.trigger("click");
		await flushPromises();

		expect(w.findComponent(ToolVisibilityModal).exists()).toBe(true);
	});
});
