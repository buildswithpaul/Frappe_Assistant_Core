<template>
	<UpgradeBanner
		class="seat-limit-banner"
		:title="`You've reached your plan's user limit (${maxUsers} ${maxUsers === 1 ? 'seat' : 'seats'}).`"
		message="Upgrade to add more team members."
		action-label="View plans"
		@upgrade="$emit('upgrade')"
	/>
</template>

<script setup>
import UpgradeBanner from "@/components/common/UpgradeBanner.vue";

defineProps({
	maxUsers: { type: Number, required: true },
});
defineEmits(["upgrade"]);
</script>

<style scoped>
.seat-limit-banner {
	margin-top: 1rem;
}
</style>
