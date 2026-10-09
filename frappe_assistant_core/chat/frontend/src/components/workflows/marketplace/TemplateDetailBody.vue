<template>
	<div class="detail-body-root">
		<div class="panel-header">
			<div class="header-left">
				<h2 class="panel-title">{{ template.template_name || __("Template") }}</h2>
				<div v-if="template.is_official || template.featured" class="title-badges">
					<span v-if="template.is_official" class="badge badge-official">
						<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
							<path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
						</svg>
						{{ __("Official") }}
					</span>
					<span v-if="template.featured" class="badge badge-featured">
						<svg width="12" height="12" viewBox="0 0 24 24" fill="#f59e0b">
							<path
								d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"
							/>
						</svg>
						{{ __("Featured") }}
					</span>
				</div>
			</div>
			<button
				class="close-btn"
				:title="__('Close')"
				:aria-label="__('Close')"
				@click="emit('close')"
			>
				<svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M6 18L18 6M6 6l12 12"
					/>
				</svg>
			</button>
		</div>

		<div class="panel-body">
			<div class="meta-row">
				<span class="meta-category">{{ template.category || __("General") }}</span>
				<span v-if="template.version" class="meta-item">v{{ template.version }}</span>
				<span v-if="template.author_name" class="meta-item">{{
					__("by {0}", [template.author_name])
				}}</span>
				<span v-if="template.import_count" class="meta-item">{{ importsLabel }}</span>
				<span v-if="template.min_agent_nodes" class="meta-item" :title="tasksHint">{{
					tasksLabel
				}}</span>
			</div>

			<div class="detail-section">
				<h3 class="section-label">{{ __("Description") }}</h3>
				<p class="description-text">
					{{ template.description || __("No description provided.") }}
				</p>
			</div>

			<TemplateRatingSection
				ref="ratingRef"
				:template="template"
				:rating="template.average_rating || 0"
				@rate="(payload) => emit('rate', payload)"
			/>

			<TemplateNeeds :requires="template.requires" :fallback-tools="legacyTools" />
			<TemplateMiniGraph :graph-json="template.graph_json" />

			<div v-if="variables.length > 0" class="detail-section">
				<h3 class="section-label">{{ __("Configurable Variables") }}</h3>
				<div class="variables-list">
					<div v-for="v in variables" :key="v.key" class="variable-item">
						<span class="variable-name">{{ v.label }}</span>
						<span v-if="v.description" class="variable-desc">{{ v.description }}</span>
					</div>
				</div>
			</div>
		</div>

		<div
			v-if="template.review_status && template.review_status !== 'Approved'"
			class="review-status-bar"
		>
			<span :class="['review-badge', reviewClass]">{{ template.review_status }}</span>
			<p
				v-if="template.review_notes && template.review_status === 'Rejected'"
				class="review-reason"
			>
				{{ template.review_notes }}
			</p>
		</div>
	</div>
</template>

<script setup>
import { computed, ref } from "vue";
import { __ } from "@/utils/i18n";
import TemplateRatingSection from "./TemplateRatingSection.vue";
import TemplateNeeds from "./TemplateNeeds.vue";
import TemplateMiniGraph from "./TemplateMiniGraph.vue";
import { legacyRequiredTools, normalizeVariableSchema } from "./templateSchema";

const props = defineProps({
	template: { type: Object, required: true },
});

const emit = defineEmits(["rate", "close"]);

const ratingRef = ref(null);

const legacyTools = computed(() => {
	const tools = legacyRequiredTools(props.template);
	return tools.length ? tools : legacyRequiredTools({ required_tools: props.template.tool_hints });
});
const variables = computed(() =>
	normalizeVariableSchema(props.template.variables_schema, props.template.default_variables)
);
const reviewClass = computed(
	() => `review-${(props.template.review_status || "").toLowerCase().replace(/ /g, "-")}`
);

const importsLabel = computed(() => {
	const n = props.template.import_count;
	return n === 1 ? __("1 import") : __("{0} imports", [n]);
});
const tasksLabel = computed(() => {
	const n = props.template.min_agent_nodes;
	return n === 1 ? __("1 task") : __("{0} tasks", [n]);
});
const tasksHint = computed(() =>
	__("This template uses {0}. More tasks = higher credit cost per run.", [tasksLabel.value])
);

defineExpose({
	resetForm: () => ratingRef.value?.resetForm(),
	onRatingComplete: () => ratingRef.value?.onRatingComplete(),
});
</script>

<style scoped>
.detail-body-root {
	display: flex;
	flex-direction: column;
	flex: 1;
	min-height: 0;
}
.panel-header {
	display: flex;
	align-items: flex-start;
	justify-content: space-between;
	padding: 1.25rem 1.25rem 1rem;
	border-bottom: 1px solid var(--ql-border);
	flex-shrink: 0;
	gap: 0.75rem;
}
.header-left {
	display: flex;
	flex-direction: column;
	gap: 0.5rem;
	min-width: 0;
}
.panel-title {
	font-size: 1.125rem;
	font-weight: 600;
	color: var(--ql-text);
	margin: 0;
	line-height: 1.3;
}
.title-badges {
	display: flex;
	gap: 0.375rem;
	flex-wrap: wrap;
}
.badge {
	display: inline-flex;
	align-items: center;
	gap: 0.2rem;
	font-size: 0.625rem;
	font-weight: 600;
	padding: 0.125rem 0.375rem;
	border-radius: 9999px;
	text-transform: uppercase;
	letter-spacing: 0.03em;
}
.badge-official {
	background: var(--ql-accent-soft);
	color: var(--ql-accent);
}
.badge-featured {
	background: rgba(245, 158, 11, 0.1);
	color: #f59e0b;
}
.close-btn {
	display: flex;
	align-items: center;
	justify-content: center;
	width: 28px;
	height: 28px;
	background: transparent;
	border: none;
	color: var(--ql-text-muted);
	border-radius: 0.25rem;
	cursor: pointer;
	transition: all 0.15s ease;
	flex-shrink: 0;
}
.close-btn:hover {
	background: var(--ql-subtle);
	color: var(--ql-text);
}
.panel-body {
	flex: 1;
	overflow-y: auto;
	padding: 1.25rem;
	display: flex;
	flex-direction: column;
	gap: 1.25rem;
}
.meta-row {
	display: flex;
	flex-wrap: wrap;
	align-items: center;
	gap: 0.5rem;
}
.meta-category {
	font-size: 0.6875rem;
	font-weight: 600;
	padding: 0.125rem 0.5rem;
	border-radius: 9999px;
	text-transform: uppercase;
	letter-spacing: 0.03em;
	background: var(--ql-accent-soft);
	color: var(--ql-accent);
}
.meta-item {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
}
.meta-item::before {
	content: "\00b7";
	margin-right: 0.5rem;
}
.detail-section {
	display: flex;
	flex-direction: column;
	gap: 0.5rem;
}
.section-label {
	font-size: 0.75rem;
	font-weight: 600;
	color: var(--ql-text-muted);
	text-transform: uppercase;
	letter-spacing: 0.04em;
	margin: 0;
}
.description-text {
	font-size: 0.8125rem;
	color: var(--ql-text);
	line-height: 1.6;
	margin: 0;
	white-space: pre-wrap;
}
.variables-list {
	display: flex;
	flex-direction: column;
	gap: 0.375rem;
}
.variable-item {
	display: flex;
	flex-direction: column;
	gap: 0.125rem;
	padding: 0.5rem 0.625rem;
	background: var(--ql-bg);
	border-radius: 0.375rem;
}
.variable-name {
	font-size: 0.8125rem;
	font-weight: 600;
	color: var(--ql-text);
}
.variable-desc {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
}
.review-status-bar {
	padding: 0.625rem 1.25rem;
	border-top: 1px solid var(--ql-border);
}
.review-badge {
	font-size: 0.6875rem;
	font-weight: 600;
	padding: 0.125rem 0.5rem;
	border-radius: 9999px;
	text-transform: uppercase;
	letter-spacing: 0.03em;
}
.review-pending-review {
	background: rgba(245, 158, 11, 0.12);
	color: #d97706;
}
.review-rejected,
.review-suspended {
	background: rgba(239, 68, 68, 0.12);
	color: #dc2626;
}
.review-reason {
	font-size: 0.75rem;
	color: var(--ql-danger);
	margin: 0.375rem 0 0;
}
</style>
