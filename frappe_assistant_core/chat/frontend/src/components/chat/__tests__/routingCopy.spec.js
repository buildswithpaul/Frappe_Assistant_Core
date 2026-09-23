import { describe, it, expect } from "vitest";
import {
	TIER_LABELS,
	FLOOR_REASONS,
	CEILING_SOURCES,
	PICK_REASONS,
	CLASSIFICATION_SOURCES,
	NOTICES,
	BAND_LABELS,
	THINKING_NOT_APPLIED,
	SUPPRESSED_REASONS,
	creditsLabel,
	hasRouting,
	routingChipLabel,
	routingHeadline,
	routingRows,
} from "../routingCopy.js";

// The closed sets, read off the AR tree — routing_policy.py, routing_stats.py
// and routing_receipt.py. A code with no string renders as nothing, which is
// silence by construction; that is what this file exists to prevent.
const CODES = {
	TIER_LABELS: ["Economy", "Standard", "Premium"],
	FLOOR_REASONS: [
		"attachment_document",
		"complexity",
		"reasoning_heavy",
		"thinking_capability",
	],
	CEILING_SOURCES: ["plan", "posture", "none"],
	PICK_REASONS: [
		"sticky",
		"cost_weighted",
		"only_candidate",
		"unpriced_shortlist",
		"fallback_rate_limited",
		"capability",
	],
	CLASSIFICATION_SOURCES: ["llm", "greeting", "ack", "continuation", "short"],
	NOTICES: ["downgraded_for_credits"],
	BAND_LABELS: ["healthy", "watch", "conserve", "critical"],
	THINKING_NOT_APPLIED: ["model_unsupported", "output_cap"],
	SUPPRESSED_REASONS: [
		"capped_by_floor",
		"band_watch",
		"band_conserve",
		"band_critical",
		"capability_vision",
		"capability_context",
		"capability_tools",
		"capability_thinking",
		"plan_ceiling",
		"clamped_one_step",
		"classifier_default",
		"shadow",
		"auto_suspended",
		"tier_unreachable",
	],
};

const MAPS = {
	TIER_LABELS,
	FLOOR_REASONS,
	CEILING_SOURCES,
	PICK_REASONS,
	CLASSIFICATION_SOURCES,
	NOTICES,
	BAND_LABELS,
	THINKING_NOT_APPLIED,
	SUPPRESSED_REASONS,
};

function receipt(over = {}) {
	return {
		v: 1,
		mode: "auto",
		incomplete: false,
		selected_model: "claude-sonnet-4-6",
		selected_tier: "Standard",
		fallback_from: null,
		classification: {
			complexity: "moderate",
			task_type: "general",
			source: "llm",
			floor_applied: true,
		},
		floor: { tier: "Standard", reasons: ["attachment_document"] },
		ceiling: { tier: "Premium", source: "plan", reasons: [] },
		bound_by: "floor",
		target_tier: "Standard",
		band: null,
		band_disclosed: "capacity_managed",
		shortlist_size: 8,
		pick_reason: "cost_weighted",
		notices: [],
		thinking: {
			requested: false,
			applied: false,
			effort: null,
			effective_budget: null,
			not_applied_reason: null,
		},
		credits: { actual: 12 },
		cycles: 1,
		also_ran: [],
		preference: null,
		preference_source: "none",
		...over,
	};
}

describe("the catalogue is closed and complete", () => {
	for (const [name, codes] of Object.entries(CODES)) {
		it(`${name} has a string for every member`, () => {
			for (const code of codes) {
				expect(MAPS[name][code], `${name}.${code}`).toBeTruthy();
				expect(typeof MAPS[name][code]).toBe("string");
			}
		});

		it(`${name} carries no strings for codes that do not exist`, () => {
			expect(Object.keys(MAPS[name]).sort()).toEqual([...codes].sort());
		});
	}
});

describe("hasRouting", () => {
	it("is false for a user bubble and for a bubble with no receipt", () => {
		expect(hasRouting({ role: "user" })).toBe(false);
		expect(hasRouting({ role: "assistant" })).toBe(false);
		expect(hasRouting({ role: "assistant", routing: null })).toBe(false);
	});

	it("is true once the receipt is attached, even while incomplete", () => {
		expect(
			hasRouting({ role: "assistant", routing: receipt({ incomplete: true }) })
		).toBe(true);
	});
});

describe("L0 — the chip is exception-only", () => {
	it("says NOTHING on a turn that went the way it should", () => {
		// The load-bearing assertion of the whole level. A grade printed under
		// every reply is a verdict on the answer, and on most turns the verdict
		// would be "Economy" for a question that deserved Economy.
		expect(routingChipLabel(receipt())).toBe("");
	});

	it("stays silent on an explicit turn — the member chose the model", () => {
		expect(routingChipLabel(receipt({ mode: "explicit" }))).toBe("");
	});

	it("says nothing without a receipt", () => {
		expect(routingChipLabel(null)).toBe("");
	});

	it("names saver mode when capacity took the grade down", () => {
		const r = receipt({ notices: ["downgraded_for_credits"] });
		expect(routingChipLabel(r)).toBe("Ran in saver mode");
	});

	it("names a FAC Cloud default as ours, never as the workspace's", () => {
		// The worst thing this level can say. A member told their workspace
		// chose the model goes to an admin who cannot find the rule, because
		// the rule is ours and lives in AR Admin.
		const r = receipt({ preference: { applied: true, scope: "Application" } });
		expect(routingChipLabel(r)).toBe("A FAC Cloud default chose this model");
		expect(routingChipLabel(r)).not.toContain("workspace");
	});

	it("names a workspace rule, and separates it from the member's own", () => {
		const tenant = receipt({ preference: { applied: true, scope: "Tenant" } });
		const own = receipt({ preference: { applied: true, scope: "User" } });
		expect(routingChipLabel(tenant)).toBe("A workspace rule chose this model");
		expect(routingChipLabel(own)).toBe("Your rule chose this model");
	});

	it("stays silent for a rule that matched but changed nothing", () => {
		// Shadow mode: recorded, not applied. Nothing happened to the member.
		const r = receipt({ preference: { applied: false, scope: "Tenant" } });
		expect(routingChipLabel(r)).toBe("");
	});

	it("names a mid-answer model switch", () => {
		const r = receipt({ fallback_from: "claude-opus-4-6" });
		expect(routingChipLabel(r)).toBe("Switched models mid-answer");
	});

	it("puts saver mode ahead of a rule and a fallback on the same turn", () => {
		// Only one line fits, and only one of the three has an action behind it.
		const r = receipt({
			notices: ["downgraded_for_credits"],
			preference: { applied: true, scope: "Tenant" },
			fallback_from: "claude-opus-4-6",
		});
		expect(routingChipLabel(r)).toBe("Ran in saver mode");
	});

	it("never leaks a model codename or a grade at this level", () => {
		for (const r of [
			receipt({ notices: ["downgraded_for_credits"] }),
			receipt({ preference: { applied: true, scope: "Tenant" } }),
			receipt({ fallback_from: "claude-opus-4-6" }),
		]) {
			const label = routingChipLabel(r);
			expect(label).not.toMatch(/claude|gpt|sonnet|opus/i);
			for (const grade of ["Economy", "Standard", "Premium"]) {
				expect(label).not.toContain(grade);
			}
		}
	});
});

describe("L1 — the one line", () => {
	it("gives the floor sentence ALONE when the floor bound", () => {
		const line = routingHeadline(receipt(), "Sonnet 4.6");
		expect(line).toContain("Standard");
		expect(line).toContain("attached a document");
		// The ceiling did not bind. Naming it here reads as "I pay for Premium
		// and got Standard" — the most expensive misreading this can produce.
		expect(line).not.toContain("Premium");
	});

	it("names the ceiling only when the ceiling bound", () => {
		const r = receipt({
			bound_by: "ceiling",
			ceiling: { tier: "Standard", source: "plan", reasons: [] },
			selected_tier: "Standard",
			floor: { tier: "Premium", reasons: ["complexity"] },
		});
		expect(routingHeadline(r, "Sonnet 4.6")).toContain("plan");
	});

	it("says nothing bound when nothing did", () => {
		const r = receipt({ bound_by: "neither", floor: { tier: "Economy", reasons: [] } });
		expect(routingHeadline(r, "Sonnet 4.6")).toMatch(/matched/i);
	});

	it("explains a mid-turn fallback from both model names", () => {
		const r = receipt({ fallback_from: "claude-opus-4-6", pick_reason: "fallback_rate_limited" });
		const line = routingHeadline(r, "Sonnet 4.6", "Opus 4.6");
		expect(line).toContain("Opus 4.6");
		expect(line).toContain("Sonnet 4.6");
	});

	it("names the rule when a rule is what moved the turn", () => {
		// Otherwise the sentence credits a bound that did not bind — the panel
		// would tell a member their plan capped them when an admin rule did.
		const r = receipt({
			bound_by: "neither",
			selected_tier: "Economy",
			preference: { applied: true, scope: "Tenant", target_tier: "Economy" },
		});
		const line = routingHeadline(r, "Haiku 4.5");
		expect(line).toMatch(/rule/i);
		expect(line).toContain("Economy");
		expect(line).not.toContain("ceiling");
		expect(line).not.toContain("plan");
	});

	it("says whose rule it was", () => {
		const mine = routingHeadline(
			receipt({ bound_by: "neither", selected_tier: "Economy",
				preference: { applied: true, scope: "User", target_tier: "Economy" } }), "H");
		const team = routingHeadline(
			receipt({ bound_by: "neither", selected_tier: "Economy",
				preference: { applied: true, scope: "Tenant", target_tier: "Economy" } }), "H");
		expect(team).toMatch(/workspace|team/i);
		expect(mine).not.toMatch(/workspace/i);
	});

	it("ignores a rule that did not apply", () => {
		const r = receipt({
			preference: { applied: false, suppressed_reason: "shadow",
				scope: "Tenant", target_tier: "Economy" },
		});
		expect(routingHeadline(r, "S")).not.toMatch(/rule/i);
	});

	it("never renders a raw code", () => {
		const line = routingHeadline(receipt(), "Sonnet 4.6");
		expect(line).not.toContain("attachment_document");
		expect(line).not.toMatch(/_/);
	});
});

describe("L2 — the rows", () => {
	it("gives the four rows in the order a person asks", () => {
		const keys = routingRows(receipt(), "Sonnet 4.6").map((r) => r.key);
		expect(keys).toEqual(["read", "needed", "ran"]);
	});

	it("adds the allowed row ONLY when the ceiling bound", () => {
		const r = receipt({
			bound_by: "ceiling",
			ceiling: { tier: "Standard", source: "plan", reasons: [] },
		});
		expect(routingRows(r, "Sonnet 4.6").map((x) => x.key)).toEqual([
			"read",
			"needed",
			"allowed",
			"ran",
		]);
	});

	it("keeps the band out of the allowed row when it was withheld", () => {
		const r = receipt({
			bound_by: "ceiling",
			ceiling: { tier: "Standard", source: "posture", reasons: [] },
			band: null,
			band_disclosed: "capacity_managed",
		});
		const allowed = routingRows(r, "Sonnet 4.6").find((x) => x.key === "allowed");
		expect(allowed.detail).toBeFalsy();
	});

	it("names the band for an admin-capable viewer", () => {
		const r = receipt({
			bound_by: "ceiling",
			ceiling: { tier: "Standard", source: "posture", reasons: [] },
			band: "conserve",
			band_disclosed: "full",
		});
		const allowed = routingRows(r, "Sonnet 4.6").find((x) => x.key === "allowed");
		expect(allowed.detail).toBeTruthy();
	});

	it("uses neutral wording when the classifier fell back to defaults", () => {
		const r = receipt({
			classification: { complexity: "moderate", task_type: "general", source: "llm", floor_applied: false },
		});
		const read = routingRows(r, "Sonnet 4.6").find((x) => x.key === "read");
		expect(read.value).toBeTruthy();
	});

	it("reports thinking honestly when it was asked for and did nothing", () => {
		const r = receipt({
			thinking: {
				requested: true,
				applied: false,
				effort: null,
				effective_budget: null,
				not_applied_reason: "model_unsupported",
			},
		});
		const ran = routingRows(r, "Sonnet 4.6").find((x) => x.key === "ran");
		expect(ran.detail).toContain(THINKING_NOT_APPLIED.model_unsupported);
	});

	it("joins the ran-row clauses as whole sentences", () => {
		// The detail concatenates pick reason + thinking + also-ran; a bare
		// fragment renders as "…at this grade Thinking was on."
		const r = receipt({
			pick_reason: "only_candidate",
			thinking: { requested: true, applied: true },
		});
		const ran = routingRows(r, "S").find((x) => x.key === "ran");
		expect(ran.detail).toBe("The only model available at this grade. Thinking was on.");
	});

	it("never prints a credits figure, however tempting the receipt makes it", () => {
		// The receipt covers ONE stream cycle. An approval or a delegation makes
		// a turn several, so receipt.credits.actual is a fraction of the turn —
		// and it sat directly under a chip showing the real total, telling the
		// user two different numbers for the same message. Cost belongs to the
		// chip (message.credits_used); this panel explains routing.
		const rows = routingRows(receipt({ credits: { actual: 196 } }), "Sonnet 4.6");
		expect(JSON.stringify(rows)).not.toMatch(/credits/i);
		expect(rows.find((x) => x.key === "ran").value).toBe("Sonnet 4.6");
	});

	it("names the whole-turn model list rather than a count", () => {
		const r = receipt({ also_ran: ["claude-opus-4-6"], cycles: 2 });
		const ran = routingRows(r, "Sonnet 4.6").find((x) => x.key === "ran");
		expect(ran.detail).toContain("claude-opus-4-6");
		expect(ran.detail).not.toMatch(/\+\s*1 more/);
	});

	it("shows no shortlist size and no expected credits anywhere", () => {
		const text = JSON.stringify(routingRows(receipt(), "Sonnet 4.6"));
		expect(text).not.toContain("8 models");
		expect(text).not.toMatch(/expected/i);
	});

	it("renders nothing at all without a receipt", () => {
		expect(routingRows(null, null)).toEqual([]);
	});
});

describe("creditsLabel — the footer chip's figure", () => {
	// Still exported for MessageFooter after the panel stopped showing credits:
	// the chip is now the only place a turn's cost is written, so its rounding
	// is the only rounding left to get wrong.
	it("rounds a raw float instead of printing 12.340000000001", () => {
		expect(creditsLabel(12.340000000001)).toBe("12 credits");
	});

	it("keeps one decimal below ten, where rounding to zero would read as free", () => {
		expect(creditsLabel(3.456)).toBe("3.5 credits");
	});

	it("treats a missing figure as zero rather than NaN", () => {
		expect(creditsLabel(undefined)).toBe("0 credits");
		expect(creditsLabel(null)).toBe("0 credits");
	});
});

describe("§3.6 — what must never be shown", () => {
	it("no presenter emits a price, a rate or a review timestamp", () => {
		const text = [
			routingChipLabel(receipt({ notices: ["downgraded_for_credits"] })),
			routingHeadline(receipt(), "Sonnet 4.6"),
			JSON.stringify(routingRows(receipt(), "Sonnet 4.6")),
		].join(" ");
		for (const forbidden of ["$", "USD", "per million", "price", "rate", "reviewed"]) {
			expect(text.toLowerCase()).not.toContain(forbidden.toLowerCase());
		}
	});
});

describe("the needed row reports the level, not the floor", () => {
	// The floor rises only for an attachment, a complex request, an
	// analysis-heavy task or Thinking. A moderate message routes to Standard
	// through the classifier, leaving the floor at Economy — so this row used
	// to tell the member the task needed Economy while Standard ran, on every
	// moderate turn that was not ceiling-bound.
	const MODERATE = {
		needed_tier: "Standard",
		floor: { tier: "Economy", reasons: [] },
		target_tier: "Standard",
	};

	function needed(over) {
		const rows = routingRows(receipt({ ...MODERATE, ...over }), "Sonnet 4.6");
		return rows.find((r) => r.key === "needed");
	}

	it("shows what the turn called for, not the floor beneath it", () => {
		expect(needed().value).toBe("Standard");
	});

	it("keeps needed and allowed as two numbers on a capped turn", () => {
		const rows = routingRows(
			receipt({
				needed_tier: "Premium",
				floor: { tier: "Premium", reasons: ["complexity"] },
				ceiling: { tier: "Standard", source: "plan", reasons: [] },
				bound_by: "ceiling",
				target_tier: "Standard",
			}),
			"Sonnet 4.6"
		);
		expect(rows.find((r) => r.key === "needed").value).toBe("Premium");
		expect(rows.find((r) => r.key === "allowed").value).toBe("Standard");
	});

	it("falls back to the floor on a receipt written before the fix", () => {
		const rows = routingRows(
			receipt({ needed_tier: undefined, floor: { tier: "Standard", reasons: [] } }),
			"Sonnet 4.6"
		);
		expect(rows.find((r) => r.key === "needed").value).toBe("Standard");
	});

	it("says where the level came from when it was held", () => {
		expect(needed({ tier_held: true }).detail).toBe(
			"Held from earlier in this conversation."
		);
	});

	it("prefers the floor reason over the held note", () => {
		const row = needed({
			tier_held: true,
			floor: { tier: "Standard", reasons: ["attachment_document"] },
		});
		expect(row.detail).toContain("attached a document");
	});
});

describe("only_candidate is a claim about how many models there were", () => {
	it("is not said when the receipt itself recorded several", () => {
		// The defect: only_candidate was the else branch for unverified rates,
		// so this sentence appeared beside a shortlist of three — falsifiable
		// by opening the model picker.
		const rows = routingRows(
			receipt({ pick_reason: "unpriced_shortlist", shortlist_size: 3 }),
			"Sonnet 4.6"
		);
		const ran = rows.find((r) => r.key === "ran");
		expect(ran.detail).toContain("One of several models at this grade.");
		expect(ran.detail).not.toContain("only model");
	});

	it("still says it when there genuinely was one", () => {
		const rows = routingRows(
			receipt({ pick_reason: "only_candidate", shortlist_size: 1 }),
			"Sonnet 4.6"
		);
		expect(rows.find((r) => r.key === "ran").detail).toContain(
			"The only model available at this grade."
		);
	});
});
