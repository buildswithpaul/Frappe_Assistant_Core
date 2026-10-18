import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/utils/i18n", () => ({ __: (text, args) => `T(${text}|${(args || []).join(",")})` }));
vi.mock("@/components/chat/welcomeGreeting", () => ({ relativeTimeLabel: () => "2h ago" }));

import ContinueList from "./ContinueList.vue";

describe("ContinueList", () => {
	it("translates the heading and the whole Continue sentence", () => {
		const w = mount(ContinueList, {
			props: { sessions: [{ session_id: "s1", preview: "Q", last_activity: "2026-07-06 16:00:00" }] },
		});
		expect(w.find(".cl-label").text()).toBe("T(Pick up where you left off|)");
		expect(w.find(".cl-meta").text()).toBe("T(Continue · {0}|2h ago)");
	});
});
