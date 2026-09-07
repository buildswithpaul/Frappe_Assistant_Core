import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

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
		consumeAttachmentIds: () => ["F9"],
		reset: vi.fn(),
	}),
}));

import TicketDetail from "@/components/settings/tickets/TicketDetail.vue";

const openTicket = { subject: "S", status: "Open", creation: "2026-07-08", messages: [] };

describe("TicketDetail attachments + rendering", () => {
	it("keeps <img src> and <a href> through DOMPurify", () => {
		const w = mount(TicketDetail, {
			props: { ticket: openTicket },
			global: { stubs: { TicketStatusPill: true, AttachmentPicker: true } },
		});
		const html = w.vm.renderContent('<img src="/private/files/a.png"><a href="/private/files/b.pdf">b.pdf</a>');
		expect(html).toContain('src="/private/files/a.png"');
		expect(html).toContain('href="/private/files/b.pdf"');
		expect(html).not.toContain("onerror");
	});

	it("emits reply with text and attachmentIds", async () => {
		const w = mount(TicketDetail, {
			props: { ticket: openTicket },
			global: { stubs: { TicketStatusPill: true, AttachmentPicker: true } },
		});
		await w.find("textarea").setValue("my reply");
		await w.find(".send-btn").trigger("click");
		expect(w.emitted("reply")[0][0]).toEqual({ text: "my reply", attachmentIds: ["F9"] });
	});

	it("strips a script tag from content", () => {
		const w = mount(TicketDetail, {
			props: { ticket: openTicket },
			global: { stubs: { TicketStatusPill: true, AttachmentPicker: true } },
		});
		expect(w.vm.renderContent('<img src=x><script>alert(1)<\/script>')).not.toContain("<script>");
	});
});
