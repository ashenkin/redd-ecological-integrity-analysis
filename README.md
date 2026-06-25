# REDD+ Ecological Integrity Analysis

Extending **Ong et al. 2026** (*Nature Climate Change*, DOI: [10.1038/s41558-026-02657-2](https://doi.org/10.1038/s41558-026-02657-2)).

**Research question**: Do newer avoided-deforestation projects — or those using newer methodologies — achieve better ecological outcomes?

**Approach**: Dot plot with project start year on the x-axis and quality of ecological outcome on the y-axis, across all 133 well-matched projects in the paper.

---

## Data sources

| File | Source | Notes |
|------|--------|-------|
| `data/zenodo/REDD.zip` | [Zenodo 10.5281/zenodo.19726735](https://doi.org/10.5281/zenodo.19726735) | 196 project polygons (shapefile) |
| `data/zenodo/ext4.zip` | Zenodo | Extended Data Table 4 — sensitivity analysis per project × metric |
| `data/zenodo/*_orig.Rmd` | Zenodo | Original R code (matching + linear models) |
| `data/registry_metadata/project_metadata.csv` | Generated | Project start dates from Verra API + registry scrapes |
| `data/registry_metadata/sensitivity_data.csv` | Generated | Parsed sensitivity stats (proxy for effect strength) |
| `data/source_data/effect_sizes.csv` | **Not included** | Real standardized effect sizes — see below |

### Getting the real effect sizes

The paper provides "Source Data" for Fig. 1 at the Nature article page.
Download it and save as `data/source_data/effect_sizes.csv` with columns:

```
uid, metric, estimate, std_error, p_value, comparison
```

Then re-run with `--use-effect-sizes`.

Alternatively, run the original R code (requires raw raster inputs — see `data/zenodo/README.txt`).

---

## Running the analysis

```bash
# Install dependencies
pip install matplotlib numpy openpyxl

# Fetch project metadata (start dates from Verra API, ~5 min for 112 VCS projects)
python analysis/fetch_project_metadata.py

# Parse sensitivity data
python analysis/load_sensitivity_data.py

# Plot (uses rv_q robustness proxy for outcome quality)
python analysis/plot_outcomes_over_time.py

# Or run everything:
bash analysis/run_all.sh
```

Output: `results/outcomes_over_time_rvq_proxy.png`

---

## Ecological integrity indicators (5 metrics)

| Metric | What it measures |
|--------|-----------------|
| `biodIntact2015` | Biodiversity Intactness Index — species abundance relative to intact baseline |
| `forestInt` | Forest Landscape Integrity Index — anthropogenic pressure & degradation |
| `forestFrag` | Forest fragmentation — edge density, patch size |
| `canopy_height` | Mean canopy height (m) — forest structure & age |
| `carbon_flux` | GHG net flux 2001–2020 — ecosystem carbon permanence |

Positive standardized effect size = project area better than matched controls.

---

## Notes on methodology

- **Y-axis (current)**: `mean rv_q` = mean robustness value across 5 metrics for the primary comparison (unprotected REDD vs unprotected controls). Higher rv_q = effect harder to attribute to unobserved confounders = stronger evidence of real impact. This is a *proxy* — sign and magnitude differ from raw effect sizes.
- **Y-axis (preferred)**: Mean standardized treatment effect (Fig. 1 in paper). Range −1 to +1; positive = ecological benefit. Available from paper's source data.
- **X-axis**: Project start year from credit period start date (Verra) or registration date.
