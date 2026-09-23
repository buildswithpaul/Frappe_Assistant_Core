import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import ConnectionForm from "@/components/settings/connections/ConnectionForm.vue";

const mountForm = (props = {}) =>
	mount(ConnectionForm, { props: { existingNames: [], initial: null, ...props } });

describe("ConnectionForm", () => {
	it("rejects a duplicate name", async () => {
		const w = mountForm({ existingNames: ["Acme CRM"] });
		await w.find('[data-test="name"]').setValue("Acme CRM");
		await w.find('[data-test="url"]').setValue("https://x.example.com/mcp");
		await w.find("form").trigger("submit");
		expect(w.emitted("save")).toBeFalsy();
		expect(w.text()).toMatch(/already have a connection/i);
	});

	it("rejects the reserved managed name", async () => {
		const w = mountForm();
		await w.find('[data-test="name"]').setValue("Main Frappe Site");
		await w.find('[data-test="url"]').setValue("https://x.example.com/mcp");
		await w.find("form").trigger("submit");
		expect(w.emitted("save")).toBeFalsy();
	});

	it("rejects a non-https endpoint", async () => {
		const w = mountForm();
		await w.find('[data-test="name"]').setValue("Acme");
		await w.find('[data-test="url"]').setValue("ftp://x.example.com/mcp");
		await w.find("form").trigger("submit");
		expect(w.emitted("save")).toBeFalsy();
	});

	it("emits save with a valid payload", async () => {
		const w = mountForm();
		await w.find('[data-test="name"]').setValue("Acme");
		await w.find('[data-test="url"]').setValue("https://x.example.com/mcp");
		await w.find("form").trigger("submit");
		expect(w.emitted("save")[0][0]).toMatchObject({
			server_name: "Acme",
			endpoint_url: "https://x.example.com/mcp",
			auth_type: "None",
		});
	});

	it("shows the api key field only for API key auth", async () => {
		const w = mountForm();
		expect(w.find('[data-test="api-key"]').exists()).toBe(false);
		await w.find('[data-test="auth-type"]').setValue("APIKey");
		expect(w.find('[data-test="api-key"]').exists()).toBe(true);
	});
});
