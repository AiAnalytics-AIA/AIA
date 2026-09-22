import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Button } from "./Button";
import { Kbd } from "./Kbd";
import { Icon } from "./Icon";
import { Panel } from "./Panel";
import { ThemeSwitch } from "@/components/theme/ThemeSwitch";

describe("Button", () => {
  it("is reachable by keyboard and activates on Enter and Space", async () => {
    const onClick = vi.fn();
    render(<><Button onClick={onClick}>Schválit výdaj</Button></>);
    const user = userEvent.setup();
    await user.tab();
    expect(screen.getByRole("button", { name: "Schválit výdaj" })).toHaveFocus();
    await user.keyboard("{Enter}");
    await user.keyboard(" ");
    expect(onClick).toHaveBeenCalledTimes(2);
  });
  it("defaults to type=button so it never submits a form by accident", () => {
    render(<Button>Uložit</Button>);
    expect(screen.getByRole("button")).toHaveAttribute("type", "button");
  });
  it("announces its shortcut", () => {
    render(<Button kbd="⌘↵">Uložit jako novou revizi</Button>);
    expect(screen.getByRole("button")).toHaveAttribute("aria-keyshortcuts", "⌘↵");
  });
  it("has no disabled state to render — absent permission means absent button", () => {
    // @ts-expect-error — `disabled` is deliberately not part of the props.
    render(<Button disabled>X</Button>);
  });
});

describe("Kbd, Icon, Panel", () => {
  it("renders a key hint", () => {
    render(<Kbd>g p</Kbd>);
    expect(screen.getByText("g p").tagName).toBe("KBD");
  });
  it("is decorative unless labelled", () => {
    const { container } = render(<Icon name="gate" />);
    expect(container.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
    render(<Icon name="suppressed" label="Potlačeno" />);
    expect(screen.getByRole("img", { name: "Potlačeno" })).toBeInTheDocument();
  });
  it("labels its region with its title", () => {
    render(<Panel title="Rozpočet studie">obsah</Panel>);
    expect(screen.getByRole("region", { name: "Rozpočet studie" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Rozpočet studie", level: 2 })).toBeInTheDocument();
  });
});

describe("ThemeSwitch — light, dark and system", () => {
  it("sets and clears data-theme and remembers the choice", async () => {
    const user = userEvent.setup();
    render(<ThemeSwitch />);
    await user.click(screen.getByLabelText("Tmavý"));
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
    expect(localStorage.getItem("aia.theme")).toBe("dark");
    await user.click(screen.getByLabelText("Světlý"));
    expect(document.documentElement).toHaveAttribute("data-theme", "light");
    await user.click(screen.getByLabelText("Systém"));
    expect(document.documentElement).not.toHaveAttribute("data-theme");
    expect(localStorage.getItem("aia.theme")).toBeNull();
  });
  it("is operable from the keyboard as a radio group", async () => {
    const user = userEvent.setup();
    render(<ThemeSwitch />);
    await user.tab();
    expect(screen.getByLabelText("Systém")).toHaveFocus();
    await user.keyboard("{ArrowRight}");
    expect(screen.getByLabelText("Světlý")).toBeChecked();
    expect(document.documentElement).toHaveAttribute("data-theme", "light");
  });
});
