"""Integrity checks for The Complete Pokédex Dataset. Run before every Kaggle upload:

    python scripts/validate.py

Exits non-zero and lists every failed check if anything is off.
"""

import json
import re
import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
IMAGES = ROOT / 'images'
AUDIO = ROOT / 'audio'

STATS = ['hp', 'attack', 'defense', 'sp_attack', 'sp_defense', 'speed']
TYPES = ['normal', 'fire', 'water', 'electric', 'grass', 'ice', 'fighting', 'poison', 'ground',
         'flying', 'psychic', 'bug', 'rock', 'ghost', 'dragon', 'dark', 'steel', 'fairy']
AGAINST = [f'against_{t}' for t in TYPES]
MULTIPLIERS = {0, 0.25, 0.5, 1, 2, 4}
SAFE_NAME = re.compile(r'^[A-Za-z0-9._-]+$')  # Kaggle rejects apostrophes and is unreliable with non-ASCII

# Current (Gen VI+) type chart, attacking type -> {defending type: multiplier}; 1 is omitted.
CHART = {
    'normal': {'rock': .5, 'ghost': 0, 'steel': .5},
    'fire': {'fire': .5, 'water': .5, 'grass': 2, 'ice': 2, 'bug': 2, 'rock': .5, 'dragon': .5, 'steel': 2},
    'water': {'fire': 2, 'water': .5, 'grass': .5, 'ground': 2, 'rock': 2, 'dragon': .5},
    'electric': {'water': 2, 'electric': .5, 'grass': .5, 'ground': 0, 'flying': 2, 'dragon': .5},
    'grass': {'fire': .5, 'water': 2, 'grass': .5, 'poison': .5, 'ground': 2, 'flying': .5, 'bug': .5,
              'rock': 2, 'dragon': .5, 'steel': .5},
    'ice': {'fire': .5, 'water': .5, 'grass': 2, 'ice': .5, 'ground': 2, 'flying': 2, 'dragon': 2, 'steel': .5},
    'fighting': {'normal': 2, 'ice': 2, 'poison': .5, 'flying': .5, 'psychic': .5, 'bug': .5, 'rock': 2,
                 'ghost': 0, 'dark': 2, 'steel': 2, 'fairy': .5},
    'poison': {'grass': 2, 'poison': .5, 'ground': .5, 'rock': .5, 'ghost': .5, 'steel': 0, 'fairy': 2},
    'ground': {'fire': 2, 'electric': 2, 'grass': .5, 'poison': 2, 'flying': 0, 'bug': .5, 'rock': 2, 'steel': 2},
    'flying': {'electric': .5, 'grass': 2, 'fighting': 2, 'bug': 2, 'rock': .5, 'steel': .5},
    'psychic': {'fighting': 2, 'poison': 2, 'psychic': .5, 'dark': 0, 'steel': .5},
    'bug': {'fire': .5, 'grass': 2, 'fighting': .5, 'poison': .5, 'flying': .5, 'psychic': 2, 'ghost': .5,
            'dark': 2, 'steel': .5, 'fairy': .5},
    'rock': {'fire': 2, 'ice': 2, 'fighting': .5, 'ground': .5, 'flying': 2, 'bug': 2, 'steel': .5},
    'ghost': {'normal': 0, 'psychic': 2, 'ghost': 2, 'dark': .5},
    'dragon': {'dragon': 2, 'steel': .5, 'fairy': 0},
    'dark': {'fighting': .5, 'psychic': 2, 'ghost': 2, 'dark': .5, 'fairy': .5},
    'steel': {'fire': .5, 'water': .5, 'electric': .5, 'ice': 2, 'rock': 2, 'steel': .5, 'fairy': 2},
    'fairy': {'fire': .5, 'fighting': 2, 'poison': .5, 'dragon': 2, 'dark': 2, 'steel': .5},
}

failures = []


def check(ok, message):
    if not ok:
        failures.append(message)


def expected_against(t1, t2):
    return [CHART[a].get(t1, 1) * (CHART[a].get(t2, 1) if isinstance(t2, str) else 1) for a in TYPES]


def check_against(df, name):
    bad = [row.Index for row in df.itertuples()
           if [getattr(row, c) for c in AGAINST] != expected_against(row.primary_type, row.secondary_type)]
    check(not bad, f'{name}: against_* disagrees with the type chart for {len(bad)} rows, e.g. {bad[:5]}')


def main():
    m = pd.read_csv(DATA / 'pokemon_utf8.csv')
    legacy = pd.read_csv(DATA / 'pokemon.csv', encoding='utf-16', sep='\t')
    forms = pd.read_csv(DATA / 'pokemon_forms.csv')
    evo = pd.read_csv(DATA / 'evolutions.csv')
    moves = pd.read_csv(DATA / 'moves.csv')
    pm = pd.read_csv(DATA / 'pokemon_moves.csv')
    images = pd.read_csv(DATA / 'images.csv')
    stats = pd.read_csv(DATA / 'pokemon_stats.csv')

    # ---- species master
    check(len(m) == 1025 and m.national_number.tolist() == list(range(1, 1026)),
          'pokemon: national_number must be exactly 1..1025 in order')
    check(m.english_name.notna().all() and m.english_name.is_unique, 'pokemon: english_name missing or duplicated')
    check(legacy.equals(m), 'pokemon.csv (UTF-16) and pokemon_utf8.csv differ')
    check(m.primary_type.isin(TYPES).all(), 'pokemon: invalid primary_type')
    check(m.secondary_type.dropna().isin(TYPES).all(), 'pokemon: invalid secondary_type')
    check((m.primary_type != m.secondary_type).all(), 'pokemon: primary_type equals secondary_type')
    for c in STATS:
        check(m[c].between(1, 255).all(), f'pokemon: {c} outside 1..255')
    check((m[STATS].sum(axis=1) == m.base_total).all(), 'pokemon: base_total != sum of base stats')
    ev = m[[f'ev_yield_{s}' for s in STATS]]
    check(ev.isin([0, 1, 2, 3]).all().all() and ev.sum(axis=1).between(1, 3).all(), 'pokemon: EV yields out of range')
    check(pd.api.types.is_integer_dtype(m.capture_rate) and m.capture_rate.between(1, 255).all(),
          'pokemon: capture_rate must be an integer 1..255')
    check((m.base_egg_steps % 256 == 0).all(), 'pokemon: base_egg_steps not a multiple of 256')
    gendered = m.percent_male.notna()
    check((m.percent_male.isna() == m.percent_female.isna()).all(), 'pokemon: gender columns inconsistent')
    check(((m.percent_male[gendered] + m.percent_female[gendered]) == 100).all(), 'pokemon: gender ratio != 100')
    check(((m.percent_female[gendered] % 12.5) == 0).all(), 'pokemon: gender ratio not a multiple of 12.5')
    check((m[['is_sublegendary', 'is_legendary', 'is_mythical']].sum(axis=1) <= 1).all(),
          'pokemon: a species has more than one legendary/mythical flag')
    check(m[AGAINST].isin(MULTIPLIERS).all().all(), 'pokemon: against_* holds a non-type-chart value')
    check_against(m, 'pokemon')
    check(m.egg_group_1.notna().all() and m.growth_rate.notna().all() and m.color.notna().all()
          and m['shape'].notna().all() and m.base_experience.notna().all(), 'pokemon: species fields missing')
    for i in (1, 3, 5):
        cells = m[f'evochain_{i}'].dropna()
        check(not cells.str.fullmatch(r'Level ?').any(), f'pokemon: evochain_{i} has a bare "Level" method')
        check((cells == cells.str.strip()).all() and not cells.str.contains('  ').any(),
              f'pokemon: evochain_{i} has stray whitespace')
    check(len(stats) == 6 * len(m) and stats.merge(m, on='national_number').shape[0] == len(stats),
          'pokemon_stats: must hold six stats for every species')
    long = stats.pivot(index='national_number', columns='stat_name', values='stat_value')[STATS]
    check((long.values == m.set_index('national_number')[STATS].values).all(), 'pokemon_stats disagrees with pokemon')

    # ---- forms
    check(forms.form_id.is_unique, 'pokemon_forms: form_id not unique')
    check(forms.national_number.isin(m.national_number).all(), 'pokemon_forms: unknown national_number')
    default = forms[(forms.is_default_variety == 1) & (forms.is_default_form == 1)]
    check(len(default) == 1025 and default.national_number.is_unique,
          'pokemon_forms: need exactly one default form per species')
    d = default.set_index('national_number').loc[m.national_number]
    for c in STATS + ['primary_type', 'secondary_type']:
        check(d[c].fillna('').astype(str).tolist() == m[c].fillna('').astype(str).tolist(),
              f'pokemon_forms: default form {c} disagrees with pokemon')
    check(forms.groupby('pokemon_id').is_default_form.sum().eq(1).all(),
          'pokemon_forms: every variety needs exactly one default form')
    check(forms.display_name.notna().all(), 'pokemon_forms: display_name missing')
    check((forms[STATS].sum(axis=1) == forms.base_total).all(), 'pokemon_forms: base_total != sum of stats')
    check(forms.primary_type.isin(TYPES).all() and forms.secondary_type.dropna().isin(TYPES).all(),
          'pokemon_forms: invalid type')
    check_against(forms, 'pokemon_forms')
    files = forms.image_file.dropna()
    check(all((IMAGES / f).exists() for f in files), 'pokemon_forms: image_file points at a missing image')

    # ---- evolutions
    check(evo.evolution_id.is_unique, 'evolutions: evolution_id not unique')
    check(evo.from_national_number.isin(m.national_number).all(), 'evolutions: unknown from_national_number')
    check(evo.to_national_number.isin(m.national_number).all(), 'evolutions: unknown to_national_number')
    check(evo.condition.notna().all() and not evo.condition.str.contains('None|nan').any(),
          'evolutions: condition text missing or contains an unresolved value')
    check(evo.min_level.dropna().between(1, 100).all(), 'evolutions: min_level outside 1..100')

    # ---- moves and learnsets
    check(moves.move_id.is_unique and moves.name.notna().all(), 'moves: move_id not unique or name missing')
    check(moves.type.isin(TYPES).all(), 'moves: invalid type')
    check(moves.damage_class.isin(['physical', 'special', 'status']).all(), 'moves: invalid damage_class')
    check(moves.power.dropna().between(1, 250).all(), 'moves: power outside 1..250')
    check(moves.accuracy.dropna().between(1, 100).all(), 'moves: accuracy outside 1..100')
    check(moves.pp.between(1, 40).all(), 'moves: pp outside 1..40')
    check(pm.move_id.isin(moves.move_id).all(), 'pokemon_moves: unknown move_id')
    check(pm.pokemon_id.isin(forms.pokemon_id).all(), 'pokemon_moves: unknown pokemon_id')
    check(pm.national_number.isin(m.national_number).all(), 'pokemon_moves: unknown national_number')
    check(not pm.duplicated().any(), 'pokemon_moves: duplicate rows')
    check(pm.level.isna().eq(pm.method != 'Level up').all(), 'pokemon_moves: level set for a non level-up method')

    # ---- species fields corrected in v2.1
    abil = m[['abilities_0', 'abilities_1', 'abilities_hidden']]
    check(m.abilities_0.notna().all() and m.abilities_2.isna().all(), 'pokemon: abilities_0 missing or abilities_2 set')
    check(not abil.stack().dropna().str.contains(r'\(|- |^\s|\s$').any(),
          'pokemon: an ability cell holds a form note, a joined pair or stray whitespace')
    d_ab = default.set_index('national_number').loc[m.national_number, ['abilities_0', 'abilities_1', 'abilities_hidden']]
    check((d_ab.fillna('').values == abil.fillna('').values).all(), 'pokemon: abilities disagree with pokemon_forms')
    check(m.classification.str.endswith('Pokémon').all(), 'pokemon: classification must end with "Pokémon"')
    check(m.japanese_name_kana.notna().all() and m.japanese_name_official.notna().all(),
          'pokemon: Japanese name columns incomplete')

    # ---- reference tables (v2.2)
    ab = pd.read_csv(DATA / 'abilities.csv')
    pab = pd.read_csv(DATA / 'pokemon_abilities.csv')
    check(ab.ability_id.is_unique and ab.name.notna().all(), 'abilities: ability_id not unique or name missing')
    check(set(abil.stack().dropna()) <= set(ab.name), 'pokemon: an ability is missing from abilities.csv')
    check(set(forms[['abilities_0', 'abilities_1', 'abilities_hidden']].stack().dropna()) <= set(ab.name),
          'pokemon_forms: an ability is missing from abilities.csv')
    check(pab.ability_id.isin(ab.ability_id).all() and pab.pokemon_id.isin(forms.pokemon_id).all(),
          'pokemon_abilities: unknown ability_id or pokemon_id')
    check(pd.read_csv(DATA / 'items.csv').item_id.is_unique, 'items: item_id not unique')
    na = pd.read_csv(DATA / 'natures.csv')
    check(len(na) == 25 and na.is_neutral.sum() == 5, 'natures: expected 25 natures, 5 of them neutral')
    tc = pd.read_csv(DATA / 'type_chart.csv')
    check(len(tc) == 324 and all(CHART[r.attacking_type].get(r.defending_type, 1) == r.multiplier
                                 for r in tc.itertuples()), 'type_chart: disagrees with the Gen VI+ type chart')
    entries = pd.read_csv(DATA / 'pokedex_entries.csv')
    check(entries.national_number.isin(m.national_number).all() and entries.text.str.len().gt(0).all(),
          'pokedex_entries: unknown species or empty text')
    check(set(entries[entries.language == 'en'].national_number) == set(m.national_number),
          'pokedex_entries: a species has no English entry')
    names = pd.read_csv(DATA / 'pokemon_names.csv')
    en_names = names[names.language == 'en'].set_index('national_number').name
    check((en_names.loc[m.national_number].values == m.english_name.values).all(),
          'pokemon_names: English names disagree with pokemon')
    enc = pd.read_csv(DATA / 'encounters.csv')
    check(enc.encounter_id.is_unique and enc.national_number.isin(m.national_number).all(),
          'encounters: encounter_id not unique or unknown species')
    check((enc.min_level <= enc.max_level).all() and enc.max_level.between(1, 100).all(),
          'encounters: level range invalid')
    dexn = pd.read_csv(DATA / 'pokedex_numbers.csv')
    nat = dexn[dexn.pokedex_identifier == 'national']
    check(len(nat) == 1025 and (nat.national_number == nat.number).all(), 'pokedex_numbers: National Dex numbers off')
    mach = pd.read_csv(DATA / 'machines.csv')
    check(mach.move_id.isin(moves.move_id).all() and mach.machine.str.match(r'^(TM|HM|TR)\d+$').all(),
          'machines: unknown move or malformed machine name')
    vg = pd.read_csv(DATA / 'version_groups.csv')
    check(vg.version_group.is_unique and set(pm.version_group) <= set(vg.version_group),
          'version_groups: duplicate or missing version group')

    # ---- cries (v3, committed)
    cries = pd.read_csv(DATA / 'cries.csv')
    audio_disk = sorted(f'{p.parent.name}/{p.name}' for p in AUDIO.glob('*/*') if p.is_file())
    check(sorted(cries.audio_file) == audio_disk, 'cries: manifest and audio/ folder differ')
    check((cries.file_name.str.rsplit('.', n=1).str[1] == cries.format).all(), 'cries: extension != format')
    check(cries.duration_s.gt(0).all() and cries.national_number.isin(m.national_number).all()
          and cries.form_id.isin(forms.form_id).all(), 'cries: bad duration, species or form')
    check(set(cries[cries.cry_set == 'cries'].national_number) == set(m.national_number),
          'cries: a species has no current cry')
    check(cries.split.eq(cries.national_number.map(images.groupby('national_number').split.first())).all(),
          'cries: split disagrees with images')

    # ---- competitive (v3)
    tiers = pd.read_csv(DATA / 'competitive_tiers.csv')
    check(tiers.showdown_id.is_unique and tiers.national_number.isin(m.national_number).all()
          and tiers.form_id.dropna().isin(forms.form_id).all(), 'competitive_tiers: bad key')
    check(tiers.form_id.notna().mean() > 0.99, 'competitive_tiers: under 99% of Showdown entries mapped to a form')
    if (DATA / 'smogon_usage.csv').exists():
        su = pd.read_csv(DATA / 'smogon_usage.csv')
        check(su.usage_pct.between(0, 100).all() and su['rank'].ge(1).all(), 'smogon_usage: bad usage or rank')
        check(not su.duplicated(['period', 'format', 'pokemon']).any(), 'smogon_usage: duplicate rows')
        check(su.national_number.notna().mean() > 0.99, 'smogon_usage: under 99% of rows mapped to a species')
        check(su.national_number.dropna().isin(m.national_number).all(), 'smogon_usage: unknown national_number')

    # ---- images
    check(images.image_file.is_unique, 'images: duplicate image_file')
    built = []
    for s in images.image_set.unique():
        folder = IMAGES / s
        if not folder.exists():
            continue  # v3 sets are built by build_media.py for Kaggle and not kept in git
        built.append(s)
        on_disk = sorted(f'{s}/{p.name}' for p in folder.iterdir() if p.is_file())
        check(sorted(images[images.image_set == s].image_file) == on_disk, f'images: manifest and images/{s} differ')
    check({'small_images', 'large_images', 'alt_images'} <= set(built), 'images: a git-tracked image set is missing')
    bad = [n for n in pd.concat([images.file_name, cries.file_name]) if not SAFE_NAME.match(n)]
    bad += [p.name for p in IMAGES.rglob('*') if p.is_file() and not SAFE_NAME.match(p.name)]
    check(not bad, f'images/cries: filenames Kaggle may reject: {bad[:5]}')
    for s in ('small_images', 'large_images'):
        nums = sorted(images[images.image_set == s].national_number)
        check(nums == list(range(1, 1026)), f'images: {s} must cover #1..#1025 exactly once')
    check(images.national_number.isin(m.national_number).all(), 'images: unknown national_number')
    check(images.form_id.dropna().isin(forms.form_id).all(), 'images: unknown form_id')
    check(images.split.isin(['train', 'val', 'test']).all(), 'images: invalid split')
    check(images.groupby('national_number').split.nunique().eq(1).all(),
          'images: a species is spread over more than one split')

    # ---- SQLite mirrors the CSVs (built by build_sqlite.py for Kaggle; not kept in git)
    if (DATA / 'pokedex.sqlite').exists():
        con = sqlite3.connect(DATA / 'pokedex.sqlite')
        for p in sorted(DATA.glob('*.csv')):
            if p.name == 'pokemon.csv':
                continue
            table = 'pokemon' if p.name == 'pokemon_utf8.csv' else p.stem
            n = con.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
            rows = sum(1 for _ in open(p, encoding='utf-8')) - 1 if table not in ('pokedex_entries', 'moves',
                                                                                  'abilities', 'items') \
                else len(pd.read_csv(p))
            check(n == rows, f'pokedex.sqlite: {table} has {n} rows, CSV has {rows}')
        fk = con.execute('PRAGMA foreign_key_check').fetchall()
        check(not fk, f'pokedex.sqlite: {len(fk)} foreign key violations')
        con.close()

    # ---- Kaggle metadata documents every column of every CSV, in order
    meta = json.loads((ROOT / 'dataset-metadata.json').read_text())
    check(3 <= len(meta['title']) <= 50 and 20 <= len(meta['subtitle']) <= 80,
          'dataset-metadata.json: title/subtitle length outside Kaggle limits')
    documented = {r['path']: [f['name'] for f in r.get('schema', {}).get('fields', [])] for r in meta['resources']}
    for p in sorted(DATA.glob('*.csv')):
        cols = list(pd.read_csv(p, nrows=0, encoding='utf-16' if p.name == 'pokemon.csv' else 'utf-8',
                                sep='\t' if p.name == 'pokemon.csv' else ',').columns)
        key = f'data/{p.name}'
        check(key in documented, f'dataset-metadata.json: {key} not listed in resources')
        if documented.get(key):
            check(documented[key] == cols, f'dataset-metadata.json: {key} fields do not match its columns')
    check('data/pokedex.sqlite' in documented, 'dataset-metadata.json: data/pokedex.sqlite not listed in resources')

    if failures:
        print(f'FAILED {len(failures)} check(s):')
        for f in failures:
            print('  -', f)
        sys.exit(1)
    print(f'OK: {len(m)} species, {len(forms)} forms, {len(evo)} evolution methods, {len(moves)} moves, '
          f'{len(pm):,} learnset rows, {len(images)} images ({", ".join(sorted(built))} on disk), '
          f'{len(cries)} cries, {len(entries):,} Pokédex entries, {len(enc):,} encounters')


if __name__ == '__main__':
    main()
