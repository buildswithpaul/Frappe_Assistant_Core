<template>
	<button v-if="featured" class="featured-card" @click="$emit('select', template)">
		<div class="featured-badge">
			<svg width="12" height="12" viewBox="0 0 24 24" fill="#f59e0b">
				<path
					d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"
				/>
			</svg>
			Featured
		</div>
		<h4 class="featured-name">{{ template.template_name }}</h4>
		<p class="featured-description">
			{{ template.short_description || template.description || "No description" }}
		</p>
		<div class="featured-meta">
			<span class="featured-category">{{ template.category || "General" }}</span>
			<span v-if="template.average_rating > 0" class="featured-rating">
				<svg width="10" height="10" viewBox="0 0 24 24" fill="#f59e0b">
					<path
						d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"
					/>
				</svg>
				{{ template.average_rating.toFixed(1) }}
			</span>
		</div>
	</button>

	<button v-else class="marketplace-card" @click="$emit('select', template)">
		<div class="card-top">
			<div class="card-name-row">
				<span class="card-name">
					<svg
						v-if="template.is_official"
						class="verified-icon"
						width="14"
						height="14"
						viewBox="0 0 24 24"
						fill="currentColor"
					>
						<path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
					</svg>
					<svg
						v-if="template.featured"
						class="featured-star"
						width="12"
						height="12"
						viewBox="0 0 24 24"
						fill="#f59e0b"
					>
						<path
							d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"
						/>
					</svg>
					{{ template.template_name }}
				</span>
				<span class="card-category">{{ template.category || "General" }}</span>
				<span
					v-if="template.review_status === 'Pending Review'"
					class="review-badge review-pending"
					>Pending</span
				>
				<span
					v-else-if="template.review_status === 'Rejected'"
					class="review-badge review-rejected"
					>Rejected</span
				>
				<span
					v-else-if="template.review_status === 'Suspended'"
					class="review-badge review-suspended"
					>Suspended</span
				>
			</div>
			<p class="card-description">
				{{ template.short_description || template.description || "No description" }}
			</p>
		</div>

		<div class="card-bottom">
			<div class="card-stats">
				<span v-if="template.average_rating > 0" class="card-rating">
					<svg width="10" height="10" viewBox="0 0 24 24" fill="#f59e0b">
						<path
							d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"
						/>
					</svg>
					{{ template.average_rating.toFixed(1) }}
					<span class="rating-count">({{ template.rating_count }})</span>
				</span>
				<span v-if="template.import_count" class="card-imports"
					>{{ template.import_count }} import{{
						template.import_count !== 1 ? "s" : ""
					}}</span
				>
				<span v-if="template.author_name" class="card-author">{{
					template.author_name
				}}</span>
			</div>
			<span class="use-btn" @click.stop="$emit('quick-use', template)">Use Template</span>
		</div>
	</button>
</template>

<script setup>
defineProps({
	template: { type: Object, required: true },
	featured: { type: Boolean, default: false },
});

defineEmits(["select", "quick-use"]);
</script>

<style scoped>
/* Featured card */
.featured-card {
	flex: 0 0 220px;
	text-align: left;
	background: linear-gradient(135deg, rgba(245, 158, 11, 0.05), rgba(245, 158, 11, 0.02));
	border: 1px solid rgba(245, 158, 11, 0.2);
	border-radius: 0.75rem;
	padding: 1rem;
	cursor: pointer;
	transition: all 0.15s ease;
	display: flex;
	flex-direction: column;
	gap: 0.5rem;
}

.featured-card:hover {
	border-color: rgba(245, 158, 11, 0.5);
	box-shadow: 0 2px 12px rgba(245, 158, 11, 0.1);
}

.featured-badge {
	display: inline-flex;
	align-items: center;
	gap: 0.25rem;
	font-size: 0.625rem;
	font-weight: 600;
	color: #f59e0b;
	text-transform: uppercase;
	letter-spacing: 0.04em;
}

.featured-name {
	font-size: 0.875rem;
	font-weight: 600;
	color: var(--ql-text);
	margin: 0;
	line-height: 1.3;
}

.featured-description {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	margin: 0;
	display: -webkit-box;
	-webkit-line-clamp: 2;
	-webkit-box-orient: vertical;
	overflow: hidden;
	line-height: 1.4;
	flex: 1;
}

.featured-meta {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	margin-top: auto;
}

.featured-category {
	font-size: 0.625rem;
	font-weight: 600;
	padding: 0.125rem 0.375rem;
	border-radius: 9999px;
	text-transform: uppercase;
	letter-spacing: 0.03em;
	background: var(--ql-accent-soft);
	color: var(--ql-accent);
}

.featured-rating {
	display: inline-flex;
	align-items: center;
	gap: 0.2rem;
	font-size: 0.6875rem;
	font-weight: 500;
	color: var(--ql-text);
}

/* Regular marketplace card */
.marketplace-card {
	text-align: left;
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.75rem;
	padding: 1.25rem;
	cursor: pointer;
	transition: all 0.15s ease;
	display: flex;
	flex-direction: column;
	gap: 0.75rem;
}

.marketplace-card:hover {
	border-color: var(--ql-accent);
	box-shadow: 0 2px 8px var(--ql-accent-soft);
}

.card-top {
	display: flex;
	flex-direction: column;
	gap: 0.5rem;
	flex: 1;
}

.card-name-row {
	display: flex;
	align-items: flex-start;
	justify-content: space-between;
	gap: 0.5rem;
}

.card-name {
	font-size: 0.875rem;
	font-weight: 600;
	color: var(--ql-text);
	display: flex;
	align-items: center;
	gap: 0.25rem;
	line-height: 1.3;
}

.verified-icon {
	color: var(--ql-accent);
	flex-shrink: 0;
}

.featured-star {
	flex-shrink: 0;
}

.card-category {
	font-size: 0.625rem;
	font-weight: 600;
	padding: 0.125rem 0.375rem;
	border-radius: 9999px;
	text-transform: uppercase;
	letter-spacing: 0.03em;
	background: var(--ql-accent-soft);
	color: var(--ql-accent);
	flex-shrink: 0;
	white-space: nowrap;
}

.card-description {
	font-size: 0.8125rem;
	color: var(--ql-text-muted);
	margin: 0;
	display: -webkit-box;
	-webkit-line-clamp: 2;
	-webkit-box-orient: vertical;
	overflow: hidden;
	line-height: 1.4;
}

.card-bottom {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 0.5rem;
	margin-top: auto;
}

.card-stats {
	display: flex;
	gap: 0.625rem;
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
	align-items: center;
	flex-wrap: wrap;
}

.card-rating {
	display: inline-flex;
	align-items: center;
	gap: 0.2rem;
	color: var(--ql-text);
	font-weight: 500;
}

.rating-count {
	color: var(--ql-text-muted);
	font-weight: 400;
}

.card-imports,
.card-author {
	white-space: nowrap;
}

.use-btn {
	display: inline-flex;
	align-items: center;
	padding: 0.375rem 0.75rem;
	font-size: 0.75rem;
	font-weight: 500;
	color: var(--ql-accent);
	background: var(--ql-accent-soft);
	border: none;
	border-radius: 0.375rem;
	cursor: pointer;
	transition: all 0.15s ease;
	white-space: nowrap;
	flex-shrink: 0;
}

.use-btn:hover {
	background: var(--ql-accent-soft);
}

/* Review status badges */
.review-badge {
	font-size: 0.5625rem;
	font-weight: 600;
	padding: 0.0625rem 0.375rem;
	border-radius: 9999px;
	text-transform: uppercase;
	letter-spacing: 0.03em;
}
.review-pending {
	background: rgba(245, 158, 11, 0.12);
	color: #d97706;
}
.review-rejected {
	background: rgba(239, 68, 68, 0.12);
	color: #dc2626;
}
.review-suspended {
	background: rgba(239, 68, 68, 0.12);
	color: #dc2626;
}

@media (max-width: 640px) {
	.featured-card {
		flex: 0 0 180px;
	}
}
</style>
