- ts: 2025-09-07T11:18:06Z
  step: "Normalize CLI writes canonical jsonl"
  evidence:
    coverage_before: 0.00
    coverage_after: 0.00
    fp_rate_before: 0.00
    fp_rate_after: 0.00
    artifacts: []
  next_hint: "Add schema checker for Canonical Event Envelope; rollback: remove normalize CLI and test"
- ts: 2025-09-07T11:23:20Z
  step: "Schema checker validates canonical envelopes"
  evidence:
    coverage_before: 0.00
    coverage_after: 0.00
    fp_rate_before: 0.00
    fp_rate_after: 0.00
    artifacts: []
  next_hint: "Integrate hb_re or implement goblin.report for cadence; rollback: remove schema checker and test"
- ts: 2025-09-07T11:33:58Z
  step: "Basic report computes cadence and playhead monotonicity"
  evidence:
    coverage_before: 0.00
    coverage_after: 0.00
    fp_rate_before: 0.00
    fp_rate_after: 0.00
    artifacts: []
  next_hint: "Emit baseline CSVs from report; rollback: remove goblin.report and tests"
