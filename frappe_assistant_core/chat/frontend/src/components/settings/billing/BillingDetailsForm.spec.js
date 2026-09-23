import { beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";

const getBillingDetails = vi.fn();
const saveBillingDetails = vi.fn();

vi.mock("@/api/client", () => ({
	api: {
		billing: {
			getBillingDetails: (...a) => getBillingDetails(...a),
			saveBillingDetails: (...a) => saveBillingDetails(...a),
		},
	},
}));

vi.mock("@/utils/logger", () => ({ logger: { warn: vi.fn(), error: vi.fn() } }));

import BillingDetailsForm from "./BillingDetailsForm.vue";

const SAVED = {
	billing_legal_name: "Promantia Business Solutions Pvt. Ltd.",
	billing_email: "hari.madhavan@promantia.com",
	billing_phone: "+919900000000",
	billing_country: "India",
	gstin: "",
	billing_state: "Karnataka",
	billing_city: "Bengaluru",
	billing_pincode: "560017",
	billing_address_line1: "Tower C, 4th Floor, Golden Enclave",
	billing_address_line2: "Old Airport Road",
};

async function mountForm(details = SAVED) {
	getBillingDetails.mockResolvedValue(details);
	const w = mount(BillingDetailsForm);
	await flushPromises();
	return w;
}

describe("BillingDetailsForm", () => {
	beforeEach(() => {
		getBillingDetails.mockReset();
		saveBillingDetails.mockReset();
		saveBillingDetails.mockResolvedValue({ ok: true });
	});

	it("renders the saved legal name so it is not silently re-typed", async () => {
		const w = await mountForm();
		expect(w.find("#bd-legal-name").element.value).toBe(
			"Promantia Business Solutions Pvt. Ltd."
		);
	});

	it("round-trips address line 2, which the API used to discard", async () => {
		const w = await mountForm();
		expect(w.find("#bd-line2").element.value).toBe("Old Airport Road");

		await w.find("form").trigger("submit");
		await flushPromises();

		expect(saveBillingDetails).toHaveBeenCalledWith(
			expect.objectContaining({ billing_address_line2: "Old Airport Road" })
		);
	});

	it("sends the legal name on save", async () => {
		const w = await mountForm();

		await w.find("form").trigger("submit");
		await flushPromises();

		expect(saveBillingDetails).toHaveBeenCalledWith(
			expect.objectContaining({
				billing_legal_name: "Promantia Business Solutions Pvt. Ltd.",
			})
		);
	});

	it("refuses to save without a legal name and says why", async () => {
		const w = await mountForm({ ...SAVED, billing_legal_name: "" });

		await w.find("form").trigger("submit");
		await flushPromises();

		expect(saveBillingDetails).not.toHaveBeenCalled();
		expect(w.text()).toMatch(/business or legal name/i);
	});

	it("renders the country and state dropdowns with real options", async () => {
		// Both lists moved into a shared module; a stale identifier renders an
		// empty <select> that every other assertion here would still pass.
		const w = await mountForm();
		expect(w.findAll("#bd-country option").length).toBeGreaterThan(1);
		const states = w.findAll("#bd-state option").map((o) => o.text());
		expect(states).toContain("Karnataka");
		expect(states).toContain("Lakshadweep Islands");
	});

	it("marks a blank city on its own input instead of a banner", async () => {
		// City is `reqd` on the Address doctype. Left to the server it came
		// back as `MandatoryError: [Address, <name>]: city` — true, and useless
		// to the person who has to fix it.
		const w = await mountForm({ ...SAVED, billing_city: "" });

		await w.find("form").trigger("submit");
		await flushPromises();

		expect(saveBillingDetails).not.toHaveBeenCalled();
		expect(w.find("#bd-city").classes()).toContain("input-error");
		expect(w.text()).toMatch(/city or town/i);
	});

	it("attaches a server rejection to the field the server names", async () => {
		const w = await mountForm();
		const err = new Error("Postal code 110001 is not in Karnataka.");
		Object.defineProperty(err, "field", { value: "billing_pincode" });
		saveBillingDetails.mockRejectedValueOnce(err);

		await w.find("form").trigger("submit");
		await flushPromises();

		expect(w.find("#bd-pincode").classes()).toContain("input-error");
		expect(w.text()).toContain("Postal code 110001 is not in Karnataka.");
	});

	it("keeps an unattributed server error at form level", async () => {
		const w = await mountForm();
		saveBillingDetails.mockRejectedValueOnce(new Error("Service unavailable"));

		await w.find("form").trigger("submit");
		await flushPromises();

		expect(w.text()).toContain("Service unavailable");
		expect(w.find("#bd-pincode").classes()).not.toContain("input-error");
	});

	it("clears a field error as soon as the user edits that field", async () => {
		const w = await mountForm({ ...SAVED, billing_city: "" });
		await w.find("form").trigger("submit");
		await flushPromises();
		expect(w.find("#bd-city").classes()).toContain("input-error");

		await w.find("#bd-city").setValue("Bengaluru");
		await flushPromises();

		expect(w.find("#bd-city").classes()).not.toContain("input-error");
	});
});
