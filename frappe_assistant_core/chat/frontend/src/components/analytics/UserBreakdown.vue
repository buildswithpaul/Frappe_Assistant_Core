<template>
	<div class="user-table-card" v-if="users.length">
		<table class="user-table">
			<thead>
				<tr>
					<th class="col-user">User</th>
					<th class="col-num">Credits</th>
					<th class="col-num">Requests</th>
				</tr>
			</thead>
			<tbody>
				<tr v-for="user in users" :key="user.user_id">
					<td class="col-user">
						<span class="user-id">{{ user.user_id }}</span>
					</td>
					<td class="col-num">
						<div class="percent-bar-wrapper">
							<div
								class="percent-bar"
								:style="{ width: getPercent(user) + '%' }"
							></div>
							<span class="credit-label">{{ formatNumber(getCredits(user)) }}</span>
							<span class="percent-label">({{ getPercent(user) }}%)</span>
						</div>
					</td>
					<td class="col-num">{{ formatNumber(user.request_count) }}</td>
				</tr>
			</tbody>
		</table>
	</div>
	<p v-else class="empty-text">No user data available</p>
</template>

<script setup>
const props = defineProps({
	users: { type: Array, default: () => [] },
	totalCredits: { type: Number, default: 0 },
});

function formatNumber(val) {
	if (!val) return "0";
	return Number(val).toLocaleString();
}

function getCredits(user) {
	return Math.round(user.credits_consumed || 0);
}

function getPercent(user) {
	const total = props.totalCredits;
	const value = getCredits(user);
	if (!total || !value) return 0;
	return Math.round((value / total) * 100);
}
</script>

<style scoped>
.user-table-card {
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.75rem;
	overflow: hidden;
}

.user-table {
	width: 100%;
	border-collapse: collapse;
	font-size: 0.875rem;
}

.user-table thead {
	background: var(--ql-bg);
}

.user-table th {
	padding: 0.75rem 1rem;
	font-weight: 600;
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	text-transform: uppercase;
	letter-spacing: 0.05em;
	text-align: left;
	border-bottom: 1px solid var(--ql-border);
}

.user-table td {
	padding: 0.75rem 1rem;
	color: var(--ql-text);
	border-bottom: 1px solid var(--ql-border);
}

.user-table tbody tr:last-child td {
	border-bottom: none;
}

.user-table tbody tr:hover {
	background: var(--ql-subtle);
}

.col-user {
	min-width: 200px;
}

.col-num {
	text-align: right !important;
	white-space: nowrap;
}

.user-id {
	font-weight: 500;
	color: var(--ql-text);
}

.percent-bar-wrapper {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	justify-content: flex-end;
}

.percent-bar {
	height: 6px;
	background: var(--ql-accent);
	border-radius: 3px;
	min-width: 2px;
	max-width: 100px;
}

.credit-label {
	font-size: 0.8125rem;
	font-weight: 600;
	color: var(--ql-text);
	min-width: 2rem;
	text-align: right;
}

.percent-label {
	font-size: 0.75rem;
	font-weight: 400;
	color: var(--ql-text-muted);
	min-width: 2rem;
	text-align: right;
}

.empty-text {
	font-size: 0.875rem;
	color: var(--ql-text-muted);
}

@media (max-width: 768px) {
	.user-table {
		font-size: 0.8rem;
	}

	.user-table th,
	.user-table td {
		padding: 0.5rem;
	}
}
</style>
