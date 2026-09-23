import { describe, it, expect, beforeAll } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

/**
 * The widget and the SPA answer the same question — "may this person finish
 * their own setup?" — and they used to answer it differently. The SPA asks
 * whether you hold a seat (`isAdmin || isPendingMember`); the widget asked
 * whether you hold the System Manager role. An invited member without that
 * role was told "your administrator hasn't added you to FACO yet" by the
 * widget, with no button, while the very same click through the Desk
 * notification opened the SPA's working "Connect your account" screen.
 *
 * `needs_setup` is only ever reached when `can_use` is true, and `can_use` IS
 * the membership check — so by the time we render that screen the person is a
 * seated member by construction. Site registration is the one step here that
 * genuinely belongs to an admin.
 */

const onboardingJs = resolve(process.cwd(), "../../public/chat/widget/widget_onboarding.js");

let Onboarding;

beforeAll(() => {
	globalThis.__ = (s) => s;
	// eslint-disable-next-line no-new-func
	new Function(readFileSync(onboardingJs, "utf8"))();
	Onboarding = window.FACOWidgetOnboarding;
});

function renderSetup({ isAdmin }, context) {
	let html = "";
	let buttonWired = false;
	const nodes = {
		".faco-messages": { html: (h) => (html = h) },
		".faco-input-area": { hide: () => {} },
		".faco-setup-btn": { on: () => (buttonWired = true) },
	};
	Onboarding.show_setup_required(
		{ is_admin: isAdmin, $widget: { find: (sel) => nodes[sel] } },
		context,
	);
	return { html, buttonWired };
}

describe("widget setup screen", () => {
	it("lets a seated member without the admin role finish their own setup", () => {
		const { html, buttonWired } = renderSetup({ isAdmin: false }, "needs_setup");

		expect(html).toContain("Complete Setup");
		expect(buttonWired).toBe(true);
		expect(html).not.toContain("administrator");
	});

	it("still lets an admin finish theirs", () => {
		const { html, buttonWired } = renderSetup({ isAdmin: true }, "needs_setup");

		expect(html).toContain("Complete Setup");
		expect(buttonWired).toBe(true);
	});

	it("treats consent as the user's own, admin or not", () => {
		const { html, buttonWired } = renderSetup({ isAdmin: false }, "needs_consent");

		expect(html).toContain("Complete Setup");
		expect(buttonWired).toBe(true);
	});

	it("keeps connecting the site itself an admin's job", () => {
		const { html, buttonWired } = renderSetup({ isAdmin: false }, "not_registered");

		expect(buttonWired).toBe(false);
		expect(html).toContain("ask your administrator to enable FACO");
		expect(html).not.toContain("faco-setup-btn");
	});

	it("offers the site owner the way in", () => {
		const { html, buttonWired } = renderSetup({ isAdmin: true }, "not_registered");

		expect(html).toContain("Get Started Free");
		expect(buttonWired).toBe(true);
	});
});
