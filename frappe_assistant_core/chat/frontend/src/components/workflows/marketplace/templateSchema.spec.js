import { describe, it, expect } from "vitest";
import {
	coerceVariables,
	initialValues,
	legacyRequiredTools,
	normalizeVariableSchema,
	parseRequires,
	validateVariables,
} from "./templateSchema";

const TYPED = {
	company: { type: "link", options: "Company", label: "Company", required: true },
	notify_email: { type: "email", label: "Send to", required: true, default: "finance@example.com" },
	aging_days: { type: "int", label: "Aging threshold (days)", default: 30 },
	min_amount: { type: "float", label: "Minimum amount" },
	include_draft: { type: "check", label: "Include drafts" },
	tier: { type: "select", options: ["Gold", "Silver"], label: "Tier", required: true },
	notes: { type: "text", label: "Notes" },
};

describe("normalizeVariableSchema", () => {
	it("accepts an array of plain variable names", () => {
		const fields = normalizeVariableSchema(["company", "month"], null);
		expect(fields.map((f) => [f.key, f.label, f.type])).toEqual([
			["company", "company", "text"],
			["month", "month", "text"],
		]);
	});

	it("keeps typed entries, labels and options", () => {
		const fields = normalizeVariableSchema(TYPED, null);
		const byKey = Object.fromEntries(fields.map((f) => [f.key, f]));
		expect(byKey.company).toMatchObject({ type: "link", options: "Company", label: "Company", required: true });
		expect(byKey.tier.options).toEqual(["Gold", "Silver"]);
		expect(byKey.aging_days.type).toBe("int");
	});

	it("maps legacy types and enums", () => {
		const fields = normalizeVariableSchema(
			JSON.stringify({
				company: { type: "string", required: true },
				days: { type: "integer" },
				amt: { type: "number" },
				flag: { type: "boolean" },
				mode: { enum: ["a", "b"] },
				ref: { type: "link" },
			}),
			null
		);
		expect(fields.map((f) => f.type)).toEqual(["text", "int", "float", "check", "select", "text"]);
		expect(fields[0].label).toBe("Company");
	});

	it("survives malformed or empty JSON", () => {
		expect(normalizeVariableSchema("{oops", "{also bad")).toEqual([]);
		expect(normalizeVariableSchema(null, null)).toEqual([]);
		expect(normalizeVariableSchema("", undefined)).toEqual([]);
	});

	it("reads string options one choice per line, as the server does", () => {
		const [f] = normalizeVariableSchema({ tier: { type: "select", options: "Gold, Plus\nSilver" } }, null);
		expect(f.options).toEqual(["Gold, Plus", "Silver"]);
	});

	it("takes defaults from default_variables when the schema has none", () => {
		const [f] = normalizeVariableSchema({ days: { type: "int" } }, '{"days": "45"}');
		expect(f.default).toBe("45");
	});
});

describe("initialValues", () => {
	it("prefills plain defaults but never a link or an email", () => {
		const values = initialValues(normalizeVariableSchema(TYPED, { company: "Your Company" }));
		expect(values.company).toBe("");
		expect(values.notify_email).toBe("");
		expect(values.aging_days).toBe(30);
		expect(values.include_draft).toBe(false);
	});
});

describe("validateVariables", () => {
	const fields = normalizeVariableSchema(TYPED, null);

	it("names every missing required field", () => {
		const errors = validateVariables(fields, initialValues(fields));
		expect(errors.company).toBe("Company is required");
		expect(errors.notify_email).toBe("Send to is required");
		expect(errors.tier).toBe("Tier is required");
		expect(errors.notes).toBeUndefined();
	});

	it("checks emails, numbers and choices", () => {
		const errors = validateVariables(fields, {
			company: "Northwind",
			notify_email: "not-an-email",
			aging_days: "3.5",
			min_amount: "abc",
			tier: "Bronze",
		});
		expect(errors.notify_email).toBe("Send to must be an email address");
		expect(errors.aging_days).toBe("Aging threshold (days) must be a whole number");
		expect(errors.min_amount).toBe("Minimum amount must be a number");
		expect(errors.tier).toBe("Tier must be one of the listed options");
	});
});

describe("coerceVariables", () => {
	it("sends typed values and drops empty optional ones", () => {
		const fields = normalizeVariableSchema(TYPED, null);
		expect(
			coerceVariables(fields, {
				company: "Northwind",
				notify_email: " ops@northwind.example ",
				aging_days: "30",
				min_amount: "",
				include_draft: true,
				tier: "Gold",
				notes: "",
			})
		).toEqual({
			company: "Northwind",
			notify_email: "ops@northwind.example",
			aging_days: 30,
			include_draft: true,
			tier: "Gold",
		});
	});

	it("is null when there is nothing to send", () => {
		expect(coerceVariables([], {})).toBe(null);
	});
});

describe("parseRequires", () => {
	it("reads the requires block from a string or an object", () => {
		const raw = {
			modules: ["Accounts"],
			reports: ["Accounts Receivable Summary"],
			tools: ["generate_report"],
			write_tools: ["send_email"],
			min_erpnext: "15",
		};
		const expected = {
			modules: ["Accounts"],
			reports: ["Accounts Receivable Summary"],
			tools: ["generate_report"],
			writeTools: ["send_email"],
			minErpnext: "15",
		};
		expect(parseRequires(raw)).toEqual(expected);
		expect(parseRequires(JSON.stringify(raw))).toEqual(expected);
		expect(parseRequires("{bad")).toBe(null);
		expect(parseRequires({ tools: "a, b" }).tools).toEqual(["a", "b"]);
	});
});

describe("legacyRequiredTools", () => {
	it("accepts a list, a JSON string or a comma list", () => {
		expect(legacyRequiredTools({ required_tools: ["a"] })).toEqual(["a"]);
		expect(legacyRequiredTools({ required_tools: '["a","b"]' })).toEqual(["a", "b"]);
		expect(legacyRequiredTools({ required_tools: "a, b" })).toEqual(["a", "b"]);
		expect(legacyRequiredTools({})).toEqual([]);
	});
});
