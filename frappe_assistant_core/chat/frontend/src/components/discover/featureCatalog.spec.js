import { describe, expect, it } from "vitest";
import {
	FEATURE_IDS,
	availableFeatures,
	featureForPath,
	previewContent,
	featureById,
} from "./featureCatalog";

const ALL = ["agents", "knowledge", "pages", "templates"];

describe("availableFeatures", () => {
	it("leaves out Agents without workflows and Knowledge without memory", () => {
		expect(availableFeatures({}).map((f) => f.id)).toEqual(["pages", "templates"]);
		expect(availableFeatures({ workflowsEnabled: true, memoryEnabled: true }).map((f) => f.id)).toEqual(ALL);
	});
});

describe("featureForPath", () => {
	it("maps a feature's routes, and nothing else", () => {
		expect(featureForPath("/knowledge")).toBe("knowledge");
		expect(featureForPath("/agents/WF-1")).toBe("agents");
		expect(featureForPath("/pages/sales")).toBe("pages");
		expect(featureForPath("/agentsx")).toBe(null);
		expect(featureForPath("/chat")).toBe(null);
		expect(featureForPath(undefined)).toBe(null);
	});
});

describe("previewContent", () => {
	it("is the SpotlightModal shape: three uses and Give it a try / Maybe later", () => {
		for (const id of FEATURE_IDS) {
			const c = previewContent(featureById(id));
			expect(c.media).toEqual({ art: "feature", feature: id });
			expect(c.highlights).toHaveLength(3);
			expect(c.primary.label).toBe("Give it a try");
			expect(c.secondary.label).toBe("Maybe later");
		}
	});
});
