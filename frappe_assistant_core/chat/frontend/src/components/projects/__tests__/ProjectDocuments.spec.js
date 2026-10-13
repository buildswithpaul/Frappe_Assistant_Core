import { describe, it, expect, beforeAll, beforeEach, afterEach, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";

const list = vi.fn();
const upload = vi.fn();
const remove = vi.fn();
vi.mock("@/api/client", () => ({
	api: {
		documents: {
			list: (...a) => list(...a),
			upload: (...a) => upload(...a),
			delete: (...a) => remove(...a),
			getDownloadUrl: (id) => `/dl/${id}`,
		},
	},
}));
const showError = vi.fn();
const showToast = vi.fn();
vi.mock("@/composables/useToast", () => ({ useToast: () => ({ showError, showToast }) }));

import { createPinia, setActivePinia } from "pinia";
import { useUserStore } from "@/stores/userStore";
import ProjectDocuments from "@/components/projects/ProjectDocuments.vue";

beforeAll(() => {
	window.__ = (s) => s;
});

const doc = (id, status, name = `${id}.pdf`) => ({
	document_id: id,
	file_name: name,
	file_size: 2048,
	embedding_status: status,
	project_id: "p1",
});

const ConfirmStub = {
	props: ["open"],
	emits: ["confirm", "cancel"],
	template: `<div v-if="open" data-test="confirm"><button data-test="confirm-ok" @click="$emit('confirm')"/></div>`,
};

function mountBlock() {
	return mount(ProjectDocuments, {
		props: { projectId: "p1" },
		attachTo: document.body,
		global: { plugins: [pinia], stubs: { ConfirmModal: ConfirmStub } },
	});
}

let pinia;
beforeEach(() => {
	pinia = createPinia();
	setActivePinia(pinia);
	vi.useFakeTimers();
	vi.clearAllMocks();
	list.mockResolvedValue({ documents: [] });
});

afterEach(() => {
	vi.useRealTimers();
	document.body.innerHTML = "";
});

describe("ProjectDocuments", () => {
	it("shows the empty state", async () => {
		const w = mountBlock();
		await flushPromises();
		expect(list).toHaveBeenCalledWith({ project: "p1" });
		expect(w.get("[data-test=docs-empty]").text()).toBe(
			"No documents yet. Upload files the assistant should know for this project."
		);
	});

	it("lists documents with a status pill per embedding state", async () => {
		list.mockResolvedValue({
			documents: [doc("a", "Pending"), doc("b", "Processing"), doc("c", "Completed"), doc("d", "Failed")],
		});
		const w = mountBlock();
		await flushPromises();
		expect(w.findAll("[data-test=doc-status]").map((n) => n.text())).toEqual([
			"Processing",
			"Processing",
			"Ready",
			"Failed",
		]);
		w.unmount();
	});

	it("uploads with the project and refreshes the list", async () => {
		upload.mockResolvedValue({});
		const w = mountBlock();
		await flushPromises();
		list.mockResolvedValue({ documents: [doc("a", "Completed", "notes.pdf")] });
		const file = new File(["x"], "notes.pdf", { type: "application/pdf" });
		const input = w.get("[data-test=docs-file-input]");
		Object.defineProperty(input.element, "files", { value: [file], configurable: true });
		await input.trigger("change");
		await flushPromises();
		expect(upload).toHaveBeenCalledWith(file, { project: "p1" });
		expect(w.findAll("[data-test=doc-row]")).toHaveLength(1);
		w.unmount();
	});

	it("refuses an unsupported file without calling upload", async () => {
		const w = mountBlock();
		await flushPromises();
		const file = new File(["x"], "pic.png", { type: "image/png" });
		await w.get("[data-test=project-documents]").trigger("drop", { dataTransfer: { files: [file] } });
		await flushPromises();
		expect(upload).not.toHaveBeenCalled();
		expect(showError).toHaveBeenCalled();
		w.unmount();
	});

	it("a dropped file goes through the same upload", async () => {
		upload.mockResolvedValue({});
		const w = mountBlock();
		await flushPromises();
		const file = new File(["x"], "a.md", { type: "text/markdown" });
		await w.get("[data-test=project-documents]").trigger("drop", { dataTransfer: { files: [file] } });
		await flushPromises();
		expect(upload).toHaveBeenCalledWith(file, { project: "p1" });
		w.unmount();
	});

	it("polls every 5s while processing, stops when done, and stops on unmount", async () => {
		list.mockResolvedValue({ documents: [doc("a", "Processing")] });
		const w = mountBlock();
		await flushPromises();
		expect(list).toHaveBeenCalledTimes(1);
		await vi.advanceTimersByTimeAsync(5000);
		expect(list).toHaveBeenCalledTimes(2);

		list.mockResolvedValue({ documents: [doc("a", "Completed")] });
		await vi.advanceTimersByTimeAsync(5000);
		expect(list).toHaveBeenCalledTimes(3);
		await vi.advanceTimersByTimeAsync(15000);
		expect(list).toHaveBeenCalledTimes(3);
		w.unmount();
	});

	it("stops polling when unmounted while a document is still processing", async () => {
		list.mockResolvedValue({ documents: [doc("a", "Pending")] });
		const w = mountBlock();
		await flushPromises();
		w.unmount();
		const calls = list.mock.calls.length;
		await vi.advanceTimersByTimeAsync(20000);
		expect(list).toHaveBeenCalledTimes(calls);
	});

	it("deletes after confirmation and removes the row", async () => {
		list.mockResolvedValue({ documents: [doc("a", "Completed"), doc("b", "Completed")] });
		remove.mockResolvedValue({});
		const w = mountBlock();
		await flushPromises();
		await w.findAll("[data-test=doc-menu]")[0].trigger("click");
		await w.get("[data-test=doc-delete]").trigger("click");
		expect(remove).not.toHaveBeenCalled();
		await w.get("[data-test=confirm-ok]").trigger("click");
		await flushPromises();
		expect(remove).toHaveBeenCalledWith("a");
		expect(w.findAll("[data-test=doc-row]")).toHaveLength(1);
		w.unmount();
	});

	it("keeps the row and toasts when delete fails", async () => {
		list.mockResolvedValue({ documents: [doc("a", "Completed")] });
		remove.mockRejectedValue(new Error("nope"));
		const w = mountBlock();
		await flushPromises();
		await w.get("[data-test=doc-menu]").trigger("click");
		await w.get("[data-test=doc-delete]").trigger("click");
		await w.get("[data-test=confirm-ok]").trigger("click");
		await flushPromises();
		expect(showError).toHaveBeenCalledWith("nope");
		expect(w.findAll("[data-test=doc-row]")).toHaveLength(1);
		w.unmount();
	});

	it("offers Download and closes the menu on an outside click or Escape without bubbling", async () => {
		list.mockResolvedValue({ documents: [doc("a", "Completed")] });
		const w = mountBlock();
		await flushPromises();
		await w.get("[data-test=doc-menu]").trigger("click");
		expect(w.get("[data-test=doc-download]").attributes("href")).toBe("/dl/a");

		document.body.click();
		await flushPromises();
		expect(w.find("[data-test=doc-download]").exists()).toBe(false);

		await w.get("[data-test=doc-menu]").trigger("click");
		const outer = vi.fn();
		document.addEventListener("keydown", outer);
		const ev = new KeyboardEvent("keydown", { key: "Escape", bubbles: true });
		w.get("[role=menu]").element.dispatchEvent(ev);
		await flushPromises();
		document.removeEventListener("keydown", outer);
		expect(w.find("[data-test=doc-download]").exists()).toBe(false);
		expect(outer).not.toHaveBeenCalled();
		w.unmount();
	});

	it("toasts once and stops polling when the poll keeps failing", async () => {
		list.mockResolvedValueOnce({ documents: [doc("a", "Processing")] });
		list.mockRejectedValue(new Error("down"));
		const w = mountBlock();
		await flushPromises();
		await vi.advanceTimersByTimeAsync(5000);
		await vi.advanceTimersByTimeAsync(5000);
		await vi.advanceTimersByTimeAsync(5000);
		expect(list).toHaveBeenCalledTimes(2);
		expect(showError).toHaveBeenCalledTimes(1);
		expect(w.findAll("[data-test=doc-row]")).toHaveLength(1);
		w.unmount();
	});

	it("resumes polling after a later successful load", async () => {
		list.mockResolvedValueOnce({ documents: [doc("a", "Processing")] });
		list.mockRejectedValueOnce(new Error("down"));
		const w = mountBlock();
		await flushPromises();
		await vi.advanceTimersByTimeAsync(5000);
		list.mockResolvedValue({ documents: [doc("a", "Processing")] });
		upload.mockResolvedValue({});
		const file = new File(["x"], "a.md", { type: "text/markdown" });
		await w.get("[data-test=project-documents]").trigger("drop", { dataTransfer: { files: [file] } });
		await flushPromises();
		const calls = list.mock.calls.length;
		await vi.advanceTimersByTimeAsync(5000);
		expect(list).toHaveBeenCalledTimes(calls + 1);
		w.unmount();
	});

	it("never overlaps a slow poll with the next tick", async () => {
		list.mockResolvedValueOnce({ documents: [doc("a", "Processing")] });
		let resolveSlow;
		list.mockReturnValueOnce(new Promise((r) => (resolveSlow = r)));
		const w = mountBlock();
		await flushPromises();
		await vi.advanceTimersByTimeAsync(5000);
		await vi.advanceTimersByTimeAsync(20000);
		expect(list).toHaveBeenCalledTimes(2);
		resolveSlow({ documents: [doc("a", "Processing")] });
		w.unmount();
	});

	it("a poll in flight during a delete does not resurrect the row", async () => {
		list.mockResolvedValueOnce({ documents: [doc("a", "Processing"), doc("b", "Completed")] });
		let resolveSlow;
		list.mockReturnValueOnce(new Promise((r) => (resolveSlow = r)));
		remove.mockResolvedValue({});
		const w = mountBlock();
		await flushPromises();
		await vi.advanceTimersByTimeAsync(5000);
		await w.findAll("[data-test=doc-menu]")[1].trigger("click");
		await w.get("[data-test=doc-delete]").trigger("click");
		await w.get("[data-test=confirm-ok]").trigger("click");
		await flushPromises();
		resolveSlow({ documents: [doc("a", "Processing"), doc("b", "Completed")] });
		await flushPromises();
		expect(w.findAll("[data-test=doc-row]")).toHaveLength(1);
		expect(w.get("[data-test=doc-row]").text()).toContain("a.pdf");
		w.unmount();
	});

	it("shows an error with Retry, not the empty state, when the first load fails", async () => {
		list.mockRejectedValueOnce(new Error("down"));
		const w = mountBlock();
		await flushPromises();
		expect(w.find("[data-test=docs-empty]").exists()).toBe(false);
		expect(w.get("[data-test=docs-error]").text()).toContain("Couldn't load this project's documents.");
		list.mockResolvedValue({ documents: [doc("a", "Completed")] });
		await w.get("[data-test=docs-retry]").trigger("click");
		await flushPromises();
		expect(w.find("[data-test=docs-error]").exists()).toBe(false);
		expect(w.findAll("[data-test=doc-row]")).toHaveLength(1);
		w.unmount();
	});

	it("ignores a stale response after the project changes mid-load", async () => {
		let resolveOld;
		list.mockReturnValueOnce(new Promise((r) => (resolveOld = r)));
		list.mockResolvedValueOnce({ documents: [doc("new", "Completed", "new.pdf")] });
		const w = mountBlock();
		await w.setProps({ projectId: "p2" });
		await flushPromises();
		resolveOld({ documents: [doc("old", "Completed", "old.pdf")] });
		await flushPromises();
		expect(w.findAll("[data-test=doc-row]").map((r) => r.text())[0]).toContain("new.pdf");
		expect(w.findAll("[data-test=doc-row]")).toHaveLength(1);
		w.unmount();
	});

	it("tells the user when files are dropped during an upload", async () => {
		let finish;
		upload.mockReturnValue(new Promise((r) => (finish = r)));
		const w = mountBlock();
		await flushPromises();
		const file = new File(["x"], "a.md", { type: "text/markdown" });
		const block = w.get("[data-test=project-documents]");
		await block.trigger("drop", { dataTransfer: { files: [file] } });
		await block.trigger("drop", { dataTransfer: { files: [file] } });
		expect(upload).toHaveBeenCalledTimes(1);
		expect(showToast).toHaveBeenCalledWith("Wait for the current upload to finish");
		finish({});
		await flushPromises();
		w.unmount();
	});

	it("hides Upload when the plan excludes the knowledge base", async () => {
		useUserStore().quotaInfo = { features: { knowledge_base: false } };
		const w = mountBlock();
		await flushPromises();
		expect(w.find("[data-test=docs-upload]").exists()).toBe(false);
		w.unmount();
	});

	it("keeps Upload when the plan does not say", async () => {
		const w = mountBlock();
		await flushPromises();
		expect(w.find("[data-test=docs-upload]").exists()).toBe(true);
		w.unmount();
	});

	it("offers Retry above the rows after a failed poll and resumes polling", async () => {
		list.mockResolvedValueOnce({ documents: [doc("a", "Processing")] });
		list.mockRejectedValueOnce(new Error("down"));
		const w = mountBlock();
		await flushPromises();
		await vi.advanceTimersByTimeAsync(5000);
		expect(w.get("[data-test=docs-refresh-error]").text()).toContain("Couldn't refresh.");
		expect(w.findAll("[data-test=doc-row]")).toHaveLength(1);
		list.mockResolvedValue({ documents: [doc("a", "Completed")] });
		await w.get("[data-test=docs-refresh-retry]").trigger("click");
		await flushPromises();
		expect(w.find("[data-test=docs-refresh-error]").exists()).toBe(false);
		expect(w.get("[data-test=doc-row]").text()).not.toContain("Processing");
		w.unmount();
	});
});
