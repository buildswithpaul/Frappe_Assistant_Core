<template>
	<button
		v-if="spine"
		class="spine-tick"
		:class="{ active }"
		:aria-current="active ? 'true' : 'false'"
		:aria-label="entry.heading"
		@click="$emit('jump')"
	>
		<span class="tick" :class="{ gold: entry.approval }"></span>
		<span class="flyout">{{ entry.heading }}</span>
	</button>
	<button
		v-else
		class="index-entry"
		:class="{ active }"
		:aria-current="active ? 'true' : 'false'"
		@click="$emit('jump')"
	>
		<span class="node" aria-hidden="true"></span>
		<span class="index-heading">{{ entry.heading }}</span>
		<span v-if="entry.streaming" class="index-streaming" aria-label="Answering">
			<i></i><i></i><i></i>
		</span>
		<span v-else class="index-meta">
			<template v-if="entry.toolCount">⚙ {{ entry.toolCount }} · </template>
			<template v-if="entry.hasChart">📊 · </template>
			<template v-if="entry.hasFiles">📎 · </template>
			<span
				v-if="entry.approval"
				class="gold-dot"
				:title="entry.approval === 'pending' ? 'Approval waiting' : 'Approved'"
			></span>
			<template v-if="entry.approval === 'resolved'">approved · </template>
			{{ entry.time }}
		</span>
	</button>
</template>

<script setup>
defineProps({
	entry: { type: Object, required: true },
	active: { type: Boolean, default: false },
	spine: { type: Boolean, default: false },
});
defineEmits(["jump"]);
</script>

<style scoped>
.index-entry {
	display: block;
	width: 100%;
	text-align: left;
	padding: 6px 8px 6px 14px;
	border: none;
	background: transparent;
	border-radius: 6px;
	position: relative;
	cursor: pointer;
}
.index-entry:hover {
	background: var(--ql-subtle);
}
.index-entry.active {
	background: var(--ql-accent-soft);
}

.node {
	position: absolute;
	left: -4px;
	top: 12px;
	width: 6px;
	height: 6px;
	border-radius: 50%;
	background: var(--ql-border);
}
.index-entry.active .node {
	width: 8px;
	height: 8px;
	left: -5px;
	background: var(--ql-accent);
}

.index-heading {
	display: block;
	font-size: 12px;
	font-weight: 500;
	color: var(--ql-text-secondary);
	line-height: 1.35;
}
.index-entry.active .index-heading {
	color: var(--ql-text);
	font-weight: 600;
}

.index-meta {
	display: block;
	font-family: var(--ql-font-mono);
	font-size: 10px;
	color: var(--ql-text-muted);
	margin-top: 2px;
}

.gold-dot {
	width: 7px;
	height: 7px;
	border-radius: 50%;
	background: var(--ql-gold);
	box-shadow: 0 0 0 3px var(--ql-gold-soft);
	display: inline-block;
}

.index-streaming {
	display: flex;
	align-items: center;
	gap: 3px;
	margin-top: 4px;
}
.index-streaming i {
	width: 6px;
	height: 6px;
	border-radius: 50%;
	background: var(--ql-accent);
	font-style: normal;
	animation: index-pulse 1.4s infinite ease-in-out;
}
.index-streaming i:nth-child(2) {
	animation-delay: 0.2s;
}
.index-streaming i:nth-child(3) {
	animation-delay: 0.4s;
}

@keyframes index-pulse {
	0%,
	80%,
	100% {
		opacity: 0.3;
	}
	40% {
		opacity: 1;
	}
}
@media (prefers-reduced-motion: reduce) {
	.index-streaming i {
		animation: none;
		opacity: 0.6;
	}
}

.spine-tick {
	display: flex;
	align-items: center;
	justify-content: center;
	width: 28px;
	height: 22px;
	border: none;
	background: transparent;
	cursor: pointer;
	position: relative;
	padding: 0;
}
.spine-tick .tick {
	width: 6px;
	height: 6px;
	border-radius: 50%;
	background: var(--ql-border);
}
.spine-tick.active .tick {
	width: 8px;
	height: 8px;
	background: var(--ql-accent);
}
.spine-tick .tick.gold {
	background: var(--ql-gold);
	box-shadow: 0 0 0 3px var(--ql-gold-soft);
}

.flyout {
	position: absolute;
	left: 32px;
	top: 50%;
	transform: translateY(-50%);
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 6px;
	box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
	padding: 4px 10px;
	font-size: 12px;
	color: var(--ql-text);
	white-space: nowrap;
	opacity: 0;
	visibility: hidden;
	pointer-events: none;
	transition: opacity 0.12s ease;
	z-index: 10;
}
.spine-tick:hover .flyout,
.spine-tick:focus-visible .flyout {
	opacity: 1;
	visibility: visible;
}
</style>
