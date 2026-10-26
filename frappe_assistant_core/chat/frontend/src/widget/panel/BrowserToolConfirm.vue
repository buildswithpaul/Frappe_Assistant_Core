<template>
	<div class="btc" role="group" :aria-label="t(copy.action)">
		<div class="btc-head">
			<span class="btc-icon" aria-hidden="true">
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
					<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" />
					<circle cx="12" cy="12" r="3" />
				</svg>
			</span>
			<div class="btc-heading">
				<div class="btc-title">{{ t(copy.action) }}</div>
				<div class="btc-detail">
					{{ t(copy.detail) }}
					<template v-if="request.description"> · {{ request.description }}</template>
				</div>
			</div>
		</div>
		<div class="btc-actions">
			<button
				type="button"
				class="ql-btn ql-btn-approve"
				data-test="confirm-approve"
				@click="$emit('decide', 'approve')"
			>
				{{ t("Approve") }}
			</button>
			<button type="button" class="ql-btn ql-btn-reject" data-test="confirm-deny" @click="$emit('decide', 'deny')">
				{{ t("Reject") }}
			</button>
		</div>
		<div class="btc-trust">
			<button type="button" class="btc-link" data-test="confirm-trust-page" @click="$emit('decide', 'trust_page')">
				{{ t("Allow on this page in this chat") }}
			</button>
			<button type="button" class="btc-link" data-test="confirm-trust" @click="$emit('decide', 'trust')">
				{{ t("Always allow") }}
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
			detail: `FACO wants to use the ${props.request.tool_name} browser tool.`,
		}
);
</script>

<style src="../../components/chat/interactions/interactionButtons.css"></style>

<style scoped>
.btc {
	margin: 12px;
	padding: 14px 16px;
	border: 1px solid color-mix(in srgb, var(--ql-gold) 45%, var(--ql-border));
	border-radius: var(--ql-radius-xl, 12px);
	background: var(--ql-surface);
	box-shadow: 0 1px 3px rgba(26, 26, 23, 0.06);
}

.btc-head {
	display: flex;
	align-items: flex-start;
	gap: 12px;
}

.btc-icon {
	flex-shrink: 0;
	display: flex;
	align-items: center;
	justify-content: center;
	width: 28px;
	height: 28px;
	border-radius: var(--ql-radius-md, 8px);
	background: var(--ql-gold-soft);
	color: var(--ql-warning);
}

.btc-icon svg {
	width: 16px;
	height: 16px;
}

.btc-heading {
	min-width: 0;
}

.btc-title {
	font-size: 14px;
	font-weight: 600;
	line-height: 1.35;
	color: var(--ql-text);
}

.btc-detail {
	margin-top: 3px;
	font-size: 12.5px;
	line-height: 1.5;
	color: var(--ql-text-secondary);
}

.btc-actions {
	display: flex;
	flex-wrap: wrap;
	gap: 8px;
	margin-top: 12px;
}

.btc-trust {
	display: flex;
	flex-wrap: wrap;
	gap: 4px 16px;
	margin-top: 10px;
}

.btc-link {
	padding: 0;
	border: none;
	background: transparent;
	font: inherit;
	font-size: 12.5px;
	color: var(--ql-accent);
	cursor: pointer;
}

.btc-link:hover {
	color: var(--ql-accent-hover);
	text-decoration: underline;
	text-underline-offset: 2px;
}

.btc-link:focus-visible {
	outline: 2px solid var(--ql-accent);
	outline-offset: 2px;
	border-radius: 4px;
}
</style>
