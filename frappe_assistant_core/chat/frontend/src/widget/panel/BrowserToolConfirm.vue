<template>
	<div class="btc" role="group" :aria-label="t('Approval Required')">
		<div class="btc-title">{{ t("Approval Required") }}: {{ copy.action }}</div>
		<div class="btc-detail">
			{{ copy.detail }}
			<template v-if="request.description"> · {{ request.description }}</template>
		</div>
		<div class="btc-actions">
			<button type="button" class="btc-btn" data-test="confirm-deny" @click="$emit('decide', 'deny')">
				{{ t("Reject") }}
			</button>
			<button
				type="button"
				class="btc-btn btc-primary"
				data-test="confirm-approve"
				@click="$emit('decide', 'approve')"
			>
				{{ t("Approve") }}
			</button>
			<button type="button" class="btc-btn" data-test="confirm-trust" @click="$emit('decide', 'trust')">
				{{ t("Always Allow") }}
			</button>
		</div>
	</div>
</template>

<script setup>
import { computed } from "vue";
import { TOOL_CONFIRMATION_COPY } from "../desk/browserTools.js";
import { t } from "./i18n.js";

const props = defineProps({
	request: { type: Object, required: true },
});
defineEmits(["decide"]);

// The tool name and params come from the model: rendered as text only, never as HTML.
const copy = computed(
	() =>
		TOOL_CONFIRMATION_COPY[props.request.tool_name] || {
			action: t("Run browser tool"),
			detail: `The AI wants to run the \`${props.request.tool_name}\` browser tool.`,
		}
);
</script>

<style scoped>
.btc {
	margin: 12px;
	padding: 12px;
	border: 1px solid var(--ql-border);
	border-left: 3px solid var(--ql-accent);
	border-radius: 8px;
	background: var(--ql-surface);
}
.btc-title {
	font-weight: 600;
	color: var(--ql-text);
	margin-bottom: 4px;
}
.btc-detail {
	font-size: 13px;
	color: var(--ql-text-secondary);
}
.btc-actions {
	display: flex;
	gap: 8px;
	margin-top: 10px;
}
.btc-btn {
	padding: 5px 12px;
	border: 1px solid var(--ql-border);
	border-radius: 6px;
	background: transparent;
	color: var(--ql-text);
	font: inherit;
	font-size: 13px;
	cursor: pointer;
}
.btc-btn:hover {
	background: var(--ql-accent-soft);
}
.btc-primary {
	background: var(--ql-accent);
	border-color: var(--ql-accent);
	color: #fff;
}
.btc-primary:hover {
	background: var(--ql-accent-hover);
}
</style>
