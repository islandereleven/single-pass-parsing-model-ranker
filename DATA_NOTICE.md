# Data Notice

This repository can mix public datasets, generated data, and hand-authored fixtures. Documents record a source name in `documents/documents.json`; this file holds the corresponding provenance and license disclosure.

Corpus rows stay focused on evaluation cases. A corpus references documents by `document_id`; each document records its source name and, when useful, its record name within that source.

## Current Sources

### ACME Invoice Fixture

- Source name: `ACME Invoice Fixture`
- Type: hand-authored fixture
- License: `project-internal`
- Role: smoke-test document and ground truth
- Local files: `documents/acme_invoice.txt`, ACME rows in `corpora/*.json`
- Attribution: hand-authored ACME invoice fixture created for `single-pass-parsing-model-ranker`.

### High-Quality Invoice Images for OCR

- Source name: `High-Quality Invoice Images for OCR`
- Type: public dataset
- Publisher: Osama Hosam Abdellatif
- Source: https://www.kaggle.com/datasets/osamahosamabdellatif/high-quality-invoice-images-for-ocr
- License: `ODbL-1.0+DbCL-1.0`
- License URLs:
  - https://opendatacommons.org/licenses/odbl/1-0/
  - https://opendatacommons.org/licenses/dbcl/1-0/
- Local subset: `documents/invoice-batch-1-sample-20-v0.1/*.jpg`, invoice extraction rows in `corpora/0.2.0.json` and `corpora/0.3.0.json`
- Attribution: High-Quality Invoice Images for OCR by Osama Hosam Abdellatif, published on Kaggle.

Kaggle lists the license as `Database: Open Database, Contents: Database Contents`. Treat public adapted corpus releases as ODbL-covered database releases: keep attribution, disclose the license, preserve source notices, and offer the public adapted database under the same database license.

## Adding A Source

When adding a new public, generated, or hand-authored source:

1. Add `source_name` and, when useful, `source_record_id` to each new document row in `documents/documents.json`.
2. Add a section to this file with the same source name and its provenance, license, and attribution.
3. If the data is generated, record the generator, prompt recipe, seed policy, and ownership/license here.
4. If generated data was derived from a public source, disclose both the generated source and the upstream source.
