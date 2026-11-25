"""Stage a Kaggle upload of The Complete Pokédex Dataset for the web uploader.

Creates kaggle_upload/ (ignored by git):

    kaggle_upload/dataset/        everything to upload, laid out as on Kaggle
        *.csv, pokedex.sqlite     the data files (at the dataset root)
        small_images.zip, ...     one zip per image and audio folder; Kaggle unpacks each into a folder
    kaggle_upload/UPLOAD.md       step-by-step guide for the web uploader
    kaggle_upload/COLUMNS.md      every column description, per file, ready to paste into the Data Card
    kaggle_upload/description.md  the dataset description (paste into "About Dataset")
    kaggle_upload/cover.png       the cover image
    kaggle_upload/metadata/dataset-metadata.json   for the optional Kaggle CLI shortcut

Run after the build (bash scripts/build_all.sh runs it last):
    python scripts/stage_kaggle.py              # each zip holds its folder: small_images.zip -> small_images/...
    python scripts/stage_kaggle.py --flat-zips  # zips hold the files only, if Kaggle nests the folder twice
"""

import argparse
import json
import os
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA, IMAGES, AUDIO = ROOT / 'data', ROOT / 'images', ROOT / 'audio'
OUT = ROOT / 'kaggle_upload'
FOLDERS = [IMAGES / s for s in ('small_images', 'large_images', 'alt_images', 'shiny_images', 'home_images',
                                'home_shiny_images', 'animated_sprites', 'type_icons')] + \
          [AUDIO / s for s in ('cries', 'cries_legacy')]


def place(src, dst):
    """Hard-link when possible (no extra disk), copy otherwise."""
    dst.unlink(missing_ok=True)
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def zip_folder(folder, dst, flat=False):
    # Images and audio are already compressed: store them, which is fast and no larger.
    with zipfile.ZipFile(dst, 'w', zipfile.ZIP_STORED) as z:
        for p in sorted(folder.iterdir()):
            if p.is_file() and not p.name.startswith('.'):
                z.write(p, p.name if flat else f'{folder.name}/{p.name}')


def columns_markdown(meta):
    lines = ['# Column descriptions', '',
             'Paste these into each file\'s column descriptions on the Kaggle Data Card '
             '(Data Explorer → file → Columns → edit).', '']
    for r in meta['resources']:
        lines += [f'## {r["path"]}', '', r['description'], '']
        for f in r.get('schema', {}).get('fields', []):
            lines.append(f'- **{f["name"]}** ({f["type"]}): {f["description"]}')
        lines.append('')
    return '\n'.join(lines)


def upload_guide(meta, files, missing):
    lic = meta['licenses'][0]['name']
    tags = ', '.join(meta['keywords'])
    warn = ''
    if missing:
        warn = ('\n> **Not built yet:** ' + ', '.join(missing) + '. Run `bash scripts/build_all.sh` (or '
                '`SKIP_COMPETITIVE=1 bash scripts/build_all.sh`) first, or these will be missing from the upload.\n')
    return f"""# Uploading {meta['title']} with the Kaggle web uploader
{warn}
Dataset: https://www.kaggle.com/datasets/{meta['id']}

## 1. Upload the files
1. Open the dataset and choose **New Version**.
2. Remove the files of the previous version that are being replaced (every file below replaces one of the
   same name; `pokedex.sqlite` and the zips replace their earlier copies).
3. Drag in **everything in `kaggle_upload/dataset/`** ({len(files)} files). Kaggle unpacks each `.zip` into a
   folder of the same name (`small_images/`, `cries/`, ...), which is where `images.csv` and `cries.csv` expect them.
4. Version notes: summarise the changelog entry at the top of the README's Changelog section.
5. When processing finishes, open the Data Explorer and check one image path. It should read
   `small_images/001.png`. If it reads `small_images/small_images/001.png`, run
   `python scripts/stage_kaggle.py --flat-zips` and upload the zips again.

## 2. Settings and Data Card
| Field | Value |
|---|---|
| Title | {meta['title']} |
| Subtitle | {meta['subtitle']} |
| About Dataset (description) | paste `description.md` |
| License | {lic} (see the README's Licenses section) |
| Tags | {tags} |
| Cover image | `cover.png` (1280 × 640) |
| Expected update frequency | {meta['expectedUpdateFrequency']} |
| Provenance / sources | {meta['userSpecifiedSources']} |

## 3. Column descriptions
Kaggle's usability score counts file and column descriptions. Paste them from `COLUMNS.md`
(Data Explorer → choose a file → Columns → edit each description). Each file's one-line description is there too.

**Optional shortcut:** with the Kaggle CLI installed and an API token configured, the description and every
column description can be applied in one step from `metadata/dataset-metadata.json`:

    kaggle datasets metadata --update -p kaggle_upload/metadata {meta['id']}

(check `kaggle datasets metadata --help` for your CLI version).
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--flat-zips', action='store_true', help='put files at the top level of each zip')
    args = ap.parse_args()
    meta = json.loads((ROOT / 'dataset-metadata.json').read_text())
    if OUT.exists():
        shutil.rmtree(OUT)
    ds = OUT / 'dataset'
    ds.mkdir(parents=True)
    files, missing = [], []
    for p in sorted(DATA.glob('*.csv')) + [DATA / 'pokedex.sqlite']:
        if not p.exists():
            missing.append(f'data/{p.name}')
            continue
        place(p, ds / p.name)
        files.append(p.name)
    for folder in FOLDERS:
        if not folder.exists() or not any(folder.iterdir()):
            missing.append(f'{folder.relative_to(ROOT)}/')
            continue
        zip_folder(folder, ds / f'{folder.name}.zip', args.flat_zips)
        files.append(f'{folder.name}.zip')
    documented = {r['path'] for r in meta['resources']}
    undocumented = [f for f in files if not f.endswith('.zip') and f not in documented]
    if undocumented:
        raise SystemExit(f'files without a dataset-metadata.json resource: {undocumented}')

    (OUT / 'metadata').mkdir()
    shutil.copy2(ROOT / 'dataset-metadata.json', OUT / 'metadata' / 'dataset-metadata.json')
    shutil.copy2(ROOT / 'docs' / 'kaggle_description.md', OUT / 'description.md')
    shutil.copy2(ROOT / 'dataset-cover-image.png', OUT / 'cover.png')
    (OUT / 'COLUMNS.md').write_text(columns_markdown(meta))
    (OUT / 'UPLOAD.md').write_text(upload_guide(meta, files, missing))
    size = sum(p.stat().st_size for p in ds.iterdir()) / 1e6
    print(f'kaggle_upload/dataset: {len(files)} files, {size:,.0f} MB; guide in kaggle_upload/UPLOAD.md')
    if missing:
        print('missing (not built):', ', '.join(missing))


if __name__ == '__main__':
    main()
