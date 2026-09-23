import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount } from "@vue/test-utils";
import { ref } from "vue";
import { setActivePinia, createPinia } from "pinia";
import { useUserStore } from "@/stores/userStore";
import KnowledgeBase from "@/views/KnowledgeBase.vue";
import SharedKnowledge from "@/components/knowledge/SharedKnowledge.vue";
import KnowledgeToolbar from "@/components/knowledge/KnowledgeToolbar.vue";
import EmptyState from "@/components/common/list/EmptyState.vue";

vi.mock("vue-router", () => ({ useRouter: () => ({ push: vi.fn() }) }));

const listDocuments = vi.fn();
vi.mock("@/api/client", () => ({
	api: {
		documents: {
			list: (...args) => listDocuments(...args),
			getStorageInfo: vi.fn(),
		},
	},
}));

vi.mock("@/composables/useDocumentUpload", () => ({
	useDocumentUpload: () => ({
		uploads: ref([]),
		uploadError: ref(null),
		isDragging: ref(false),
		fileInput: ref(null),
		pendingFiles: ref([]),
		triggerUpload: vi.fn(),
		handleFileSelect: vi.fn(),
		confirmUpload: vi.fn(),
		cancelPending: vi.fn(),
		onDragOver: vi.fn(),
		onDragLeave: vi.fn(),
		onDrop: vi.fn(),
	}),
}));

const stubs = {
	NavigationSidebar: true,
	KnowledgeTopBar: true,
	SharedKnowledge: true,
	KnowledgeToolbar: true,
	KnowledgeDocumentGrid: true,
	KnowledgeStates: true,
	KnowledgeSkeleton: true,
	DocumentPreviewPanel: true,
	ChunkBrowserPanel: true,
	DeleteConfirmDialog: true,
	UploadConfirmModal: true,
	DocumentAccessModal: true,
	ListHeaderBand: true,
	AddSlotCard: true,
	FacoRobot: true,
};

async function mountKb(documents) {
	listDocuments.mockResolvedValue({ documents, storage: null });
	const wrapper = mount(KnowledgeBase, { global: { stubs } });
	await vi.waitFor(() => expect(listDocuments).toHaveBeenCalled());
	await vi.waitFor(() => expect(wrapper.html()).not.toContain("knowledgeskeleton-stub"));
	await wrapper.vm.$nextTick();
	return wrapper;
}

describe("KnowledgeBase — Team Notes visibility", () => {
	beforeEach(() => {
		global.ResizeObserver = class {
			observe() {}
			disconnect() {}
		};
		setActivePinia(createPinia());
		const userStore = useUserStore();
		userStore.memoryEnabled = true;
		userStore.isAdmin = true;
		listDocuments.mockReset();
	});

	it("shows Team Notes alongside the empty state when no documents exist", async () => {
		const wrapper = await mountKb([]);

		expect(wrapper.findComponent(SharedKnowledge).exists()).toBe(true);
		expect(wrapper.findComponent(EmptyState).exists()).toBe(true);
		// Filter/search controls stay hidden — there is nothing to filter yet.
		expect(wrapper.findComponent(KnowledgeToolbar).exists()).toBe(false);
	});

	it("shows Team Notes and the toolbar once documents exist", async () => {
		const wrapper = await mountKb([
			{ document_id: "d1", file_name: "handbook.pdf", embedding_status: "Completed" },
		]);

		expect(wrapper.findComponent(SharedKnowledge).exists()).toBe(true);
		expect(wrapper.findComponent(KnowledgeToolbar).exists()).toBe(true);
		expect(wrapper.findComponent(EmptyState).exists()).toBe(false);
	});
});
