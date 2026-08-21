[← Back to plan index](../PLAN.md)

**Depends on:** nothing blocking — opportunistic cleanup, fold in wherever convenient.
**Blocks:** nothing.

---

## Also worth doing

✅ **All three DONE.**

- **`fight_events` needs a structured `state` column.** ✅ Added (migration
  `c5d6e7f8a9b0_add_state_to_fight_events.py`); `predictions.py` reads it
  directly, falling back to the description regex only for pre-existing rows.
- `_print_standing_punch_diag` reports "100% of both-visible standing frames are
  dropped by the all-15-joints bar", which is stale — the PARTIAL path now runs
  detection on those frames. ✅ Message corrected to report the real FULL/PARTIAL split.
- **Both `CLAUDE.md` DB-schema blocks predate the `state` column.** ✅ Both
  `ai/CLAUDE.md` and `backend/CLAUDE.md` rewritten to reflect `state`/`pid`/
  `labeled_at`/`label_events`/`label_spans` and the current route tables,
  alongside every Stage 0/1 change made this session.

---

← [Back to plan index](../PLAN.md)
