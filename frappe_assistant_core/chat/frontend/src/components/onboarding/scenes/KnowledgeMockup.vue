<template>
	<div class="mockup">
		<div class="row">
			<div class="icon" aria-hidden="true">📄</div>
			<div class="meta">
				<div class="title">Q3-financials.pdf</div>
				<div class="sub">Indexed · 47 chunks</div>
			</div>
		</div>
		<div class="bar"><div class="fill"></div></div>
	</div>
</template>

<style scoped>
.mockup {
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-md);
	padding: 16px;
	max-width: 320px;
	margin: 0 auto;
}
.row { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
.icon {
	width: 36px; height: 36px;
	background: var(--ql-accent-soft);
	border: 1px solid var(--ql-border);
	border-radius: 8px;
	display: flex; align-items: center; justify-content: center;
	font-size: 18px;
}
.meta { text-align: left; }
.title { font-size: 13px; font-weight: 600; color: var(--ql-text); }
.sub { font-size: 11px; color: var(--ql-text-muted); margin-top: 2px; }
.bar {
	height: 4px;
	background: var(--ql-subtle);
	border-radius: 2px;
	overflow: hidden;
}
.fill {
	width: 80%;
	height: 100%;
	background: var(--ql-accent);
	border-radius: 2px;
}
</style>
