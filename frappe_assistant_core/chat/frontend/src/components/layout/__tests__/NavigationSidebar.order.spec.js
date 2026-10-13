import { describe, it, expect, beforeAll, beforeEach, vi } from "vitest";
import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import NavigationSidebar from "@/components/layout/NavigationSidebar.vue";

vi.mock("vue-router", () => ({ useRoute: () => ({ path: "/chat", fullPath: "/chat" }) }));
vi.mock("@/api/client", () => ({ api: { chat: {}, projects: {} } }));
vi.mock("frappe-ui", () => ({ call: vi.fn().mockResolvedValue({}) }));

beforeAll(() => {
	window.__ = (s) => s;
});
beforeEach(() => setActivePinia(createPinia()));

describe("NavigationSidebar layout", () => {
	it("puts search above Projects, and Projects above Recents", () => {
		const w = mount(NavigationSidebar, {
			global: {
				stubs: {
					NavMenu: true,
					UserDropdown: true,
					FacoRobot: true,
					ProjectsSection: { template: "<div data-test='projects' />" },
					ConversationsList: { template: "<div data-test='recents' />" },
					ConversationSearch: { template: "<div data-test='search' />" },
				},
			},
		});
		const order = w
			.findAll("[data-test]")
			.map((n) => n.attributes("data-test"))
			.filter((t) => ["search", "projects", "recents"].includes(t));
		expect(order).toEqual(["search", "projects", "recents"]);
	});
});
