# Synthetic baseline mechanics

No model-superiority or Iceberg-advantage claim is made.

| strategy | utility | coverage | cost nanos | unresolved holds | latency ms | failures | paired utility CI vs fixed |
|---|---:|---:|---:|---:|---:|---:|---:|
| fixed-cheap | 5 | 5/6 | 120 | 0 | 84 | 1 | [0.0, 0.0] |
| feasible-mixture | 3 | 3/6 | 100 | 0 | 70 | 0 | [-0.833333, 0.333333] |
| task-feature-control | 3 | 3/6 | 240 | 0 | 168 | 3 | [-0.833333, 0.333333] |
| wr-paper-reproduction | 5 | 5/6 | 140 | 0 | 98 | 0 | [0.0, 0.0] |
| wr-plus-common-guard | 6 | 6/6 | 190 | 0 | 133 | 0 | [0.0, 0.5] |
| wr-path-plus-common-guard | 4 | 4/6 | 220 | 0 | 154 | 2 | [-0.666667, 0.333333] |
