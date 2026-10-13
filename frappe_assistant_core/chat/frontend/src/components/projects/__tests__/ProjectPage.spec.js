import { describe, it, expect, beforeAll, beforeEach, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";

const getSessions = vi.fn();
const projectsList = vi.fn();
const projectsUpdate = vi.fn();
vi.mock("@/api/client", () => ({
	api: {
		chat: { getSessions: (...a) => getSessions(...a) },
		projects: { list: (...a) => projectsList(...a), update: (...a) => projectsUpdate(...a) },
	},
}));
const push = vi.fn();
vi.mock("vue-router", () => ({ useRouter: () => ({ push }) }));

import ProjectPage from "@/components/projects/ProjectPage.vue";
import { useProjectsStore } from "@/stores/projectsStore";

beforeAll(() => {
	window.__ = (s) => s;
});

const stubs = { RouterLink: { template: "<a><slot/></a>" }, ConfirmModal: true };

async function mountPage(projectId = "p1") {
	const pinia = createPinia();
	setActivePinia(pinia);
	const w = mount(ProjectPage, { props: { projectId }, global: { plugins: [pinia], stubs } });
	return w;
}

beforeEach(() => {
	vi.clearAllMocks();
	getSessions.mockResolvedValue([]);
});

describe("ProjectPage", () => {
	it("shows loading, then not found when the project does not exist", async () => {
		let resolve;
		projectsList.mockReturnValue(new Promise((r) => (resolve = r)));
		const w = await mountPage();
		expect(w.find("[data-test=project-loading]").exists()).toBe(true);
		expect(w.find("[data-test=project-not-found]").exists()).toBe(false);
		resolve([]);
		await flushPromises();
		expect(w.find("[data-test=project-not-found]").exists()).toBe(true);
		expect(getSessions).not.toHaveBeenCalled();
	});

	it("loads the project's chats and shows the empty state", async () => {
		projectsList.mockResolvedValue([{ name: "p1", title: "Q3 Close", instructions: "" }]);
		const w = await mountPage();
		await flushPromises();
		expect(getSessions).toHaveBeenCalledWith({ limit: 100, project: "p1" });
		expect(w.find("[data-test=project-empty]").exists()).toBe(true);
	});

	it("Escape in the title editor discards despite the unmount blur", async () => {
		projectsList.mockResolvedValue([{ name: "p1", title: "Q3 Close", instructions: "" }]);
		const w = await mountPage();
		await flushPromises();
		await w.find("[data-test=project-title]").trigger("click");
		const input = w.find("[data-test=project-title-input]");
		await input.setValue("discard");
		input.trigger("keydown", { key: "Escape" });
		input.trigger("blur");
		await flushPromises();
		expect(projectsUpdate).not.toHaveBeenCalled();
	});

	it("Enter saves the renamed title once", async () => {
		projectsList.mockResolvedValue([{ name: "p1", title: "Q3 Close", instructions: "" }]);
		projectsUpdate.mockResolvedValue({ name: "p1", title: "Q4" });
		const w = await mountPage();
		await flushPromises();
		await w.find("[data-test=project-title]").trigger("click");
		const input = w.find("[data-test=project-title-input]");
		await input.setValue(" Q4 ");
		input.trigger("keydown", { key: "Enter" });
		input.trigger("blur");
		await flushPromises();
		expect(projectsUpdate).toHaveBeenCalledTimes(1);
		expect(projectsUpdate).toHaveBeenCalledWith("p1", { title: "Q4" });
		expect(useProjectsStore().byId("p1").title).toBe("Q4");
	});
});
