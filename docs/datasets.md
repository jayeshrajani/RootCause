# Reference datasets

Crop reference images for retrieval (Shivansh's subsystem). Dataset labels record what each
source annotated. They are **not** ground truth for urgency, treatment or field diagnosis.

## Sources

| Crop | Source | Version | Licence | Images | What we downloaded |
| --- | --- | --- | --- | --- | --- |
| Rice | [Rice Leaf Disease Image Samples](https://data.mendeley.com/datasets/fwcj7stb8r/2) (Mendeley Data) | v2, doi:10.17632/fwcj7stb8r.2 | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | Field | Whole archive (171 MB, SHA-256 pinned): 5,932 files |
| Tomato, potato | [PlantDoc](https://github.com/pratikkayal/PlantDoc-Dataset) (cropped classification set) | git `5467f60` | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | Field (web-scraped) | Tomato and potato folders only: 968 files |
| Tomato, potato | [PlantVillage](https://github.com/spMohanty/PlantVillage-Dataset) (colour) | git `7f7ecc7` | [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/) | Lab (plain background) | 40 images per tomato/potato class (518 files) plus the leaf map |

### Rice: Mendeley replaces Paddy Doctor

The assignment named Paddy Doctor for rice. Its IEEE DataPort files require a paid subscription,
and the free Kaggle subset forbids redistributing images outside that competition. The team
agreed to use the Mendeley dataset above as the **initial rice reference corpus** instead.
Paddy Doctor can be added later if licensed access becomes available.

### Attribution (required by the licences)

- Sethy, P. K. (2024). *Rice Leaf Disease Image Samples*. Mendeley Data, V2,
  doi:10.17632/fwcj7stb8r.2. See also Sethy et al. (2020), *Computers and Electronics in
  Agriculture* 175:105527, doi:10.1016/j.compag.2020.105527.
- Singh, Jain, Jain, Kayal, Kumawat and Batra (2020). *PlantDoc: A Dataset for Visual Plant
  Disease Detection*. CoDS-COMAD 2020, doi:10.1145/3371158.3371196.
- Mohanty, Hughes and Salathé (2016). *Using deep learning for image-based plant disease
  detection*. Frontiers in Plant Science 7:1419, doi:10.3389/fpls.2016.01419.

Every manifest row also carries its source, version, licence, attribution and source URL.
PlantVillage is share-alike: if we redistribute modified PlantVillage images, they must keep
CC BY-SA 3.0. PlantDoc images were scraped from the web by its authors; the original
photographers' rights were not verified by the dataset.

## Prepared pilot set

Produced by `python scripts/prepare_datasets.py --data-dir <DATA_DIR>` (seed 42). Counts are
images (field/lab). Evaluation images are held out and never used as references.

| Crop | Condition | Reference | Evaluation |
| --- | --- | --- | --- |
| Rice | bacterial_blight | 59 (59/0) | 15 (15/0) |
| Rice | blast | 59 (59/0) | 16 (16/0) |
| Rice | brown_spot | 62 (62/0) | 19 (19/0) |
| Rice | tungro | 54 (54/0) | 22 (22/0) |
| **Rice** | **total** | **234** | **72** |
| Tomato | bacterial_spot | 30 (30/0) | 25 (18/7) |
| Tomato | early_blight | 30 (30/0) | 25 (17/8) |
| Tomato | healthy | 30 (30/0) | 21 (13/8) |
| Tomato | late_blight | 30 (30/0) | 25 (18/7) |
| Tomato | leaf_mold | 30 (30/0) | 25 (17/8) |
| Tomato | mosaic_virus | 30 (30/0) | 19 (11/8) |
| Tomato | septoria_leaf_spot | 30 (30/0) | 25 (20/5) |
| Tomato | spider_mites | 30 (2/28) | 8 (0/8) |
| Tomato | target_spot | 30 (0/30) | 8 (0/8) |
| Tomato | yellow_leaf_curl_virus | 30 (30/0) | 22 (14/8) |
| **Tomato** | **total** | **300** | **203** |
| Potato | early_blight | 100 (90/10) | 25 (18/7) |
| Potato | healthy | 29 (0/29) | 8 (0/8) |
| Potato | late_blight | 100 (75/25) | 25 (18/7) |
| **Potato** | **total** | **229** | **58** |

Full per-crop statistics: [apps/api/data/manifests/summary.json](../apps/api/data/manifests/summary.json).

## Known gaps and limitations

- **Rice:** only bacterial blight, blast, brown spot and tungro. No healthy rice and no other
  diseases or pests; none are fabricated.
- **Rice is heavily augmented:** 5,571 of 5,932 files are rotated/flipped/re-encoded copies, leaving
  about 360 distinct photos. That is why rice has 234 references instead of the ~300 target.
- **Lab-only classes:** tomato target spot and potato healthy have no field images. Tomato
  spider mites has only 2 field images. Lab images have plain backgrounds, which can bias
  similarity towards background rather than symptoms.
- **Label noise:** 7 tomato and 7 potato PlantDoc image groups appeared under different disease
  labels and were excluded. One PlantDoc potato image in MPO (multi-picture) format was rejected.
- **Class balance:** tomato references are balanced (30 per condition); potato and rice are
  limited by available distinct images.

## How the pipeline works

- **Data location:** raw downloads, cache and prepared images live in `ROOTCAUSE_DATA_DIR`
  (outside Git and synced folders). Only the manifests in `apps/api/data/manifests/` are
  committed.
- **Downloads:** the rice archive is resumable and verified by size and SHA-256. PlantDoc and
  PlantVillage are fetched from GitHub file by file at pinned commits, so only the needed images
  are downloaded. Re-running reuses everything already present; `--offline` makes no network
  calls.
- **Validation:** every image is fully decoded with Pillow; only JPEG, PNG and WebP of at least
  32 px are kept.
- **Duplicates:** images are grouped as copies when they have identical bytes, show the same
  physical leaf (PlantVillage leaf map), or have 64-bit dHashes within 1 bit under any
  rotation/flip. One image per group is kept. Groups with conflicting labels are dropped.
- **Splits:** per condition, up to 20% (max 25) of groups go to evaluation, sampled across field
  and lab images. References are filled with field images first. Any image within 6 dHash bits
  (any rotation/flip) of an evaluation image or an already chosen reference is skipped, so no
  near-duplicates leak between splits.
- **Manifest columns:** reference ID, crop, canonical condition, original source label, dataset
  source and version, source image ID, image URI (`local://`, later `gs://`), SHA-256, dHash,
  media type, size, group ID, split, image style, licence, attribution and source URL.
