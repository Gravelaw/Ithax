import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { issue } from "../test/fakes";
import { LOST_CONTACT, ServiceProblem } from "./ServiceProblem";

describe("ServiceProblem", () => {
  it("shows each issue as the service wrote it", () => {
    render(
      <ServiceProblem
        result={{
          kind: "refused",
          status: 400,
          error: { code: "E184", message: "two problems" },
          issues: [
            issue("E184", "The request field 'name' is empty.", "/name", "Give it a name."),
            issue("E186", "The folder is not empty."),
          ],
        }}
      />,
    );
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("E184 The request field 'name' is empty.");
    expect(alert).toHaveTextContent("Give it a name.");
    expect(alert).toHaveTextContent("at /name");
    expect(alert).toHaveTextContent("E186 The folder is not empty.");
    expect(alert).not.toHaveTextContent("two problems");
  });

  it("shows the error itself when there are no issues", () => {
    render(
      <ServiceProblem
        result={{
          kind: "refused",
          status: 404,
          error: { code: "E185", message: "There is no folder '/x'." },
          issues: [],
        }}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("E185 There is no folder '/x'.");
  });

  it("says contact was lost when the service did not answer, and nothing when all is well", () => {
    const { rerender } = render(
      <ServiceProblem result={{ kind: "failed", status: 0, reason: "unreachable" }} />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(LOST_CONTACT);
    rerender(<ServiceProblem result={{ kind: "ok", status: 200, data: null }} />);
    expect(screen.queryByRole("alert")).toBeNull();
    rerender(<ServiceProblem result={null} />);
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
