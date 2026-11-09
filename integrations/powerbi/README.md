# Power BI handoff

1. Run the [data pipeline](../../backend/pipeline/README.md) and select one snapshot from `gold/current.json`.
2. Import `fact_monthly_pnl.csv`, `dim_branch.csv`, and `dim_month.csv` from that snapshot.
3. Set branch IDs to text, VND amounts to whole numbers, and `month_start` to date.
4. Create single-direction, one-to-many relationships from `dim_branch[id]` and `dim_month[month_start]` to the corresponding fact keys. The month dimension has one row per month.
5. Create the measures in `measures.dax`. Calculate ratios from filtered totals rather than averaging row percentages.

The dataset is monthly by branch and supports revenue, cost, margin, and rent analysis. The repository provides source tables and DAX measures. Report publishing and branch-level row security require configuration in your Power BI environment. See the [Fabric template](../fabric/README.md) for versioned Delta tables.
