<template>
	<div class="page-list">
		<div v-if="!pages.length" class="page-list-empty">
			<p>{{ __("No pages yet. Ask FACO to build one in chat.") }}</p>
			<router-link to="/chat">{{ __("Back to chat") }}</router-link>
		</div>
		<ul v-else class="page-list-rows">
			<li v-for="page in pages" :key="page.name">
				<button type="button" class="page-list-row" @click="emit('open', page.name)">
					<span class="page-list-title">{{ page.title || page.name }}</span>
					<span class="page-list-chip">{{ page.visibility === "Shared" ? __("Shared") : __("Only you") }}</span>
					<span v-if="page.draft" class="page-list-chip">{{ __("Draft") }}</span>
					<span class="page-list-updated">
						{{ __("Updated {0}", [updatedAgo(page.modified)]) }}
					</span>
				</button>
			</li>
		</ul>
	</div>
</template>

<script setup>
import { formatRelativeTime } from "@/composables/useFormatters";
import { __ } from "@/utils/i18n";

defineProps({
	pages: { type: Array, default: () => [] },
});

const emit = defineEmits(["open"]);

// The helper opens with a capital ("Just now"), which reads wrong after "Updated".
const updatedAgo = (modified) => {
	const text = formatRelativeTime(modified);
	return text.charAt(0).toLowerCase() + text.slice(1);
};
</script>

<style scoped>
.page-list-rows {
	list-style: none;
	margin: 0;
	padding: 0;
	display: flex;
	flex-direction: column;
	gap: 0.5rem;
	max-width: 48rem;
}

.page-list-row {
	width: 100%;
	display: flex;
	align-items: center;
	gap: 0.5rem;
	padding: 0.75rem 1rem;
	text-align: left;
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	color: var(--ql-text);
	cursor: pointer;
}

.page-list-row:hover {
	background: var(--ql-subtle);
}

.page-list-title {
	flex: 1;
	font-weight: 600;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.page-list-chip {
	font-size: 0.7rem;
	padding: 0.125rem 0.5rem;
	border-radius: 999px;
	background: var(--ql-subtle);
	color: var(--ql-text-secondary);
}

.page-list-updated {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
}

.page-list-empty {
	padding: 3rem 1rem;
	text-align: center;
	color: var(--ql-text-muted);
}

.page-list-empty a {
	color: var(--ql-accent);
}
</style>
