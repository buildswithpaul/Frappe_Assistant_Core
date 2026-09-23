import { mount } from "@vue/test-utils";
import { describe, it, expect } from "vitest";
import SiteUnreachablePanel from "@/components/onboarding/SiteUnreachablePanel.vue";

const MESSAGE =
	"FAC Cloud could not reach http://mysite.localhost:8000. Cloud chat runs in the cloud and calls your site back for every action.";

function mountPanel(props = {}) {
	return mount(SiteUnreachablePanel, {
		props: { message: MESSAGE, ...props },
		global: { stubs: { FacoRobot: true } },
	});
}

describe("SiteUnreachablePanel", () => {
	it("leads with AR's own message so the unreachable URL is named", () => {
		const w = mountPanel();
		expect(w.find('[data-test="unreachable-message"]').text()).toBe(MESSAGE);
	});

	it("offers the local MCP server as the primary door", () => {
		const w = mountPanel();
		const cta = w.find('[data-test="unreachable-mcp-cta"]');
		expect(cta.exists()).toBe(true);
		expect(cta.attributes("href")).toBe(
			"https://docs.assistantcore.cloud/getting-started/quick-start"
		);
		// Opening docs must never replace the half-finished onboarding screen.
		expect(cta.attributes("target")).toBe("_blank");
		expect(cta.attributes("rel")).toContain("noopener");
	});

	it("keeps the public-URL door collapsed until asked", () => {
		const w = mountPanel();
		expect(w.find('[data-test="unreachable-tunnel-toggle"]').exists()).toBe(true);
		expect(w.find('[data-test="unreachable-tunnel-steps"]').exists()).toBe(false);
	});

	it("reveals the tunnel steps, including the host_name step, on request", async () => {
		const w = mountPanel();
		await w.find('[data-test="unreachable-tunnel-toggle"]').trigger("click");

		const steps = w.find('[data-test="unreachable-tunnel-steps"]');
		expect(steps.exists()).toBe(true);
		// host_name is the step people miss — a tunnel alone leaves get_url()
		// still reporting localhost, so registration re-sends the local URL.
		expect(steps.text()).toContain("host_name");
		expect(steps.text()).toContain("site_config.json");
		expect(steps.text()).toContain("clear-cache");
		expect(steps.find('[data-test="unreachable-local-docs"]').attributes("href")).toBe(
			"https://docs.assistantcore.cloud/fac-chat/local-sites"
		);
	});

	it("emits retry for someone who just brought a tunnel up", async () => {
		const w = mountPanel();
		await w.find('[data-test="unreachable-retry"]').trigger("click");
		expect(w.emitted("retry")).toHaveLength(1);
	});

	it("blocks a second retry while one is in flight", async () => {
		const w = mountPanel({ retrying: true });
		expect(w.find('[data-test="unreachable-retry"]').attributes("disabled")).toBeDefined();
	});
});
