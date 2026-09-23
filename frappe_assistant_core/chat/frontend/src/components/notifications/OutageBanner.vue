<template>
	<TransitionGroup name="outage-slide" tag="div" class="outage-stack" aria-live="assertive">
		<div v-for="n in store.outageNotifications" :key="n.id"
			class="outage-banner" :class="typeClass(n.type)">
			<div class="outage-row">
				<svg class="outage-icon" width="18" height="18" fill="none"
					stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
						d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
				</svg>
				<div class="outage-body">
					<span class="outage-title">{{ n.title }}</span>
					<span v-if="n.message" class="outage-message" v-html="renderNotificationMarkdown(n.message)"></span>
					<a v-if="n.action_label && safeActionUrl(n.action_url)"
						:href="safeActionUrl(n.action_url)" target="_blank"
						rel="noopener noreferrer" class="outage-action">{{ n.action_label }}</a>
				</div>
				<button v-if="n.dismissible === true" data-testid="outage-dismiss" class="outage-close"
					aria-label="Dismiss notification" @click="store.dismiss(n.id)">
					<svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
					</svg>
				</button>
			</div>
		</div>
	</TransitionGroup>
</template>

<script setup>
import { useNotificationStore } from "@/stores/notificationStore";
import { renderNotificationMarkdown } from "@/utils/markdown";
import { typeClass, safeActionUrl } from "./typeMeta";

const store = useNotificationStore();
</script>

<style scoped>
.outage-banner {
	flex-shrink: 0;
	border-bottom: 1px solid var(--ql-border);
}
.ntype-outage {
	background: color-mix(in srgb, var(--ql-danger) 10%, transparent);
	color: var(--ql-danger);
}
.ntype-maintenance {
	background: color-mix(in srgb, var(--ql-warning) 10%, transparent);
	color: var(--ql-warning);
}
.outage-row {
	display: flex;
	align-items: flex-start;
	gap: 0.625rem;
	padding: 0.625rem 1.25rem;
	font-size: 0.8438rem;
}
.outage-icon {
	flex-shrink: 0;
	margin-top: 0.125rem;
}
.outage-body {
	flex: 1;
	min-width: 0;
}
.outage-title {
	font-weight: 650;
	margin-right: 0.5rem;
}
.outage-message {
	opacity: 0.9;
	white-space: normal;
	word-break: break-word;
}
.outage-message :deep(p) {
	display: inline;
	margin: 0;
}
.outage-action {
	font-weight: 600;
	margin-left: 0.5rem;
	color: inherit;
	text-decoration: underline;
}
.outage-close {
	flex-shrink: 0;
	background: transparent;
	border: none;
	cursor: pointer;
	opacity: 0.6;
	color: inherit;
}
.outage-close:hover {
	opacity: 1;
}
.outage-slide-enter-active,
.outage-slide-leave-active {
	transition: all 0.25s ease;
}
.outage-slide-enter-from,
.outage-slide-leave-to {
	opacity: 0;
	transform: translateY(-4px);
}
</style>
