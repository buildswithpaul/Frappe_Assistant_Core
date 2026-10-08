import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import WorkflowCard from "@/components/workflows/WorkflowCard.vue";
import { useUserStore } from "@/stores/userStore";

setActivePinia(createPinia());
const wf = { name: "WF-1", workflow_name: "Digest", status: "Draft" };

function mountCard() {
	// Production: the Duplicate/Delete buttons render for admins (userStore.isAdmin).
	useUserStore().isAdmin = true;
	return mount(WorkflowCard, { props: { workflow: wf } });
}

describe("WorkflowCard keyboard access", () => {
	it("keeps the root non-interactive and nests no button in a role=button", () => {
		const w = mountCard();
		expect(w.attributes("role")).toBeUndefined();
		expect(w.attributes("tabindex")).toBeUndefined();
		expect(w.find('[role="button"] button').exists()).toBe(false);
	});

	it("opens from the title button on click", async () => {
		const w = mountCard();
		const title = w.find("button.card-open-btn");
		expect(title.attributes("type")).toBe("button");
		expect(title.text()).toBe("Digest");
		await title.trigger("click");
		expect(w.emitted("click")).toHaveLength(1);
	});

	it("does not open when Duplicate or Delete is used", async () => {
		const w = mountCard();
		const actions = w.findAll("button.delete-btn");
		expect(actions).toHaveLength(2);
		for (const b of actions) {
			await b.trigger("click");
			await b.trigger("keydown", { key: "Enter" });
		}
		expect(w.emitted("click")).toBeUndefined();
		expect(w.emitted("duplicate")).toHaveLength(1);
		expect(w.emitted("delete")).toHaveLength(1);
	});
});
