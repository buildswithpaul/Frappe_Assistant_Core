<template>
	<div class="tool-summary">
		<template v-if="pills.length">
			<span class="summary-label">{{ __("Asked for") }}</span>
			<ul class="summary-pills">
				<li v-for="(pill, i) in pills" :key="i">
					{{ pill.label }} <strong>{{ pill.value }}</strong>
				</li>
			</ul>
		</template>

		<template v-if="view.kind !== 'none'">
			<span class="summary-label">{{ view.kind === "error" ? __("What went wrong") : __("Got back") }}</span>
			<RecordTable v-if="view.kind === 'table'" :view="view" :has-raw="hasRaw" />
			<!-- <div>, not <p>: a paragraph inside an assistant turn takes the message's body size. -->
			<div v-else-if="view.kind === 'empty'" class="summary-plain">{{ __("Nothing matched.") }}</div>
			<div v-else-if="view.kind === 'count'" class="summary-plain">{{ __("{0} found. No preview for this one.", [view.count]) }}</div>
			<div v-else-if="view.kind === 'stopped'" class="summary-plain">
				{{ block.stoppedReason || __("This call did not finish. If it needed your approval, the assistant makes it as a separate step with its card.") }}
			</div>
			<div v-else-if="view.kind === 'truncated'" class="summary-plain">{{ __("This result is too large to show while the chat is live. Reload the page to see it.") }}</div>
			<FieldList v-else-if="view.kind === 'record'" :fields="view.fields" />
			<div v-else class="summary-plain" :class="{ 'summary-error': view.kind === 'error' }">
				{{ view.text || (hasRaw ? __("The call failed. Raw has the full response.") : __("The call failed.")) }}
			</div>
			<div v-if="view.more" class="summary-more">
				{{ moreFields }}
			</div>
		</template>
		<div v-else-if="!pills.length" class="summary-plain">{{ running ? __("Waiting for the result…") : hasRaw ? __("Nothing to show. Raw has the full call.") : __("Nothing to show.") }}</div>
	</div>
</template>

<script setup>
import { computed } from "vue";
import { __ } from "@/utils/i18n";
import FieldList from "./FieldList.vue";
import RecordTable from "./RecordTable.vue";
import { requestPills, resultView } from "./toolView";

const props = defineProps({
	block: { type: Object, required: true },
	// False for a script's step, which has no Raw tab for these lines to point at.
	hasRaw: { type: Boolean, default: true },
});

const pills = computed(() => requestPills(props.block.input));
const view = computed(() => resultView(props.block));
const running = computed(() => props.block.status === "running");
const moreFields = computed(() => {
	const more = view.value.more;
	if (props.hasRaw) return more === 1 ? __("1 more field in Raw.") : __("{0} more fields in Raw.", [more]);
	return more === 1 ? __("1 more field.") : __("{0} more fields.", [more]);
});
</script>

<style scoped>
.tool-summary {
	display: flex;
	flex-direction: column;
	gap: 6px;
	min-width: 0;
}
.summary-label {
	font-size: 10px;
	font-weight: 600;
	letter-spacing: 0.08em;
	text-transform: uppercase;
	color: var(--ql-text-muted);
}
.summary-label:not(:first-child) {
	margin-top: 4px;
}
.summary-pills {
	display: flex;
	flex-wrap: wrap;
	gap: 5px;
	margin: 0;
	padding: 0;
	list-style: none;
}
.summary-pills li {
	max-width: 100%;
	padding: 2px 9px;
	font-size: 11.5px;
	overflow-wrap: anywhere;
	color: var(--ql-text-secondary);
	background: var(--ql-subtle);
	border-radius: 999px;
}
.summary-pills strong {
	font-weight: 500;
	color: var(--ql-text);
}
.summary-plain {
	max-height: 320px;
	overflow-y: auto;
}
.summary-plain,
.summary-more {
	font-size: 12px;
	line-height: 1.5;
	white-space: pre-wrap;
	overflow-wrap: anywhere;
	color: var(--ql-text-secondary);
}
.summary-more {
	font-size: 11px;
	color: var(--ql-text-muted);
}
.summary-error {
	color: var(--ql-danger);
}
</style>
