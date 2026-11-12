import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({ api: { imports: { planProgress: vi.fn(), stopPlan: vi.fn() } } }));

import { api } from "@/api/client";
import PlanProgressBlock from "./PlanProgressBlock.vue";

const running = { plan: "IMP-9", status: "Running", running: true, ended: false, files: [{ session: "IMP-10", file_name: "items.csv", status: "Importing", created: 120 }] };

afterEach(() => vi.clearAllMocks());

describe("the plan's progress block: Stop (PR #392, F7)", () => {
	it("stops a running plan from the block, with no chat turn", async () => {
		// Live: "stop now" waited in the composer behind FACO's turn until the plan had finished
		api.imports.planProgress.mockResolvedValue(running);
		api.imports.stopPlan.mockResolvedValue({
			success: true,
			message: "The plan stops once items.csv is imported. What's imported stays.",
			progress: { ...running, status: "Running" },
		});
		const w = mount(PlanProgressBlock, { props: { plan: "IMP-9" } });
		await flushPromises();

		const button = w.find("button.pp-stop");
		expect(button.exists()).toBe(true);
		await button.trigger("click");
		await flushPromises();

		expect(api.imports.stopPlan).toHaveBeenCalledWith("IMP-9");
		expect(w.text()).toContain("The plan stops once items.csv is imported");
		expect(w.find("button.pp-stop").exists()).toBe(false); // asked once
		w.unmount();
	});

	it("says why a stop was refused", async () => {
		api.imports.planProgress.mockResolvedValue(running);
		api.imports.stopPlan.mockResolvedValue({ success: false, error: "Plan IMP-9 is Completed, not running." });
		const w = mount(PlanProgressBlock, { props: { plan: "IMP-9" } });
		await flushPromises();
		await w.find("button.pp-stop").trigger("click");
		await flushPromises();
		expect(w.text()).toContain("not running");
		w.unmount();
	});

	it("has no Stop once the plan has ended", async () => {
		api.imports.planProgress.mockResolvedValue({ ...running, status: "Completed", running: false, ended: true });
		const w = mount(PlanProgressBlock, { props: { plan: "IMP-9" } });
		await flushPromises();
		expect(w.find("button.pp-stop").exists()).toBe(false);
		w.unmount();
	});
});
