import { describe, it, expect, vi, beforeEach } from "vitest";
import { raiseAttention, clearAttention } from "./attention.js";
import { bridge } from "../bridge.js";

describe("raiseAttention", () => {
	let view;
	beforeEach(() => {
		view = { setAttention: vi.fn() };
		bridge.state.attention = false;
		window.__ = (s) => s;
		window.frappe = { show_alert: vi.fn() };
	});

	it("toasts once while attention is already raised", () => {
		raiseAttention(view, {});
		raiseAttention(view, { tool_name: "x" });
		expect(window.frappe.show_alert).toHaveBeenCalledTimes(1);
		clearAttention(view);
	});

	it("toasts again after attention was cleared", () => {
		raiseAttention(view, {});
		clearAttention(view);
		raiseAttention(view, {});
		expect(window.frappe.show_alert).toHaveBeenCalledTimes(2);
		clearAttention(view);
	});
});
