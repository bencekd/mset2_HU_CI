# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**MINDSET / MSET** (Model of Innovation in Dynamic Low-Carbon Structural Economic and Employment Transformations) is a global, demand-driven, recursively dynamic macroeconometric simulation model: a multi-regional input–output core (GLORIA v57, base year 2019) combined with econometric equations for prices, wages, employment, investment, household and government demand.

This repository (`mset2_IPCC`) runs **10 IPCC regions × 23 sectors** (the 8 GLORIA energy sectors kept standalone, the other 112 merged into 15 groups) for the Ortec pilot. Lineage: `cpmodel/mset2` → `bencekd/mset2_HU_CI` (git remote `upstream`) → `binderiya-bya/mset2_IPCC` (`origin`). Model dimensions always come from `Data/MSET_data/Variable_list_MINDSET.xlsx` (sheets `R`, `P`); never assume 163 regions or 120 sectors.

## Running the Model

```bash
python MINDSET_dynamic_run.py s_base.ini            # empty scenario (CALIBRATING = True: calibration; False: baseline)
python MINDSET_dynamic_run.py s_cprice_disagg.ini   # carbon-price scenario
```

Workflow (same `s_base.ini`, only `CALIBRATING` changes):
1. Calibration: `s_base.ini` with `CALIBRATING = True` writes `Residuals/residuals_{year}.pkl`.
2. Baseline: `s_base.ini` with `CALIBRATING = False` reads those residuals; this is the reference for scenario comparisons.
3. Scenarios: e.g. `s_cprice_disagg.ini` (`CALIBRATING = False`).
Forward runs read `Residuals/residuals_{year}.pkl` directly; the `residuals_file` setting is not read.

- The only argument is the `.ini` file. With no argument the model reads `settings.ini`, which is not in the repo.
- The script changes to its own folder, so it can be launched from anywhere. `run_dynamic_disagg.cmd` runs the three configurations on Windows.
- For a quick test, set `model_end = 2021` (2019–2021 runs in a couple of minutes); set it back to 2050 afterwards.
- Python ≥ 3.10 with `numpy`, `pandas`, `scipy`, `pyarrow`, `openpyxl`, `dill` (there is no `requirements.txt`).

## Configuration (`.ini`, section `[settings]`)

| Parameter | Meaning |
|---|---|
| `scenario_name` | File in `Data/MSET_data/Scenarios/` (`empty` = baseline) |
| `model_start` / `model_end` | Simulation years |
| `CALIBRATING` | `True`: fit to `output_projection` and write `Residuals/residuals_{year}.pkl`; `False`: scenario run that reads those residuals |
| `SWITCH_WITHIN_YEAR_LOOP` | Within-year convergence iterations |
| `mrio_inverse_recalculate` | Recompute Leontief/Ghosh inverses |
| `ftt_run` | FTT:Power sub-model (only works with 120 sectors, see Known issues) |
| `cost_curves_run` | Cost curves for fossil extraction (sector role `cost_curve`; data in `Energy_emissions/cost_curves.csv`) |
| `remittance_channel` | Remittance income channel (input file missing; keep `False`) |
| `fuel_substitution_start` | Optional; first year with fuel substitution (default `model_start + 1`) |
| `bta` | Border tax adjustment switch |
| `COND_LABOR/TAX/TRADE/PRICE` | Within-year convergence thresholds (%) |
| `ITER_MAX` | Max within-year iterations |
| `WRITE_AT_END` | Write results only after the final year |
| `tax_incidence_file`, `dL_ener_file` | Read but not used |
| `residuals_file`, `COND_OUTPUT` | Present in the `.ini` files but not read by the code |

- Every setting without a default must be present, or the run stops at start-up with a missing-option error.
- `SWITCH_WITHIN_YEAR_LOOP`, `mrio_inverse_recalculate`, `CALIBRATING`, `ftt_run`, `remittance_channel` and `cost_curves_run` are parsed with `istruefalse`: only the exact string `True` counts as true. `WRITE_AT_END` uses `getboolean`.

## Architecture

### Execution flow

```
MINDSET_dynamic_run.py
  └─ ModelRun (SourceCode/model_class.py)
       ├─ __init__: reads .ini, loads exog_vars (incl. SECTOR_ROLES), builds variables_table self.V
       ├─ run(): archives old outputs, loops over years [model_start, model_end]
       └─ solve_year(year):
            ├─ calibration loop (CALIBRATING=True): fits final-demand residuals to output_projection
            ├─ initiate_modules() [SourceCode/initiate_modules.py]: all modules, within-year iterations
            └─ dynamics: output, employment, prices, wages, capital, government, value added → next year
```

### Module order in `initiate_modules.py`

1. **scenario** — policy shocks (carbon tax, CBAM, FD changes, IO changes, prices, supply constraints)
2. **ener_balance / cost_curves** — energy flows, fuel substitution, emissions, carbon-tax incidence
3. **prod_cost / price** — cost-push and second-order (Leontief) price effects
4. **household / government / trade / investment** — demand responses
5. **InputOutput** — output changes (`dq_*`), summed into `dq_total`
6. **employment / income / tax_rev / BTA / GDP**
7. repeat until `COND_*` are met or `ITER_MAX`

### Key source files

| File | Role |
|---|---|
| `SourceCode/model_class.py` | `ModelRun`; settings, calibration, `solve_year()`, year-end dynamics (value added, capital, government) |
| `SourceCode/initiate_modules.py` | Calls all modules; within-year loop; writes `Temp/iter*.csv` |
| `SourceCode/variables.py` | `variables_table` (`self.V`); typed storage of all cross-year variables, registered in `variables.xlsx` |
| `SourceCode/exog_vars.py` | Loads inputs listed in `Variable_list_MINDSET.xlsx`; builds `SECTOR_ROLES` |
| `SourceCode/scenario.py` | Reads scenario sheets; resolves `ALL`, ranges and lists |
| `SourceCode/government.py` | Government spending by revenue source (income tax, sales tax, capital tax, royalties, residual) |
| `SourceCode/household.py`, `income.py` | Household demand, saving, wages |
| `SourceCode/ener_balance.py` | Energy balance, fuel substitution, emission costs |
| `SourceCode/utils.py` | MRIO vector/matrix helpers, `resolve_*`, logging, console helpers |

## Variable store (`self.V`) — rules

- Every variable written or read through `self.V` must be a row in `variables.xlsx` (sheet `vars`: `VAR_NAME`, `DIM1`–`DIM4`, `TYPE`, `MIN`, `MAX`). An unregistered name fails with `IndexError` (`write_var` / `read_var`) or `ValueError` (`write_var_df`).
- `write_var(..., from_df=True)` needs the dimension columns plus a column named exactly like the variable.
- `write_var` warns and **clips** values to [`MIN`, `MAX`]; use `-Inf` / `Inf` unless a bound is intended.
- `write_var_df` / `read_var_df` store 3D/4D data as parquet in `Results/`; they check that every listed dimension is a column and that its values belong to the model's lists (regions, model sectors, `FD_1`/`FD_3`/`FD_4`).
- `read_var` returns a reference to the stored array, not a copy.

## Sector roles — never hard-code sector numbers

Sector-specific logic must use `EXOG_VARS.SECTOR_ROLES[...]` and "all sectors" must use the model list (`EXOG_VARS.P_list`, `scenario.P_IDS`), never GLORIA-120 or aggregated numbers.

- Roles are defined once in GLORIA-120 codes (`GLORIA_SECTOR_ROLES` in `exog_vars.py`): `cost_curve` 24–26, `refining` 62/63/94, `non_market` 115–118, `royalty` 22–40, `electricity` 93.
- They are mapped through the `product_groups` sheet of the workbook in `Data/MSET_data/Country_groupings/` whose sector numbers and names match sheet `P`; a model sector takes a role when more than half of its GLORIA sectors have it.
- Start-up prints the result, e.g. for R10×S23: `cost_curve [2, 3, 4]; refining [9, 10, 16]; non_market [23]; royalty [2, 3, 4, 5, 6]; electricity [15]`.

## Data (`Data/`, git-ignored)

| Path | Content |
|---|---|
| `Data/MSET_data/Variable_list_MINDSET.xlsx` | Sheet `variables`: input name → file (`Location`); sheets `R`, `P`: regions and sectors |
| `Data/MSET_data/Scenarios/` | Scenario workbooks (`empty.xlsx` = baseline) |
| `Data/MSET_data/Country_groupings/` | Grouping workbook (`IPCC_regions_23sectors.xlsx`) |
| `Data/MSET_data/Investment/` | Capital stock, investment, output and value-added history 2016–2019, inflation targets, depreciation |
| `Data/MSET_data/modelinputdata/` | `parameters.csv` (econometric parameters, `REG_imp` × `PROD_COMM`), `compensation_share.csv` |
| `Data/MSET_data/{Employment,Government,Energy_emissions,Population}/` | Labour, revenue shares, cost curves and process emissions, population |
| `Data/GLORIA_db/` | Collapsed GLORIA tables (`IND_sparse.pkl`, `HH/GOV/FCF/VA/labor_data.pkl`, `output_projection_2019-2050.csv`, inverse `.mat` files) |
| `Data/Energy_db/` | `ALL_FUELS.csv`, `ALL_POLLUTANTS.csv`, `ALL_PROCESS_EMISSIONS.csv` |

`Data/` is produced outside the repo by `MINDSET/DATA/collapse_MRIO.py --grouping IPCC_regions_23sectors.xlsx [--overwrite]` from the full-resolution inputs in `DATA/MSET_data_original`, `DATA/parsed_db_original` and `DATA/Energy_emissions/2026 Aug/out`; it writes `DATA/IPCC_R10_S23_DataFolder/`, which is copied into `Data/`. Fix input data in `DATA/MSET_data_original` and re-collapse instead of editing `Data/` by hand. Sanity check for capital stock: capital ÷ gross output is about 1.5–3.5 for most countries.

## Outputs

| Folder | Content |
|---|---|
| `Results/` | All model results: `results_file_long_{scenario}_*` CSV/parquet (`self.V`), `emissions_{scenario}_{year}.parquet`, `calibration_convergence_summary_{scenario}.csv`, remittance parquet; figure scripts `baseline_figures.Rmd`, `scenario_figures.Rmd` and their PDFs |
| `Results/archive_{calibration\|baseline\|scenario}_{scenario}_{YYYYMMDD_HHMM}/` | Previous results of one scenario, moved there at the start of the next run of that scenario; `calibration` = calibrating run, `baseline` = forward run of `empty`, `scenario` = any other; timestamp = when they were produced |
| `Residuals/` | `residuals_{year}.pkl`, `calibration_errors_{year}.csv`; archived to `Residuals/archive_<timestamp>/` at the start of a calibrating run |
| `Temp/` | `iter{year}-{iter}.csv` (cleared at the start of every run), `all_vars.pkl`, `carbon_tax_rate.pkl` |
| `Log/` | Run logs, created only when something is written |

- Archiving moves only the files of the scenario being run (`ModelRun._is_result_of_scenario` matches the exact file names, so `cprice_disagg` never picks up `cprice_disagg_rr` files), so the baseline stays in `Results/` for scenario comparisons.
- Figures: set `results_dir` (and in `scenario_figures.Rmd` also `baseline_dir`, `scenario`) in the YAML `params` and press Knit; the scripts read from that folder (relative to `Results/`) and write `baseline_figures_empty.pdf` / `scenario_figures_<scenario>.pdf` into it. Fuel sectors are identified by name from sheet `P`. Table headers in `scenario_figures.Rmd` are built from the data (`pivot_header()`), so any number of scenarios and any scenario names work.
- There is no `GLORIA_results/` folder any more. The `FullResults_{scenario}.xlsx` export is commented out in `ModelRun.run()`.

## Debugging

- `Temp/iter{year}-{iter}.csv`: one row per `REG_imp` × `PROD_COMM`; `output` is `dq_total` and the `dq_*` columns are its components; `current` is the price change `dp_all`; `v_all` minus the listed `v_*` columns is the sum of the profit-rate, carbon-tax, CBAM, exogenous-price and scarcity-rent effects.
- `Results/calibration_convergence_summary_{scenario}.csv`: per-year calibration result; `error_revert` means the year did not converge and kept the previous residuals.
- Divergence signature: a within-year loop that explodes (infinite `dq_hh_inc`, NaN output), after which every later year is frozen with zero changes and calibration "converges" with zero error. Trace the first year in which one region or sector departs, and check input data before code (the 2026-11 LAC blow-up came from Brazil's capital stock).

## Known issues

- Calibration does not converge in 2020–2021 (worst country error 0.028 / 0.043 against 0.02).
- `set_ely_investment` / `set_power_io_changes` (`scenario.py`) read recipe files from `GLORIA_template/…`, which is not in this repo; `set_power_io_changes` still expands `ALL` to sectors 1–56.
- Remittance input is read from `GLORIA_template/modelinputdata/parameters_global.xlsx` (missing).
- Scarcity rent multiplies by `0.84`; its comment says 0.84 % per year.
- FTT code paths hard-code GLORIA sector 93 (`ftt_power.py`, `model_class.py`).
- Source capital stock still high for VEN and TJK.

## FTT:Power

`MINDSET_FTT_Power/` contains the standalone FTT:Power electricity model, enabled with `ftt_run = True` and imported only then. Converters in `MINDSET_FTT_Power/Utilities/` map FTT technologies to MINDSET investment and fuel categories. It assumes GLORIA-120 sector numbering.

## Change records

`CHANGELOG.md` (user-facing summary) and `CHANGELOG_detailed.md` (technical notes) record changes; add an entry for significant changes.
