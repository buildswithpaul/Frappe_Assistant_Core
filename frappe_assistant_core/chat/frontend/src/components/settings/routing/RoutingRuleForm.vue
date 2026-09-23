<template>
	<form class="rule-form" @submit.prevent="submit">
		<div class="rule-row">
			<label class="rule-field">
				<span class="rule-label">When</span>
				<select v-model="matchKind" class="rule-input">
					<option value="keyword">a message mentions</option>
					<option value="doctype">the page is</option>
					<option value="task_type">the task is</option>
				</select>
			</label>

			<label class="rule-field rule-field-grow">
				<span class="rule-label">{{ valueLabel }}</span>
				<input
					v-model="matchValue"
					class="rule-input"
					type="text"
					:placeholder="valuePlaceholder"
				/>
			</label>

			<label class="rule-field">
				<span class="rule-label">use</span>
				<select v-model="targetTier" class="rule-input">
					<option v-for="t in TIERS" :key="t" :value="t">{{ t }}</option>
				</select>
			</label>
		</div>

		<p v-if="hint" class="rule-hint">{{ hint }}</p>

		<p v-if="forecast && forecast.cost_multiplier" class="rule-forecast">
			{{ forecastSentence }}
			<span v-if="!forecast.rates_reviewed" class="rule-forecast-caveat">
				Based on rates nobody has reviewed yet.
			</span>
		</p>

		<div class="rule-actions">
			<button type="submit" class="rule-save" :disabled="!canSubmit || saving">
				{{ saving ? "Saving…" : confirmNeeded ? "Yes, add it" : "Add rule" }}
			</button>
			<button v-if="confirmNeeded" type="button" class="rule-cancel" @click="reset">
				Cancel
			</button>
		</div>
	</form>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { api } from "@/api/client";

const emit = defineEmits(["created", "error"]);

const TIERS = ["Economy", "Standard", "Premium"];

const matchKind = ref("keyword");
const matchValue = ref("");
const targetTier = ref("Economy");
const forecast = ref(null);
const saving = ref(false);
// A material increase is confirmed twice: the first press asks, the second
// commits. Nothing is saved on the first press.
const confirmNeeded = ref(false);

const VALUE_LABEL = {
	doctype: "this record type",
	task_type: "this task type",
	keyword: "these words",
};
const valueLabel = computed(() => VALUE_LABEL[matchKind.value] || "these words");
const valuePlaceholder = computed(() =>
	matchKind.value === "doctype"
		? "Sales Invoice"
		: matchKind.value === "task_type"
			? "structured"
			: "invoice overdue"
);

// The server refuses task_type "general" outright, so the button should not
// invite a press that can only fail.
const refused = computed(
	() => matchKind.value === "task_type" && matchValue.value.trim() === "general"
);
const canSubmit = computed(
	() => matchValue.value.trim().length > 0 && !refused.value
);

const hint = computed(() => {
	if (matchKind.value === "keyword" && matchValue.value.trim().split(/\s+/).length > 1) {
		// Stated because the opposite is the intuitive reading.
		return "Every word must appear — more words means the rule matches less often.";
	}
	if (refused.value) {
		return "“general” covers most conversations — pick something narrower.";
	}
	return "";
});

const forecastSentence = computed(() => {
	const m = forecast.value?.cost_multiplier;
	if (!m) return "";
	return m >= 1
		? `Turns matching this rule would cost about ${m}× what they do now.`
		: `Turns matching this rule would cost about ${Math.round((1 - m) * 100)}% less.`;
});

watch([matchKind, matchValue, targetTier], () => {
	confirmNeeded.value = false;
	forecast.value = null;
});

async function submit() {
	if (!canSubmit.value) return;

	// Forecast first, and stop for a confirmation when it is material.
	if (!confirmNeeded.value) {
		try {
			forecast.value = await api.routingPreferences.forecast(
				matchKind.value, matchValue.value.trim(), targetTier.value
			);
		} catch {
			forecast.value = null;
		}
		if (forecast.value?.requires_confirmation) {
			confirmNeeded.value = true;
			return;
		}
	}

	saving.value = true;
	try {
		await api.routingPreferences.create(
			matchKind.value, matchValue.value.trim(), targetTier.value
		);
		reset();
		emit("created");
	} catch (err) {
		emit("error", err?.message || "That rule could not be saved.");
	} finally {
		saving.value = false;
	}
}

function reset() {
	matchValue.value = "";
	forecast.value = null;
	confirmNeeded.value = false;
}
</script>

<style scoped>
.rule-form {
	padding: 0.875rem;
	border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-md);
	background: var(--ql-subtle);
}

.rule-row {
	display: flex;
	flex-wrap: wrap;
	gap: 0.75rem;
	align-items: flex-end;
}

.rule-field {
	display: flex;
	flex-direction: column;
	gap: 0.25rem;
}

.rule-field-grow {
	flex: 1 1 12rem;
}

.rule-label {
	font-size: 0.7rem;
	color: var(--ql-text-muted);
}

.rule-input {
	padding: 0.375rem 0.5rem;
	border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-sm);
	background: var(--ql-bg);
	color: var(--ql-text);
	font: inherit;
	font-size: 0.8125rem;
}

.rule-hint,
.rule-forecast {
	margin: 0.625rem 0 0;
	font-size: 0.75rem;
	color: var(--ql-text-secondary);
}

.rule-forecast-caveat {
	display: block;
	color: var(--ql-text-muted);
}

.rule-actions {
	display: flex;
	gap: 0.5rem;
	margin-top: 0.75rem;
}

.rule-save {
	padding: 0.375rem 0.875rem;
	border: 1px solid var(--ql-accent);
	border-radius: var(--ql-radius-sm);
	background: var(--ql-accent);
	color: var(--ql-bg);
	font: inherit;
	font-size: 0.8125rem;
	cursor: pointer;
}

.rule-save:disabled {
	opacity: 0.5;
	cursor: default;
}

.rule-cancel {
	padding: 0.375rem 0.75rem;
	border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-sm);
	background: none;
	color: var(--ql-text-secondary);
	font: inherit;
	font-size: 0.8125rem;
	cursor: pointer;
}
</style>
