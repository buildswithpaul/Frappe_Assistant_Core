import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";

import EntryStep from "./EntryStep.vue";

// jsdom does not fire a form's submit event from a real button click unless
// the form is attached to `document` — trigger "submit" on the form directly,
// the same workaround ConnectWizard.spec.js and FeedbackForm.spec.js use.
async function submit(w) {
	await w.find("form").trigger("submit");
}

describe("EntryStep", () => {
	it("starts empty and pre-fills from initialUrl", () => {
		const empty = mount(EntryStep);
		expect(empty.find('[data-test="endpoint-url"]').element.value).toBe("");

		const seeded = mount(EntryStep, { props: { initialUrl: "https://acme.example/mcp" } });
		expect(seeded.find('[data-test="endpoint-url"]').element.value).toBe("https://acme.example/mcp");
	});

	it("emits check with the trimmed URL on submit", async () => {
		const w = mount(EntryStep);
		await w.find('[data-test="endpoint-url"]').setValue("  https://acme.example/mcp  ");
		await submit(w);
		expect(w.emitted("check")[0]).toEqual(["https://acme.example/mcp"]);
	});

	it("does no validation of its own — an empty or non-https value is still emitted", async () => {
		// Validation lives in the parent, next to the single `error` slot it
		// shares with the manual-credentials retry path. This component only
		// trims, so a stale parent-level error is never joined by a second,
		// child-owned one for the same submission.
		const w = mount(EntryStep);
		await submit(w);
		expect(w.emitted("check")[0]).toEqual([""]);
	});

	it("disables the button and shows progress text while busy", () => {
		const w = mount(EntryStep, { props: { busy: true } });
		const button = w.find('[data-test="check"]');
		expect(button.attributes("disabled")).not.toBeUndefined();
		expect(button.text()).toBe("Checking…");
	});
});
