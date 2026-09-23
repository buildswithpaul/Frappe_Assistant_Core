import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import ConnectionCard from "./ConnectionCard.vue";

const card = (connection) => mount(ConnectionCard, { props: { connection } });

const ACME = {
	server_name: "Acme",
	endpoint_url: "https://acme.example/mcp",
	auth_type: "MCPOAuth",
	status: "Active",
};

describe("ConnectionCard status", () => {
	it("marks an active connection active", () => {
		const w = card(ACME);
		expect(w.find('[data-test="status"]').classes()).toContain("is-active");
	});

	it("marks an errored connection errored", () => {
		const w = card({ ...ACME, status: "Error" });
		expect(w.find('[data-test="status"]').classes()).toContain("is-error");
	});

	it("gives Token Expired its own badge, not the neutral one", () => {
		// AR sets this status when a refresh fails. Under is-neutral it reads
		// as "switched off" rather than "this needs you", which is the opposite
		// of what it means.
		const w = card({ ...ACME, status: "Token Expired" });
		const classes = w.find('[data-test="status"]').classes();
		expect(classes).toContain("is-token-expired");
		expect(classes).not.toContain("is-neutral");
	});

	it("leaves Inactive on the neutral badge", () => {
		const w = card({ ...ACME, status: "Inactive" });
		expect(w.find('[data-test="status"]').classes()).toContain("is-neutral");
	});
});

describe("ConnectionCard reconnect action", () => {
	it("offers Reconnect only when the token expired", () => {
		expect(card(ACME).find('[data-test="reconnect"]').exists()).toBe(false);
		expect(
			card({ ...ACME, status: "Token Expired" }).find('[data-test="reconnect"]').exists()
		).toBe(true);
	});

	it("emits reconnect with the server name", async () => {
		const w = card({ ...ACME, status: "Token Expired" });
		await w.find('[data-test="reconnect"]').trigger("click");
		expect(w.emitted("reconnect")[0]).toEqual(["Acme"]);
	});

	it("never offers Reconnect on the managed connection", () => {
		// The managed row keeps its Frappe-specific OAuth path and refreshes
		// itself, so a reconnect would offer a fix to a problem it cannot have.
		const w = card({
			server_name: "Main Frappe Site",
			status: "Token Expired",
			managed: true,
		});
		expect(w.find('[data-test="reconnect"]').exists()).toBe(false);
	});
});

describe("ConnectionCard edit affordance", () => {
	// The edit form asks for an endpoint and an authentication type. A
	// wizard-built connection discovered both, its auth_type is not one of the
	// form's options (so the field renders blank), and its tokens belong to the
	// endpoint that issued them — the form can only offer to break it.
	it("offers Edit for a hand-entered connection", () => {
		expect(card({ ...ACME, auth_type: "APIKey" }).find('[data-test="edit"]').exists()).toBe(true);
		expect(card({ ...ACME, auth_type: "None" }).find('[data-test="edit"]').exists()).toBe(true);
	});

	it("withholds Edit from a connection the wizard built", () => {
		expect(card({ ...ACME, auth_type: "MCPOAuth" }).find('[data-test="edit"]').exists()).toBe(
			false
		);
	});

	it("still offers Tools and Test on a wizard-built connection", () => {
		const w = card({ ...ACME, auth_type: "MCPOAuth" });
		expect(w.find('[data-test="tools"]').exists()).toBe(true);
		expect(w.find('[data-test="test"]').exists()).toBe(true);
	});
});
