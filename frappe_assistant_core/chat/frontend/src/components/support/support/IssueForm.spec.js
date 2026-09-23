import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";
import { flushPromises } from "@vue/test-utils";

vi.mock("@/composables/useTicketAttachments.js", () => ({
	TICKET_MAX_FILES: 5,
	TICKET_ACCEPT: "image/png",
	useTicketAttachments: () => ({
		files: { value: [] },
		fileInput: { value: null },
		canAdd: { value: true },
		triggerFileInput: vi.fn(),
		addFiles: vi.fn(),
		handlePaste: vi.fn(),
		removeFile: vi.fn(),
		retryFile: vi.fn(),
		consumeAttachmentIds: () => ["F1", "F2"],
		reset: vi.fn(),
	}),
}));

import IssueForm from "@/components/support/support/IssueForm.vue";

describe("IssueForm attachments", () => {
	it("includes attachmentIds in the submit payload", async () => {
		const w = mount(IssueForm, {
			props: { environment: { model: "x" }, submitting: false },
			global: { stubs: { EnvironmentDisclosure: true, AttachmentPicker: true } },
		});
		await w.find('input[type="text"]').setValue("Subj");
		await w.find("textarea").setValue("Details here");
		await w.find("form").trigger("submit.prevent");
		const payload = w.emitted("submit")[0][0];
		expect(payload.attachmentIds).toEqual(["F1", "F2"]);
		expect(payload.subject).toBe("Subj");
	});
});

describe("IssueForm attachments (real composable + child, regression for reactivity propagation)", () => {
	vi.doUnmock("@/composables/useTicketAttachments.js");

	it("reflects an upload's 'done' status in the rendered AttachmentPicker chip after the network call resolves", async () => {
		vi.resetModules();
		vi.doMock("@/api/client", () => ({
			api: { support: { uploadTicketAttachment: vi.fn() } },
		}));
		vi.stubGlobal("URL", { createObjectURL: () => "blob:x", revokeObjectURL() {} });

		const { api } = await import("@/api/client");
		let resolveUpload;
		api.support.uploadTicketAttachment.mockReturnValue(
			new Promise((resolve) => {
				resolveUpload = resolve;
			})
		);

		const { default: RealIssueForm } = await import("@/components/support/support/IssueForm.vue");

		const w = mount(RealIssueForm, {
			props: { environment: { model: "x" }, submitting: false },
			global: { stubs: { EnvironmentDisclosure: true } },
		});

		const file = new File([1], "a.png", { type: "image/png" });
		const input = w.find("input[type=file]");
		Object.defineProperty(input.element, "files", { value: [file] });
		await input.trigger("change");
		await flushPromises();

		expect(w.find(".chip").classes()).toContain("uploading");
		expect(w.find(".spinner").exists()).toBe(true);

		resolveUpload({ file_id: "F9", file_name: "a.png", is_image: true });
		await flushPromises();
		await flushPromises();

		expect(w.find(".chip").classes()).toContain("done");
		expect(w.find(".spinner").exists()).toBe(false);

		vi.unstubAllGlobals();
	});
});
