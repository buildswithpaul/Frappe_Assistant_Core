<template>
	<div class="mockup">
		<div class="avatars">
			<div class="av av-a">AK</div>
			<div class="av av-b">RS</div>
			<div class="av av-c">JP</div>
			<div class="av av-plus">+5</div>
		</div>
		<div class="caption">Your workspace, your team</div>
	</div>
</template>

<style scoped>
.mockup { text-align: center; }
.avatars { display: inline-flex; }
.av {
	width: 44px; height: 44px;
	border-radius: 50%;
	display: flex; align-items: center; justify-content: center;
	font-size: 12px; font-weight: 700; color: #ffffff;
	border: 2px solid var(--ql-bg);
	margin-left: -10px;
	box-shadow: 0 4px 12px -4px rgba(0, 0, 0, 0.2);
}
.av:first-child { margin-left: 0; }
.av-a { background: var(--ql-accent); }
.av-b { background: var(--ql-gold); }
.av-c { background: var(--ql-text-secondary); }
.av-plus {
	background: var(--ql-subtle);
	border-color: var(--ql-border);
	color: var(--ql-text-secondary);
}
.caption {
	margin-top: 14px;
	font-size: 12px;
	color: var(--ql-text-muted);
}
</style>
