<template>
	<TransitionGroup
		name="card-enter"
		tag="div"
		class="documents-grid"
		:class="{ 'list-view': viewMode === 'list' }"
	>
		<!-- Uploading Cards -->
		<div v-for="upload in uploads" :key="'upload-' + upload.id" class="upload-card">
			<div class="upload-card-accent"></div>
			<div class="upload-card-inner">
				<span class="type-badge" :class="'badge-' + upload.type.toLowerCase()">{{
					upload.type
				}}</span>
				<div class="upload-card-name">{{ upload.name }}</div>
				<div class="upload-progress">
					<div class="progress-bar">
						<div class="progress-fill" :style="{ width: upload.progress + '%' }"></div>
					</div>
					<span class="progress-text">Uploading...</span>
				</div>
			</div>
		</div>

		<!-- Document Cards -->
		<DocumentCard
			v-for="doc in documents"
			:key="doc.document_id"
			:doc="doc"
			:is-admin="isAdmin"
			@preview="$emit('preview', $event)"
			@delete="$emit('delete', $event)"
			@manage-access="$emit('manage-access', $event)"
		/>

		<!-- Trailing slot — e.g. the "Add document" tile, rendered as the
		     last cell of this same grid (not a sibling below it). -->
		<slot />
	</TransitionGroup>
</template>

<script setup>
import DocumentCard from "./DocumentCard.vue";

defineProps({
	documents: { type: Array, default: () => [] },
	uploads: { type: Array, default: () => [] },
	viewMode: { type: String, default: "grid" },
	isAdmin: { type: Boolean, default: false },
});

defineEmits(["preview", "delete", "manage-access"]);
</script>

<style scoped>
/* Document Grid */
.documents-grid {
	display: grid;
	grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
	gap: 0.75rem;
}

.documents-grid.list-view {
	grid-template-columns: 1fr;
	gap: 0.375rem;
}

/* List view: restyle child DocumentCards as compact horizontal rows */
.documents-grid.list-view :deep(.document-card) {
	display: flex;
	align-items: stretch;
}

.documents-grid.list-view :deep(.card-accent) {
	width: 3px;
	height: auto;
	border-radius: 0.75rem 0 0 0.75rem;
	flex-shrink: 0;
}

.documents-grid.list-view :deep(.card-inner) {
	display: flex;
	align-items: center;
	gap: 0.75rem;
	padding: 0.5rem 1rem;
	width: 100%;
	min-width: 0;
}

.documents-grid.list-view :deep(.card-header) {
	margin-bottom: 0;
	flex-shrink: 0;
}

.documents-grid.list-view :deep(.card-name) {
	flex: 1;
	min-width: 0;
	margin: 0;
	font-size: 0.875rem;
}

.documents-grid.list-view :deep(.card-footer) {
	flex-shrink: 0;
}

.documents-grid.list-view :deep(.error-hint) {
	display: none;
}

/* TransitionGroup animations */
.card-enter-enter-active {
	transition: opacity 0.3s ease, transform 0.3s ease;
}

.card-enter-enter-from {
	opacity: 0;
	transform: translateY(8px);
}

.card-enter-leave-active {
	transition: opacity 0.2s ease, transform 0.2s ease;
}

.card-enter-leave-to {
	opacity: 0;
	transform: scale(0.97);
}

.card-enter-move {
	transition: transform 0.3s ease;
}

/* Upload Card */
.upload-card {
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.75rem;
	overflow: hidden;
	opacity: 0.7;
}

.upload-card-accent {
	height: 3px;
	background: var(--ql-accent);
	animation: upload-shimmer 1.5s ease-in-out infinite;
}

@keyframes upload-shimmer {
	0%,
	100% {
		opacity: 0.5;
	}
	50% {
		opacity: 1;
	}
}

.upload-card-inner {
	padding: 0.75rem 1rem;
}

.upload-card-name {
	font-size: 0.875rem;
	font-weight: 500;
	color: var(--ql-text);
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
	margin: 0.5rem 0;
}

.type-badge {
	font-size: 0.625rem;
	font-weight: 600;
	letter-spacing: 0.05em;
	text-transform: uppercase;
	padding: 0.125rem 0.375rem;
	border-radius: 0.25rem;
	background: var(--ql-subtle);
	color: var(--ql-text-secondary);
}

.type-badge.badge-pdf {
	background: rgba(239, 68, 68, 0.1);
	color: #ef4444;
}
.type-badge.badge-markdown {
	background: var(--ql-accent-soft);
	color: var(--ql-accent);
}
.type-badge.badge-text {
	background: var(--ql-subtle);
	color: var(--ql-text-muted);
}

.upload-progress {
	display: flex;
	flex-direction: column;
	gap: 0.25rem;
}

.progress-bar {
	height: 4px;
	background: var(--ql-border);
	border-radius: 2px;
	overflow: hidden;
}

.progress-fill {
	height: 100%;
	background: var(--ql-accent);
	border-radius: 2px;
	transition: width 0.3s ease;
}

.progress-text {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
}

@media (max-width: 768px) {
	.documents-grid {
		grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
		gap: 0.75rem;
	}
}
</style>
