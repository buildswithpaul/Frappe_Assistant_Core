import { describe, it, expect } from "vitest";
import { turnKind, turnLabel, userInitial } from "./turns.js";

describe("turnKind", () => {
  it("classifies a user row", () => {
    expect(turnKind({ role: "user", content: "hi" })).toBe("user");
  });
  it("classifies a divider row", () => {
    expect(turnKind({ role: "divider", content: "summarized" })).toBe("divider");
  });
  it("treats assistant + unknown roles as assistant", () => {
    expect(turnKind({ role: "assistant" })).toBe("assistant");
    expect(turnKind({ role: "tool" })).toBe("assistant");
    expect(turnKind(null)).toBe("assistant");
  });
});

describe("turnLabel", () => {
  it("labels user turns YOU", () => {
    expect(turnLabel({ role: "user" })).toBe("YOU");
  });
  it("labels assistant turns FACO", () => {
    expect(turnLabel({ role: "assistant" })).toBe("FACO");
  });
  it("returns empty for dividers", () => {
    expect(turnLabel({ role: "divider" })).toBe("");
  });
});

describe("userInitial", () => {
  it("uppercases the first character", () => {
    expect(userInitial("clinton@example.com")).toBe("C");
  });
  it("falls back to U when empty/missing", () => {
    expect(userInitial("")).toBe("U");
    expect(userInitial(null)).toBe("U");
    expect(userInitial(undefined)).toBe("U");
  });
});
