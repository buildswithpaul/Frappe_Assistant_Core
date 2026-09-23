<template>
	<div class="mockup">
		<!-- Shield with a lock — conversations stay on your machine -->
		<div class="shield" aria-hidden="true">
			<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
				<path stroke-linecap="round" stroke-linejoin="round" d="M12 2 4 5v6c0 5 3.4 8.3 8 9.9 4.6-1.6 8-4.9 8-9.9V5l-8-3z" />
				<rect x="9" y="11" width="6" height="5" rx="1" stroke-linecap="round" stroke-linejoin="round" />
				<path stroke-linecap="round" stroke-linejoin="round" d="M10.5 11V9.5a1.5 1.5 0 0 1 3 0V11" />
			</svg>
		</div>

		<!-- The promise — your data never touches our servers -->
		<div class="rows" aria-hidden="true">
			<div class="row">
				<span class="tick">✓</span>
				<span>Conversations stay on your machine</span>
			</div>
			<div class="row">
				<span class="tick">✓</span>
				<span>Never retained on our servers</span>
			</div>
			<div class="row">
				<span class="tick">✓</span>
				<span>Zero-retention by design</span>
			</div>
		</div>
	</div>
</template>

<style scoped>
.mockup {
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 18px;
	max-width: 360px;
	margin: 0 auto;
}

.shield {
	width: 64px;
	height: 64px;
	border-radius: 50%;
	background: var(--ql-accent-soft);
	color: var(--ql-accent);
	display: flex;
	align-items: center;
	justify-content: center;
	box-shadow: 0 0 24px var(--ql-accent-soft);
	flex-shrink: 0;
}
.shield svg { width: 34px; height: 34px; }

.rows {
	display: flex;
	flex-direction: column;
	gap: 8px;
	width: 100%;
}
.row {
	display: flex;
	align-items: center;
	gap: 10px;
	padding: 9px 14px;
	border-radius: 10px;
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	font-size: 13px;
	color: var(--ql-text-secondary);
}
.tick {
	display: flex;
	align-items: center;
	justify-content: center;
	width: 18px;
	height: 18px;
	border-radius: 50%;
	background: var(--ql-accent);
	color: #ffffff;
	font-size: 11px;
	font-weight: 700;
	flex-shrink: 0;
}
</style>
