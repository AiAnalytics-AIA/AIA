// Whether the results panel a component sits in is the one on screen. ResultsWorkspace keeps every
// panel mounted (hidden) so its choices survive a switch; a panel's content that would write or
// open something on mount (the report editor's POST …/report/editor) waits until it is shown.
// Outside ResultsWorkspace a component is on screen: true.
import { createContext, useContext } from "react";

export const PanelShown = createContext(true);

export const usePanelShown = (): boolean => useContext(PanelShown);
