# GLM-Focused Analysis Context

## Framing
- **Research goal:** Quantify whether later Pokémon generations exhibit higher offensive or overall stat strength (“power creep”) after adjusting for observable covariates.
- **Primary target:** Base `attack` (continuous, approx. Gaussian after mild transformation). Secondary composite targets such as `total_offense = attack + sp_attack` or `overall_stat_sum = hp + attack + defense + sp_attack + sp_defense + speed`.
- **Key predictor of interest:** `gen` treated as an ordered categorical or numeric variable depending on linearity checks.

## Data Assets
- Source files under `data/` (`pokemon.csv`, `pokemon_ix.csv`, cleaned variants) already contain generations 1–8 plus Gen IX draft.
- Relevant columns include stats (`hp`, `attack`, `defense`, `sp_attack`, `sp_defense`, `speed`), resistances (`against_*`), rarity indicators, evolution metadata, and fandom preference (`votes_*`).
- Create modeling table with one row per species, ensuring:
  - Deduplication of forms unless mega/gigantamax is modeled via indicator variables.
  - Consistent currency of `rarity`, `has_mega_evolution`, `has_gigantamax`, and `evo_length`.

## Data Preparation Plan
1. **Filtering:** Drop rows with excessive missingness; optionally flag legendaries/mythicals.
2. **Transforms:** Address skew (`log1p` for `weight_kg`, `base_egg_steps`, `capture_rate`; square-root for `votes_*`).
3. **Encoding:** One-hot encode `primary_type`, `secondary_type`, `rarity`, `has_*` indicators. Consider Helmert contrasts for `gen` to capture monotone change.
4. **Interactions & Splines:**
   - Natural cubic splines for `hp`, `defense`, `speed`, `sp_attack`, `sp_defense`.
   - Interactions between `gen` and key types/rarity to detect differential creep.

## Candidate GLM Specifications
| Model | Response | Distribution / Link | Notes |
| --- | --- | --- | --- |
| Baseline LM | `attack` | Gaussian / Identity | Reference for comparisons. |
| Penalized GLM | `attack` | Gaussian / Identity with ElasticNet | Feature shrinkage + type encodings. |
| Composite Strength GLM | `overall_stat_sum` | Gaussian / Identity | Tests broader “power creep”. |
| Offensive Count GLM | `num_abilities` or indicator of `attack > threshold` | Poisson / Log or Binomial / Logit | Evaluates shift in special mechanics prevalence. |
| Aggressive Share Model | Count of “high-attack” pokémon per generation | Poisson regression with exposure term (# species) | Detects growth of strong species counts. |

## Core Questions to Answer
1. **Generational effect:** After adjusting for stats, rarity, and typings, is the `gen` coefficient significantly positive? Report effect sizes (per-generation slope or contrasts vs. Gen 1).
2. **Type-adjusted creep:** Are certain types (e.g., Dragon, Steel) driving the generational increase? Test `gen × type` interaction terms.
3. **Rarity mediation:** Does including `rarity` attenuate the generational effect (i.e., is creep explained by more legendary entries)?
4. **Nonlinear dynamics:** Do spline terms reveal diminishing returns for defensive stats while offensive stats keep rising?
5. **Model robustness:** Do conclusions persist when removing outliers (legendary or mega forms) or when training on gens ≤5 and testing on ≥6 (time-split CV)?

## Evaluation & Diagnostics
- Train/validation split respecting generation order (e.g., rolling origin CV).
- Compare nested models with ANOVA or Likelihood Ratio Tests for `gen` terms.
- Inspect residuals, leverage, and variance inflation to ensure model adequacy.
- Use permutation importance or standardized coefficients to interpret top predictors.

## Deliverables & Next Steps
1. Build preprocessing pipeline in Python (pandas + patsy/polars + scikit-learn or statsmodels).
2. Implement baseline LM, ElasticNet GLM, and at least one alternative distribution model.
3. Document statistical tests highlighting whether generation remains significant.
4. Produce visuals: generational partial dependence plots, coefficient paths, and predicted vs. observed attack per generation.
5. Summarize findings in report/notebook, linking back to “power creep” hypothesis.

## Inspiration from Legacy SAN Projects
- **Dual-model comparisons:** Mirror past teams by training paired GLMs with/without the hypothesized driver (here: generation or mechanics). Compare AIC/RMSE and run likelihood-ratio tests to quantify added value.
- **Multi-metric correlations:** Compute Pearson, Spearman, and Kendall correlations between key stats to uncover robust relationships before modeling—helps surface collinearity similar to the unemployment/refugee study.
- **Lag-style signals:** Reproduce the “distributed lag” idea using Pokémon generations: derive per-type rolling means or cumulative attack deltas to encode how a species compares with historical counterparts.
- **Temporal cross-validation:** Adopt rolling generation splits (train ≤ Gen *k*, test Gen *k*+1) instead of random CV so we gauge forward-looking predictive power, akin to earlier seasonality analyses.
- **Seasonality-style plots:** Even without monthly data, plot generation-conditioned trajectories (means, quantiles, offense ratios) and overlay mechanic adoption curves to echo the informative seasonal plots from prior projects.

## Notebook Findings (Nov 26 2025 run)

### Data snapshot & engineered fields
- `glm_analysis.ipynb` loads `data/data_clean.csv` (1024 rows × 41 raw columns) and engineers 54 modeling columns via:
  - composite stats (`total_offense`, `total_defense`, `overall_stat_sum`, `offense_ratio`, `aggression_index`, `offense_share`);
  - mechanic features where `mechanic_stack = has_mega_evolution + has_gigantamax`, `long_evo_chain = 1` for evolution depth ≥3, and `mechanic_complexity = mechanic_stack + long_evo_chain`;
  - resistance PCA (`resistance_pc1`–`pc3`) explaining 19.9%, 13.9%, and 11.5% of scaled variance, respectively.
- Modeling table (`model_df`) fills `rarity → "normal"`, `class_primary → "Unknown"` (later mapped back to numeric type ids 0–17), `class_secondary → "None"`, and drops rows missing `attack`, `overall_stat_sum`, or `num_abilities`, leaving 1024 usable species.
- Type encoding: `class_primary` integers follow the Kaggle order (0=grass, 1=fire, 2=water, 3=bug, 4=normal, 5=poison, 6=electric, 7=ground, 8=fairy, 9=fighting, 10=psychic, 11=rock, 12=ghost, 13=ice, 14=dragon, 15=dark, 16=steel, 17=flying). `rarity` uses 0=normal, 1=sublegendary, 2=legendary, 3=mythical.

### Generational aggregates

| Gen | Mean Attack | Mean Total Offense | Mean Overall Sum | Mean Offense Ratio | Mean Mechanic Complexity |
| --- | --- | --- | --- | --- | --- |
| 1 | 72.91 | 140.05 | 407.64 | 1.07 | 1.07 |
| 2 | 68.26 | 132.76 | 407.18 | 1.02 | 0.87 |
| 3 | 73.11 | 140.97 | 403.73 | 1.13 | 0.96 |
| 4 | 80.21 | 153.50 | 445.76 | 1.10 | 0.87 |
| 5 | 81.03 | 150.28 | 425.76 | 1.12 | 0.84 |
| 6 | 72.50 | 145.04 | 429.31 | 1.00 | 0.85 |
| 7 | 84.77 | 159.73 | 449.41 | 1.12 | 0.66 |
| 8 | 82.88 | 154.18 | 438.53 | 1.12 | 0.91 |
| 9 | 82.42 | 155.29 | 457.39 | 1.08 | 0.57 |

Later generations (7–9) sustain higher mean attack/total offense even as mechanic complexity drops back below earlier-gen levels.

### Correlation diagnostics
- Kendall correlations with `attack`: `total_offense` 0.62, `hp` 0.44, `defense` 0.38, `total_defense` 0.33, `speed` 0.25. Defensive stats maintain non-trivial association, confirming the need to keep both offense and defense aggregates in GLMs.

### ElasticNet feature screen
- 5-fold ElasticNetCV (`drop_first=True` dummies) selected `alpha = 0.208` with `l1_ratio = 0.9`.
- Largest absolute coefficients: `defense` 12.6, `hp` 9.15, `speed` 8.72, `sp_defense` –5.07, `resistance_pc2` –2.99, followed by smaller but non-zero weights on `rarity`, `mechanic_complexity`, `gen`, `sp_attack`, and `resistance_pc1`. Dummy-expanded `class_primary`/`class_secondary` columns were shrunk to ~0, indicating type effects can be reintroduced via explicit contrasts rather than penalized regression.

### GLM comparison (Gaussian attack target)

| Model | AIC | Deviance | Pseudo R² |
| --- | --- | --- | --- |
| Baseline (no `gen`, no mechanics) | 8577.46 | 248 971.99 | 0.726 |
| Legacy-inspired (adds `C(gen)`, mechanics, resistances) | 8568.72 | 241 609.80 | 0.734 |

Adding generational/mechanic signals trims deviance by ~7.4k and nudges pseudo-R² up by ~0.8 percentage points, mirroring the “with vs. without key driver” comparisons from legacy SAN projects.

### Rolling generation CV (legacy formula)

| Train gens | Test gen | RMSE |
| --- | --- | --- |
| ≤2 | 3 | 14.07 |
| ≤3 | 4 | 16.82 |
| ≤4 | 5 | 15.85 |
| ≤5 | 6 | 15.36 |
| ≤6 | 7 | 20.13 |
| ≤7 | 8 | 17.03 |
| ≤8 | 9 | 20.07 |

Forward-chaining error stays near 15–16 for mid-era hand-offs but spikes above 20 when predicting Gen 7+ or Gen 9, highlighting where mechanic shifts/outliers hurt extrapolation.

### Attack GLM (Gaussian with categorical contrasts)
- Formula: `attack ~ C(gen, levels=1–9) + total_offense + total_defense + mechanic_complexity + resistance_pc1/2/3 + C(rarity) + C(class_primary)`, using Grass/Normal/Gen 1 as baselines.
- Continuous effects: `total_offense` +0.515 attack per point (p < 1e-15), `resistance_pc2` –2.14 (p = 1.7e-05) implying certain resistance profiles trade off with attack. `total_defense`, `mechanic_complexity`, `resistance_pc1`, and `resistance_pc3` were not significant at α=0.05.
- Key categorical offsets (vs. grass/normal/Gen1 baselines):

| Term | Coef | p-value |
| --- | --- | --- |
| primary_type = fighting | +21.93 | 3.6e-11 |
| primary_type = ground | +15.91 | 5.2e-06 |
| primary_type = psychic | –11.61 | 1.2e-04 |
| primary_type = electric | –8.80 | 7.5e-03 |
| primary_type = bug | +8.53 | 1.4e-03 |
| primary_type = steel | +8.45 | 4.2e-02 |
| primary_type = rock | +8.05 | 4.0e-02 |
| primary_type = dragon | +6.50 | 4.4e-02 |
| rarity = mythical | –6.10 | 1.1e-01 (directional: mythicals trend lower attack after adjusting for stats) |

These contrasts show type-level residual “power creep” (e.g., Fighting/Ground maintain +16–22 attack beyond aggregates) while Electric/Psychic skew lower once base stats are accounted for.

### Likelihood-ratio test for `gen`
- Comparing the full attack GLM vs. the same specification without `C(gen, ...)` yields χ² = 10.36 with 8 df (p = 0.24), i.e., once stats, resistances, mechanics, rarity, and primary type are controlled, the generation block no longer improves fit at conventional significance levels—useful when discussing whether “power creep” is fully mediated by other covariates.

### Additional GLMs
- `overall_stat_sum ~ ...` Gaussian GLM reports deviance/df ≈ 899.3, confirming that aggregate offense/defense terms nearly saturate the response; remaining variance is mostly scale noise.
- Poisson GLM on `num_abilities` (AIC 3032.86) shows strong rarity effects: sublegendary (–0.37), legendary (–0.39), and mythical (–0.76) categories list fewer explicit abilities after adjusting for stats/mechanics. Generations 7 and 9 have mild negative coefficients (~–0.16) suggesting recent entries focus on stats over ability count. Primary-type effects are comparatively small (flying +0.26, normal +0.15, both weakly significant).

Use this section as the single source of truth for the numbers cited elsewhere (reports, slides, README). When rerunning the notebook, refresh these tables/metrics so `GLM_context.md` stays synchronized with the executed analysis.

