<template>
	<div ref="card" class="pulse-card" data-test="pulse-card" role="region" :aria-label="__('How is FACO doing for you?')">
		<div v-if="store.thanked" class="pulse-thanks" data-test="pulse-thanks" role="status">
			{{ __("Thank you, that helps.") }}
		</div>
		<template v-else>
			<button
				type="button"
				class="pulse-close"
				data-test="pulse-dismiss"
				:title="__('Dismiss')"
				:aria-label="__('Dismiss')"
				@click="store.dismiss()"
			>
				&times;
			</button>
			<div class="pulse-title">{{ __("How is FACO doing for you?") }}</div>
			<div class="pulse-scale" role="group" :aria-label="__('Rating from 1 to 5')">
				<button
					v-for="n in 5"
					:key="n"
					type="button"
					class="pulse-rating"
					:class="{ 'is-selected': rating === n }"
					:data-rating="n"
					:aria-pressed="rating === n"
					@click="rating = n"
				>
					{{ n }}
				</button>
			</div>
			<template v-if="rating">
				<textarea
					v-model="comment"
					class="pulse-comment"
					data-test="pulse-comment"
					rows="2"
					maxlength="2000"
					:placeholder="__('Anything we should fix or build? (optional)')"
				/>
				<label class="pulse-contact">
					<input v-model="contactOk" type="checkbox" data-test="pulse-contact" />
					{{ __("Happy for us to contact you") }}
				</label>
				<div v-if="failed" class="pulse-error" data-test="pulse-error" role="alert">
					{{ __("Couldn't send. Please try again.") }}
				</div>
				<button type="button" class="pulse-send" data-test="pulse-send" :disabled="sending" @click="send">
					{{ __("Send") }}
				</button>
			</template>
		</template>
	</div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from "vue";
import { __ } from "@/utils/i18n";
import { usePulseStore } from "@/stores/pulseStore";

const store = usePulseStore();
const card = ref(null);
const rating = ref(null);
const comment = ref("");
const contactOk = ref(false);
const sending = ref(false);
const failed = ref(false);

onMounted(() => {
	store.markShown();
	card.value?.scrollIntoView?.({ block: "nearest" });
});

// A card removed mid-thanks must not leave a stuck "thanked" state behind.
onBeforeUnmount(() => {
	if (store.thanked) store.hide();
});

async function send() {
	if (!rating.value || sending.value) return;
	sending.value = true;
	failed.value = false;
	const ok = await store.submit({
		rating: rating.value,
		comment: comment.value.trim() || null,
		contactOk: contactOk.value,
	});
	sending.value = false;
	failed.value = !ok;
}
</script>

<style scoped>
.pulse-card {
	position: relative;
	display: flex;
	flex-direction: column;
	gap: 0.625rem;
	margin-top: 1rem;
	padding: 0.875rem 1rem;
	background: var(--ql-surface, var(--ql-bg));
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	color: var(--ql-text);
	font-size: 0.875rem;
}

.pulse-title {
	font-weight: 600;
	padding-right: 1.5rem;
}

.pulse-close {
	position: absolute;
	top: 0.375rem;
	right: 0.5rem;
	font-size: 1.125rem;
	line-height: 1;
	color: var(--ql-text-muted);
	background: none;
	border: none;
	cursor: pointer;
}

.pulse-scale {
	display: flex;
	gap: 0.375rem;
}

.pulse-rating {
	width: 2.25rem;
	padding: 0.25rem 0;
	color: var(--ql-text);
	background: none;
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	cursor: pointer;
}

.pulse-rating.is-selected {
	background-color: var(--ql-subtle);
	border-color: var(--ql-text-muted);
}

.pulse-comment {
	width: 100%;
	padding: 0.375rem 0.5rem;
	font-size: 0.8125rem;
	color: var(--ql-text);
	background: none;
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	resize: vertical;
}

.pulse-contact {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	font-size: 0.8125rem;
	color: var(--ql-text-muted);
}

.pulse-error {
	font-size: 0.8125rem;
	color: var(--ql-danger, #b42318);
}

.pulse-send {
	align-self: flex-end;
	padding: 0.25rem 0.875rem;
	font-size: 0.8125rem;
	color: var(--ql-text);
	background-color: var(--ql-subtle);
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	cursor: pointer;
}

.pulse-send:disabled {
	opacity: 0.6;
	cursor: default;
}

.pulse-thanks {
	color: var(--ql-text-muted);
}
</style>
