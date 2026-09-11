/**
 * Routing copy for the Desk widget.
 *
 * The map literals are generated from the SPA's components/chat/routingCopy.js:
 * the widget is browser-global JS and cannot import the SPA bundle, so the
 * delivery is duplicated. widgetRouting.spec.js asserts the two are identical
 * in keys and values, so the wording cannot drift even though the file does.
 *
 * Widget disclosure is L0 + L1 only — chip and tooltip, no panel.
 */
(function () {
	const TIER_LABELS = {
		Economy: "Economy",
		Standard: "Standard",
		Premium: "Premium",
	};

	const FLOOR_REASONS = {
		attachment_document: "this turn attached a document",
		complexity: "the request needed more reasoning",
		reasoning_heavy: "the task was analysis-heavy",
		thinking_capability: "Thinking was on and needed a model that supports it",
	};

	const CEILING_SOURCES = {
		plan: "your plan's ceiling",
		posture: "your workspace's current capacity",
		none: "no ceiling",
	};

	const PICK_REASONS = {
		sticky: "Kept for continuity with this conversation.",
		cost_weighted: "The best value at this grade.",
		only_candidate: "The only model available at this grade.",
		unpriced_shortlist: "One of several models at this grade.",
		fallback_rate_limited: "The first choice was busy.",
		capability: "You chose it.",
	};

	const CLASSIFICATION_SOURCES = {
		llm: "we read the message",
		greeting: "a greeting",
		ack: "a short acknowledgement",
		continuation: "a continuation of the previous turn",
		short: "a very short message",
	};

	const NOTICES = {
		downgraded_for_credits: "Capacity was tight, so a lower grade ran this turn.",
	};

	const BAND_LABELS = {
		healthy: "healthy",
		watch: "watch",
		conserve: "conserving",
		critical: "critical",
	};

	const THINKING_NOT_APPLIED = {
		model_unsupported: "this model cannot think out loud",
		output_cap: "the response length limit left no room for it",
	};

	const SUPPRESSED_REASONS = {
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

	const JOIN = (parts) => parts.filter(Boolean).join(" · ");
	// The name the server resolved — the widget has no model catalogue.
	const modelName = (r, name) =>
		name || (r && (r.selected_model_name || r.selected_model)) || "";
	const tier = (code) => TIER_LABELS[code] || "";

	function firstFloorReason(receipt) {
		const codes = (receipt && receipt.floor && receipt.floor.reasons) || [];
		for (const code of codes) {
			if (FLOOR_REASONS[code]) return FLOOR_REASONS[code];
		}
		return "";
	}

	// Mirrors routingCopy.js: L0 is exception-only. The widget has no panel, so
	// an ordinary turn shows nothing at all here — which is the right answer
	// twice over, since a chip that opens nothing is pure noise.
	const CHIP_EXCEPTIONS = {
		saver: "Ran in saver mode",
		rule_platform: "A FAC Cloud default chose this model",
		rule_tenant: "A workspace rule chose this model",
		rule_own: "Your rule chose this model",
		fallback: "Switched models mid-answer",
	};

	// Mirrors routingCopy.js: scope decides whose rule it was.
	const RULE_OWNER = {
		Application: { chip: "rule_platform", phrase: "a FAC Cloud default" },
		Tenant: { chip: "rule_tenant", phrase: "a workspace rule" },
		User: { chip: "rule_own", phrase: "your rule" },
	};

	const ruleOwner = (scope) => RULE_OWNER[scope] || RULE_OWNER.User;

	function chipLabel(receipt) {
		if (!receipt) return "";
		if ((receipt.notices || []).indexOf("downgraded_for_credits") !== -1)
			return CHIP_EXCEPTIONS.saver;
		if (receipt.preference && receipt.preference.applied)
			return CHIP_EXCEPTIONS[ruleOwner(receipt.preference.scope).chip];
		if (receipt.fallback_from) return CHIP_EXCEPTIONS.fallback;
		return "";
	}

	function headline(receipt, name, fallbackName) {
		if (!receipt) return "";
		const ran = modelName(receipt, name);

		if (receipt.fallback_from) {
			const from =
				fallbackName || receipt.fallback_from_name || receipt.fallback_from;
			return `Started on ${from}; it was busy, so ${ran} answered.`;
		}

		const grade = tier(receipt.selected_tier);

		// Mirrors routingCopy.js: a rule that moved the turn is the reason, and
		// bound_by describes the bounds alone.
		if (receipt.preference && receipt.preference.applied) {
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
			const source = CEILING_SOURCES[receipt.ceiling && receipt.ceiling.source];
			return source
				? `${grade}, the most this turn could use under ${source}.`
				: `${grade} for this message.`;
		}

		return `${grade} matched what this message needed.`;
	}

	window.FACOWidgetRouting = {
		chipLabel,
		headline,
		CODE_MAPS: {
			TIER_LABELS,
			FLOOR_REASONS,
			CEILING_SOURCES,
			PICK_REASONS,
			CLASSIFICATION_SOURCES,
			NOTICES,
			BAND_LABELS,
			THINKING_NOT_APPLIED,
			SUPPRESSED_REASONS,
			CHIP_EXCEPTIONS,
		},
	};
})();
