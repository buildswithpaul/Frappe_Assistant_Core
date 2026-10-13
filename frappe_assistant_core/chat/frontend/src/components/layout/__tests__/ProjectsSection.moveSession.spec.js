import { describe, it, expect, beforeAll, beforeEach, vi } from "vitest";
import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { nextTick } from "vue";
import NavigationSidebar from "@/components/layout/NavigationSidebar.vue";
import ProjectsSection from "@/components/layout/ProjectsSection.vue";
import { api } from "@/api/client";

const push = vi.fn();
vi.mock("vue-router", () => ({
	useRoute: () => ({ path: "/chat", fullPath: "/chat", params: {} }),
	useRouter: () => ({ push }),
}));
vi.mock("@/api/client", () => ({
	api: {
		chat: { moveSessionToProject: vi.fn() },
		projects: { create: vi.fn() },
	},
}));
vi.mock("frappe-ui", () => ({ call: vi.fn().mockResolvedValue({}) }));

beforeAll(() => {
	window.__ = (s) => s;
});

describe("New project… from a chat row", () => {
	let wrapper;
	beforeEach(() => {
		setActivePinia(createPinia());
		vi.clearAllMocks();
		api.projects.create.mockResolvedValue({ name: "P1", title: "Alpha" });
		api.chat.moveSessionToProject.mockResolvedValue({ project: "P1", project_title: "Alpha" });
		wrapper = mount(NavigationSidebar, {
			global: {
				stubs: {
					NavMenu: true,
					UserDropdown: true,
					FacoRobot: true,
					ConversationSearch: true,
					ConversationsList: {
						emits: ["new-project"],
						template: "<button data-test='row-new-project' @click=\"$emit('new-project', 's1')\" />",
					},
				},
			},
		});
	});

	async function openFromRow() {
		await wrapper.get("[data-test=row-new-project]").trigger("click");
		await nextTick();
		return wrapper.get("[data-test=new-project-input]");
	}

	it("opens the inline input, even with no projects yet", async () => {
		expect(wrapper.findComponent(ProjectsSection).exists()).toBe(true);
		const input = await openFromRow();
		expect(input.exists()).toBe(true);
	});

	it("Enter creates the project, moves the chat into it and stays on the page", async () => {
		const input = await openFromRow();
		await input.setValue("Alpha");
		await input.trigger("keydown.enter");
		await vi.waitFor(() => expect(api.chat.moveSessionToProject).toHaveBeenCalledWith("s1", "P1"));
		expect(api.projects.create).toHaveBeenCalled();
		expect(push).not.toHaveBeenCalled();
	});

	it("Esc cancels without creating", async () => {
		const input = await openFromRow();
		await input.setValue("Alpha");
		await input.trigger("keydown.esc");
		await nextTick();
		expect(wrapper.find("[data-test=new-project-input]").exists()).toBe(false);
		expect(api.projects.create).not.toHaveBeenCalled();
		expect(api.chat.moveSessionToProject).not.toHaveBeenCalled();
	});
});
