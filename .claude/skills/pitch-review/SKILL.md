# /pitch-review — Review and Manage Pitches

Browse, approve, or develop existing content pitches.

## Workflow

1. Read the latest pitch file from `~/bksp/pitches/` (most recent by date)
2. Present each pitch as a numbered list with title, lane, format, and hook
3. Ask the user which pitches to act on
4. For selected pitches, offer actions:
   - **Approve**: Move to `~/bksp/drafts/` as a skeleton with the pitch metadata as a writing prompt
   - **Develop**: Expand the pitch with additional source material research
   - **Kill**: Remove from the pitch file with a note on why
   - **Defer**: Leave in the pitch file for future consideration

## Arguments

- No arguments: show latest pitches
- `--all`: show all pitches across all files in `~/bksp/pitches/`
- `--approved`: show only pitches that have been approved and are waiting for drafts

## Notes

- This skill helps manage the pipeline between mining and writing
- Approved pitches become skeleton files in `~/bksp/drafts/` with the pitch metadata preserved as writing guidance
- The user writes the first draft; the copywriter/editor agent refines it
