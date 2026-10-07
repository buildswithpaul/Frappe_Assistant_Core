<template>
	<section v-if="tasks.length" class="wps" :class="{ 'is-live': live }">
		<!-- One status line in every state; the rows open on demand so a running plan does not
		     take half the panel. A native button gives Enter/Space for free. -->
		<button
			type="button"
			class="wps-heading wps-toggle wps-oneline"
			:aria-expanded="String(expanded)"
			@click="expanded = !expanded"
		>
			<span class="wps-status" :aria-live="live ? 'polite' : null">{{ heading }}</span>
			<span v-if="activityLine" class="wps-activity"> — {{ activityLine }}</span>
		</button>
		<div v-if="expanded" class="wps-rows">
			<TaskList :tasks="tasks" :live="live" :stopped="stopped" :activity="activity" bare />
		</div>
	</section>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import TaskList from "@/components/chat/rail/TaskList.vue";
import { t } from "./i18n.js";
import { WAITING_LABELS } from "@/utils/turnState";

const props = defineProps({
	// The turn's plan block ({ status, tasks }), or null when the turn has none.
	plan: { type: Object, default: null },
	// False once the turn is over: the strip stops presenting work as in flight.
	live: { type: Boolean, default: false },
	// Latest live label per running task id (chatStore.taskActivity).
	activity: { type: Object, default: () => ({}) },
	// The user pressed Stop on this turn: its open rows read as stopped, not as work left over.
	stopped: { type: Boolean, default: false },
	// A turn paused on the user: "approval" or "question" while a card waits, "resume" while an
	// answered card's resume is in flight, "" otherwise.
	waitingOn: { type: String, default: "" },
});

const expanded = ref(false);
const tasks = computed(() => props.plan?.tasks || []);
const running = computed(() => tasks.value.filter((task) => task.status === "running"));

// Which task's label changed last. Each task_activity event replaces chatStore.taskActivity with
// a new object, so the changed key is the one whose label differs from the previous object.
const latestActivityId = ref(null);
watch(
	() => props.activity,
	(now, before) => {
		const changed = Object.keys(now || {}).filter((id) => now[id] !== before?.[id]);
		if (changed.length) latestActivityId.value = changed[changed.length - 1];
	}
);

// The muted tail of a running line: the newest label among running helpers, else any running
// helper's label, else the title of the row being worked on.
const activityLine = computed(() => {
	if (!props.live) return "";
	const labelled = running.value.filter((task) => props.activity[task.id]);
	const latest = labelled.find((task) => task.id === latestActivityId.value) || labelled[0];
	if (latest) return props.activity[latest.id];
	return running.value[0]?.title || "";
});

const heading = computed(() => {
	const total = tasks.value.length;
	const done = tasks.value.filter((task) => task.status === "done").length;
	if (!props.live && WAITING_LABELS[props.waitingOn]) return t(WAITING_LABELS[props.waitingOn]);
	if (!props.live) {
		if (props.stopped) {
			return total === 1
				? t("⊘ Stopped after {0} of {1} step", [done, total])
				: t("⊘ Stopped after {0} of {1} steps", [done, total]);
		}
		return total === 1
			? t("✓ Completed {0} of {1} step", [done, total])
			: t("✓ Completed {0} of {1} steps", [done, total]);
	}
	const parallel = running.value.filter((task) => task.helper).length;
	if (parallel > 1) return t("⠿ Running {0} in parallel · {1} of {2} done", [parallel, done, total]);
	return total === 1
		? t("⠿ Working through {0} step · {1} of {2} done", [total, done, total])
		: t("⠿ Working through {0} steps · {1} of {2} done", [total, done, total]);
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
/* One line in every state: the tail is cut with an ellipsis, never wrapped. */
.wps-oneline {
	overflow: hidden;
	white-space: nowrap;
	text-overflow: ellipsis;
}
.wps-activity {
	color: var(--ql-text-muted);
}
/* A long plan must not squeeze the conversation above it. */
.wps-rows {
	margin-top: 8px;
	max-height: 160px;
	overflow-y: auto;
}
</style>
