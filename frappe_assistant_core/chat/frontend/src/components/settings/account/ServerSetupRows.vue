<template>
	<div v-if="showWeb || showRelay" class="server-setup-rows">
		<div
			v-if="showWeb"
			class="setup-row"
			:class="serverSetup.status === 'ok' ? 'banner-success' : 'banner-warn'"
			data-testid="server-setup"
		>
			<div class="row-body">
				<p class="row-title">{{ __("Web server") }}</p>
				<p v-if="serverSetup.status === 'ok' && serverSetup.slots" class="row-text">
					{{
						__("{0} request slots; FACO needs at least {1}.", [
							serverSetup.slots,
							serverSetup.required_slots,
						])
					}}
				</p>
				<p v-else-if="serverSetup.status === 'ok'" class="row-text">
					{{ __("Workers handle many connections each, so no slot limit applies.") }}
				</p>
				<template v-else>
					<p v-for="reason in serverSetup.reasons" :key="reason" class="row-text">
						{{ reason }}
					</p>
				</template>
			</div>
		</div>

		<div
			v-if="showRelay"
			class="setup-row"
			:class="relay.status === 'ok' ? 'banner-success' : 'banner-warn'"
			data-testid="relay-workers"
		>
			<div class="row-body">
				<p class="row-title">{{ __("Chat relay workers") }}</p>
				<p v-if="relay.status === 'ok'" class="row-text">
					{{
						__("{0} relay workers listening, {1} busy, {2} waiting.", [
							relay.workers,
							relay.busy,
							relay.queued,
						])
					}}
				</p>
				<template v-else>
					<p v-for="reason in relay.reasons" :key="reason" class="row-text">
						{{ reason }}
					</p>
				</template>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed } from "vue";
import { __ } from "@/utils/i18n";

const props = defineProps({
	serverSetup: { type: Object, default: null },
});

const relay = computed(() => props.serverSetup?.relay || null);
const showWeb = computed(() => !!props.serverSetup && props.serverSetup.status !== "unknown");
const showRelay = computed(() => !!relay.value && relay.value.status !== "off");
</script>

<style scoped>
.server-setup-rows {
	display: flex;
	flex-direction: column;
	gap: 1rem;
}

.setup-row {
	display: flex;
	gap: 0.75rem;
	padding: 0.875rem 1rem;
	border-radius: 0.5rem;
	border: 1px solid transparent;
}

.banner-success {
	background: rgba(34, 197, 94, 0.08);
	border-color: rgba(34, 197, 94, 0.25);
	color: #16a34a;
}

.banner-warn {
	background: rgba(234, 179, 8, 0.08);
	border-color: rgba(234, 179, 8, 0.25);
	color: #a16207;
}

.row-body {
	display: flex;
	flex-direction: column;
	gap: 0.5rem;
	min-width: 0;
}

.row-title {
	margin: 0;
	font-size: 0.875rem;
	font-weight: 600;
}

.row-text {
	margin: 0;
	font-size: 0.8125rem;
	color: var(--ql-text);
	line-height: 1.5;
	word-break: break-word;
}
</style>
