import { describe, it, expect, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";

vi.mock("@/api/client", () => {
	const api = {
		workflows: {
			triggers: {
				log: vi.fn().mockResolvedValue({
					logs: [
						{
							name: "L1",
							status: "dispatched",
							fired_at: "2026-10-09 09:00:00",
							reference_doctype: "Sales Order",
							reference_docname: "SO-1",
							fac_cloud_run_id: "WFR-00012",
						},
					],
				}),
			},
		},
	};
	return { api, default: api };
});

import TriggerFireLog from "./TriggerFireLog.vue";

describe("TriggerFireLog", () => {
	it("opens the run a firing started", async () => {
		const w = mount(TriggerFireLog, { props: { triggerName: "T1" } });
		await flushPromises();
		await w.get('[data-test="open-run"]').trigger("click");
		expect(w.emitted("open-run")[0]).toEqual(["WFR-00012"]);
	});
});
