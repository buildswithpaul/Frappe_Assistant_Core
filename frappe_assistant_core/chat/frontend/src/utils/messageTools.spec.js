import { describe, it, expect } from "vitest";

import { MESSAGE_TOOLS, isMessageTool, renderMessageBody } from "./messageTools";

describe("isMessageTool", () => {
	it("matches the message tools by their exact bare name", () => {
		expect(isMessageTool("send_email")).toBe(true);
		expect(isMessageTool("reply_to_helpdesk_ticket")).toBe(true);
	});

	it("does not match a BYO server's prefixed tool or anything else", () => {
		for (const name of ["myserver_send_email", "create_document", "", null, undefined, "toString"]) {
			expect(isMessageTool(name)).toBe(false);
		}
	});
});

describe("MESSAGE_TOOLS.read", () => {
	it("reads send_email's recipients, cc, subject and body from its input", () => {
		const out = MESSAGE_TOOLS.send_email.read({
			recipients: ["a@x.com"],
			cc: ["b@x.com"],
			subject: "Hi",
			message: "Body",
		});
		expect(out).toEqual({ to: ["a@x.com"], cc: ["b@x.com"], subject: "Hi", body: "Body" });
	});

	it("leaves the reply's recipient and subject to the server preview", () => {
		const out = MESSAGE_TOOLS.reply_to_helpdesk_ticket.read({ ticket: "12", message: "<p>Hi</p>" });
		expect(out).toEqual({ to: null, cc: [], subject: null, body: "<p>Hi</p>" });
		expect(MESSAGE_TOOLS.reply_to_helpdesk_ticket.previewArgs({ ticket: "12" })).toEqual({ ticket: "12" });
	});
});

describe("renderMessageBody", () => {
	it("renders plain text with line breaks", () => {
		expect(renderMessageBody("a\nb")).toContain("a<br>b");
	});

	it("escapes plain text instead of treating it as markup", () => {
		expect(renderMessageBody("1 < 2 & 3\nok")).toContain("1 &lt; 2 &amp; 3<br>ok");
	});

	it("strips scripts and images", () => {
		const html = renderMessageBody('<p>x</p><script>alert(1)</script><img src=x onerror="y()">');
		expect(html).toContain("<p>x</p>");
		expect(html).not.toContain("script");
		expect(html).not.toContain("img");
	});
});
