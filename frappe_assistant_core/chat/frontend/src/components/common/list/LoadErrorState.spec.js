import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import LoadErrorState from "@/components/common/list/LoadErrorState.vue";

describe("LoadErrorState", () => {
	it("shows the message and asks for a retry", async () => {
		const w = mount(LoadErrorState, { props: { message: "FAC Cloud down" } });
		expect(w.text()).toContain("FAC Cloud down");
		expect(w.attributes("role")).toBe("alert");
		await w.get("button").trigger("click");
		expect(w.emitted("retry")).toHaveLength(1);
	});
});
