<template>
	<div class="menu" role="menu" @click.stop>
		<template v-if="!moveOpen">
			<button class="menu-item" role="menuitem" data-test="menu-rename" @click="$emit('rename')">
				{{ __("Rename") }}
			</button>
			<button class="menu-item" role="menuitem" data-test="menu-move" @click="moveOpen = true">
				{{ __("Move to project") }}
			</button>
			<button class="menu-item danger" role="menuitem" data-test="menu-archive" @click="$emit('archive')">
				{{ __("Archive") }}
			</button>
		</template>
		<div v-else class="submenu">
			<button
				v-for="p in projects"
				:key="p.name"
				class="menu-item"
				role="menuitem"
				:data-test="`move-${p.name}`"
				@click="$emit('move', p.name)"
			>
				<span class="check">{{ p.name === session.project ? "✓" : "" }}</span>
				{{ p.title }}
			</button>
			<button
				v-if="session.project"
				class="menu-item"
				role="menuitem"
				data-test="move-none"
				@click="$emit('move', null)"
			>
				{{ __("Remove from project") }}
			</button>
			<button class="menu-item" role="menuitem" data-test="move-new" @click="$emit('new-project')">
				{{ __("New project…") }}
			</button>
		</div>
	</div>
</template>

<script setup>
import { ref } from "vue";
import { __ } from "@/utils/i18n";

defineProps({
	session: { type: Object, required: true },
	projects: { type: Array, default: () => [] },
});

defineEmits(["rename", "move", "new-project", "archive"]);

const moveOpen = ref(false);
</script>

<style scoped>
.menu {
	position: absolute;
	top: 100%;
	right: 0.25rem;
	z-index: 20;
	min-width: 11rem;
	padding: 0.25rem;
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
}

.submenu {
	max-height: 14rem;
	overflow-y: auto;
}

.menu-item {
	display: flex;
	align-items: center;
	gap: 0.375rem;
	width: 100%;
	padding: 0.375rem 0.5rem;
	font-size: 0.8rem;
	text-align: left;
	color: var(--ql-text);
	background: none;
	border: none;
	border-radius: 0.375rem;
	cursor: pointer;
}

.menu-item:hover,
.menu-item:focus-visible {
	background-color: var(--ql-subtle);
}

.menu-item.danger {
	color: #ef4444;
}

.check {
	display: inline-block;
	width: 1rem;
	color: var(--ql-accent);
}
</style>
