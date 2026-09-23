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

describe("TicketDetail conversation link", () => {
	const mountWith = (ticket) =>
		mount(TicketDetail, {
			props: { ticket },
			global: { stubs: { TicketStatusPill: true, AttachmentPicker: true } },
		});

	it("offers a link into the chat when the ticket carries a conversation", () => {
		const w = mountWith({ ...openTicket, conversation_id: "sess-42" });
		const link = w.find(".conversation-link");
		expect(link.exists()).toBe(true);
		expect(link.text()).toContain("View conversation");
	});

	it("emits navigate to that conversation's chat route", async () => {
		const w = mountWith({ ...openTicket, conversation_id: "sess-42" });
		await w.find(".conversation-link").trigger("click");
		expect(w.emitted("navigate")[0]).toEqual(["/chat/sess-42"]);
	});

	it("shows nothing when the ticket has no conversation", () => {
		expect(mountWith(openTicket).find(".conversation-link").exists()).toBe(false);
	});

	it("never renders the raw transcript file to the customer", () => {
		const w = mountWith({ ...openTicket, conversation_id: "sess-42" });
		expect(w.html()).not.toContain("/private/files/");
		expect(w.html()).not.toContain(".md");
	});
});

describe("TicketDetail attachment URL rewriting", () => {
	const ticket = { ...openTicket, messages: [] };
	const mountIt = () =>
		mount(TicketDetail, {
			props: { ticket, ticketId: "58" },
			global: { stubs: { TicketStatusPill: true, AttachmentPicker: true } },
		});

	it("points AR file URLs at the FAC proxy, not this site's root", () => {
		const html = mountIt().vm.renderContent('<img src="/private/files/a.png">');
		expect(html).toContain("download_ticket_attachment");
		expect(html).toContain("ticket_id=58");
		expect(html).toContain(encodeURIComponent("/private/files/a.png"));
		expect(html).not.toContain('src="/private/files/a.png"');
	});

	it("rewrites anchor hrefs too, so PDFs open", () => {
		const html = mountIt().vm.renderContent('<a href="/private/files/b.pdf">b.pdf</a>');
		expect(html).toContain("download_ticket_attachment");
		expect(html).not.toContain('href="/private/files/b.pdf"');
	});

	it("leaves unrelated links alone", () => {
		const html = mountIt().vm.renderContent('<a href="https://example.com/x">x</a>');
		expect(html).toContain('href="https://example.com/x"');
		expect(html).not.toContain("download_ticket_attachment");
	});

	it("still strips dangerous markup", () => {
		const html = mountIt().vm.renderContent('<img src="/private/files/a.png" onerror="alert(1)">');
		expect(html).not.toContain("onerror");
	});
});
