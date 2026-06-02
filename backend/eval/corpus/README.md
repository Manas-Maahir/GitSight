# Labelled Real-Repository Corpus

The synthetic harness (`../scenarios.py`) proves the detectors behave **as designed**
on controlled inputs. It cannot tell you whether they are **accurate on real group
projects**. That requires a corpus of real repositories with human-assigned ground
truth — this directory is where that corpus lives.

**No labelled data ships with the project.** Inventing labels would corrupt the very
evaluation they are meant to validate. The framework is here; the data is human work.

## How to build a corpus

1. Copy `manifest.example.json` to `manifest.json` (gitignored — never commit real
   student data).
2. For each repository, add an entry with **human-verified** labels.
3. Run it:

   ```bash
   # from backend/
   python -m eval.corpus eval/corpus/manifest.json
   ```

   This clones and analyses each repo, then reports role accuracy and integrity-flag
   precision/recall/F1 against your labels.

## Manifest format

```jsonc
{
  "repositories": [
    {
      "name": "team-07",
      "repo_url": "https://github.com/org/team-07",
      "deadline": 1716163200,          // optional epoch seconds; sharpens deadline_spike
      "notes": "free-text rationale for the labels",
      "roles": { "Alice": "Major Contributor", "Bob": "Free Rider" },
      "flags": { "Bob": ["deadline_spike", "bulk_paste"] }
    }
  ]
}
```

Valid roles: `Major Contributor`, `Minor Contributor`, `Free Rider`.
Valid flags: `deadline_spike`, `bulk_paste`, `authorship_laundering`, `co_authored_commits`.

Author keys must match the git **display name** as it appears in GitSight's output.

## Annotation guidelines (so labels are defensible)

Label what a fair human grader would conclude *after reviewing the work*, not what the
tool predicts — the point is to measure the tool against human judgement.

- **Major Contributor** — did a substantial, central share of the real work
  (features, core logic), not merely high line counts.
- **Minor Contributor** — contributed real but secondary work.
- **Free Rider** — contributed little or nothing of substance, regardless of commit
  count (a flurry of trivial or last-minute commits is still free riding).
- **Integrity flags** — assign a flag only when you, the human, can point to the
  evidence: a genuine last-minute dump (`deadline_spike`), a large copy-paste
  (`bulk_paste`), someone committing another's work (`authorship_laundering`), or
  declared co-authorship (`co_authored_commits`).

Two annotators labelling independently, then reconciling, gives the most defensible
ground truth and lets you report inter-rater agreement.

## Privacy

Real student repositories are sensitive. Keep `manifest.json` and any private clones
out of version control (both are gitignored). Anonymise names in any published results.
