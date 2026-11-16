import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";

const getCall = vi.fn();
const baseCall = vi.fn();
vi.mock("@/api/_core", () => ({ baseCall: (...a) => baseCall(...a), getCall: (...a) => getCall(...a) }));

let options;
vi.mock("@/utils/pageFrameHost", async (original) => ({
	...(await original()),
	createPageFrame: (opts) => {
		options = opts;
		return { element: document.createElement("iframe"), dispose: vi.fn(), setTheme: vi.fn() };
	},
}));

import PageFrame from "./PageFrame.vue";

const PAGE = { title: "Bank", html: "", script: "", style: "", withheld: { fields: ["iban"], doctypes: {}, hidden_doctypes: [] } };

describe("PageFrame", () => {
	it("notes what the frame's calls show, before the method is encoded for the URL", async () => {
		const wrapper = mount(PageFrame, { props: { page: PAGE, askUser: vi.fn() } });
		getCall.mockResolvedValueOnce({ iban: "DE89" });
		baseCall.mockResolvedValueOnce("ok");

		await options.transport.get("frappe.client.get", { doctype: "Bank Account", name: "B" });
		await options.transport.post("my_app.api.thing", {});

		expect(getCall).toHaveBeenCalledWith("frappe.client.get", { doctype: "Bank Account", name: "B" });
		expect(wrapper.vm.shown()).toEqual({ fields: ["iban"], methods: ["my_app.api.thing"] });
		wrapper.unmount();
	});
});
