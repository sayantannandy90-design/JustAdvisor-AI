import { createBrowserRouter } from "react-router";
import CaseSelection from "./pages/CaseSelection";
import DualChatInterface from "./pages/DualChatInterface";
import FinalJudgment from "./pages/FinalJudgment";

export const router = createBrowserRouter([
  {
    path: "/",
    Component: CaseSelection,
  },
  {
    path: "/debate/:caseId",
    Component: DualChatInterface,
  },
  {
    path: "/judgment/:caseId",
    Component: FinalJudgment,
  },
]);
