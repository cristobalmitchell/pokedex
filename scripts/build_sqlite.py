"""Package every table in data/ into one SQLite database, data/pokedex.sqlite.

Tables keep their CSV names (pokemon_utf8.csv becomes `pokemon`), with primary keys, foreign keys
and indexes. The two large tables are stored with integer keys instead of repeated text:
`pokemon_moves` (via `move_methods` and `version_groups`) and `smogon_usage` (via `smogon_formats`).

Usage (run after the other build scripts):
    python scripts/build_sqlite.py
"""

import sqlite3
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent.parent / 'data'

PRIMARY_KEYS = {
    'pokemon': 'national_number', 'pokemon_forms': 'form_id', 'moves': 'move_id', 'abilities': 'ability_id',
    'items': 'item_id', 'natures': 'nature_id', 'encounters': 'encounter_id', 'evolutions': 'evolution_id',
    'move_methods': 'method_id', 'version_groups': 'version_group_id', 'smogon_formats': 'format_id',
    'images': 'image_file', 'cries': 'audio_file',
}
SPECIES = ('national_number', 'pokemon', 'national_number')
FOREIGN_KEYS = {
    'pokemon_stats': [SPECIES],
    'pokemon_forms': [SPECIES],
    'evolutions': [('from_national_number', 'pokemon', 'national_number'),
                   ('to_national_number', 'pokemon', 'national_number')],
    'pokemon_moves': [SPECIES, ('move_id', 'moves', 'move_id'), ('method_id', 'move_methods', 'method_id'),
                      ('version_group_id', 'version_groups', 'version_group_id')],
    'pokemon_abilities': [SPECIES, ('ability_id', 'abilities', 'ability_id')],
    'pokedex_entries': [SPECIES],
    'pokemon_names': [SPECIES],
    'encounters': [SPECIES],
    'pokedex_numbers': [SPECIES],
    'machines': [('move_id', 'moves', 'move_id'), ('item_id', 'items', 'item_id')],
    'images': [SPECIES, ('form_id', 'pokemon_forms', 'form_id')],
    'cries': [SPECIES, ('form_id', 'pokemon_forms', 'form_id')],
    'competitive_tiers': [SPECIES, ('form_id', 'pokemon_forms', 'form_id')],
    'smogon_usage': [SPECIES, ('format_id', 'smogon_formats', 'format_id')],
}
INDEXES = {
    'pokemon_forms': ['national_number', 'pokemon_id'], 'evolutions': ['from_national_number', 'to_national_number'],
    'pokemon_moves': ['pokemon_id', 'move_id'], 'pokemon_abilities': ['pokemon_id', 'ability_id'],
    'pokedex_entries': ['national_number'], 'encounters': ['national_number', 'pokemon_id'],
    'images': ['national_number'], 'cries': ['national_number'], 'smogon_usage': ['format_id', 'national_number'],
}


def sqltype(s):
    if pd.api.types.is_integer_dtype(s):
        return 'INTEGER'
    if pd.api.types.is_float_dtype(s):
        return 'REAL'
    return 'TEXT'


def load_tables():
    tables = {}
    for path in sorted(DATA.glob('*.csv')):
        if path.name == 'pokemon.csv':
            continue  # the UTF-16 copy of pokemon_utf8.csv
        name = 'pokemon' if path.name == 'pokemon_utf8.csv' else path.stem
        tables[name] = pd.read_csv(path, low_memory=False)
    for name, df in tables.items():  # nullable integer columns read as float: restore them
        for c in df.columns:
            if pd.api.types.is_float_dtype(df[c]) and df[c].dropna().mod(1).eq(0).all() and \
                    (c.endswith('_id') or c in ('level', 'min_level', 'national_number', 'from_national_number',
                                                'rank_top', 'power', 'accuracy', 'base_experience', 'number')):
                df[c] = df[c].astype('Int64')

    # Learnsets: integer keys instead of repeated text.
    pm = tables['pokemon_moves']
    methods = pd.DataFrame({'method': sorted(pm.method.dropna().unique())})
    methods.insert(0, 'method_id', range(1, len(methods) + 1))
    vg = tables['version_groups']
    tables['move_methods'] = methods
    tables['pokemon_moves'] = (pm.merge(methods, on='method')
                               .merge(vg[['version_group_id', 'version_group']], on='version_group')
                               [['pokemon_id', 'national_number', 'move_id', 'method_id', 'level', 'version_group_id']])
    # Smogon usage: one row per format in smogon_formats.
    if 'smogon_usage' in tables:
        su = tables['smogon_usage']
        formats = su[['gen', 'format']].drop_duplicates().sort_values(['gen', 'format']).reset_index(drop=True)
        formats.insert(0, 'format_id', range(1, len(formats) + 1))
        tables['smogon_formats'] = formats
        tables['smogon_usage'] = (su.merge(formats[['format_id', 'format']], on='format')
                                  .drop(columns=['format', 'gen']))
        cols = ['period', 'format_id'] + [c for c in tables['smogon_usage'].columns if c not in ('period', 'format_id')]
        tables['smogon_usage'] = tables['smogon_usage'][cols]
    # Referenced tables first, so foreign keys always point backwards.
    first = ['pokemon', 'pokemon_forms', 'moves', 'abilities', 'items', 'move_methods', 'version_groups',
             'smogon_formats']
    return {k: tables[k] for k in first if k in tables} | {k: v for k, v in tables.items() if k not in first}


def write(path, tables):
    path.unlink(missing_ok=True)
    con = sqlite3.connect(path)
    for name, df in tables.items():
        cols = []
        for c in df.columns:
            decl = f'"{c}" {sqltype(df[c])}'
            if PRIMARY_KEYS.get(name) == c:
                decl += ' PRIMARY KEY'
            cols.append(decl)
        for col, ref, refcol in FOREIGN_KEYS.get(name, []):
            if col in df.columns:
                cols.append(f'FOREIGN KEY ("{col}") REFERENCES {ref}("{refcol}")')
        con.execute(f'CREATE TABLE {name} ({", ".join(cols)})')
        rows = df.astype(object).where(df.notna(), None).itertuples(index=False, name=None)
        con.executemany(f'INSERT INTO {name} VALUES ({", ".join("?" * len(df.columns))})', rows)
        for c in INDEXES.get(name, []):
            con.execute(f'CREATE INDEX ix_{name}_{c} ON {name}("{c}")')
    con.commit()
    con.execute('VACUUM')
    con.close()


def main():
    tables = load_tables()
    write(DATA / 'pokedex.sqlite', tables)
    size = (DATA / 'pokedex.sqlite').stat().st_size / 1e6
    print(f'pokedex.sqlite: {len(tables)} tables, {size:.1f} MB')


if __name__ == '__main__':
    main()
