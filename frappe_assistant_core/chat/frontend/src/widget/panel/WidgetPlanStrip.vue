<template>
	<section v-if="tasks.length" class="wps" :class="{ 'is-live': live }">
		<p v-if="live" class="wps-heading" aria-live="polite">{{ heading }}</p>
		<button
			v-else
			type="button"
			class="wps-heading wps-toggle"
			:aria-expanded="String(expanded)"
			@click="expanded = !expanded"
		>
			{{ heading }}
		</button>
		<div v-if="live || expanded" class="wps-rows">
			<TaskList :tasks="tasks" :live="live" :activity="activity" bare />
		</div>
	</section>
</template>

<script setup>
import { computed, ref } from "vue";
import TaskList from "@/components/chat/rail/TaskList.vue";
import { t } from "./i18n.js";

const props = defineProps({
	// The turn's plan block ({ status, tasks }), or null when the turn has none.
	plan: { type: Object, default: null },
	// False once the turn is over: the strip collapses and stops presenting work as in flight.
	live: { type: Boolean, default: false },
	// Latest live label per running task id (chatStore.taskActivity).
	activity: { type: Object, default: () => ({}) },
});

const expanded = ref(false);
const tasks = computed(() => props.plan?.tasks || []);

const heading = computed(() => {
	const total = tasks.value.length;
	if (!props.live) {
		const done = tasks.value.filter((task) => task.status === "done").length;
		return total === 1
			? t("✓ Completed {0} of {1} step", [done, total])
			: t("✓ Completed {0} of {1} steps", [done, total]);
	}
	const parallel = tasks.value.filter((task) => task.helper && task.status === "running").length;
	if (parallel > 1) return t("Running {0} in parallel…", [parallel]);
	return total === 1 ? t("Working through {0} step…", [total]) : t("Working through {0} steps…", [total]);
});
</script>

<style scoped>
.wps {
	border-top: 1px solid var(--ql-border);
	background: var(--ql-surface);
	padding: 8px 12px;
}
.wps-heading {
	margin: 0;
	font-size: 11.5px;
	line-height: 1.4;
	color: var(--ql-text-secondary);
}
.wps-toggle {
	display: block;
	width: 100%;
	padding: 0;
	border: none;
	background: transparent;
	text-align: left;
	cursor: pointer;
}
.wps-toggle:hover {
	color: var(--ql-text);
}
/* A long plan must not squeeze the conversation above it. */
.wps-rows {
	margin-top: 8px;
	max-height: 160px;
	overflow-y: auto;
}
</style>
