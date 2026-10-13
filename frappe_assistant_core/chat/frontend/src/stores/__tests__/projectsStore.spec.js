import { describe, it, expect, vi, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useProjectsStore } from "@/stores/projectsStore";
import { useChatStore } from "@/stores/chatStore";
import { api } from "@/api/client";

vi.mock("@/api/client", () => ({
	api: { projects: { list: vi.fn(), create: vi.fn(), update: vi.fn(), remove: vi.fn() } },
}));
vi.mock("frappe-ui", () => ({ call: vi.fn().mockResolvedValue({}) }));

describe("projectsStore", () => {
	let store;
	beforeEach(() => {
		setActivePinia(createPinia());
		store = useProjectsStore();
		vi.clearAllMocks();
	});

	it("creates and puts the new project first", async () => {
		store.hydrate([{ name: "old", title: "Old" }]);
		api.projects.create.mockResolvedValue({ name: "new", title: "New", conversation_count: 0 });
		await store.create("New", "");
		expect(store.projects.map((p) => p.name)).toEqual(["new", "old"]);
	});

	it("update merges the response and keeps conversation_count", async () => {
		store.hydrate([{ name: "p1", title: "P", conversation_count: 4 }]);
		api.projects.update.mockResolvedValue({ name: "p1", title: "Q", instructions: "x" });
		await store.update("p1", { title: "Q" });
		expect(store.byId("p1")).toMatchObject({ title: "Q", instructions: "x", conversation_count: 4 });
	});

	it("removing a project clears it from loaded chats", async () => {
		const chat = useChatStore();
		chat.sessions = [{ session_id: "a", project: "p1", project_title: "P" }];
		store.hydrate([{ name: "p1", title: "P" }]);
		api.projects.remove.mockResolvedValue({ success: true });
		await store.remove("p1");
		expect(store.projects).toEqual([]);
		expect(chat.sessions[0]).toMatchObject({ project: null, project_title: null });
	});

	it("removing a project clears a pending project pointing at it", async () => {
		const chat = useChatStore();
		chat.setPendingProject("new-chat", "p1");
		api.projects.remove.mockResolvedValue({ success: true });
		await store.remove("p1");
		expect(chat.pendingProject).toBeNull();
	});
});
