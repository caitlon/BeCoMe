import { afterEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { RevealOnCommit } from "@/components/RevealOnCommit";

describe("RevealOnCommit", () => {
  afterEach(() => {
    document.documentElement.className = "";
  });

  it("removes lang-pending from the document element after the first render", () => {
    document.documentElement.classList.add("dark", "lang-pending");

    render(<RevealOnCommit>content</RevealOnCommit>);

    expect(document.documentElement.classList.contains("lang-pending")).toBe(false);
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("renders its children", () => {
    render(<RevealOnCommit>content</RevealOnCommit>);

    expect(screen.getByText("content")).toBeInTheDocument();
  });

  it("does nothing when the class is absent", () => {
    document.documentElement.classList.add("light");

    expect(() => render(<RevealOnCommit>content</RevealOnCommit>)).not.toThrow();
    expect(document.documentElement.className).toBe("light");
  });
});
