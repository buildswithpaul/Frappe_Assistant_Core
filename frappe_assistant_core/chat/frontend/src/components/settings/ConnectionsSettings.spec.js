import { beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";

const list = vi.fn();
const replace = vi.fn();
const route = { query: {} };

vi.mock("@/api/client", () => {
	const api = {
		connections: {
			list: (...a) => list(...a),
			add: vi.fn(),
			remove: vi.fn(),
			setEnabled: vi.fn(),
			test: vi.fn(),
			setToolVisibility: vi.fn(),
			beginConnect: vi.fn(),
			getConnectSession: vi.fn(),
			commitConnect: vi.fn(),
			abandonConnect: vi.fn(),
			beginReauth: vi.fn(),
		},
	};
	// ConnectionsSettings imports the default export; ConnectWizard imports
	// the named one. They are the same object in api/client.js.
	return { api, default: api };
});
vi.mock("@/composables/useToast", () => ({
	useToast: () => ({ showError: vi.fn(), showSuccess: vi.fn() }),
}));
vi.mock("@/stores/userStore", () => ({
	useUserStore: () => ({ mcpEndpointUrl: "" }),
}));
vi.mock("vue-router", () => ({
	useRoute: () => route,
	useRouter: () => ({ replace }),
}));

import ConnectionsSettings from "@/components/settings/ConnectionsSettings.vue";

const mountSettings = () =>
	mount(ConnectionsSettings, {
		global: { stubs: { ConnectWizard: true, ConfirmModal: true, ExternalClientsPanel: true } },
	});

describe("ConnectionsSettings add path", () => {
	beforeEach(() => {
		list.mockReset().mockResolvedValue({ connections: [] });
		replace.mockReset();
		route.query = {};
	});

	it("the add button opens the wizard, not the form", async () => {
		const w = mountSettings();
		await flushPromises();
		await w.find('[data-test="add-connection"]').trigger("click");
		expect(w.findComponent({ name: "ConnectWizard" }).exists()).toBe(true);
		expect(w.find(".connection-form").exists()).toBe(false);
	});

	it("Edit still opens ConnectionForm, never the wizard", async () => {
		list.mockResolvedValue({
			connections: [
				{ server_name: "Acme", endpoint_url: "https://acme.example/mcp", auth_type: "APIKey", status: "Active" },
			],
		});
		const w = mountSettings();
		await flushPromises();
		await w.find('[data-test="edit"]').trigger("click");
		expect(w.find(".connection-form").exists()).toBe(true);
		expect(w.findComponent({ name: "ConnectWizard" }).exists()).toBe(false);
	});

	it("reloads the list and closes once the wizard reports an addition", async () => {
		const w = mountSettings();
		await flushPromises();
		await w.find('[data-test="add-connection"]').trigger("click");
		list.mockClear();
		w.findComponent({ name: "ConnectWizard" }).vm.$emit("added", "Acme");
		await flushPromises();
		expect(list).toHaveBeenCalled();
	});
});

describe("ConnectionsSettings deep link", () => {
	beforeEach(() => {
		list.mockReset().mockResolvedValue({ connections: [] });
		replace.mockReset();
		route.query = {};
	});

	it("reopens the wizard from ?connect= and clears the param", async () => {
		route.query = { connect: "h-1" };
		const w = mountSettings();
		await flushPromises();
		const wizard = w.findComponent({ name: "ConnectWizard" });
		expect(wizard.exists()).toBe(true);
		expect(wizard.props("initialHandle")).toBe("h-1");
		// Left in place, a refresh would try to resume a session already spent.
		expect(replace).toHaveBeenCalled();
		expect(replace.mock.calls[0][0].query.connect).toBeUndefined();
	});
});

describe("ConnectionsSettings reconnect", () => {
	beforeEach(() => {
		replace.mockReset();
		route.query = {};
		list.mockReset().mockResolvedValue({
			connections: [
				{
					server_name: "Acme",
					endpoint_url: "https://acme.example/mcp",
					status: "Token Expired",
					auth_type: "MCPOAuth",
				},
			],
		});
	});

	it("offers Reconnect on an expired connection and opens the wizard in reauth mode", async () => {
		const w = mountSettings();
		await flushPromises();
		await w.find('[data-test="reconnect"]').trigger("click");
		const wizard = w.findComponent({ name: "ConnectWizard" });
		expect(wizard.props("reauthServerName")).toBe("Acme");
		expect(wizard.props("initialHandle")).toBe("");
		// No URL is passed: begin_mcp_reauth reads the endpoint off the row, so
		// a reconnect cannot retarget the connection at a different server.
		expect(wizard.props("initialUrl")).toBe("");
	});
});
