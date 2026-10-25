# Synthetic installed feature-review fixtures

These invented rows support the current Full Stack application's manual
functional review. Names/prices are synthetic, with explicit source
`SYNTHETIC_CP6_REVIEW`; they are not medication observations or assistant imports.
Keep the test dataset title prefixed `TEST CP6` and preserve existing resources.
The fixtures contain no private accounts, credentials or patient information.

Import v1 as a new private dataset, then append v2 to that same dataset only after
the pinned-v1 analysis has been saved. Keep `presentation_id` as text, price as
numeric, the empty price as missing and `observation_date` as ISO date.

| Expected value | v1 | v2 |
| --- | --- | --- |
| Data rows / columns | 9 / 8 | 10 / 8 |
| Nonmissing price values | 8 | 10 |
| Missing price values | 1 (`009`) | 0 |
| Price sum / mean | 410 / 51.25 | 450 / 45 |
| Price min / max | 0 / 200 | 0 / 90 |
| Group A: rows / price sum / price mean | 4 / 60 / 15 | 4 / 60 / 15 |
| Group B: rows / price sum / price mean | 5 / 350 / 87.5 | 6 / 390 / 65 |

With no filters or grouping, v1 type-7 Q1=17.5, median=35, Q3=52.5, IQR=35;
factor 1.5 gives fences -35 and 105. Only `008` (price 200) is an IQR outlier.
Zero is present, not missing. The v1 price-missing rate is 1/9 (about 11.11%).
For a pie chart choose `Nombre de lignes`, grouping `group`: B=5/A=4
(55.56%/44.44%). Pie charts support additive counts, not price sums/means;
the sum-based pie configuration must be rejected by the current chart rules.
Comparing versions by unique text `presentation_id`: one added row (`010`),
zero removed, two changed (`008`, `009`), seven unchanged. The original v1 must
remain unchanged after v2 publication and saved v1 analyses must still use v1.

For the invalid-number file, explicitly choose numeric price type before
validation: publication must be blocked, with a useful validation report and no
dataset/version created. The invalid-structure file has five values for eight
headers and must not publish. Cancel each rejected staging import after review.

See [the phased installed review](../../../../../docs/validation/platform-checkpoint-6-functional-review.md)
for dashboard, permissions, suspension and cleanup checks. No normal-volume
feature-review execution is claimed merely by creating these files.
