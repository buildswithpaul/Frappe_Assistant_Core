import { describe, it, expect } from "vitest";
import { roleLabel, roleClass } from "./roleLabel";

describe("roleLabel", () => {
	it("labels the orchestrator as Lead", () => {
		expect(roleLabel("orchestrator")).toBe("Lead");
	});

	it("labels a helper as Helper", () => {
		expect(roleLabel("helper")).toBe("Helper");
	});

	it("labels crew roles with a middle dot and the kind", () => {
		expect(roleLabel("crew:research")).toBe("Crew · research");
		expect(roleLabel("crew:draft")).toBe("Crew · draft");
	});

	it("labels a missing role as Lead, as AR Admin does", () => {
		expect(roleLabel(null)).toBe("Lead");
		expect(roleLabel(undefined)).toBe("Lead");
	});

	it("labels a bare crew:check role", () => {
		expect(roleLabel("crew:check")).toBe("Crew · check");
	});

	it("returns an unknown role unchanged", () => {
		expect(roleLabel("auditor")).toBe("auditor");
	});
});

describe("roleClass", () => {
	it("maps crew roles to the crew class, with no colon", () => {
		expect(roleClass("crew:draft")).toBe("crew");
	});

	it("maps a missing role to the orchestrator class", () => {
		expect(roleClass(null)).toBe("orchestrator");
		expect(roleClass(undefined)).toBe("orchestrator");
	});

	it("keeps orchestrator and helper as their own class", () => {
		expect(roleClass("orchestrator")).toBe("orchestrator");
		expect(roleClass("helper")).toBe("helper");
	});
});
