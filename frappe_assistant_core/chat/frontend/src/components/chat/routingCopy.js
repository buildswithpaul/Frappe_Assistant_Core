/**
 * Every user-facing word about routing, in one place.
 *
 * The server sends closed codes, never sentences — so translation stays here
 * and the same rule renders identically at L0, L1 and L2. A code with no
 * string renders as nothing; routingCopy.spec.js asserts each set is complete
 * and carries nothing extra.
 */

export const TIER_LABELS = {
	Economy: "Economy",
	Standard: "Standard",
	Premium: "Premium",
};

export const FLOOR_REASONS = {
	attachment_document: "this turn attached a document",
	complexity: "the request needed more reasoning",
	reasoning_heavy: "the task was analysis-heavy",
	thinking_capability: "Thinking was on and needed a model that supports it",
};

export const CEILING_SOURCES = {
	plan: "your plan's ceiling",
	posture: "your workspace's current capacity",
	none: "no ceiling",
};

// Whole sentences: the panel joins these with the thinking and also-ran
// clauses, and a bare fragment reads as "…at this grade Thinking was on."
export const PICK_REASONS = {
	sticky: "Kept for continuity with this conversation.",
	cost_weighted: "The best value at this grade.",
	only_candidate: "The only model available at this grade.",
	// Said when the grade had several models but their rates are not
	// review-stamped, so cost could not choose between them. It must not claim
	// anything about availability — the old code did, on turns whose own
	// receipt recorded three candidates.
	unpriced_shortlist: "One of several models at this grade.",
	fallback_rate_limited: "The first choice was busy.",
	capability: "You chose it.",
};

// Said in the "what the task needed" row when the level came from earlier in
// the conversation rather than from this message.
export const TIER_HELD_DETAIL = "Held from earlier in this conversation.";

export const CLASSIFICATION_SOURCES = {
	llm: "we read the message",
	greeting: "a greeting",
	ack: "a short acknowledgement",
	continuation: "a continuation of the previous turn",
	short: "a very short message",
};

export const NOTICES = {
	downgraded_for_credits: "Capacity was tight, so a lower grade ran this turn.",
};

export const BAND_LABELS = {
	healthy: "healthy",
	watch: "watch",
	conserve: "conserving",
	critical: "critical",
};

export const THINKING_NOT_APPLIED = {
	model_unsupported: "this model cannot think out loud",
	output_cap: "the response length limit left no room for it",
};

// Increment C populates `preference`; the strings exist now so C adds logic
// only. Until then every one of these renders against a null and shows
// nothing — see routingRows.
export const SUPPRESSED_REASONS = {
	capped_by_floor: "this turn needed a higher grade than your rule asks for",
	band_watch: "your workspace is watching capacity",
	band_conserve: "your workspace is conserving capacity",
	band_critical: "your workspace is at its capacity limit",
	capability_vision: "the attachment needed a model that can see images",
	capability_context: "the conversation was too long for that grade",
	capability_tools: "the tools this turn used need a more capable model",
	capability_thinking: "Thinking was on and that grade cannot do it",
	plan_ceiling: "your plan does not reach that grade",
	clamped_one_step: "we moved one step, because this rule matches on a keyword",
	classifier_default: "we used our default settings for this message",
	shadow: "it is still learning — an admin can take it live in Settings → Model routing",
	auto_suspended: "auto selection is paused for this workspace",
	tier_unreachable: "that grade is no longer available",
};

// Credits are a float, so the raw value renders as e.g. "12.340000000001".
export function creditsLabel(credits) {
	const n = Number(credits) || 0;
	return `${n >= 10 ? Math.round(n) : Math.round(n * 10) / 10} credits`;
}

function modelName(receipt, name) {
	// The caller's catalogue first, then the name the server resolved for the
	// surfaces that have no catalogue, then the raw id as a last resort.
	return name || receipt?.selected_model_name || receipt?.selected_model || "";
}

function tier(code) {
	return TIER_LABELS[code] || "";
}

function firstFloorReason(receipt) {
	const codes = receipt?.floor?.reasons || [];
	for (const code of codes) {
		if (FLOOR_REASONS[code]) return FLOOR_REASONS[code];
	}
	return "";
}

export function hasRouting(message) {
	return Boolean(message && message.role !== "user" && message.routing);
}

// L0 is exception-only. A turn that went the way it should is not news, and a
// grade printed under every reply reads as a verdict on the answer: the member
// sees "Economy" and hears "you got the cheap one" on the turns where Economy
// was simply right. These fire only when something the member did not choose
// changed the turn.
export const CHIP_EXCEPTIONS = {
	saver: "Ran in saver mode",
	rule_platform: "A FAC Cloud default chose this model",
	rule_tenant: "A workspace rule chose this model",
	rule_own: "Your rule chose this model",
	fallback: "Switched models mid-answer",
};

// Scope decides whose rule it was, and getting this wrong is the failure the
// receipt exists to prevent: telling a member their workspace chose something
// FAC Cloud chose sends them to an admin who cannot find the rule.
const RULE_OWNER = {
	Application: { chip: "rule_platform", phrase: "a FAC Cloud default" },
	Tenant: { chip: "rule_tenant", phrase: "a workspace rule" },
	User: { chip: "rule_own", phrase: "your rule" },
};

export function ruleOwner(scope) {
	return RULE_OWNER[scope] || RULE_OWNER.User;
}

// The panel still needs a door. Credits carry it wherever there is a figure to
// click; this is the door on a turn that cost nothing.
export const CHIP_DEFAULT = "How this ran";

export function routingChipLabel(receipt) {
	if (!receipt) return "";
	// Saver mode outranks the rest: it is the only one with an action behind
	// it, and a member who lost a grade to capacity needs that before news of
	// which model answered.
	if ((receipt.notices || []).includes("downgraded_for_credits"))
		return CHIP_EXCEPTIONS.saver;
	if (receipt.preference?.applied)
		return CHIP_EXCEPTIONS[ruleOwner(receipt.preference.scope).chip];
	if (receipt.fallback_from) return CHIP_EXCEPTIONS.fallback;
	return "";
}

export function routingHeadline(receipt, name, fallbackName) {
	if (!receipt) return "";
	const ran = modelName(receipt, name);

	if (receipt.fallback_from) {
		const from =
			fallbackName || receipt.fallback_from_name || receipt.fallback_from;
		return `Started on ${from}; it was busy, so ${ran} answered.`;
	}

	const grade = tier(receipt.selected_tier);

	// A rule that actually moved the turn is the reason, and saying so matters
	// more than naming a bound: `bound_by` describes the bounds alone, so
	// without this the sentence credits whichever bound happened to be nearest.
	if (receipt.preference?.applied) {
		const whose = ruleOwner(receipt.preference.scope).phrase;
		return `${grade}, because ${whose} asked for it.`;
	}

	if (receipt.bound_by === "floor") {
		const why = firstFloorReason(receipt);
		// The floor sentence ALONE. A ceiling that did not bind is not
		// mentioned at any disclosure level.
		return why ? `${grade}, because ${why}.` : `${grade} for this message.`;
	}

	if (receipt.bound_by === "ceiling") {
		const source = CEILING_SOURCES[receipt.ceiling?.source];
		return source
			? `${grade}, the most this turn could use under ${source}.`
			: `${grade} for this message.`;
	}

	return `${grade} matched what this message needed.`;
}

export function routingRows(receipt, name) {
	if (!receipt) return [];
	const rows = [];

	const source = CLASSIFICATION_SOURCES[receipt.classification?.source];
	rows.push({
		key: "read",
		label: "What we read",
		// Never a self-reported failure. The diagnostic phrasing for a
		// classifier that timed out lives in the admin integrity view.
		value: source
			? `${source[0].toUpperCase()}${source.slice(1)}.`
			: "Routed with our default settings for this message.",
		detail: "",
	});

	const why = firstFloorReason(receipt);
	rows.push({
		key: "needed",
		label: "What the task needed",
		// `needed_tier`, not the floor. The floor only rises for an
		// attachment, a complex request, an analysis-heavy task or Thinking,
		// so a moderate turn left it at Economy while Standard ran — and this
		// row told the member the two contradicted each other.
		value:
			tier(receipt.needed_tier) ||
			tier(receipt.floor?.tier) ||
			tier(receipt.target_tier),
		detail: why
			? `Because ${why}.`
			: receipt.tier_held
			? TIER_HELD_DETAIL
			: "",
	});

	// Rendered ONLY when the ceiling actually bound. A ceiling that did not
	// bind is noise that reads as a warning.
	if (receipt.bound_by === "ceiling") {
		const band = receipt.band ? BAND_LABELS[receipt.band] : null;
		rows.push({
			key: "allowed",
			label: "What was allowed",
			value: tier(receipt.ceiling?.tier),
			detail: band ? `Capacity: ${band}.` : "",
		});
	}

	const t = receipt.thinking || {};
	const parts = [PICK_REASONS[receipt.pick_reason]];
	if (t.requested) {
		parts.push(
			t.applied
				? "Thinking was on."
				: `Thinking was on, but ${
						THINKING_NOT_APPLIED[t.not_applied_reason] || "it did not apply here"
				  }.`
		);
	}
	if (receipt.also_ran?.length) {
		parts.push(`This turn also ran: ${receipt.also_ran.join(", ")}.`);
	}
	// "Capped" is wrong for a rule still in its trial — nothing capped it, it
	// was never applied. Every other reason here really is a cap.
	const suppressedReason = receipt.preference?.suppressed_reason;
	const suppressed = SUPPRESSED_REASONS[suppressedReason];
	if (suppressed) {
		parts.push(
			suppressedReason === "shadow"
				? `Your rule did not run: ${suppressed}.`
				: `Your rule was capped: ${suppressed}.`,
		);
	}

	// No credits figure here. The receipt describes ONE stream cycle, and an
	// approval or a delegation makes a turn several — so receipt.credits.actual
	// is a fraction of what the turn cost, and printing it under a footer chip
	// showing the real total told the user two different numbers. The chip owns
	// cost (message.credits_used, summed across cycles); this panel owns routing.
	rows.push({
		key: "ran",
		label: "What ran",
		value: modelName(receipt, name),
		detail: parts.filter(Boolean).join(" "),
	});

	return rows;
}
