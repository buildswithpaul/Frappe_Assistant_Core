import { describe, it, expect } from "vitest";
import { formatModelId } from "./modelLabel";

describe("formatModelId", () => {
	it.each([
		["global.anthropic.claude-haiku-4-5-20251001-v1:0", "Claude Haiku 4.5"],
		["gpt-5.6-luna", "GPT-5.6 Luna"],
		["anthropic.claude-3-5-sonnet-20240620-v1:0", "Claude 3.5 Sonnet"],
		["gemini-2.5-flash", "Gemini 2.5 Flash"],
		["", "Unknown model"],
	])("formats %s", (id, label) => {
		expect(formatModelId(id)).toBe(label);
	});

	it.each([
		["whisper-1", "Whisper 1"],
		["default", "Default"],
		["mistral.mistral-large-3-675b-instruct", "Mistral Large 3 675B Instruct"],
		["gpt-6.1-sol", "GPT-6.1 Sol"],
		["claude-sonnet-5-5", "Claude Sonnet 5.5"],
		["claude-haiku-4-5", "Claude Haiku 4.5"],
		["zai.glm-5", "GLM 5"],
		["us.deepseek.r1-v1:0", "Deepseek R1"],
		["x-ai/grok-4", "Grok 4"],
		["openai/gpt-oss-120b", "GPT Oss 120B"],
	])("reads real workspace id %s", (id, label) => {
		expect(formatModelId(id)).toBe(label);
	});
});
