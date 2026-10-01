# Phase definitions, live states and reported physical locations

The supplied BlueCity manual, section 3.4.1 (pages 16–17), documents the Phase Details GET endpoint and its `UDID` and `active_only` parameters. Its example contains `phase_id`, `phase_label`, `approach`, `active`, `allowed_movements` and `phase_type`. Phase definitions are versioned: a configuration change creates a new ID and marks the previous definition inactive. Historical calculations must use the configuration applicable to their observation time; an active flag alone does not provide validity dates.

Section 5.4.3 (page 45) defines live `phaseNumber`, status and timestamps, plus absolute initialization. The sections reviewed do not specify a join from `phase_id` to `phaseNumber`. Numeric equality or similar labels alone must not be treated as proof. Preserve the vendor's labels and movement codes until their conventions are confirmed; do not substitute conventional phase-number directions.

The user's physical descriptions are preserved in `config/signal_layouts.json`. They describe 1, 2 or 4 reported locations/assemblies per intersection, independently of the number of phases. Islington was explicitly confirmed as the intended name. Norfinch/Oakdale and Signet/Arrow references need coordinate checks. Two-location descriptions do not identify which sides. No physical coordinates or phase assignments were invented.

A physical assembly can expose several directional heads, so assigning one state to an entire centre-mounted assembly can also mislead. The required relationship is: intersection + versioned definition → verified real-time identifier → controlled movement/head → physical location. Until those relationships are verified, the removed signal icons remain removed.

Double-click `scripts/collect_phase_definitions.command` to fetch all ten Toronto sensors' definitions through a private credential prompt. Original responses, including inactive versions, are saved under ignored `data/cloud/`; credentials remain in process memory. The script does not alter site configuration and marks identifier correspondence unverified. Successful fetching alone is not mapping validation.
