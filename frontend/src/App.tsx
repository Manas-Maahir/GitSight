import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { LandingView } from "@/features/landing/LandingView";
import { AnalysisProgress } from "@/features/progress/AnalysisProgress";
import {
  DashboardActions,
  DashboardView,
} from "@/features/dashboard/DashboardView";
import type { AnalysisResult } from "@/lib/types";

type Phase =
  | { name: "landing" }
  | { name: "progress"; url: string }
  | { name: "dashboard"; result: AnalysisResult };

const fade = {
  initial: { opacity: 0, y: 6 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -6 },
  transition: { duration: 0.25, ease: "easeOut" as const },
};

export default function App() {
  const [phase, setPhase] = useState<Phase>({ name: "landing" });

  const start = useCallback((url: string) => setPhase({ name: "progress", url }), []);
  const complete = useCallback(
    (result: AnalysisResult) => setPhase({ name: "dashboard", result }),
    [],
  );
  const reset = useCallback(() => setPhase({ name: "landing" }), []);

  return (
    <AppShell
      actions={
        phase.name === "dashboard" ? (
          <DashboardActions data={phase.result} />
        ) : undefined
      }
    >
      <AnimatePresence mode="wait">
        {phase.name === "landing" && (
          <motion.div key="landing" {...fade}>
            <LandingView onSubmit={start} />
          </motion.div>
        )}
        {phase.name === "progress" && (
          <motion.div key="progress" {...fade}>
            <AnalysisProgress url={phase.url} onComplete={complete} onBack={reset} />
          </motion.div>
        )}
        {phase.name === "dashboard" && (
          <motion.div key="dashboard" {...fade}>
            <DashboardView data={phase.result} />
          </motion.div>
        )}
      </AnimatePresence>
    </AppShell>
  );
}
