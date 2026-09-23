<template>
	<Transition name="dropdown">
		<div v-if="open" ref="menuRef" class="plus-menu" role="menu">
			<button class="menu-item menu-attach" role="menuitem" @click="$emit('attach')">
				<svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
						d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
				</svg>
				<span>Attach a file</span>
			</button>

			<button
				v-if="webSearchAvailable"
				class="menu-item menu-web-search"
				role="menuitemcheckbox"
				:aria-pressed="webSearch"
				:class="{ 'menu-item-on': webSearch }"
				@click="$emit('toggle-web-search')"
			>
				<svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
						d="M21 12a9 9 0 11-18 0 9 9 0 0118 0zM3.6 9h16.8M3.6 15h16.8M12 3a15 15 0 010 18a15 15 0 010-18z" />
				</svg>
				<span>Web search</span>
				<span class="menu-state">{{ webSearch ? "On" : "Off" }}</span>
			</button>

			<button
				class="menu-item menu-thinking"
				role="menuitemcheckbox"
				:aria-pressed="thinking"
				:class="{ 'menu-item-on': thinking }"
				:disabled="!thinkingAvailable"
				:title="thinkingAvailable ? '' : 'This model cannot think longer'"
				@click="$emit('toggle-thinking')"
			>
				<svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
						d="M12 3l1.9 4.6L18.5 9l-4.6 1.9L12 15.5l-1.9-4.6L5.5 9l4.6-1.4L12 3z" />
				</svg>
				<span>Thinking</span>
				<span class="menu-state">{{ thinking ? "On" : "Off" }}</span>
			</button>
		</div>
	</Transition>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from "vue";

const props = defineProps({
	open: { type: Boolean, default: false },
	webSearchAvailable: { type: Boolean, default: false },
	webSearch: { type: Boolean, default: false },
	thinking: { type: Boolean, default: false },
	thinkingAvailable: { type: Boolean, default: true },
});

const emit = defineEmits(["attach", "toggle-web-search", "toggle-thinking", "close"]);
const menuRef = ref(null);

// The ⊕ button that opens this menu sits outside menuRef, in the toolbar, so
// its own click also reaches the document listener below. A browser flushes
// Vue's DOM update at the microtask checkpoint between the button's handler and
// that listener, so by the time we run, menuRef is already populated and the
// click that just opened the menu reads as a click outside it — the menu closed
// on the very gesture meant to open it, and the ⊕ could never be used at all.
// The trigger owns the toggle in BOTH directions, so every click on it is the
// one click this handler must keep its hands off.
// (jsdom dispatches a whole event on one JS stack and never flushes mid-dispatch,
// which is why the original unit tests could not see any of this.)
const TRIGGER_SELECTOR = "[data-composer-plus-trigger]";

function handleClickOutside(event) {
	if (!props.open) return;
	const target = event.target;
	if (target?.closest?.(TRIGGER_SELECTOR)) return;
	if (menuRef.value?.contains(target)) return;
	emit("close");
}

function handleKeydown(event) {
	if (event.key === "Escape" && props.open) emit("close");
}

onMounted(() => {
	document.addEventListener("click", handleClickOutside);
	document.addEventListener("keydown", handleKeydown);
});

onUnmounted(() => {
	document.removeEventListener("click", handleClickOutside);
	document.removeEventListener("keydown", handleKeydown);
});
</script>

<style scoped>
.plus-menu {
	position: absolute;
	bottom: calc(100% + 0.5rem);
	left: 0;
	min-width: 220px;
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.75rem;
	box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.15), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
	padding: 0.375rem;
	z-index: 30;
}

.menu-item {
	display: flex;
	align-items: center;
	gap: 0.625rem;
	width: 100%;
	padding: 0.625rem 0.875rem;
	background: transparent;
	border: none;
	border-radius: 0.5rem;
	color: var(--ql-text);
	font-size: 0.875rem;
	text-align: left;
	cursor: pointer;
	transition: background 0.1s ease;
}

.menu-item:hover:not(:disabled) {
	background: var(--ql-subtle);
}

.menu-item:disabled {
	color: var(--ql-text-muted);
	cursor: not-allowed;
}

.menu-item svg {
	width: 1.125rem;
	height: 1.125rem;
	flex-shrink: 0;
	color: var(--ql-text-muted);
}

.menu-item-on {
	color: var(--ql-accent);
	background: var(--ql-accent-soft);
}

.menu-item-on svg {
	color: var(--ql-accent);
}

.menu-item-on:hover {
	background: var(--ql-accent-soft);
}

.menu-state {
	margin-left: auto;
	font-size: 0.75rem;
	color: var(--ql-text-muted);
}

.dropdown-enter-active,
.dropdown-leave-active {
	transition: opacity 0.15s ease, transform 0.15s ease;
}

.dropdown-enter-from,
.dropdown-leave-to {
	opacity: 0;
	transform: translateY(0.5rem);
}

[data-theme="dark"] .plus-menu,
.dark .plus-menu {
	box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4), 0 8px 10px -6px rgba(0, 0, 0, 0.3);
}
</style>
