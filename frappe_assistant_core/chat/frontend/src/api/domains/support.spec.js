import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { support } from "@/api/domains/support.js";

describe("support.uploadTicketAttachment", () => {
	beforeEach(() => {
		global.fetch = vi.fn().mockResolvedValue({
			ok: true,
			json: async () => ({
				message: {
					success: true,
					file: { file_id: "F1", file_url: "/x.png", file_name: "x.png", is_image: true },
				},
			}),
		});
	});
	afterEach(() => vi.restoreAllMocks());

	it("posts multipart FormData and unwraps the file dict", async () => {
		const file = new File([new Uint8Array([1, 2, 3])], "x.png", { type: "image/png" });
		const res = await support.uploadTicketAttachment(file);
		expect(res.file_id).toBe("F1");
		const [url, opts] = global.fetch.mock.calls[0];
		expect(url).toContain("support.upload_ticket_attachment");
		expect(opts.method).toBe("POST");
		expect(opts.body).toBeInstanceOf(FormData);
		expect(opts.body.get("file")).toBe(file);
		expect(opts.headers["X-Frappe-CSRF-Token"]).toBeDefined();
	});

	it("throws a friendly error on non-ok", async () => {
		global.fetch = vi.fn().mockResolvedValue({
			ok: false,
			status: 413,
			text: async () => "too big",
		});
		const file = new File([1], "x.png", { type: "image/png" });
		await expect(support.uploadTicketAttachment(file)).rejects.toBeTruthy();
	});
});

describe("support attachment_ids threading", () => {
	beforeEach(() => {
		global.fetch = vi.fn().mockResolvedValue({
			ok: true,
			json: async () => ({ message: { ticket_id: "1" } }),
		});
	});
	afterEach(() => vi.restoreAllMocks());

	it("serializes attachment_ids as JSON on createTicket", async () => {
		await support.createTicket({ subject: "S", description: "D", attachmentIds: ["F1", "F2"] });
		const body = JSON.parse(global.fetch.mock.calls[0][1].body);
		expect(body.attachment_ids).toBe(JSON.stringify(["F1", "F2"]));
	});

	it("sends null attachment_ids when none", async () => {
		await support.createTicket({ subject: "S", description: "D" });
		const body = JSON.parse(global.fetch.mock.calls[0][1].body);
		expect(body.attachment_ids).toBeNull();
	});

	it("threads attachmentIds on replyToTicket", async () => {
		await support.replyToTicket("58", "hi", ["F9"]);
		const body = JSON.parse(global.fetch.mock.calls[0][1].body);
		expect(body.attachment_ids).toBe(JSON.stringify(["F9"]));
	});
});
