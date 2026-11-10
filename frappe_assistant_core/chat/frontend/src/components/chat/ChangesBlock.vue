<template>
	<section class="changes-block" :aria-label="__('Changes made')">
		<h4 class="cb-title">{{ __("Changes made") }}</h4>
		<ul class="cb-list">
			<li
				v-for="change in block.changes"
				:key="`${change.doctype}/${change.name}`"
				class="cb-row"
				:data-change="change.name"
			>
				<div class="cb-line">
					<span class="cb-text" :class="{ 'cb-undone': change.undone }">
						{{ changeLabel(change) }} · <strong>{{ change.name }}</strong>
					</span>
					<span v-if="change.undone" class="cb-state">{{ __("Undone") }}</span>
					<button
						v-else
						type="button"
						class="cb-undo"
						:disabled="isStreaming || isBusy(change)"
						:aria-busy="isBusy(change) ? 'true' : null"
						@click="undo(change)"
					>
						{{ __("Undo") }}
					</button>
				</div>
				<p v-if="refusals[keyOf(change)]" class="cb-refusal" role="status">
					{{ __("Can't undo: {0}", [refusals[keyOf(change)]]) }}
				</p>
			</li>
		</ul>
	</section>
</template>

<script setup>
import { reactive } from "vue";
import { useChatStore } from "@/stores/chatStore";
import { __ } from "@/utils/i18n";

const props = defineProps({
	// The message's changes_made block: { changes: [{ doctype, name, action, undo, undone }] }.
	block: { type: Object, required: true },
	messageId: { type: String, default: null },
	// The stream's final snapshot replaces the blocks, so an undo made mid-stream could be lost.
	isStreaming: { type: Boolean, default: false },
});

const chatStore = useChatStore();
const busy = reactive({});
const refusals = reactive({});

const keyOf = (change) => `${change.doctype}/${change.name}`;
const isBusy = (change) => Boolean(busy[keyOf(change)]);

function changeLabel(change) {
	if (change.action === "create") return __("Created {0}", [change.doctype]);
	return change.doctype;
}

async function undo(change) {
	const key = keyOf(change);
	if (props.isStreaming || busy[key]) return;
	busy[key] = true;
	refusals[key] = null;
	try {
		const result = await chatStore.undoChange({
			messageId: props.messageId,
			doctype: change.doctype,
			name: change.name,
		});
		if (!result.success) refusals[key] = result.reason || __("Something went wrong");
	} finally {
		busy[key] = false;
	}
}
</script>

<style scoped>
.changes-block {
	margin: 8px 0;
	padding: 10px 14px;
	border: 1px solid var(--ql-border);
	border-radius: 10px;
	background: var(--ql-subtle);
}

.cb-title {
	margin: 0 0 6px;
	font-size: 12px;
	font-weight: 600;
	color: var(--ql-text-secondary);
}

.cb-list {
	list-style: none;
	margin: 0;
	padding: 0;
}

.cb-row + .cb-row {
	border-top: 1px solid var(--ql-border);
}

.cb-line {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 10px;
	padding: 6px 0;
	font-size: 13px;
}

.cb-text {
	min-width: 0;
	color: var(--ql-text);
	overflow-wrap: anywhere;
}

.cb-undone {
	color: var(--ql-text-muted);
	text-decoration: line-through;
}

.cb-state {
	flex: none;
	font-size: 12px;
	color: var(--ql-text-muted);
}

.cb-undo {
	flex: none;
	padding: 4px 10px;
	font-family: inherit;
	font-size: 12px;
	font-weight: 500;
	color: var(--ql-text-secondary);
	background: var(--ql-surface);
	border: 1px solid var(--ql-border-hover);
	border-radius: var(--ql-radius-md, 8px);
	cursor: pointer;
}

.cb-undo:hover:not(:disabled) {
	color: var(--ql-accent);
	border-color: var(--ql-accent);
}

.cb-undo:focus-visible {
	outline: 2px solid var(--ql-accent);
	outline-offset: 2px;
}

.cb-undo:disabled {
	opacity: 0.45;
	cursor: not-allowed;
}

.cb-refusal {
	margin: 0 0 6px;
	font-size: 12px;
	color: var(--ql-danger);
}
</style>
