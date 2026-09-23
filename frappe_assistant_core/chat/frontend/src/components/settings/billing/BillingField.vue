<template>
	<div class="form-group">
		<label :for="forId">
			{{ label }} <span v-if="required" class="required">*</span>
			<span v-if="labelHint" class="field-hint">{{ labelHint }}</span>
		</label>

		<slot />

		<!-- The error replaces the hint rather than stacking under it: two
		     lines of small grey-and-red text under one input is harder to read
		     than one, and the hint is advice the error supersedes. -->
		<p v-if="error" class="field-error" role="alert">{{ error }}</p>
		<p v-else-if="$slots.hint" class="field-hint-text"><slot name="hint" /></p>
	</div>
</template>

<script setup>
/**
 * Label + control + hint/error for one billing field.
 *
 * The control itself stays in the parent via the default slot, so `v-model`,
 * `type` and the field-specific handlers are declared where the form state
 * lives — this owns only the chrome that was repeated nine times.
 */
defineProps({
	forId: { type: String, required: true },
	label: { type: String, required: true },
	required: { type: Boolean, default: false },
	// Small muted note beside the label, e.g. "as registered".
	labelHint: { type: String, default: "" },
	error: { type: String, default: "" },
});
</script>

<style scoped>
.form-group {
	display: flex;
	flex-direction: column;
	gap: 6px;
}

label {
	font-size: 13px;
	font-weight: 500;
	color: var(--faco-text, #1f2937);
}

.required {
	color: #dc2626;
}

.field-hint {
	margin-left: 6px;
	font-size: 11px;
	font-weight: 400;
	color: var(--faco-text-muted, #6b7280);
}

.field-hint-text {
	margin: 0;
	font-size: 12px;
	color: var(--faco-text-muted, #6b7280);
	line-height: 1.45;
}

.field-error {
	margin: 0;
	font-size: 12px;
	color: #dc2626;
	line-height: 1.45;
}

/* `:deep` because the control is slotted in from a parent, so it carries that
   parent's scope id rather than ours — and BillingGstFields renders its inputs
   with no scope id at all. Styling them here is the only place every field can
   reach, and it keeps one source of truth for the input chrome. */
:deep(.form-input) {
	width: 100%;
	padding: 0.625rem 0.875rem;
	font-size: 0.9375rem;
	color: var(--ql-text);
	background: var(--ql-bg, var(--ql-surface));
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	transition: border-color 0.15s ease, box-shadow 0.15s ease;
	box-sizing: border-box;
}

:deep(.form-input:focus) {
	outline: none;
	border-color: var(--ql-accent);
	box-shadow: 0 0 0 3px rgba(15, 110, 92, 0.15);
}

/* Focus must not out-rank the error: we move focus TO the offending field, so
   a plain focus ring would leave the one field we are pointing at looking like
   the only healthy one. */
:deep(.form-input.input-error),
:deep(.form-input.input-error:focus) {
	border-color: #ef4444;
	box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.15);
}
</style>
