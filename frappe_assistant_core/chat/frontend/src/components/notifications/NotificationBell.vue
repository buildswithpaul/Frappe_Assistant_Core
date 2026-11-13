<template>
	<div class="notif-bell-wrap" ref="wrapRef">
		<button data-testid="bell-button" class="bell-button"
			:aria-label="`Notifications${store.unreadCount ? `, ${store.unreadCount} unread` : ''}`"
			@click="toggle">
			<svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
					d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
			</svg>
			<span v-if="store.unreadCount" data-testid="unread-badge" class="unread-badge">{{ store.unreadCount }}</span>
		</button>
		<NotificationCenter :open="open" />
	</div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from "vue";
import { useNotificationStore } from "@/stores/notificationStore";
import NotificationCenter from "./NotificationCenter.vue";

const store = useNotificationStore();
const open = ref(false);
const wrapRef = ref(null);

function toggle() {
	open.value = !open.value;
	if (open.value) store.markAllSeen();
}

// The panel (NotificationCenter) renders as a DOM child of this wrapper, not
// a sibling of the bell button on its own — so containing the check here,
// against the wrapper that holds trigger + panel together, means the click
// that opens the panel is always "inside" regardless of whether the panel's
// own ref has bound yet. See NotificationCenter.vue for why a panel-scoped
// containment check (its previous approach) can't be timing-safe.
//
// Listening on "mousedown" rather than "click" is the other half of that
// same timing fix: a real click on an item's own dismiss button mutates
// store state (store.dismiss) synchronously enough, ahead of this handler,
// that the button can already be detached from the DOM by the time a
// "click" listener here would run — and contains() on a detached node is
// always false, so a "click" listener would wrongly read that as outside
// and close the panel it was never meant to touch. "mousedown" fires before
// any click handler runs, so the containment check always sees the DOM as
// it was at the moment of the actual press, not after whatever that press
// goes on to trigger.
function handleOutsideClick(event) {
	if (open.value && wrapRef.value && !wrapRef.value.contains(event.target)) {
		open.value = false;
	}
}

function handleKeydown(event) {
	if (open.value && event.key === "Escape") open.value = false;
}

onMounted(() => {
	document.addEventListener("mousedown", handleOutsideClick);
	document.addEventListener("keydown", handleKeydown);
});

onUnmounted(() => {
	document.removeEventListener("mousedown", handleOutsideClick);
	document.removeEventListener("keydown", handleKeydown);
});
</script>

<style scoped>
.notif-bell-wrap {
	position: relative;
}
.bell-button {
	position: relative;
	display: flex;
	align-items: center;
	justify-content: center;
	width: 32px;
	height: 32px;
	background: transparent;
	border: none;
	border-radius: var(--ql-radius-md);
	cursor: pointer;
	color: var(--ql-text-muted);
}
.bell-button:hover {
	background: var(--ql-subtle);
	color: var(--ql-text);
}
.unread-badge {
	position: absolute;
	top: 2px;
	right: 2px;
	min-width: 15px;
	height: 15px;
	padding: 0 4px;
	border-radius: 8px;
	background: var(--ql-danger);
	color: var(--ql-surface);
	font-size: 0.625rem;
	font-weight: 700;
	line-height: 15px;
	text-align: center;
}
</style>
