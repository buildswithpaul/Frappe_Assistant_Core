import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";

import AccessDeniedScreen from "./AccessDeniedScreen.vue";

describe("AccessDeniedScreen", () => {
	it("tells a seated user with assistant access off what their admin must change", () => {
		const text = mount(AccessDeniedScreen, { props: { reasonCode: "assistant_disabled" } }).text();

		expect(text).toContain("Enable Assistant Access");
		expect(text).not.toContain("hasn't added you");
	});

	it("still asks for a seat when the user has none", () => {
		const text = mount(AccessDeniedScreen).text();

		expect(text).toContain("hasn't added you");
	});
});
