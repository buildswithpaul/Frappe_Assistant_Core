import { describe, it, expect, beforeAll, beforeEach, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";

const getSessions = vi.fn();
const createSession = vi.fn();
const projectsList = vi.fn();
const projectsUpdate = vi.fn();
const documentsList = vi.fn();
const memoriesList = vi.fn();
vi.mock("@/api/client", () => ({
	api: {
		chat: { getSessions: (...a) => getSessions(...a), createSession: (...a) => createSession(...a) },
		memories: { list: (...a) => memoriesList(...a) },
		documents: { list: (...a) => documentsList(...a), getDownloadUrl: () => "#" },
		projects: { list: (...a) => projectsList(...a), update: (...a) => projectsUpdate(...a) },
	},
}));
const push = vi.fn();
vi.mock("vue-router", () => ({ useRouter: () => ({ push }) }));

import ProjectPage from "@/components/projects/ProjectPage.vue";
import { useProjectsStore } from "@/stores/projectsStore";
import { useUserStore } from "@/stores/userStore";

beforeAll(() => {
	window.__ = (s) => s;
});

const stubs = { RouterLink: { template: "<a><slot/></a>" }, ConfirmModal: true };

async function mountPage(projectId = "p1", { projectDocuments, rag = true, features = null } = {}) {
	const pinia = createPinia();
	setActivePinia(pinia);
	// The flag reaches the store from api.capabilities.get() at boot (userStore.loadCapabilities).
	if (projectDocuments !== undefined) {
		useUserStore().capabilities = { features: { project_documents: projectDocuments, rag } };
	}
	if (features) useUserStore().capabilities = { features };
	const w = mount(ProjectPage, { props: { projectId }, global: { plugins: [pinia], stubs } });
	return w;
}

beforeEach(() => {
	vi.clearAllMocks();
	getSessions.mockResolvedValue([]);
	documentsList.mockResolvedValue({ documents: [] });
	memoriesList.mockResolvedValue({ memories: [] });
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

	it("lays out the chats and the project context side by side in one grid", async () => {
		projectsList.mockResolvedValue([{ name: "p1", title: "Q3 Close", instructions: "Be brief" }]);
		const w = await mountPage();
		await flushPromises();
		const grid = w.find(".project-grid");
		expect(grid.exists()).toBe(true);
		const children = grid.element.children;
		expect(grid.find("[data-test=project-chat-input]").exists()).toBe(true);
		expect(children[1].tagName).toBe("ASIDE");
		expect(children[1].textContent).toContain("Be brief");
	});

	describe("project documents", () => {
		beforeEach(() => {
			projectsList.mockResolvedValue([{ name: "p1", title: "Q3 Close", instructions: "" }]);
		});

		it.each([[undefined], [false]])("does not render the block when the flag is %s", async (flag) => {
			const w = await mountPage("p1", { projectDocuments: flag });
			await flushPromises();
			expect(w.find("[data-test=project-documents]").exists()).toBe(false);
			expect(documentsList).not.toHaveBeenCalled();
			expect(w.findComponent("[data-test=delete-project-modal]").props("message")).toBe(
				"Delete this project? Its chats are kept and moved out of the project."
			);
		});

		it("does not render the block when RAG is off, but still names the Knowledge Base move", async () => {
			const w = await mountPage("p1", { projectDocuments: true, rag: false });
			await flushPromises();
			expect(w.find("[data-test=project-documents]").exists()).toBe(false);
			expect(documentsList).not.toHaveBeenCalled();
			expect(w.findComponent("[data-test=delete-project-modal]").props("message")).toContain(
				"its documents move to your Knowledge Base"
			);
		});

		it("renders the block and names the Knowledge Base move in the delete confirmation", async () => {
			const w = await mountPage("p1", { projectDocuments: true });
			await flushPromises();
			expect(w.find("[data-test=project-documents]").exists()).toBe(true);
			expect(documentsList).toHaveBeenCalledWith({ project: "p1" });
			expect(w.findComponent("[data-test=delete-project-modal]").props("message")).toContain(
				"its documents move to your Knowledge Base"
			);
		});
	});

	describe("project memory", () => {
		beforeEach(() => {
			projectsList.mockResolvedValue([{ name: "p1", title: "Q3 Close", instructions: "" }]);
		});

		it.each([
			["memory only", { memory: true }],
			["project_memory only", { project_memory: true }],
			["memory true, project_memory false", { memory: true, project_memory: false }],
			["memory false, project_memory true", { memory: false, project_memory: true }],
			["project_memory truthy but not true", { memory: true, project_memory: "yes" }],
			["memory truthy but not true", { memory: 1, project_memory: true }],
		])("does not render the block: %s", async (_label, features) => {
			const w = await mountPage("p1", { features });
			await flushPromises();
			expect(w.find("[data-test=project-memory]").exists()).toBe(false);
			expect(memoriesList).not.toHaveBeenCalled();
		});

		it("renders the block when both flags are true", async () => {
			const w = await mountPage("p1", { features: { memory: true, project_memory: true } });
			await flushPromises();
			expect(w.find("[data-test=project-memory]").exists()).toBe(true);
			expect(memoriesList).toHaveBeenCalledWith(null, 200, 0, "p1");
		});

		it("names the memory deletion on the delete confirmation", async () => {
			const w = await mountPage("p1", { features: { project_memory: true } });
			await flushPromises();
			expect(w.findComponent("[data-test=delete-project-modal]").props("message")).toBe(
				"Delete this project? Its chats are kept and its memories are deleted."
			);
		});
	});
});
