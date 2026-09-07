<template>
	<div class="banner-live" aria-live="polite">
		<Transition name="banner-slide">
			<div v-if="n" :key="n.id" class="banner" :class="typeClass(n.type)">
				<div class="banner-row">
					<svg v-if="n.type === 'info'" class="banner-icon" width="16" height="16" fill="none"
						stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
							d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
					</svg>
					<svg v-else-if="n.type === 'success'" class="banner-icon" width="16" height="16" fill="none"
						stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
							d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
					</svg>
					<svg v-else-if="n.type === 'warning'" class="banner-icon" width="16" height="16" fill="none"
						stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
							d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
					</svg>
					<svg v-else class="banner-icon" width="16" height="16" fill="none"
						stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
							d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
					</svg>

					<div class="banner-body">
						<span class="banner-title">{{ n.title }}</span>
						<span v-if="n.message" class="banner-message" v-html="renderNotificationMarkdown(n.message)"></span>
					</div>

					<a v-if="n.action_label && safeActionUrl(n.action_url)"
						:href="safeActionUrl(n.action_url)" target="_blank"
						rel="noopener noreferrer" class="banner-action">{{ n.action_label }}</a>

					<button v-if="n.dismissible === true" data-testid="banner-dismiss" class="banner-close"
						aria-label="Dismiss notification" @click="store.dismiss(n.id)">
						<svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
						</svg>
					</button>
				</div>
			</div>
		</Transition>
	</div>
</template>

<script setup>
import { computed } from "vue";
import { useNotificationStore } from "@/stores/notificationStore";
import { renderNotificationMarkdown } from "@/utils/markdown";
import { typeClass, safeActionUrl } from "./typeMeta";

const store = useNotificationStore();
const n = computed(() => store.bannerNotification);
</script>

<style scoped>
.banner {
	flex-shrink: 0;
	border-bottom: 1px solid var(--ql-border);
}
.ntype-info,
.ntype-feature {
	background: var(--ql-accent-soft);
	color: var(--ql-accent);
}
.ntype-success {
	background: color-mix(in srgb, var(--ql-success) 10%, transparent);
	color: var(--ql-success);
}
.ntype-warning {
	background: color-mix(in srgb, var(--ql-warning) 10%, transparent);
	color: var(--ql-warning);
}
.ntype-promotion {
	background: var(--ql-gold-soft);
	color: var(--ql-gold);
}
.banner-row {
	display: flex;
	align-items: center;
	flex-wrap: wrap;
	gap: 0.5rem;
	padding: 0.5rem 1.25rem;
	font-size: 0.8125rem;
}
.banner-icon {
	flex-shrink: 0;
}
.banner-body {
	flex: 1;
	display: flex;
	align-items: center;
	flex-wrap: wrap;
	gap: 0.5rem;
	min-width: 0;
}
.banner-title {
	font-weight: 600;
}
.banner-message {
	color: inherit;
	opacity: 0.85;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}
.banner-message :deep(p) {
	display: inline;
	margin: 0;
}
.banner-action {
	flex-shrink: 0;
	font-size: 0.75rem;
	font-weight: 600;
	text-decoration: none;
	padding: 0.25rem 0.625rem;
	border-radius: 0.375rem;
	color: inherit;
	background: var(--ql-subtle);
	transition: opacity 0.15s ease;
}
.banner-action:hover {
	opacity: 0.8;
}
.banner-close {
	flex-shrink: 0;
	display: flex;
	align-items: center;
	justify-content: center;
	width: 24px;
	height: 24px;
	background: transparent;
	border: none;
	border-radius: 0.25rem;
	cursor: pointer;
	opacity: 0.6;
	color: inherit;
	transition: all 0.15s ease;
}
.banner-close:hover {
	opacity: 1;
	background: var(--ql-subtle);
}
.banner-slide-enter-active,
.banner-slide-leave-active {
	transition: opacity 0.25s ease, transform 0.25s ease;
}
.banner-slide-enter-from,
.banner-slide-leave-to {
	opacity: 0;
	transform: translateY(-4px);
}
</style>
