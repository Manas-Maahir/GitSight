import { motion } from "framer-motion";
import { ArrowRight, Fingerprint, GitBranch, Scale, ShieldCheck } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const EXAMPLE_REPOS = [
  "https://github.com/pallets/flask",
  "https://github.com/psf/requests",
  "https://github.com/tiangolo/fastapi",
];

const GITHUB_RE = /^https?:\/\/github\.com\/[\w.-]+\/[\w.-]+\/?$/i;

const PILLARS = [
  {
    icon: GitBranch,
    title: "Ownership, not commit counts",
    body: "Line-level git-blame attribution at HEAD — who wrote the code that survived, reported as a confidence interval.",
  },
  {
    icon: Fingerprint,
    title: "Integrity forensics",
    body: "Deadline spikes, bulk pastes, authorship laundering — surfaced as advisory, evidence-bound signals.",
  },
  {
    icon: Scale,
    title: "Calibrated confidence",
    body: "Every verdict carries its regime and caveats. The tool states what it cannot know, not just what it can.",
  },
];

export function LandingView({
  onSubmit,
}: {
  onSubmit: (url: string) => void;
}) {
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = url.trim();
    if (!GITHUB_RE.test(trimmed)) {
      setError("Enter a valid public GitHub repository URL (https://github.com/owner/repo).");
      return;
    }
    setError("");
    onSubmit(trimmed);
  };

  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-16 sm:px-6 sm:py-24">
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: "easeOut" }}
        className="text-center"
      >
        <div className="mx-auto mb-5 inline-flex items-center gap-2 rounded-full border border-border bg-muted/40 px-3 py-1 text-xs text-muted-foreground">
          <ShieldCheck className="size-3.5 text-primary" />
          Contribution intelligence for repositories
        </div>
        <h1 className="text-balance text-4xl font-semibold tracking-tight sm:text-5xl">
          Understand who actually contributed.
        </h1>
        <p className="mx-auto mt-4 max-w-xl text-pretty text-base text-muted-foreground sm:text-lg">
          GitSight analyses line-level ownership, effort, code quality, and
          integrity signals — beyond raw commit counts — and explains every
          verdict with evidence.
        </p>
      </motion.div>

      <motion.form
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.08, ease: "easeOut" }}
        onSubmit={handleSubmit}
        className="mx-auto mt-10 w-full max-w-xl"
      >
        <div
          className={cn(
            "flex items-center gap-2 rounded-xl border bg-card p-2 shadow-sm transition-colors focus-within:border-primary/60 focus-within:ring-2 focus-within:ring-ring/40",
            error && "border-danger/50",
          )}
        >
          <div className="flex flex-1 items-center gap-2 pl-2">
            <GitBranch className="size-4 shrink-0 text-muted-foreground" />
            <input
              type="text"
              inputMode="url"
              autoFocus
              value={url}
              onChange={(e) => {
                setUrl(e.target.value);
                if (error) setError("");
              }}
              placeholder="https://github.com/owner/repo"
              aria-label="GitHub repository URL"
              aria-invalid={!!error}
              className="w-full bg-transparent py-2 font-mono text-sm text-foreground outline-none placeholder:text-muted-foreground/70"
            />
          </div>
          <Button type="submit" size="md" className="shrink-0">
            Analyze
            <ArrowRight />
          </Button>
        </div>

        {error ? (
          <p role="alert" className="mt-2 px-1 text-xs text-danger-foreground">
            {error}
          </p>
        ) : (
          <div className="mt-3 flex flex-wrap items-center gap-2 px-1">
            <span className="text-xs text-muted-foreground">Try</span>
            {EXAMPLE_REPOS.map((repo) => (
              <button
                key={repo}
                type="button"
                onClick={() => {
                  setUrl(repo);
                  setError("");
                }}
                className="rounded-md border border-border bg-muted/40 px-2 py-0.5 font-mono text-xs text-muted-foreground transition-colors hover:border-border hover:bg-accent hover:text-foreground"
              >
                {repo.replace("https://github.com/", "")}
              </button>
            ))}
          </div>
        )}
      </motion.form>

      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.16, ease: "easeOut" }}
        className="mt-16 grid gap-4 sm:grid-cols-3"
      >
        {PILLARS.map((p) => (
          <div key={p.title} className="surface p-4">
            <p.icon className="size-5 text-primary" />
            <h3 className="mt-3 text-sm font-semibold">{p.title}</h3>
            <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
              {p.body}
            </p>
          </div>
        ))}
      </motion.div>
    </div>
  );
}
