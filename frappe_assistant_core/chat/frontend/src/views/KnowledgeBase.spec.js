import { mount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";
import { vi } from "vitest";
import KnowledgeBase from "@/views/KnowledgeBase.vue";
import { useUserStore } from "@/stores/userStore";

// A plan that excludes the knowledge base must offer no way to upload — not a
// button, not the empty-state copy, not drag-and-drop — and must say why.
// Absent `features` means an older server; that stays allowed.

const { push, list } = vi.hoisted(() => ({ push: vi.fn(), list: vi.fn() }));

vi.mock("vue-router", () => ({ useRouter: () => ({ push }) }));
vi.stubGlobal(
	"ResizeObserver",
	class {
		observe() {}
		disconnect() {}
	}
);
vi.mock("@/api/client", () => ({
	api: { documents: { list, getStorageInfo: vi.fn(), upload: vi.fn() } },
}));

const STUBS = {
	NavigationSidebar: true,
	SharedKnowledge: true,
	DocumentPreviewPanel: true,
	ChunkBrowserPanel: true,
	DeleteConfirmDialog: true,
	DocumentAccessModal: true,
	UploadConfirmModal: true,
	FacoRobot: true,
	StorageBar: true,
};

const ONE_DOC = {
	document_id: "d1",
	file_name: "handbook.pdf",
	embedding_status: "Completed",
	visibility: "public",
	is_owner: true,
};

async function mountKb({ features, isAdmin = true, documents = [] } = {}) {
	const store = useUserStore();
	store.memoryEnabled = true;
	store.isAdmin = isAdmin;
	store.quotaInfo = { plan: "Free", quota_total: 500, ...(features ? { features } : {}) };
	list.mockResolvedValue({ documents, storage: null });
	const wrapper = mount(KnowledgeBase, { global: { stubs: STUBS } });
	await flushPromises();
	return wrapper;
}

const pdf = () => new File(["x"], "notes.pdf", { type: "application/pdf" });
const upgradeNote = (w) => w.find("[data-test=kb-upgrade-note]");

describe("KnowledgeBase plan gate", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		push.mockReset();
		list.mockReset();
	});

	describe("when the plan excludes the knowledge base", () => {
		const features = { knowledge_base: false };

		it("offers no upload action anywhere", async () => {
			const w = await mountKb({ features });
			expect(w.text()).not.toMatch(/upload/i);
			expect(w.text()).not.toMatch(/drag and drop/i);
		});

		it("explains why and links an admin to plans", async () => {
			const w = await mountKb({ features });
			expect(upgradeNote(w).exists()).toBe(true);
			await upgradeNote(w).find("button").trigger("click");
			expect(push).toHaveBeenCalledWith("/settings/billing");
		});

		it("tells a member to ask an admin instead of showing a plans button", async () => {
			const w = await mountKb({ features, isAdmin: false });
			expect(upgradeNote(w).text()).toMatch(/admin/i);
			expect(upgradeNote(w).find("button").exists()).toBe(false);
		});

		it("keeps the note visible once documents exist", async () => {
			const w = await mountKb({ features, documents: [ONE_DOC] });
			expect(upgradeNote(w).exists()).toBe(true);
			expect(w.find(".ql-primary-action").exists()).toBe(false);
		});

		it("does not highlight a drag as an upload target", async () => {
			const w = await mountKb({ features });
			await w.find(".kb-content").trigger("dragover");
			expect(w.text()).not.toContain("Drop files to upload");
		});

		it("does not start an upload from a drop", async () => {
			const w = await mountKb({ features });
			await w.find(".kb-content").trigger("drop", { dataTransfer: { files: [pdf()] } });
			const modal = w.findComponent({ name: "UploadConfirmModal" });
			expect(modal.props("files")).toEqual([]);
			expect(upgradeNote(w).exists()).toBe(true);
		});
	});

	describe("when the server does not say (older AR)", () => {
		it("keeps upload, drag-and-drop, and no upgrade note", async () => {
			const w = await mountKb();
			expect(w.text()).toContain("Upload your first document");
			expect(w.text()).toMatch(/drag and drop/i);
			expect(upgradeNote(w).exists()).toBe(false);
		});

		it("highlights a drag and accepts a drop", async () => {
			const w = await mountKb();
			await w.find(".kb-content").trigger("dragover");
			expect(w.text()).toContain("Drop files to upload");
			await w.find(".kb-content").trigger("drop", { dataTransfer: { files: [pdf()] } });
			const modal = w.findComponent({ name: "UploadConfirmModal" });
			expect(modal.props("files")).toHaveLength(1);
		});
	});
});
