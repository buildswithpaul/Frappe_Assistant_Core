<template>
	<div class="mockup">
		<div class="turn">
			<span class="who">You</span>
			<p class="ask">Summarize Q3 sales</p>
		</div>
		<div class="turn">
			<span class="who who-faco">FACO</span>
			<p class="answer">Q3 sales reached ₹4.2M, up 18% on Q2 — driven by the North region.</p>
		</div>
	</div>
</template>

<style scoped>
.mockup {
	display: flex;
	flex-direction: column;
	gap: 14px;
	max-width: 340px;
	margin: 0 auto;
	text-align: left;
}
.turn { display: flex; flex-direction: column; gap: 3px; }
.who {
	font-size: 10px;
	font-weight: 600;
	letter-spacing: 0.06em;
	text-transform: uppercase;
	color: var(--ql-text-muted);
}
.who-faco { color: var(--ql-accent); }
.ask, .answer {
	margin: 0;
	font-size: 13px;
	line-height: 1.5;
	color: var(--ql-text);
}
.ask { color: var(--ql-text-secondary); }
</style>
