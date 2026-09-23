import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import ConnectionCard from "@/components/settings/connections/ConnectionCard.vue";

const managed = { server_name: "Main Frappe Site", status: "Active", managed: true };
const personal = {
	server_name: "Acme CRM",
	status: "Active",
	managed: false,
	// auth_type is required on the doctype; a hand-entered connection is the
	// only kind the edit form can serve.
	auth_type: "APIKey",
};

describe("ConnectionCard", () => {
	it("hides remove and edit on a managed connection", () => {
		const w = mount(ConnectionCard, { props: { connection: managed } });
		expect(w.find('[data-test="remove"]').exists()).toBe(false);
		expect(w.find('[data-test="edit"]').exists()).toBe(false);
	});

	it("labels a managed connection as always on", () => {
		const w = mount(ConnectionCard, { props: { connection: managed } });
		expect(w.text()).toContain("Always on");
	});

	it("offers remove and edit on a personal connection", () => {
		const w = mount(ConnectionCard, { props: { connection: personal } });
		expect(w.find('[data-test="remove"]').exists()).toBe(true);
		expect(w.find('[data-test="edit"]').exists()).toBe(true);
	});

	it("emits remove with the server name", async () => {
		const w = mount(ConnectionCard, { props: { connection: personal } });
		await w.find('[data-test="remove"]').trigger("click");
		expect(w.emitted("remove")[0]).toEqual(["Acme CRM"]);
	});

	it("shows the error message when the connection is broken", () => {
		const w = mount(ConnectionCard, {
			props: { connection: { ...personal, status: "Error", error_message: "unreachable" } },
		});
		expect(w.text()).toContain("unreachable");
	});
});
