import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const css = readFileSync(join(__dirname, "./quiet-ledger.css"), "utf8");

// Pull the value of `name` from the FIRST block that defines it (the :root light block).
function firstValue(name) {
  const m = css.match(new RegExp(`${name}\\s*:\\s*([^;]+);`));
  return m ? m[1].trim() : null;
}

// Pull the value of `name` from inside the [data-theme="dark"] { ... } block.
function darkValue(name) {
  const block = css.match(/\[data-theme="dark"\]\s*\{([\s\S]*?)\}/);
  if (!block) return null;
  const m = block[1].match(new RegExp(`${name}\\s*:\\s*([^;]+);`));
  return m ? m[1].trim() : null;
}

describe("quiet-ledger.css light tokens (spec §2.1)", () => {
  const expected = {
    "--ql-bg": "#FBFAF8",
    "--ql-surface": "#FFFFFF",
    "--ql-subtle": "#F5F3EF",
    "--ql-border": "#ECE9E3",
    "--ql-border-hover": "#DEDAD2",
    "--ql-text": "#1A1A17",
    "--ql-text-secondary": "#57534C",
    "--ql-text-muted": "#8A857C",
    "--ql-accent": "#0F6E5C",
    "--ql-accent-hover": "#0B5A4B",
    "--ql-accent-soft": "rgba(15, 110, 92, 0.08)",
    "--ql-gold": "#C9A227",
    "--ql-gold-soft": "rgba(201, 162, 39, 0.14)",
    "--ql-success": "#1E7A52",
    "--ql-warning": "#B8791A",
    "--ql-danger": "#B4453A",
  };
  for (const [name, value] of Object.entries(expected)) {
    it(`${name} === ${value}`, () => {
      expect(firstValue(name)).toBe(value);
    });
  }
});

describe("quiet-ledger.css dark tokens (spec §2.1 Ink Ledger)", () => {
  const expected = {
    "--ql-bg": "#16150F",
    "--ql-surface": "#1E1D16",
    "--ql-subtle": "#26241B",
    "--ql-border": "#2E2C22",
    "--ql-text": "#F2EFE6",
    "--ql-text-secondary": "#B7B2A4",
    "--ql-accent": "#2DAA8F",
    "--ql-gold": "#D9B84A",
  };
  for (const [name, value] of Object.entries(expected)) {
    it(`dark ${name} === ${value}`, () => {
      expect(darkValue(name)).toBe(value);
    });
  }
});

describe("quiet-ledger.css spacing & radius scale (spec §2.3)", () => {
  it("spacing scale is 4/8/12/16/24/32/48", () => {
    expect(firstValue("--ql-space-1")).toBe("4px");
    expect(firstValue("--ql-space-2")).toBe("8px");
    expect(firstValue("--ql-space-3")).toBe("12px");
    expect(firstValue("--ql-space-4")).toBe("16px");
    expect(firstValue("--ql-space-6")).toBe("24px");
    expect(firstValue("--ql-space-8")).toBe("32px");
    expect(firstValue("--ql-space-12")).toBe("48px");
  });
  it("radius scale is 6/8/10/12/14", () => {
    expect(firstValue("--ql-radius-sm")).toBe("6px");
    expect(firstValue("--ql-radius-md")).toBe("8px");
    expect(firstValue("--ql-radius-lg")).toBe("10px");
    expect(firstValue("--ql-radius-xl")).toBe("12px");
    expect(firstValue("--ql-radius-2xl")).toBe("14px");
  });
});

describe("data-viz palette is teal-anchored (spec §2.4)", () => {
  it("viz-1 is the brand teal", () => {
    expect(firstValue("--ql-viz-1")).toBe("#0F6E5C");
  });
  it("defines at least 8 viz colors", () => {
    for (let i = 1; i <= 8; i++) {
      expect(firstValue(`--ql-viz-${i}`)).toBeTruthy();
    }
  });
});
