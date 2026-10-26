import { describe, it, expect, beforeEach } from "vitest";
import { mount } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";
import InputArea from "./InputArea.vue";

describe("InputArea holdSend", () => {
	beforeEach(() => setActivePinia(createPinia()));

	it("keeps the text and sends nothing while sending is held", async () => {
		const w = mount(InputArea, { props: { holdSend: true } });
		const textarea = w.find("textarea");
		await textarea.setValue("draft for later");
		await textarea.trigger("keydown", { key: "Enter" });
		expect(w.emitted("send")).toBeUndefined();
		expect(textarea.element.value).toBe("draft for later");
		expect(textarea.element.disabled).toBe(false);
	});

	it("sends once the hold lifts", async () => {
		const w = mount(InputArea, { props: { holdSend: true } });
		const textarea = w.find("textarea");
		await textarea.setValue("now it goes");
		await w.setProps({ holdSend: false });
		await textarea.trigger("keydown", { key: "Enter" });
		expect(w.emitted("send")[0][0].message).toBe("now it goes");
	});
});
