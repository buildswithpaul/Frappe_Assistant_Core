<template>
	<aside class="setup-panel" :aria-label="__('Agent setup')" data-test="agent-setup-panel">
		<header class="panel-header">
			<div>
				<h2 class="panel-title">{{ isLive ? __("Agent setup") : __("Get this agent running") }}</h2>
				<p class="panel-progress">{{ __("{0} of {1} done", [progress.done, progress.total]) }}</p>
			</div>
			<button type="button" class="panel-close" :aria-label="__('Close')" @click="$emit('close')">×</button>
		</header>

		<div class="panel-body">
			<ul>
				<SetupItem v-for="item in items" :key="item.key" :item="item" :show-detail="showDetail(item)">
					<SetupRunsAs
						v-if="item.key === 'runs_as'"
						:user-id="workflow?.default_user_id || ''"
						:current-user="currentUser"
						:saving="saving"
						@save="(user) => $emit('save-settings', { default_user_id: user })"
					/>
					<SetupWhenItRuns
						v-else-if="item.key === 'start'"
						:schedule="schedule"
						:triggers="triggers"
						:status="status"
						:saving="saving"
						@save-schedule="(config) => $emit('save-schedule', config)"
						@open-triggers="$emit('open-triggers')"
					/>
					<SetupWriteTools
						v-else-if="item.key === 'writes' && item.state !== 'ok'"
						:warnings="warnings"
						:current-user="currentUser"
						:stuck="stuckTools"
						:note="writeNote"
						:busy="busy"
						@allow="(w) => $emit('allow-tool', w)"
						@recheck="$emit('recheck')"
					/>
					<SetupModel
						v-else-if="item.key === 'model'"
						:model-id="workflow?.default_model_id || ''"
						:models="models"
						:saving="saving"
						@save="(id) => $emit('save-settings', { default_model_id: id })"
					/>
				</SetupItem>
			</ul>
			<button type="button" class="advanced-link" data-test="open-advanced" @click="$emit('open-advanced')">
				{{ __("Advanced settings: failure handling, timeouts, retries") }}
			</button>
		</div>

		<footer v-if="!isLive && status !== 'Archived'" class="panel-footer">
			<button
				type="button"
				class="activate-btn"
				data-test="setup-activate"
				:disabled="!!blockReason || activating"
				@click="$emit('activate')"
			>
				{{ activating ? __("Activating…") : status === "Paused" ? __("Resume") : __("Activate") }}
			</button>
			<p class="footer-hint">
				{{ blockReason || __("Turns on the schedule and document events, and the agent starts running.") }}
			</p>
		</footer>
	</aside>
</template>

<script setup>
import { computed } from "vue";
import { __ } from "@/utils/i18n";
import SetupItem from "./SetupItem.vue";
import SetupRunsAs from "./SetupRunsAs.vue";
import SetupWhenItRuns from "./SetupWhenItRuns.vue";
import SetupWriteTools from "./SetupWriteTools.vue";
import SetupModel from "./SetupModel.vue";

const props = defineProps({
	items: { type: Array, required: true },
	progress: { type: Object, required: true },
	blockReason: { type: String, default: "" },
	status: { type: String, default: "Draft" },
	workflow: { type: Object, default: null },
	schedule: { type: Object, required: true },
	triggers: { type: Array, default: () => [] },
	warnings: { type: Array, default: () => [] },
	stuckTools: { type: Array, default: () => [] },
	writeNote: { type: String, default: "" },
	models: { type: Array, default: () => [] },
	currentUser: { type: String, default: "" },
	busy: { type: Boolean, default: false },
	saving: { type: Boolean, default: false },
	activating: { type: Boolean, default: false },
});
defineEmits([
	"close",
	"open-advanced",
	"save-settings",
	"save-schedule",
	"open-triggers",
	"allow-tool",
	"recheck",
	"activate",
]);

const isLive = computed(() => props.status === "Active");

// The controls under these items already say what the detail would.
const showDetail = (item) => item.key !== "start" && !(item.key === "writes" && item.state === "todo");
</script>

<style scoped>
.setup-panel {
	width: 340px;
	flex-shrink: 0;
	display: flex;
	flex-direction: column;
	overflow: hidden;
	background: var(--ql-surface);
	border-left: 1px solid var(--ql-border);
}
.panel-header {
	display: flex;
	align-items: flex-start;
	justify-content: space-between;
	padding: 0.75rem 1rem;
	border-bottom: 1px solid var(--ql-border);
}
.panel-title {
	font-size: 0.875rem;
	font-weight: 600;
	color: var(--ql-text);
}
.panel-progress {
	margin-top: 0.125rem;
	font-size: 0.75rem;
	color: var(--ql-text-muted);
}
.panel-close {
	font-size: 1.25rem;
	line-height: 1;
	color: var(--ql-text-muted);
	background: none;
	border: none;
	cursor: pointer;
}
.panel-body {
	flex: 1;
	display: flex;
	flex-direction: column;
	overflow-y: auto;
	padding: 0 1rem;
}
.advanced-link {
	align-self: flex-start;
	margin: 0.25rem 0 0.75rem;
	padding: 0;
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
	text-align: left;
	background: none;
	border: none;
	cursor: pointer;
}
.advanced-link:hover {
	color: var(--ql-accent);
	text-decoration: underline;
}
.panel-footer {
	padding: 0.75rem 1rem;
	border-top: 1px solid var(--ql-border);
}
.activate-btn {
	width: 100%;
	padding: 0.5rem;
	font-size: 0.8125rem;
	font-weight: 600;
	color: var(--ql-accent-text, #fff);
	background: var(--ql-accent);
	border: none;
	border-radius: 0.375rem;
	cursor: pointer;
}
.activate-btn:disabled {
	opacity: 0.5;
	cursor: not-allowed;
}
.footer-hint {
	margin-top: 0.375rem;
	font-size: 0.6875rem;
	line-height: 1.4;
	color: var(--ql-text-muted);
	text-align: center;
}
</style>
