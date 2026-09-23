<template>
	<section class="credit-explainer">
		<button class="explainer-toggle" @click="isOpen = !isOpen" :aria-expanded="isOpen">
			<span>What is a credit?</span>
			<svg
				class="chevron"
				:class="{ open: isOpen }"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
			>
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M19 9l-7 7-7-7"
				/>
			</svg>
		</button>

		<div v-if="isOpen" class="explainer-body">
			<p>
				A credit measures how much work a reply took. Sending more messages isn't
				what costs — asking for more work is.
			</p>

			<!-- The scale is the thing people actually come here for. Without a
			     number, "costs more" tells a reader who just saw 300 credits
			     nothing at all. These are rounded bands, never a rate card. -->
			<dl class="scale">
				<dt>A quick question</dt>
				<dd>a few dozen credits — <em>"what's my stock balance for this item?"</em></dd>
				<dt>A bigger one</dt>
				<dd>
					a few hundred — looking things up across your data and writing a
					full answer
				</dd>
				<dt>Background work</dt>
				<dd>a handful — remembering something you told it</dd>
			</dl>

			<p>
				Two things move the number: how much the assistant has to read and
				write, and how capable a model the job needs. On <strong>Auto</strong> it
				picks the lightest model that can do the job properly, so everyday
				questions run on an economical one without you choosing.
			</p>
			<p>
				<strong>No single reply can run away with your month.</strong> Every reply has
				a ceiling. If a question turns out to be much bigger than it looked, the
				assistant finishes with what it has and tells you what it left out,
				rather than gathering indefinitely.
			</p>

			<ul class="tips">
				<li>Each reply shows what it cost, under the message.</li>
				<li>The meter beside the model picker shows what's left this month.</li>
				<li>
					A new conversation for a new topic costs less than continuing a very
					long one — there is less to re-read each time.
				</li>
			</ul>
		</div>
	</section>
</template>

<script setup>
import { ref } from "vue";

const isOpen = ref(false);
</script>

<style scoped>
.credit-explainer {
	border: 1px solid var(--ql-border);
	border-radius: 0.75rem;
	background: var(--ql-surface);
}

.explainer-toggle {
	display: flex;
	align-items: center;
	justify-content: space-between;
	width: 100%;
	padding: 0.875rem 1.25rem;
	font-size: 0.9375rem;
	font-weight: 600;
	color: var(--ql-text);
	background: transparent;
	border: none;
	cursor: pointer;
}

.chevron {
	width: 1rem;
	height: 1rem;
	transition: transform 0.2s ease;
}

.chevron.open {
	transform: rotate(180deg);
}

.explainer-body {
	padding: 0 1.25rem 1.25rem;
	font-size: 0.875rem;
	line-height: 1.6;
	color: var(--ql-text-muted);
}

.explainer-body p {
	margin: 0 0 0.75rem;
}

.scale {
	display: grid;
	grid-template-columns: auto 1fr;
	gap: 0.3rem 0.75rem;
	margin: 0 0 0.875rem;
}

.scale dt {
	font-weight: 600;
	color: var(--ql-text);
	white-space: nowrap;
}

.scale dd {
	margin: 0;
}

.tips {
	margin: 0;
	padding-left: 1.1rem;
}

.tips li {
	margin-bottom: 0.35rem;
}
</style>
