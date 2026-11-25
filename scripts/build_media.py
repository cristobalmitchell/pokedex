"""Build the image and audio sets of The Complete Pokédex Dataset and their manifests.

    data/images.csv   every image: small_images, large_images, alt_images (in git) and the
                      v3 sets below, with the form shown, its types and a fixed split
    data/cries.csv    every cry: audio/cries (current) and audio/cries_legacy (Gen I-V originals)

v3 sets copied from the PokeAPI sprites repository (https://github.com/PokeAPI/sprites):
    images/shiny_images/        shiny official artwork
    images/home_images/         Pokémon HOME 3D renders
    images/home_shiny_images/   Pokémon HOME 3D renders, shiny
    images/animated_sprites/    animated battle sprites (GIF, from Pokémon Showdown)
Cries come from https://github.com/PokeAPI/cries.

The v3 image sets add about 1 GB, so they are published on Kaggle but not committed to git
(see .gitignore); the cries (32 MB) are committed. File names are Kaggle-safe:
<4-digit national number>-<PokeAPI identifier>.<ext>, e.g. 0006-charizard-mega-x.png.

Usage (run after build_tables.py):
    git clone --depth 1 --filter=blob:none --sparse https://github.com/PokeAPI/sprites.git
    git -C sprites sparse-checkout set sprites/pokemon/other/official-artwork sprites/pokemon/other/home \\
        sprites/pokemon/other/showdown
    git clone --depth 1 https://github.com/PokeAPI/cries.git
    python scripts/build_media.py pokeapi/data/v2/csv --sprites sprites --cries cries

Without --sprites / --cries the rows already in the manifests for those sets are kept, so the
tables can be rebuilt without downloading the media again.
"""

import argparse
import shutil
import struct
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_tables import (DATA, IMAGES, PokeAPI, build_images, match_alt_images,  # noqa: E402
                          species_split)

ROOT = DATA.parent
AUDIO = ROOT / 'audio'
SPRITE_SETS = {  # image_set -> folder inside the sprites repository
    'shiny_images': 'sprites/pokemon/other/official-artwork/shiny',
    'home_images': 'sprites/pokemon/other/home',
    'home_shiny_images': 'sprites/pokemon/other/home/shiny',
    'animated_sprites': 'sprites/pokemon/other/showdown',
}
CRY_SETS = {'cries': 'cries/pokemon/latest', 'cries_legacy': 'cries/pokemon/legacy'}


def image_size(path):
    with open(path, 'rb') as f:
        head = f.read(26)
    if head[:4] == b'\x89PNG':
        return struct.unpack('>II', head[16:24])
    if head[:3] == b'GIF':
        return struct.unpack('<HH', head[6:10])
    raise ValueError(f'unknown image format: {path}')


def copy_if_changed(src, dst):
    if not dst.exists() or dst.stat().st_size != src.stat().st_size:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)


def variety_names(forms):
    v = forms[forms.is_default_form == 1].set_index('pokemon_id')
    return v, {pid: f'{row.national_number:04d}-{row.identifier}' for pid, row in v.iterrows()}


def sync_folder(src_dir, dst_dir, stems, exts):
    """Copy <pokemon_id>.<ext> files to <stem>.<ext>; remove stale files. Returns {pokemon_id: path}."""
    dst_dir.mkdir(parents=True, exist_ok=True)
    out = {}
    for pid, stem in stems.items():
        for ext in exts:
            src = src_dir / f'{pid}.{ext}'
            if src.exists():
                dst = dst_dir / f'{stem}.{ext}'
                copy_if_changed(src, dst)
                out[pid] = dst
                break
    keep = {p.name for p in out.values()}
    for p in dst_dir.iterdir():
        if p.is_file() and p.name not in keep:
            p.unlink()
    return out


def v3_image_rows(sprites, forms, master, split):
    varieties, stems = variety_names(forms)
    names = master.set_index('national_number').english_name
    rows = []
    for image_set, folder in SPRITE_SETS.items():
        ext = 'gif' if image_set == 'animated_sprites' else 'png'
        files = sync_folder(Path(sprites) / folder, IMAGES / image_set, stems, [ext])
        for pid, path in sorted(files.items(), key=lambda kv: kv[1].name):
            v = varieties.loc[pid]
            w, h = image_size(path)
            rows.append({
                'image_file': f'{image_set}/{path.name}', 'image_set': image_set, 'file_name': path.name,
                'national_number': v.national_number, 'english_name': names[v.national_number],
                'form_label': None, 'form_id': v.form_id, 'pokemon_id': pid, 'display_name': v.display_name,
                'primary_type': v.primary_type, 'secondary_type': v.secondary_type,
                'width': w, 'height': h, 'split': split[v.national_number],
            })
    return pd.DataFrame(rows)


def audio_info(path):
    from mutagen import File  # pip install mutagen
    a = File(path)
    return round(a.info.length, 3), a.info.sample_rate, a.info.channels


def cry_rows(cries, forms, master, split):
    varieties, stems = variety_names(forms)
    names = master.set_index('national_number').english_name
    rows = []
    for cry_set, folder in CRY_SETS.items():
        src_dir, dst_dir = Path(cries) / folder, AUDIO / cry_set
        dst_dir.mkdir(parents=True, exist_ok=True)
        keep = set()
        for pid, stem in stems.items():
            src = src_dir / f'{pid}.ogg'
            if not src.exists():
                continue
            # 116 upstream files named .ogg are really MP3; give them the right extension.
            fmt = 'ogg' if open(src, 'rb').read(4) == b'OggS' else 'mp3'
            dst = dst_dir / f'{stem}.{fmt}'
            copy_if_changed(src, dst)
            keep.add(dst.name)
            v = varieties.loc[pid]
            duration, rate, channels = audio_info(dst)
            rows.append({
                'audio_file': f'{cry_set}/{dst.name}', 'cry_set': cry_set, 'file_name': dst.name, 'format': fmt,
                'national_number': v.national_number, 'english_name': names[v.national_number],
                'pokemon_id': pid, 'form_id': v.form_id, 'display_name': v.display_name,
                'duration_s': duration, 'sample_rate': rate, 'channels': channels,
                'split': split[v.national_number],
            })
        for p in dst_dir.iterdir():
            if p.name not in keep:
                p.unlink()
    return pd.DataFrame(rows).sort_values(['cry_set', 'file_name']).reset_index(drop=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pokeapi_csv')
    ap.add_argument('--sprites', help='PokeAPI/sprites checkout (rebuilds the v3 image sets)')
    ap.add_argument('--cries', help='PokeAPI/cries checkout (rebuilds the cries)')
    args = ap.parse_args()
    api = PokeAPI(args.pokeapi_csv)
    master = pd.read_csv(DATA / 'pokemon_utf8.csv')
    forms = pd.read_csv(DATA / 'pokemon_forms.csv')
    split = species_split(master)

    base = build_images(api, master, forms, match_alt_images(api, forms))
    if args.sprites:
        v3 = v3_image_rows(args.sprites, forms, master, split)
    else:
        old = pd.read_csv(DATA / 'images.csv')
        v3 = old[old.image_set.isin(SPRITE_SETS)]
    images = pd.concat([base, v3], ignore_index=True)
    images[['form_id', 'pokemon_id']] = images[['form_id', 'pokemon_id']].astype('Int64')
    images.to_csv(DATA / 'images.csv', index=False)

    if args.cries:
        cries = cry_rows(args.cries, forms, master, split)
        cries.to_csv(DATA / 'cries.csv', index=False)
    else:
        cries = pd.read_csv(DATA / 'cries.csv')
    print('images:', images.image_set.value_counts().to_dict())
    print('cries:', cries.cry_set.value_counts().to_dict(), cries.format.value_counts().to_dict())


if __name__ == '__main__':
    main()
