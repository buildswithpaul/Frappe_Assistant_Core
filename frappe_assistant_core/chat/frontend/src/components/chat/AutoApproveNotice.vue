<template>
	<div class="aa-notice" role="status">
		<div class="aa-text">
			<strong>{{ __("Auto-approve is ready.") }}</strong>
			{{
				__(
					"Once you choose Got it, everyday changes run without asking and are listed in the reply. Submitting, deleting, emailing, publishing and admin changes still ask. An edit has no Undo, and your site's own alerts can still fire."
				)
			}}
		</div>
		<div class="aa-actions">
			<button type="button" class="aa-btn" :disabled="saving" @click="$emit('turn-off')">
				{{ __("Turn off") }}
			</button>
			<button type="button" class="aa-btn aa-btn-primary" :disabled="saving" @click="$emit('keep')">
				{{ __("Got it") }}
			</button>
		</div>
	</div>
</template>

<script setup>
import { __ } from "@/utils/i18n";

// Shown once, above the composer, before the mode applies to anything: nobody stops being
// asked without having been told.
defineProps({ saving: { type: Boolean, default: false } });
defineEmits(["keep", "turn-off"]);
</script>

<style scoped>
.aa-notice {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 12px;
	margin-bottom: 8px;
	padding: 8px 12px;
	border: 1px solid var(--ql-border);
	border-radius: 10px;
	background: var(--ql-subtle);
	font-size: 13px;
	line-height: 1.4;
	color: var(--ql-text);
}

.aa-actions {
	display: flex;
	flex-shrink: 0;
	gap: 6px;
}

.aa-btn {
	padding: 4px 10px;
	border: 1px solid var(--ql-border);
	border-radius: 8px;
	background: transparent;
	color: inherit;
	font-size: 12px;
	font-weight: 500;
	cursor: pointer;
}

.aa-btn-primary {
	border-color: var(--ql-accent);
	background: var(--ql-accent);
	color: var(--ql-on-accent, #fff);
}

.aa-btn:disabled {
	opacity: 0.6;
	cursor: default;
}

@media (max-width: 640px) {
	.aa-notice {
		flex-direction: column;
		align-items: stretch;
	}
	.aa-actions {
		justify-content: flex-end;
	}
}
</style>
