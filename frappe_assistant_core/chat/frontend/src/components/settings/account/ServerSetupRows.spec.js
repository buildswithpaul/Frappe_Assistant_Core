import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";

import ServerSetupRows from "./ServerSetupRows.vue";

const web = { status: "ok", slots: 32, required_slots: 20, reasons: [], fix: null };
const relayOff = { status: "off", enabled: false, reasons: [], fix: null };

const mountRows = (serverSetup) => mount(ServerSetupRows, { props: { serverSetup } });

describe("ServerSetupRows", () => {
	it("hides the relay row when the setting is off", () => {
		const wrapper = mountRows({ ...web, relay: relayOff });
		expect(wrapper.find("[data-testid='relay-workers']").exists()).toBe(false);
	});

	it("shows the relay warning with the worker command", () => {
		const wrapper = mountRows({
			...web,
			relay: {
				status: "warning",
				enabled: true,
				workers: 0,
				busy: 0,
				queued: 0,
				reasons: [
					"Chat relays are set to run in background jobs, but no worker is listening on the faco_relay queue, so they still run in the web workers. Start one with: bench worker --queue faco_relay.",
				],
				fix: "bench worker --queue faco_relay",
			},
		});
		const row = wrapper.find("[data-testid='relay-workers']");
		expect(row.text()).toContain("Chat relay workers");
		expect(row.text()).toContain("bench worker --queue faco_relay");
		expect(row.classes()).toContain("banner-warn");
	});

	it("shows workers, busy and waiting when relay workers are fine", () => {
		const wrapper = mountRows({
			...web,
			relay: { status: "ok", enabled: true, workers: 10, busy: 3, queued: 1, reasons: [], fix: null },
		});
		const row = wrapper.find("[data-testid='relay-workers']");
		expect(row.text()).toContain("10 relay workers listening, 3 busy, 1 waiting.");
		expect(row.classes()).toContain("banner-success");
	});

	it("keeps the web server row as before", () => {
		const wrapper = mountRows({ ...web, relay: relayOff });
		const row = wrapper.find("[data-testid='server-setup']");
		expect(row.text()).toContain("Web server");
		expect(row.text()).toContain("32 request slots; FACO needs at least 20.");
		expect(row.classes()).toContain("banner-success");
	});

	it("hides the web server row when the setup cannot be read but still shows the relay row", () => {
		const wrapper = mountRows({
			status: "unknown",
			relay: { status: "ok", workers: 2, busy: 0, queued: 0, reasons: [] },
		});
		expect(wrapper.find("[data-testid='server-setup']").exists()).toBe(false);
		expect(wrapper.find("[data-testid='relay-workers']").exists()).toBe(true);
	});
});
