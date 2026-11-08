import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SeverityMark } from "@/components/ui/badge";
import { Pagination } from "@/components/ui/table";
import { StatusBadge } from "@/components/domain/badges";
import { ar, en } from "@/lib/dictionaries";
import { I18nProvider, useI18n } from "@/lib/i18n";

function Wrap({ locale, children }: { locale: "ar" | "en"; children: React.ReactNode }) {
  return <I18nProvider initial={locale}>{children}</I18nProvider>;
}

describe("i18n", () => {
  it("sets document direction from locale", () => {
    render(<Wrap locale="ar"><span>x</span></Wrap>);
    expect(document.documentElement.dir).toBe("rtl");
    expect(document.documentElement.lang).toBe("ar");
    render(<Wrap locale="en"><span>y</span></Wrap>);
    expect(document.documentElement.dir).toBe("ltr");
  });

  it("has the same keys in Arabic and English dictionaries", () => {
    const keys = (o: object, p = ""): string[] => Object.entries(o).flatMap(([k, v]) =>
      v && typeof v === "object" && !Array.isArray(v) ? keys(v, `${p}${k}.`) : [`${p}${k}`]);
    expect(keys(en).sort()).toEqual(keys(ar).sort());
  });

  it("formats numbers with Latin digits in Arabic", () => {
    function N() { const { fmtNum } = useI18n(); return <span data-testid="n">{fmtNum(5000000)}</span>; }
    render(<Wrap locale="ar"><N /></Wrap>);
    expect(screen.getByTestId("n").textContent).toMatch(/5.000.000/);
  });
});

describe("components", () => {
  it("renders workflow status labels in Arabic", () => {
    render(<Wrap locale="ar"><StatusBadge status="PENDING_HUMAN_REVIEW" /></Wrap>);
    expect(screen.getByText("بانتظار المراجعة البشرية")).toBeInTheDocument();
  });

  it("severity mark carries a text label (not colour only)", () => {
    render(<SeverityMark severity="HIGH" label="عالية" />);
    expect(screen.getByText("عالية")).toBeInTheDocument();
  });

  it("pagination calls back and disables at bounds", () => {
    const onPage = vi.fn();
    render(<Wrap locale="ar"><Pagination page={1} pageSize={10} total={25} onPage={onPage} /></Wrap>);
    const prev = screen.getByLabelText(ar.common.previous);
    const next = screen.getByLabelText(ar.common.next);
    expect(prev).toBeDisabled();
    fireEvent.click(next);
    expect(onPage).toHaveBeenCalledWith(2);
  });
});
