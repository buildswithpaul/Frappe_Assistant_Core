import { mount, flushPromises } from "@vue/test-utils";
import { describe, it, expect, vi } from "vitest";
import EmailVerificationPending from "@/components/onboarding/EmailVerificationPending.vue";

vi.mock("@/api/client", () => ({ api: { registration: {} } }));

function mountPending() {
	return mount(EmailVerificationPending, {
		props: { mode: "awaiting-click", ownerEmail: "p***@x.com" },
		global: { stubs: { FacoRobot: true } },
	});
}

async function openChangeForm(w, address = "new@x.com") {
	await w.find(".link-btn").trigger("click");
	await w.find(".change-email input").setValue(address);
	await w.find(".change-email").trigger("submit");
}

describe("EmailVerificationPending change-email form", () => {
	it("is disabled while the change is in flight, so it cannot be sent twice", async () => {
		const w = mountPending();
		await openChangeForm(w);

		expect(w.find(".change-email input").attributes("disabled")).toBeDefined();
		expect(w.find(".change-email button").attributes("disabled")).toBeDefined();

		await w.find(".change-email").trigger("submit");
		expect(w.emitted("change-email")).toHaveLength(1);
	});

	it("closes once the parent reports the change went through", async () => {
		const w = mountPending();
		await openChangeForm(w);

		const [, done] = w.emitted("change-email")[0];
		done(true);
		await flushPromises();

		expect(w.find(".change-email").exists()).toBe(false);
	});

	it("stays open with the typed address when the change failed", async () => {
		const w = mountPending();
		await openChangeForm(w, "typo@x.com");

		const [, done] = w.emitted("change-email")[0];
		done(false);
		await flushPromises();

		expect(w.find(".change-email").exists()).toBe(true);
		expect(w.find(".change-email input").element.value).toBe("typo@x.com");
		expect(w.find(".change-email input").attributes("disabled")).toBeUndefined();
	});
});

describe("EmailVerificationPending verifying a dead link", () => {
	async function mountVerifying(result) {
		const { api } = await import("@/api/client");
		api.registration.completeEmailVerification = vi.fn().mockResolvedValue(result);
		const w = mount(EmailVerificationPending, {
			props: { mode: "verifying", verificationToken: "dead-link" },
			global: { stubs: { FacoRobot: true } },
		});
		await flushPromises();
		return w;
	}

	it("offers a new link instead of retrying one that can never work", async () => {
		const w = await mountVerifying({
			success: false,
			link_expired: true,
			error: "This verification link has expired or was already used.",
		});

		expect(w.find(".error-text").text()).toContain("expired");
		const button = w.find(".retry-btn");
		expect(button.text()).toBe("Get a new link");

		await button.trigger("click");
		expect(w.emitted("start-over")).toHaveLength(1);
		expect(w.emitted("verify-failed")).toHaveLength(1);
	});

	it("keeps Try again for a failure a retry can fix", async () => {
		const w = await mountVerifying({ success: false, error: "Couldn't reach the FAC Cloud server." });

		const button = w.find(".retry-btn");
		expect(button.text()).toBe("Try again");
		await button.trigger("click");
		await flushPromises();
		expect(w.emitted("start-over")).toBeUndefined();
	});
});
