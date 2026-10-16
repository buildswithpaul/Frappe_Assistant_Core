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
		expect(renderMessageBody("a\nb").html).toContain("a<br>b");
	});

	it("escapes plain text instead of treating it as markup", () => {
		expect(renderMessageBody("1 < 2 & 3\nok").html).toContain("1 &lt; 2 &amp; 3<br>ok");
	});

	it("strips scripts and images", () => {
		const { html } = renderMessageBody('<p>x</p><script>alert(1)</script><img src=x onerror="y()">');
		expect(html).toContain("<p>x</p>");
		expect(html).not.toContain("script");
		expect(html).not.toContain("img");
	});

	it("counts the elements it left out, which the email still carries", () => {
		const { hiddenCount } = renderMessageBody('<p>x</p><img src="https://t.example/p.gif"><script>1</script>');
		expect(hiddenCount).toBe(2);
		expect(renderMessageBody("<p>plain</p>").hiddenCount).toBe(0);
	});

	it("shows text hidden with a class or the hidden attribute", () => {
		const { html, hiddenCount } = renderMessageBody(
			'<p>ok</p><div class="hidden">by class</div><p hidden>by attribute</p>',
		);
		expect(html).toContain("by class");
		expect(html).toContain("by attribute");
		expect(html).not.toContain("class=");
		expect(html).not.toContain("hidden");
		expect(hiddenCount).toBe(2);
	});

	it("drops every element that could fetch a remote URL", () => {
		const { html } = renderMessageBody(
			'<p>x</p><video poster="https://t.example/v.png"></video><svg><image href="https://t.example/s.png"/></svg><audio src="https://t.example/a.mp3"></audio>',
		);
		expect(html).not.toContain("t.example");
	});

	it("shows where a link really goes", () => {
		const { html } = renderMessageBody('<p><a href="https://evil.example/x">your invoice</a></p>');
		expect(html).toContain("your invoice");
		expect(html).toContain("(https://evil.example/x)");
		expect(renderMessageBody('<a href="https://a.example">https://a.example</a>').html).not.toContain("(https://a.example)");
	});

	it("shows text the email would hide with a style", () => {
		const { html } = renderMessageBody('<p>ok</p><div style="display:none">secret instruction</div>');
		expect(html).toContain("secret instruction");
		expect(html).not.toContain("display:none");
	});
});
