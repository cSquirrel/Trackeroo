import { describe, expect, it } from "vitest";
import { ApiError } from "./api";
import { describeDependencyError } from "./errors";

describe("describeDependencyError", () => {
  it("maps 400 to a self-dependency message", () => {
    expect(describeDependencyError(new ApiError(400, null, "x"))).toMatch(
      /depend on itself/i,
    );
  });

  it("maps 404 to a missing-task message", () => {
    expect(describeDependencyError(new ApiError(404, null, "x"))).toMatch(
      /no longer exists/i,
    );
  });

  it("maps 409 to a duplicate-dependency message", () => {
    expect(describeDependencyError(new ApiError(409, null, "x"))).toMatch(
      /already exists/i,
    );
  });

  it("maps 422 to a cycle message", () => {
    expect(describeDependencyError(new ApiError(422, null, "x"))).toMatch(
      /cycle/i,
    );
  });

  it("falls back to the error message for other ApiError statuses", () => {
    expect(describeDependencyError(new ApiError(500, null, "boom"))).toBe("boom");
  });

  it("stringifies non-Error values", () => {
    expect(describeDependencyError("weird")).toBe("weird");
  });
});
