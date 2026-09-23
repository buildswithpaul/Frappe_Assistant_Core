<template>
	<Transition name="center-fade">
		<div v-if="open" class="notif-center" role="dialog" aria-label="Notifications">
			<div class="center-header">
				<span class="center-title">Notifications</span>
				<button data-testid="mark-all-read" class="mark-all-btn" @click="store.markAllSeen()">
					Mark all read
				</button>
			</div>
			<div class="center-body">
				<p v-if="items.length === 0" class="center-empty">You're all caught up.</p>
				<div v-for="n in items" :key="n.id" data-testid="center-item" :data-id="n.id" class="center-item"
					:class="[typeClass(n.type), { 'is-dismissed': store.isDismissed(n) }]">
					<svg class="item-icon" width="16" height="16" fill="none" stroke="currentColor"
						viewBox="0 0 24 24" aria-hidden="true">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="iconPath(n.type)" />
					</svg>
					<div class="item-body">
						<div class="item-row">
							<span class="item-title">{{ n.title }}</span>
							<span class="item-time">{{ formatTime(n.created_at) }}</span>
						</div>
						<div v-if="n.message" class="item-message" v-html="renderNotificationMarkdown(n.message)"></div>
						<a v-if="n.action_label && safeActionUrl(n.action_url)" :href="safeActionUrl(n.action_url)"
							target="_blank" rel="noopener noreferrer" class="item-action">{{ n.action_label }}</a>
					</div>
					<button v-if="n.dismissible === true && !store.isDismissed(n)" data-testid="item-dismiss"
						class="item-dismiss" aria-label="Dismiss notification" @click="store.dismiss(n.id)">
						<svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
						</svg>
					</button>
				</div>
			</div>
		</div>
	</Transition>
</template>

<script setup>
import { computed } from "vue";
import { useNotificationStore } from "@/stores/notificationStore";
import { renderNotificationMarkdown } from "@/utils/markdown";
import { typeClass, safeActionUrl, OUTAGE_TYPES } from "./typeMeta";

// Open/close is fully owned by the parent (NotificationBell), which wraps
// both the trigger button and this panel in one element and does its own
// outside-click/Escape containment check against that shared wrapper. A
// panel-only containment check here would see the bell button as an outside
// sibling on the very click that opens the panel — see NotificationBell.vue.
defineProps({ open: { type: Boolean, default: false } });

const store = useNotificationStore();

// stable sort — outage-class first, original store order preserved within tiers
const items = computed(() =>
	[...store.notifications].sort(
		(a, b) => (OUTAGE_TYPES.has(a.type) ? 0 : 1) - (OUTAGE_TYPES.has(b.type) ? 0 : 1)
	)
);

const ICON_PATHS = {
	info: "M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z",
	success: "M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z",
	warning:
		"M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z",
	star: "M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z",
};

function iconPath(type) {
	if (type === "info") return ICON_PATHS.info;
	if (type === "success") return ICON_PATHS.success;
	if (type === "warning" || OUTAGE_TYPES.has(type)) return ICON_PATHS.warning;
	return ICON_PATHS.star;
}

function formatTime(createdAt) {
	if (!createdAt) return "";
	const d = new Date(String(createdAt).replace(" ", "T"));
	return Number.isNaN(d.getTime()) ? "" : d.toLocaleString();
}
</script>

<style scoped>
.notif-center {
	position: absolute;
	top: calc(100% + 0.5rem);
	right: 0;
	z-index: 50;
	width: min(380px, 92vw);
	max-height: 60vh;
	display: flex;
	flex-direction: column;
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-lg);
	box-shadow: 0 8px 24px color-mix(in srgb, var(--ql-text) 18%, transparent);
	overflow: hidden;
}
.center-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	flex-shrink: 0;
	padding: 0.75rem 1rem;
	border-bottom: 1px solid var(--ql-border);
}
.center-title {
	font-size: 0.875rem;
	font-weight: 650;
	color: var(--ql-text);
}
.mark-all-btn {
	background: transparent;
	border: none;
	cursor: pointer;
	font-size: 0.75rem;
	font-weight: 600;
	color: var(--ql-accent);
	padding: 0.25rem 0.5rem;
	border-radius: var(--ql-radius-sm);
}
.mark-all-btn:hover {
	background: var(--ql-accent-soft);
}
.center-body {
	overflow-y: auto;
	max-height: 60vh;
}
.center-empty {
	padding: 1.5rem 1rem;
	text-align: center;
	font-size: 0.8125rem;
	color: var(--ql-text-muted);
}
.center-item {
	display: flex;
	align-items: flex-start;
	gap: 0.625rem;
	padding: 0.75rem 1rem;
	border-bottom: 1px solid var(--ql-border);
}
.center-item:last-child {
	border-bottom: none;
}
.center-item.is-dismissed {
	opacity: 0.55;
}
.item-icon {
	flex-shrink: 0;
	margin-top: 0.125rem;
	color: var(--ql-text-muted);
}
.ntype-info .item-icon,
.ntype-feature .item-icon {
	color: var(--ql-accent);
}
.ntype-success .item-icon {
	color: var(--ql-success);
}
.ntype-warning .item-icon,
.ntype-maintenance .item-icon {
	color: var(--ql-warning);
}
.ntype-outage .item-icon {
	color: var(--ql-danger);
}
.ntype-promotion .item-icon {
	color: var(--ql-gold);
}
.item-body {
	flex: 1;
	min-width: 0;
}
.item-row {
	display: flex;
	align-items: baseline;
	justify-content: space-between;
	gap: 0.5rem;
}
.item-title {
	font-size: 0.8125rem;
	font-weight: 600;
	color: var(--ql-text);
}
.item-time {
	flex-shrink: 0;
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
}
.item-message {
	margin-top: 0.125rem;
	font-size: 0.8125rem;
	color: var(--ql-text-secondary);
	word-break: break-word;
}
.item-message :deep(p) {
	margin: 0;
}
.item-action {
	display: inline-block;
	margin-top: 0.375rem;
	font-size: 0.75rem;
	font-weight: 600;
	color: var(--ql-accent);
	text-decoration: underline;
}
.item-dismiss {
	flex-shrink: 0;
	display: flex;
	align-items: center;
	justify-content: center;
	width: 20px;
	height: 20px;
	background: transparent;
	border: none;
	border-radius: var(--ql-radius-sm);
	cursor: pointer;
	opacity: 0.6;
	color: var(--ql-text-muted);
}
.item-dismiss:hover {
	opacity: 1;
	background: var(--ql-subtle);
}
.center-fade-enter-active,
.center-fade-leave-active {
	transition: opacity 0.15s ease, transform 0.15s ease;
}
.center-fade-enter-from,
.center-fade-leave-to {
	opacity: 0;
	transform: translateY(-4px);
}
</style>
