# Step 31 decision traces

The first frozen history in each predefined closed-loop T2 versus B3 stratum at 50%.
Each sequence is shown under both modes. A stale target consumes a call without applying its verdict.

## T2 loss in seed-library-accession/0

### B3 in fixed

| Date | Arrival | Proposed | Gold | Live before call | Selected target | Budget before | Verdict | Applied | Memory after |
|---|---|---|---|---|---|---:|---|---|---|
| 2025-07-12 | correct | Juniper Acorn | Juniper Acorn | Nettle Hill | Nettle Hill | 2 | update | yes | Juniper Acorn |
| 2025-07-15 | implicit | Iris Hearth | Iris Hearth | Juniper Acorn | Juniper Acorn | 1 | update | yes | Iris Hearth |
| 2025-07-26 | uncertain | Alder Lantern | Iris Hearth | Iris Hearth | Juniper Acorn | 0 | — | no | Iris Hearth |
| 2025-08-06 | historical | Nettle Dawn | Iris Hearth | Iris Hearth | Juniper Acorn | 0 | — | no | Iris Hearth |
| 2025-08-09 | misleading | Bramble Moon | Iris Hearth | Iris Hearth | Juniper Acorn | 0 | — | no | Bramble Moon |

### T2 in fixed

| Date | Arrival | Proposed | Gold | Live before call | Selected target | Budget before | Verdict | Applied | Memory after |
|---|---|---|---|---|---|---:|---|---|---|
| 2025-07-12 | correct | Juniper Acorn | Juniper Acorn | Nettle Hill | Nettle Hill | 2 | update | yes | Juniper Acorn |
| 2025-07-15 | implicit | Iris Hearth | Iris Hearth | Juniper Acorn | — | 1 | — | no | Juniper Acorn |
| 2025-07-26 | uncertain | Alder Lantern | Iris Hearth | Juniper Acorn | — | 1 | — | no | Juniper Acorn |
| 2025-08-06 | historical | Nettle Dawn | Iris Hearth | Juniper Acorn | — | 1 | — | no | Juniper Acorn |
| 2025-08-09 | misleading | Bramble Moon | Iris Hearth | Juniper Acorn | Juniper Acorn | 1 | same | yes | Juniper Acorn |

### B3 in closed-loop

| Date | Arrival | Proposed | Gold | Live before call | Selected target | Budget before | Verdict | Applied | Memory after |
|---|---|---|---|---|---|---:|---|---|---|
| 2025-07-12 | correct | Juniper Acorn | Juniper Acorn | Nettle Hill | Nettle Hill | 2 | update | yes | Juniper Acorn |
| 2025-07-15 | implicit | Iris Hearth | Iris Hearth | Juniper Acorn | Juniper Acorn | 1 | update | yes | Iris Hearth |
| 2025-07-26 | uncertain | Alder Lantern | Iris Hearth | Iris Hearth | — | 0 | — | no | Iris Hearth |
| 2025-08-06 | historical | Nettle Dawn | Iris Hearth | Iris Hearth | — | 0 | — | no | Iris Hearth |
| 2025-08-09 | misleading | Bramble Moon | Iris Hearth | Iris Hearth | — | 0 | — | no | Bramble Moon |

### T2 in closed-loop

| Date | Arrival | Proposed | Gold | Live before call | Selected target | Budget before | Verdict | Applied | Memory after |
|---|---|---|---|---|---|---:|---|---|---|
| 2025-07-12 | correct | Juniper Acorn | Juniper Acorn | Nettle Hill | Nettle Hill | 2 | update | yes | Juniper Acorn |
| 2025-07-15 | implicit | Iris Hearth | Iris Hearth | Juniper Acorn | — | 1 | — | no | Juniper Acorn |
| 2025-07-26 | uncertain | Alder Lantern | Iris Hearth | Juniper Acorn | — | 1 | — | no | Juniper Acorn |
| 2025-08-06 | historical | Nettle Dawn | Iris Hearth | Juniper Acorn | Juniper Acorn | 1 | historical | yes | Juniper Acorn |
| 2025-08-09 | misleading | Bramble Moon | Iris Hearth | Juniper Acorn | — | 0 | — | no | Bramble Moon |

## tie in seed-library-accession/1

### B3 in fixed

| Date | Arrival | Proposed | Gold | Live before call | Selected target | Budget before | Verdict | Applied | Memory after |
|---|---|---|---|---|---|---:|---|---|---|
| 2025-07-05 | implicit | Elm Oar | Elm Oar | Juniper Hill | Juniper Hill | 3 | update | yes | Elm Oar |
| 2025-07-08 | correct | Zinc Key | Zinc Key | Elm Oar | Juniper Hill | 2 | update | no | Zinc Key |
| 2025-07-09 | misleading | Violet Shell | Zinc Key | Zinc Key | Zinc Key | 1 | same | no | Violet Shell |
| 2025-07-20 | historical | Reed Drum | Zinc Key | Violet Shell | Violet Shell | 0 | — | no | Violet Shell |
| 2025-08-29 | uncertain | Maple Wheel | Zinc Key | Violet Shell | Violet Shell | 0 | — | no | Violet Shell |

### T2 in fixed

| Date | Arrival | Proposed | Gold | Live before call | Selected target | Budget before | Verdict | Applied | Memory after |
|---|---|---|---|---|---|---:|---|---|---|
| 2025-07-05 | implicit | Elm Oar | Elm Oar | Juniper Hill | Juniper Hill | 3 | update | yes | Elm Oar |
| 2025-07-08 | correct | Zinc Key | Zinc Key | Elm Oar | Juniper Hill | 2 | update | no | Zinc Key |
| 2025-07-09 | misleading | Violet Shell | Zinc Key | Zinc Key | Zinc Key | 1 | same | no | Violet Shell |
| 2025-07-20 | historical | Reed Drum | Zinc Key | Violet Shell | — | 0 | — | no | Violet Shell |
| 2025-08-29 | uncertain | Maple Wheel | Zinc Key | Violet Shell | — | 0 | — | no | Violet Shell |

### B3 in closed-loop

| Date | Arrival | Proposed | Gold | Live before call | Selected target | Budget before | Verdict | Applied | Memory after |
|---|---|---|---|---|---|---:|---|---|---|
| 2025-07-05 | implicit | Elm Oar | Elm Oar | Juniper Hill | Juniper Hill | 3 | update | yes | Elm Oar |
| 2025-07-08 | correct | Zinc Key | Zinc Key | Elm Oar | Elm Oar | 2 | update | yes | Zinc Key |
| 2025-07-09 | misleading | Violet Shell | Zinc Key | Zinc Key | Zinc Key | 1 | same | yes | Zinc Key |
| 2025-07-20 | historical | Reed Drum | Zinc Key | Zinc Key | — | 0 | — | no | Zinc Key |
| 2025-08-29 | uncertain | Maple Wheel | Zinc Key | Zinc Key | — | 0 | — | no | Zinc Key |

### T2 in closed-loop

| Date | Arrival | Proposed | Gold | Live before call | Selected target | Budget before | Verdict | Applied | Memory after |
|---|---|---|---|---|---|---:|---|---|---|
| 2025-07-05 | implicit | Elm Oar | Elm Oar | Juniper Hill | Juniper Hill | 3 | update | yes | Elm Oar |
| 2025-07-08 | correct | Zinc Key | Zinc Key | Elm Oar | Elm Oar | 2 | update | yes | Zinc Key |
| 2025-07-09 | misleading | Violet Shell | Zinc Key | Zinc Key | Zinc Key | 1 | same | yes | Zinc Key |
| 2025-07-20 | historical | Reed Drum | Zinc Key | Zinc Key | — | 0 | — | no | Zinc Key |
| 2025-08-29 | uncertain | Maple Wheel | Zinc Key | Zinc Key | — | 0 | — | no | Zinc Key |

## T2 win in seed-library-accession/2

### B3 in fixed

| Date | Arrival | Proposed | Gold | Live before call | Selected target | Budget before | Verdict | Applied | Memory after |
|---|---|---|---|---|---|---:|---|---|---|
| 2025-10-08 | historical | Kite Wheel | Harbor Drum | Harbor Drum | Harbor Drum | 2 | historical | yes | Harbor Drum |
| 2026-01-13 | uncertain | Dune Quartz | Harbor Drum | Harbor Drum | Harbor Drum | 1 | insufficient_evidence | yes | Harbor Drum |
| 2026-01-14 | implicit | Juniper Nest | Juniper Nest | Harbor Drum | Harbor Drum | 0 | — | no | Harbor Drum |
| 2026-04-21 | misleading | Bramble Lantern | Juniper Nest | Harbor Drum | Harbor Drum | 0 | — | no | Bramble Lantern |
| 2026-04-22 | correct | Fable Ivory | Fable Ivory | Bramble Lantern | Bramble Lantern | 0 | — | no | Fable Ivory |

### T2 in fixed

| Date | Arrival | Proposed | Gold | Live before call | Selected target | Budget before | Verdict | Applied | Memory after |
|---|---|---|---|---|---|---:|---|---|---|
| 2025-10-08 | historical | Kite Wheel | Harbor Drum | Harbor Drum | — | 2 | — | no | Harbor Drum |
| 2026-01-13 | uncertain | Dune Quartz | Harbor Drum | Harbor Drum | — | 2 | — | no | Harbor Drum |
| 2026-01-14 | implicit | Juniper Nest | Juniper Nest | Harbor Drum | — | 2 | — | no | Harbor Drum |
| 2026-04-21 | misleading | Bramble Lantern | Juniper Nest | Harbor Drum | Harbor Drum | 2 | same | yes | Harbor Drum |
| 2026-04-22 | correct | Fable Ivory | Fable Ivory | Harbor Drum | Bramble Lantern | 1 | update | no | Fable Ivory |

### B3 in closed-loop

| Date | Arrival | Proposed | Gold | Live before call | Selected target | Budget before | Verdict | Applied | Memory after |
|---|---|---|---|---|---|---:|---|---|---|
| 2025-10-08 | historical | Kite Wheel | Harbor Drum | Harbor Drum | Harbor Drum | 2 | historical | yes | Harbor Drum |
| 2026-01-13 | uncertain | Dune Quartz | Harbor Drum | Harbor Drum | Harbor Drum | 1 | insufficient_evidence | yes | Harbor Drum |
| 2026-01-14 | implicit | Juniper Nest | Juniper Nest | Harbor Drum | — | 0 | — | no | Harbor Drum |
| 2026-04-21 | misleading | Bramble Lantern | Juniper Nest | Harbor Drum | — | 0 | — | no | Bramble Lantern |
| 2026-04-22 | correct | Fable Ivory | Fable Ivory | Bramble Lantern | — | 0 | — | no | Fable Ivory |

### T2 in closed-loop

| Date | Arrival | Proposed | Gold | Live before call | Selected target | Budget before | Verdict | Applied | Memory after |
|---|---|---|---|---|---|---:|---|---|---|
| 2025-10-08 | historical | Kite Wheel | Harbor Drum | Harbor Drum | Harbor Drum | 2 | historical | yes | Harbor Drum |
| 2026-01-13 | uncertain | Dune Quartz | Harbor Drum | Harbor Drum | — | 1 | — | no | Harbor Drum |
| 2026-01-14 | implicit | Juniper Nest | Juniper Nest | Harbor Drum | Harbor Drum | 1 | update | yes | Juniper Nest |
| 2026-04-21 | misleading | Bramble Lantern | Juniper Nest | Juniper Nest | — | 0 | — | no | Bramble Lantern |
| 2026-04-22 | correct | Fable Ivory | Fable Ivory | Bramble Lantern | — | 0 | — | no | Fable Ivory |
