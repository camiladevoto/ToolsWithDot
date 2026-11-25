# SalaryLens maintenance

- FX: ECB daily reference rates (EUR base), scheduled on weekdays at 16:42 UTC. No salary data is transmitted. The workflow must be enabled and permitted to push; verify the first run and Pages deployment. Rates are indicative, not transaction prices. 
- Tax rules: edit rates.json only after reviewing official authorities, effective dates, thresholds, regional rules, and regression tests. Update the embedded DEFAULTS in index.html in the same change for offline fallback. Do not automatically publish tax rules extracted from webpages.
- Australia: resident marginal brackets 2026–27, simplified; offsets and levy reductions not modeled. Review annually before July 1. Spain, Switzerland, Italy: manual scenario inputs only pending validated country/regime engines. Review before January 1 and after legislative changes.
- Benchmark: Spain INE 2024 mean annual gross earnings per worker; not occupation-specific. Other benchmarks user-entered. Review official releases and add comparable measures only with date, scope and source.
- Before launch of additional engines: test against official calculators, boundary cases, freelancer regimes and regional rules. 
