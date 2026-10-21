import { describe, it, expect } from "vitest";
import { describeCondition, isConditionKey } from "./conditions";

describe("describeCondition", () => {
	it("reads a comparison with a number", () => {
		expect(describeCondition("eval:doc.base_grand_total > 100000")).toBe("when Base Grand Total is over 100000");
		expect(describeCondition("eval:doc.qty < 5")).toBe("when Qty is under 5");
		expect(describeCondition("eval:doc.discount_amount >= 10.5")).toBe("when Discount Amount is at least 10.5");
		expect(describeCondition("eval:doc.qty <= 5")).toBe("when Qty is at most 5");
	});

	it("reads an equality with a number or a quoted string", () => {
		expect(describeCondition("eval:doc.qty == 3")).toBe("when Qty is 3");
		expect(describeCondition("eval:doc.status === 'Open'")).toBe("when Status is Open");
		expect(describeCondition('eval:doc.status != "Closed"')).toBe("when Status is not Closed");
	});

	it("reads an empty quoted value as empty or set, never as a blank", () => {
		expect(describeCondition("eval:doc.status == ''")).toBe("when Status is empty");
		expect(describeCondition('eval:doc.status === ""')).toBe("when Status is empty");
		expect(describeCondition("eval:doc.status != ''")).toBe("when Status is set");
	});

	it("does not throw on an ordering comparison with an empty string, or on garbage", () => {
		expect(describeCondition("eval:doc.x > ''")).toBe("Has a condition");
		expect(describeCondition('eval:doc.x <= ""')).toBe("Has a condition");
		expect(describeCondition({ not: "a string" })).toBe("Has a condition");
		expect(describeCondition(null)).toBe("Has a condition");
	});

	it("reads a bare field as set", () => {
		expect(describeCondition("eval:doc.customer_po")).toBe("when Customer Po is set");
	});

	it("never guesses at anything else", () => {
		expect(describeCondition("eval:doc.a > 1 && doc.b")).toBe("Has a condition");
		expect(describeCondition("eval:!doc.is_return")).toBe("Has a condition");
		expect(describeCondition("customer_po")).toBe("Has a condition");
		expect(describeCondition("")).toBe("Has a condition");
	});
});

describe("isConditionKey", () => {
	it("names the three condition fields", () => {
		expect(["depends_on", "mandatory_depends_on", "read_only_depends_on"].every(isConditionKey)).toBe(true);
		expect(isConditionKey("label")).toBe(false);
	});
});
