<script setup>
// A tiny looping picture of what a feature does, so it reads at a glance with no text.
// Pure CSS; reduced-motion users see the finished frame.
defineProps({ feature: { type: String, required: true } });
</script>

<template>
	<div class="fpa" :class="`fpa--${feature}`" aria-hidden="true" data-test="feature-preview-art">
		<div v-if="feature === 'agents'" class="fpa-agents">
			<span></span><em></em><span></span><em></em><span></span>
		</div>
		<div v-else-if="feature === 'knowledge'" class="fpa-knowledge">
			<div class="doc"></div>
			<i class="ln ln1"></i><i class="ln ln2"></i><i class="cite"></i>
		</div>
		<div v-else-if="feature === 'pages'" class="fpa-pages">
			<span style="--h: 45%"></span><span style="--h: 70%"></span><span style="--h: 55%"></span
			><span style="--h: 90%"></span>
		</div>
		<div v-else class="fpa-templates">
			<span class="slash">/</span>
			<div class="ls"><i></i><i></i><i></i></div>
		</div>
	</div>
</template>

<style scoped>
.fpa {
	position: relative;
	width: 100%;
	height: 100%;
	min-height: 56px;
	background: var(--ql-subtle);
	overflow: hidden;
}
.fpa > div {
	position: absolute;
	inset: 18% 12%;
}

/* Agents: three steps light up in turn. */
.fpa-agents { display: flex; align-items: center; gap: 6%; }
.fpa-agents span {
	flex: 1;
	height: 40%;
	min-height: 18px;
	border-radius: 6px;
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	opacity: 0.3;
	animation: fpa-lit 3s infinite;
}
.fpa-agents span:nth-of-type(2) { animation-delay: 0.6s; }
.fpa-agents span:nth-of-type(3) { animation-delay: 1.2s; }
.fpa-agents em { width: 6%; height: 2px; background: var(--ql-border); }

/* Knowledge: a document drops in, lines appear, then the cited answer. */
.fpa-knowledge .doc {
	position: absolute;
	left: 0;
	top: 0;
	width: 22%;
	height: 90%;
	border-radius: 4px;
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	animation: fpa-drop 3s infinite;
}
.fpa-knowledge i { position: absolute; left: 32%; height: 12%; border-radius: 4px; opacity: 0; animation: fpa-show 3s infinite; }
.fpa-knowledge .ln { right: 0; background: var(--ql-border); }
.fpa-knowledge .ln1 { top: 8%; animation-delay: 0.8s; }
.fpa-knowledge .ln2 { top: 34%; right: 30%; animation-delay: 1.1s; }
.fpa-knowledge .cite { top: 66%; width: 36%; background: var(--ql-accent); animation-delay: 1.5s; }

/* Pages: a chart grows. */
.fpa-pages { display: flex; align-items: flex-end; gap: 8%; border-bottom: 1px solid var(--ql-border); }
.fpa-pages span {
	flex: 1;
	height: var(--h);
	border-radius: 3px 3px 0 0;
	background: var(--ql-accent);
	animation: fpa-grow 3s infinite;
}
.fpa-pages span:nth-child(2) { animation-delay: 0.2s; }
.fpa-pages span:nth-child(3) { animation-delay: 0.4s; }
.fpa-pages span:nth-child(4) { animation-delay: 0.6s; }

/* Prompt templates: "/" opens a list of saved questions. */
.fpa-templates .slash {
	display: inline-block;
	padding: 0 6px;
	border-radius: 5px;
	border: 1px solid var(--ql-border);
	background: var(--ql-surface);
	color: var(--ql-accent);
	font-weight: 600;
	font-size: 13px;
}
.fpa-templates .ls { margin-top: 6px; display: grid; gap: 4px; }
.fpa-templates .ls i { display: block; height: 8px; border-radius: 4px; background: var(--ql-border); opacity: 0; animation: fpa-show 3s infinite; }
.fpa-templates .ls i:nth-child(2) { width: 80%; animation-delay: 0.3s; }
.fpa-templates .ls i:nth-child(3) { width: 60%; animation-delay: 0.6s; }

@keyframes fpa-lit {
	0%, 15% { opacity: 0.3; border-color: var(--ql-border); }
	30%, 80% { opacity: 1; border-color: var(--ql-accent); }
	100% { opacity: 0.3; }
}
@keyframes fpa-drop {
	0% { transform: translateY(-40%); opacity: 0; }
	20%, 85% { transform: none; opacity: 1; }
	100% { opacity: 0; }
}
@keyframes fpa-show {
	0%, 20% { opacity: 0; }
	35%, 85% { opacity: 1; }
	100% { opacity: 0; }
}
@keyframes fpa-grow {
	0% { height: 4%; }
	35%, 85% { height: var(--h); }
	100% { height: 4%; }
}

@media (prefers-reduced-motion: reduce) {
	.fpa * { animation: none !important; opacity: 1 !important; }
}
:global(html.reduce-motion) .fpa * { animation: none !important; opacity: 1 !important; }
</style>
