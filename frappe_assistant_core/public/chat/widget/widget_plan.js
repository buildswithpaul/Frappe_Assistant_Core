/**
 * FACOPlanStrip — renders an agent task plan as a compact inline strip
 * inside the streaming assistant bubble. Vanilla JS + jQuery, mirrors the
 * thinking/tool indicator idiom in widget_streaming.js.
 *
 * Plan payload (every plan_* event carries the FULL plan — replace wholesale):
 *   { id, status, tasks: [{ id, title, status, note, delegated, parentId }] }
 *   status ∈ pending | running | done | failed | skipped
 */
window.FACOPlanStrip = {
	GLYPHS: {
		pending: "☐",
		running: "⠿",
		done: "✓",
		failed: "✗",
		skipped: "⊘",
	},

	glyph(status) {
		return this.GLYPHS[status] || this.GLYPHS.pending;
	},

	_escape(s) {
		// Reuse the widget's sanitizer boundary if present; else minimal escape.
		if (window.FACOCore && typeof FACOCore.escape_html === "function") {
			return FACOCore.escape_html(s == null ? "" : String(s));
		}
		return (s == null ? "" : String(s)).replace(/[&<>"]/g, (c) => (
			{ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]
		));
	},

	/** Count of completed (done/skipped) tasks, for the collapsed summary. */
	_doneCount(tasks) {
		return (tasks || []).filter((t) => t.status === "done" || t.status === "skipped").length;
	},

	/** HTML for one task row. running=true also leaves a sub-activity slot. */
	rowHtml(task) {
		const isChild = !!task.parentId;
		const noteHtml = task.note
			? ` <span class="faco-plan-note">· ${this._escape(task.note)}</span>`
			: "";
		const delegatedHtml = task.delegated
			? ` <span class="faco-plan-delegated">↳ specialist</span>`
			: "";
		const subSlot = task.status === "running"
			? `<div class="faco-plan-subactivity" data-task-id="${this._escape(task.id)}"></div>`
			: "";
		return (
			`<li class="faco-plan-row faco-plan-${this._escape(task.status)}${isChild ? " faco-plan-child" : ""}"` +
			` data-task-id="${this._escape(task.id)}"` +
			` aria-label="${this._escape(task.title)} — ${this._escape(task.status)}">` +
			`<span class="faco-plan-glyph">${this.glyph(task.status)}</span>` +
			`<span class="faco-plan-title">${this._escape(task.title)}</span>` +
			delegatedHtml + noteHtml + subSlot +
			`</li>`
		);
	},

	/** Full expanded strip HTML for a live/loaded plan. */
	stripHtml(plan) {
		const tasks = (plan && plan.tasks) || [];
		const rows = tasks.map((t) => this.rowHtml(t)).join("");
		const heading = `Working through ${tasks.length} step${tasks.length === 1 ? "" : "s"}…`;
		return (
			`<div class="faco-plan-strip" data-plan-id="${this._escape(plan && plan.id)}">` +
			`<div class="faco-plan-heading">${this._escape(heading)}</div>` +
			`<ul class="faco-plan-list">${rows}</ul>` +
			`</div>`
		);
	},

	/** Collapsed one-line summary (post-completion / on reload), expandable. */
	collapsedHtml(plan) {
		const tasks = (plan && plan.tasks) || [];
		const done = this._doneCount(tasks);
		const rows = tasks.map((t) => this.rowHtml(t)).join("");
		const label = `Completed ${done} of ${tasks.length} step${tasks.length === 1 ? "" : "s"}`;
		return (
			`<div class="faco-plan-strip faco-plan-collapsed" data-plan-id="${this._escape(plan && plan.id)}">` +
			`<button type="button" class="faco-plan-summary">✓ ${this._escape(label)} <span class="faco-plan-caret">›</span></button>` +
			`<ul class="faco-plan-list" style="display:none;">${rows}</ul>` +
			`</div>`
		);
	},
};
