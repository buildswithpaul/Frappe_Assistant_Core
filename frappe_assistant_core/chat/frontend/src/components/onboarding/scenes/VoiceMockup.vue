<template>
	<div class="mockup">
		<!-- Mic pulsing with waveform suggesting active recording -->
		<div class="mic-row" aria-hidden="true">
			<div class="mic">
				<div class="mic-pulse"></div>
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
					<path stroke-linecap="round" stroke-linejoin="round" d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
					<path stroke-linecap="round" stroke-linejoin="round" d="M19 10v2a7 7 0 0 1-14 0v-2" />
					<line x1="12" y1="19" x2="12" y2="23" stroke-linecap="round" />
					<line x1="8" y1="23" x2="16" y2="23" stroke-linecap="round" />
				</svg>
			</div>
			<div class="wave">
				<span></span><span></span><span></span><span></span><span></span>
			</div>
		</div>

		<!-- Language chips — pick from your own language -->
		<div class="chips" aria-hidden="true">
			<span class="chip">English</span>
			<span class="chip">हिंदी</span>
			<span class="chip chip-active">தமிழ்</span>
			<span class="chip">ಕನ್ನಡ</span>
			<span class="chip">العربية</span>
			<span class="chip">Español</span>
		</div>
	</div>
</template>

<style scoped>
.mockup {
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 16px;
	max-width: 360px;
	margin: 0 auto;
}

.mic-row {
	display: flex;
	align-items: center;
	gap: 14px;
}

.mic {
	position: relative;
	width: 56px;
	height: 56px;
	border-radius: 50%;
	background: var(--ql-accent);
	color: #ffffff;
	display: flex;
	align-items: center;
	justify-content: center;
	box-shadow: 0 8px 24px -8px var(--ql-accent-soft);
	flex-shrink: 0;
}
.mic svg { width: 24px; height: 24px; }

.mic-pulse {
	position: absolute;
	inset: -6px;
	border-radius: 50%;
	border: 2px solid var(--ql-accent);
	opacity: 0.5;
	animation: mic-pulse 1.6s ease-out infinite;
}

.wave {
	display: flex;
	align-items: center;
	gap: 4px;
	height: 36px;
}
.wave span {
	width: 3px;
	border-radius: 2px;
	background: var(--ql-accent);
	animation: wave 1.1s ease-in-out infinite;
}
.wave span:nth-child(1) { height: 40%; animation-delay: 0.0s; }
.wave span:nth-child(2) { height: 80%; animation-delay: 0.15s; }
.wave span:nth-child(3) { height: 60%; animation-delay: 0.30s; }
.wave span:nth-child(4) { height: 90%; animation-delay: 0.45s; }
.wave span:nth-child(5) { height: 50%; animation-delay: 0.60s; }

.chips {
	display: flex;
	flex-wrap: wrap;
	gap: 6px;
	justify-content: center;
	margin-top: 4px;
}
.chip {
	padding: 5px 11px;
	border-radius: 999px;
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	font-size: 12px;
	color: var(--ql-text-secondary);
}
.chip-active {
	background: var(--ql-accent-soft);
	border-color: var(--ql-accent);
	color: var(--ql-accent-hover);
	box-shadow: 0 0 10px var(--ql-accent-soft);
}

@keyframes mic-pulse {
	0%   { transform: scale(1);   opacity: 0.6; }
	100% { transform: scale(1.5); opacity: 0;   }
}
@keyframes wave {
	0%, 100% { transform: scaleY(0.5); }
	50%      { transform: scaleY(1);   }
}

@media (prefers-reduced-motion: reduce) {
	.mic-pulse, .wave span { animation: none; }
}
</style>
