# PR 8 controlled evidence-acquisition study

This study is a **synthetic mechanics-only** test over the frozen PR 7 fixtures. It
is not provider evidence and does not establish an Iceberg advantage.

Run offline:

```sh
PYTHONPATH=src python -m iceberg_router.experiments.evidence --output results/evidence-v1
```

The downstream empirical-success-then-cost allocator is identical in every arm.
The arms are zero-probe, cash-capped seeded random probing, cash-capped stratified
probing, and separately named resource-aware racing. Racing changes scheduling only;
it does not irreversibly eliminate an option. Every nonzero arm predeclares the
rule “stop before the next whole probe would exceed the cap.” Production helpers
turn that plan into distinct durable ledger authorizations under the transactional
adaptation subbudget before any probe side effect.

Calibration and probe labels are available only in their declared splits. Final
counterfactuals are withheld until evaluation. Reports separate Bernoulli outcome
variance from the standard error of estimated success probability, and include
calibration, probing, and serving cost in net utility.

## Predeclared stop decision

The frozen study produced a null result: none of the probe variants repaid its full
synthetic acquisition cost relative to zero-probe. The recorded conclusion is
`null-result-simplify-to-zero-probe`. Baselines, cap, utility conversion, coverage,
and information access were not changed after observing the result. Learned probe
value, adaptive feedback, and dynamic graphs therefore remain unimplemented.
