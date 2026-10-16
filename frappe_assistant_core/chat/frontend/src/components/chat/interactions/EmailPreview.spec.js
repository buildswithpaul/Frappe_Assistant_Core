import { mount } from "@vue/test-utils";
import { describe, it, expect } from "vitest";

import EmailPreview from "@/components/chat/interactions/EmailPreview.vue";

function mountPreview(props = {}) {
	return mount(EmailPreview, {
		props: {
			preview: { will_email: true, sender: "support@acme.com" },
			to: ["priya@acme.in"],
			cc: ["ops@acme.in"],
			subject: "Re: Invoice PDF shows wrong tax total",
			body: "<p>Hi Priya,</p><p>The fix ships <b>Friday</b>.</p>",
			...props,
		},
	});
}

describe("EmailPreview", () => {
	it("shows the To, Cc and Subject rows", () => {
		const text = mountPreview().text();
		expect(text).toContain("priya@acme.in");
		expect(text).toContain("ops@acme.in");
		expect(text).toContain("Re: Invoice PDF shows wrong tax total");
	});

	it("renders the full body as formatted HTML", () => {
		const body = mountPreview().find(".email-body");
		expect(body.html()).toContain("<b>Friday</b>");
	});

	it("hides the Cc row when there is no cc", () => {
		expect(mountPreview({ cc: [] }).text()).not.toContain("Cc");
	});

	it("names the sending account", () => {
		expect(mountPreview().find(".email-sender").text()).toBe("Sends from support@acme.com");
	});

	it("warns when the email carries content the preview does not show", () => {
		const wrapper = mountPreview({ body: '<p>Hi</p><img src="https://t.example/p.gif">' });
		expect(wrapper.find(".email-hidden").text()).toBe("1 image or other element is not shown here but will be sent.");
		expect(mountPreview().find(".email-hidden").exists()).toBe(false);
	});

	it("says when Helpdesk will only record the reply", () => {
		const wrapper = mountPreview({ preview: { will_email: false, sender: null } });
		expect(wrapper.find(".email-sender").text()).toBe("Recorded on the ticket; Helpdesk won't email it.");
	});
});
