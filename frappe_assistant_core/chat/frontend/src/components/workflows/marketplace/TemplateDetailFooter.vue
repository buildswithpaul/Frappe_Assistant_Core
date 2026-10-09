<template>
	<div class="panel-footer">
		<button
			v-if="template.is_public && !template.is_official"
			class="btn-report"
			:title="__('Report template')"
			@click="emit('report')"
		>
			<svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M3 21v-4m0 0V5a2 2 0 012-2h6.5l1 1H21l-3 6 3 6h-8.5l-1-1H5a2 2 0 00-2 2z"
				/>
			</svg>
			{{ __("Report") }}
		</button>
		<div class="footer-right">
			<p v-if="useBlocked" class="use-hint">
				{{ __("Only an administrator can import workflow templates.") }}
			</p>
			<button class="btn-secondary" @click="emit('download')">
				<svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
					/>
				</svg>
				{{ __("Download JSON") }}
			</button>
			<button class="btn-primary" :disabled="useBlocked" @click="emit('use')">
				{{ __("Use This Template") }}
			</button>
		</div>
	</div>
</template>

<script setup>
import { computed } from "vue";
import { __ } from "@/utils/i18n";
import { useUserStore } from "@/stores/userStore";

const props = defineProps({
	template: { type: Object, required: true },
});

const emit = defineEmits(["report", "download", "use"]);

const userStore = useUserStore();

// Mirrors import_listing: only Prompt and Skill listings are open to every member.
const MEMBER_IMPORTABLE_TYPES = ["Prompt", "Skill"];
const useBlocked = computed(
	() => !userStore.isAdmin && !MEMBER_IMPORTABLE_TYPES.includes(props.template.listing_type)
);
</script>

<style scoped>
.panel-footer {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 0.625rem;
	padding: 1rem 1.25rem;
	border-top: 1px solid var(--ql-border);
	flex-shrink: 0;
	flex-wrap: wrap;
}
.footer-right {
	display: flex;
	align-items: center;
	gap: 0.625rem;
	flex-wrap: wrap;
}
.use-hint {
	flex-basis: 100%;
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	margin: 0;
}
.btn-report {
	display: inline-flex;
	align-items: center;
	gap: 0.25rem;
	padding: 0.375rem 0.625rem;
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	background: transparent;
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	cursor: pointer;
}
.btn-report:hover {
	color: var(--ql-danger);
	border-color: var(--ql-danger);
}
.btn-primary {
	display: inline-flex;
	align-items: center;
	gap: 0.375rem;
	padding: 0.5rem 1rem;
	font-size: 0.8125rem;
	font-weight: 500;
	color: white;
	background: var(--ql-accent);
	border: none;
	border-radius: 0.5rem;
	cursor: pointer;
	transition: all 0.15s ease;
}
.btn-primary:hover:not(:disabled) {
	opacity: 0.9;
}
.btn-primary:disabled {
	opacity: 0.5;
	cursor: not-allowed;
}
.btn-secondary {
	display: inline-flex;
	align-items: center;
	gap: 0.375rem;
	padding: 0.5rem 1rem;
	font-size: 0.8125rem;
	font-weight: 500;
	color: var(--ql-text);
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	cursor: pointer;
	transition: all 0.15s ease;
}
.btn-secondary:hover {
	border-color: var(--ql-text);
}
@media (max-width: 640px) {
	.panel-footer,
	.footer-right {
		flex-direction: column;
		align-items: stretch;
	}
	.btn-primary,
	.btn-secondary {
		width: 100%;
		justify-content: center;
	}
}
</style>
