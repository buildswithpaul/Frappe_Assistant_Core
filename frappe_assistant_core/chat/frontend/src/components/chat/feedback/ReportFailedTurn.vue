<template>
	<div class="truncation-notice retry-notice">
		<span>{{ __("This answer did not finish.") }}</span>
		<button
			v-if="support.canOpen && lastError && isReportable(lastError.code)"
			type="button"
			class="report-link"
			data-test="report-failed-turn"
			@click="report(lastError)"
		>
			{{ __("Report this") }}
		</button>
		<button class="continue-btn retry-btn" @click="$emit('retry')">{{ __("Retry") }}</button>
	</div>
</template>

<script setup>
import { __ } from "@/utils/i18n";
import { isReportable } from "@/utils/reportableError";
import { useSupportStore } from "@/stores/supportStore";
import { useReportFailure } from "@/composables/useReportFailure";

defineProps({
	// {code, message, at} stored on the message when its turn failed.
	lastError: { type: Object, default: null },
});
defineEmits(["retry"]);

const support = useSupportStore();
const report = useReportFailure();
</script>

<style scoped>
.truncation-notice {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	margin-top: 0.75rem;
	padding: 0.5rem 0.75rem;
	background-color: var(--ql-gold-soft);
	border: 1px solid var(--ql-gold-soft);
	border-radius: 0.5rem;
	font-size: 0.8125rem;
	color: var(--ql-text-secondary);
	line-height: 1.4;
}

.continue-btn {
	margin-left: auto;
	padding: 0.3rem 0.75rem;
	background-color: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	font-size: 0.8125rem;
	font-weight: 500;
	color: var(--ql-text);
	cursor: pointer;
	transition: all 0.15s ease;
}

.continue-btn:hover {
	background-color: var(--ql-subtle);
	border-color: var(--ql-text-muted);
}

.report-link {
	margin-left: auto;
	background: none;
	border: none;
	padding: 0;
	font-size: 0.8125rem;
	color: var(--ql-text-secondary);
	text-decoration: underline;
	cursor: pointer;
}

.report-link:hover {
	color: var(--ql-text);
}

.report-link + .continue-btn {
	margin-left: 0;
}
</style>
