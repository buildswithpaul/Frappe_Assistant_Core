<template>
	<div v-if="stats" class="creator-stats">
		<div class="stats-header">
			<h3 class="stats-title">Your Templates</h3>
		</div>

		<!-- Summary cards -->
		<div class="stats-grid">
			<div class="stat-card">
				<span class="stat-value">{{ stats.templates_published || 0 }}</span>
				<span class="stat-label">Published</span>
			</div>
			<div class="stat-card">
				<span class="stat-value">{{ stats.total_imports || 0 }}</span>
				<span class="stat-label">Imports</span>
			</div>
			<div class="stat-card">
				<span class="stat-value">{{ formatCredits(stats.total_credits_earned) }}</span>
				<span class="stat-label">Credits Earned</span>
			</div>
		</div>

		<!-- Per-template breakdown -->
		<div v-if="stats.templates && stats.templates.length > 0" class="templates-list">
			<div v-for="t in stats.templates" :key="t.name" class="template-row">
				<div class="template-info">
					<span class="template-name">{{ t.template_name }}</span>
					<span class="template-category">{{ t.category }}</span>
				</div>
				<div class="template-stats">
					<span v-if="t.average_rating > 0" class="template-rating">
						<svg width="10" height="10" viewBox="0 0 24 24" fill="#f59e0b">
							<path
								d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"
							/>
						</svg>
						{{ t.average_rating.toFixed(1) }}
					</span>
					<span class="template-imports">{{ t.import_count || 0 }} imports</span>
				</div>
			</div>
		</div>

		<p v-else class="no-templates">You haven't published any templates yet.</p>
	</div>
</template>

<script setup>
defineProps({
	stats: { type: Object, default: null },
});

function formatCredits(val) {
	if (!val) return "0";
	return val >= 1000 ? `${(val / 1000).toFixed(1)}K` : val.toFixed(1);
}
</script>

<style scoped>
.creator-stats {
	padding: 1rem;
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.75rem;
	margin-bottom: 1rem;
}
.stats-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	margin-bottom: 0.75rem;
}
.stats-title {
	font-size: 0.875rem;
	font-weight: 600;
	color: var(--ql-text);
	margin: 0;
}
.stats-grid {
	display: grid;
	grid-template-columns: repeat(3, 1fr);
	gap: 0.5rem;
	margin-bottom: 0.75rem;
}
.stat-card {
	display: flex;
	flex-direction: column;
	align-items: center;
	padding: 0.625rem 0.5rem;
	background: var(--ql-bg);
	border-radius: 0.5rem;
	gap: 0.125rem;
}
.stat-value {
	font-size: 1.125rem;
	font-weight: 700;
	color: var(--ql-text);
}
.stat-label {
	font-size: 0.625rem;
	color: var(--ql-text-muted);
	text-transform: uppercase;
	letter-spacing: 0.04em;
}

.templates-list {
	display: flex;
	flex-direction: column;
	gap: 0.375rem;
}
.template-row {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 0.5rem 0.625rem;
	background: var(--ql-bg);
	border-radius: 0.375rem;
	font-size: 0.75rem;
}
.template-info {
	display: flex;
	flex-direction: column;
	gap: 0.125rem;
	min-width: 0;
}
.template-name {
	font-weight: 500;
	color: var(--ql-text);
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}
.template-category {
	font-size: 0.625rem;
	color: var(--ql-text-muted);
	text-transform: uppercase;
}
.template-stats {
	display: flex;
	align-items: center;
	gap: 0.625rem;
	flex-shrink: 0;
}
.template-rating {
	display: flex;
	align-items: center;
	gap: 0.2rem;
	color: var(--ql-text);
}
.template-imports {
	color: var(--ql-text-muted);
}
.no-templates {
	font-size: 0.8125rem;
	color: var(--ql-text-muted);
	text-align: center;
	margin: 0;
}
</style>
