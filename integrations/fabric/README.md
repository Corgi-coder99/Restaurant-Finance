# Microsoft Fabric integration template

`pipeline-plan.json` documents a proposed orchestration. It is a design reference. The repository includes a notebook for loading an approved Gold snapshot into Delta tables.

1. Create a Fabric workspace and attach a default lakehouse to the notebook.
2. Run the Python pipeline and read `gold/current.json`.
3. Upload the full approved snapshot to `Files/bep/approved_gold/<snapshot_id>/`.
4. Import `import_approved_gold.ipynb`, set `snapshot_id`, and run it after reconciling the source.
5. Select all three versioned tables from the same snapshot for the Power BI semantic model. The ready marker indicates that all tables were produced. Model refresh remains a separate operation.

Validate the notebook and permissions in your tenant before scheduling it. See the [Power BI guide](../powerbi/README.md).
