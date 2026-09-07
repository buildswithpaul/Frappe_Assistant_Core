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
				Credits measure how much work a reply took, not how many messages you sent. A
				one-line question costs very little. Asking for a long document summary, or working
				through a long conversation, costs more — the assistant is reading and writing more
				each time.
			</p>
			<p>
				The model you choose matters too. The faster, lighter models are the most economical
				for everyday questions; the more capable ones think harder and cost more per reply.
				If you leave the model on <strong>Auto</strong>, the assistant picks a suitable one
				per message — simple questions go to a lighter model on their own.
			</p>
			<p>
				A little of your balance also goes to work you don't see directly: choosing that
				model for you, and remembering things you've told it. That's why the total can move
				slightly more than your own messages alone would suggest.
			</p>

			<ul class="tips">
				<li>Each reply shows what it cost, under the message.</li>
				<li>The meter at the top of the screen shows what's left this month.</li>
				<li>Starting a new conversation for a new topic keeps replies cheaper than
					continuing one very long thread.</li>
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

.tips {
	margin: 0;
	padding-left: 1.1rem;
}

.tips li {
	margin-bottom: 0.35rem;
}
</style>
