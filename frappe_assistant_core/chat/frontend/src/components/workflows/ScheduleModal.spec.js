import { describe, it, expect, afterEach } from "vitest";
import { mount } from "@vue/test-utils";
import ScheduleModal from "./ScheduleModal.vue";

// Saved schedules reach the modal through the workflow's `config` prop, so the
// test opens it the same way: closed first, then opened with a saved config.
const wrappers = [];

async function open(config) {
	const w = mount(ScheduleModal, {
		props: { modelValue: false, config },
		attachTo: document.body,
	});
	wrappers.push(w);
	await w.setProps({ modelValue: true });
	return w;
}

afterEach(() => {
	wrappers.splice(0).forEach((w) => w.unmount());
});

describe("ScheduleModal", () => {
	it("keeps a saved zone that is not in the short list", async () => {
		await open({ cron: "0 9 * * 1", timezone: "Asia/Dubai", defaultInput: "", enabled: true });
		const select = document.body.querySelector('[data-test="schedule-tz"]');
		expect([...select.options].map((o) => o.value)).toContain("Asia/Dubai");
		expect(select.value).toBe("Asia/Dubai");
	});

	// Regression guard: the user leaves the zone alone and saves; the saved zone must come back unchanged.
	it("saves a non-listed zone back unchanged", async () => {
		const w = await open({ cron: "0 9 * * 1", timezone: "Asia/Dubai", defaultInput: "", enabled: true });
		const saveButton = [...document.body.querySelectorAll(".action-btn.primary")][0];
		saveButton.click();
		expect(w.emitted("save")[0][0].timezone).toBe("Asia/Dubai");
	});

	it("fills the cron from a preset", async () => {
		await open({ cron: "", timezone: "UTC", defaultInput: "", enabled: true });
		const preset = [...document.body.querySelectorAll(".preset-btn")].find((b) =>
			b.textContent.includes("Weekdays")
		);
		preset.click();
		await new Promise((resolve) => setTimeout(resolve));
		expect(document.body.querySelector('[data-test="schedule-cron"]').value).toBe("0 9 * * 1-5");
	});
});
