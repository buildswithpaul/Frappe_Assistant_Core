<template>
	<div class="mockup">
		<div class="rocket" aria-hidden="true">🚀</div>
		<div class="streak"></div>
	</div>
</template>

<style scoped>
.mockup {
	position: relative;
	width: 160px; height: 80px;
	margin: 0 auto;
}
.rocket {
	position: absolute;
	left: 50%; top: 50%;
	transform: translate(-50%, -50%);
	font-size: 56px;
}
.streak {
	position: absolute;
	left: 0; right: 0; top: 50%;
	height: 2px;
	background: linear-gradient(90deg, transparent, var(--ql-accent), var(--ql-gold), transparent);
	transform: translateY(-1px);
}
</style>
