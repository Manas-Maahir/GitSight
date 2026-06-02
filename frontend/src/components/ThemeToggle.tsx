import { Monitor, Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import { InfoTip } from "@/components/ui/tooltip";
import { useTheme, type Theme } from "@/lib/theme";

const ORDER: Theme[] = ["light", "dark", "system"];
const ICON = { light: Sun, dark: Moon, system: Monitor } as const;
const LABEL = { light: "Light", dark: "Dark", system: "System" } as const;

/** Cycles light → dark → system. Quiet, icon-only control. */
export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const next = ORDER[(ORDER.indexOf(theme) + 1) % ORDER.length];
  const Icon = ICON[theme];

  return (
    <InfoTip label={`Theme: ${LABEL[theme]} — switch to ${LABEL[next]}`}>
      <Button
        variant="ghost"
        size="icon"
        aria-label={`Switch theme (currently ${LABEL[theme]})`}
        onClick={() => setTheme(next)}
      >
        <Icon />
      </Button>
    </InfoTip>
  );
}
