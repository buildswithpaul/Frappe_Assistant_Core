import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import WidgetSetupGate from "./WidgetSetupGate.vue";

/**
 * The widget and the SPA answer the same question — "may this person finish
 * their own setup?" — and they used to answer it differently. The SPA asks
 * whether you hold a seat (`isAdmin || isPendingMember`); the widget asked
 * whether you hold the System Manager role. An invited member without that
 * role was told "your administrator hasn't added you to FACO yet" by the
 * widget, with no button, while the very same click through the Desk
 * notification opened the SPA's working "Connect your account" screen.
 *
 * The gate is only reached when `can_use` is true, and `can_use` IS the
 * membership check — so by the time we render the per-user screens the person
 * is a seated member by construction. Site registration is the one step here
 * that genuinely belongs to an admin.
 */

const base = { status: "ready", isAdmin: false, userSetupComplete: true, privacyConsentComplete: true };
const render = (props) => mount(WidgetSetupGate, { props: { ...base, ...props } });

describe("widget setup screen", () => {
	it("lets a seated member without the admin role finish their own setup", () => {
		const w = render({ userSetupComplete: false });

		expect(w.find("button").text()).toContain("Complete Setup");
		expect(w.text()).not.toContain("administrator");
	});

	it("still lets an admin finish theirs", () => {
		const w = render({ isAdmin: true, userSetupComplete: false });

		expect(w.find("button").text()).toContain("Complete Setup");
	});

	it("treats consent as the user's own, admin or not", () => {
		const w = render({ privacyConsentComplete: false });

		expect(w.find("button").text()).toContain("Complete Setup");
	});

	it("keeps connecting the site itself an admin's job", () => {
		const w = render({ status: "not_registered" });

		expect(w.find("button").exists()).toBe(false);
		expect(w.text()).toContain("ask your administrator to enable FACO");
	});

	it("offers the site owner the way in", () => {
		const w = render({ status: "not_registered", isAdmin: true });

		expect(w.find("button").text()).toContain("Get Started Free");
	});
});
