<template>
	<Transition name="dropdown">
		<div v-if="open" ref="menuRef" class="thinking-menu" role="menu" aria-label="Thinking level">
			<button
				v-for="level in levels"
				:key="level"
				class="menu-item"
				role="menuitemradio"
				:aria-checked="level === selected"
				:class="{ 'menu-item-on': level === selected }"
				@click="choose(level)"
			>
				<span class="level-label">{{ labelFor(level) }}</span>
				<span v-if="!legacy && COSTLY.includes(level)" class="level-cost">uses more credits</span>
				<span v-if="hintFor(level)" class="level-hint">{{ hintFor(level) }}</span>
			</button>
			<p v-if="offFloor && selected === 'off'" class="menu-note">
				This model always thinks a little, even when Thinking is off.
			</p>
			<p v-if="!legacy" class="menu-note">Higher levels think longer and use more credits.</p>
		</div>
	</Transition>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from "vue";
import { LEVEL_LABELS } from "@/stores/composerModesStore";

const props = defineProps({
	open: { type: Boolean, default: false },
	levels: { type: Array, default: () => ["off"] },
	selected: { type: String, default: "off" },
	legacy: { type: Boolean, default: false },
	offFloor: { type: Boolean, default: false },
	hintFor: { type: Function, default: () => null },
});
const emit = defineEmits(["select", "close"]);
const menuRef = ref(null);

const COSTLY = ["xhigh", "max"];
// Triggers own their own toggle, as in ComposerPlusMenu.
const TRIGGER_SELECTOR = "[data-thinking-trigger]";

function labelFor(level) {
	if (props.legacy) return level === "off" ? "Off" : "On";
	return LEVEL_LABELS[level] || level;
}

function choose(level) {
	emit("select", level);
	emit("close");
}

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
.thinking-menu {
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
	padding: 0.5rem 0.875rem;
	background: transparent;
	border: none;
	border-radius: 0.5rem;
	color: var(--ql-text);
	font-size: 0.875rem;
	text-align: left;
	cursor: pointer;
	transition: background 0.1s ease;
}

.menu-item:hover {
	background: var(--ql-subtle);
}

.menu-item-on,
.menu-item-on:hover {
	color: var(--ql-accent);
	background: var(--ql-accent-soft);
}

.level-cost,
.level-hint {
	margin-left: auto;
	font-size: 0.75rem;
	color: var(--ql-text-muted);
}

.level-cost + .level-hint {
	margin-left: 0;
}

.menu-note {
	margin: 0;
	padding: 0.375rem 0.875rem 0.25rem;
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

[data-theme="dark"] .thinking-menu,
.dark .thinking-menu {
	box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4), 0 8px 10px -6px rgba(0, 0, 0, 0.3);
}
</style>
