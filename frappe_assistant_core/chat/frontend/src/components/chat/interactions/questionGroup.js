import { isApprovalInteraction } from "@/stores/chat/interactionRegime";
import { __ } from "@/utils/i18n";

function isQuestion(block) {
	return block.type === "interaction" && !isApprovalInteraction(block.interactionType);
}

/**
 * Questions FACO asked together, keyed by the first question's id.
 *
 * Parallel ask_user calls arrive as one question card each. Questions from one pause
 * sit next to each other, with only the tool calls that asked them in between, so a
 * run of two or more becomes one group. Prose or an approval ends a run, and waiting
 * and answered questions never share one.
 */
export function findQuestionGroups(blocks) {
	const groups = new Map();
	let run = [];

	const close = () => {
		if (run.length >= 2) groups.set(run[0].id, run);
		run = [];
	};

	for (const block of blocks || []) {
		if (isQuestion(block)) {
			const waiting = block.status === "pending";
			if (run.length && (run[0].status === "pending") !== waiting) close();
			run.push(block);
		} else if (block.type !== "tool_call" && block.type !== "thinking") {
			close();
		}
	}
	close();
	return groups;
}

/** An answer as the card shows it. */
export function answerText(answer) {
	if (Array.isArray(answer)) return answer.join(", ");
	if (answer === "yes") return __("Yes");
	if (answer === "no") return __("No");
	return String(answer ?? "");
}

/** The interrupt responses that carry one answer for a question card. */
export function responsesFor(block, answer) {
	return (block.interrupts || []).map((i) => ({ interruptId: i.id, response: answer }));
}

/** A question's text without markdown, for its one-line summary. */
export function plainQuestion(block) {
	return String(block.question ?? "")
		.replace(/[*_`#>]/g, "")
		.replace(/\s+/g, " ")
		.trim();
}
