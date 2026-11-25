"""Build the v2 relational tables of The Complete Pokédex Dataset.

The species table (data/pokemon_utf8.csv) is the scraped, cross-verified master
built by pokedex.ipynb. This script enriches it and derives the companion tables
from the PokeAPI CSV database (https://github.com/PokeAPI/pokeapi, data/v2/csv,
BSD-3-Clause):

    data/pokemon_utf8.csv / data/pokemon.csv   species master (+ new species fields)
    data/pokemon_stats.csv                     base stats, long format
    data/pokemon_forms.csv                     every form/variety with its own stats and types
    data/evolutions.csv                        one row per evolution method
    data/moves.csv                             every move
    data/pokemon_moves.csv                     learnsets for every game
    data/images.csv                            image manifest with a fixed train/val/test split
    data/pokedex.sqlite                        all of the above as one SQLite database

Usage:
    git clone --depth 1 --filter=blob:none --sparse https://github.com/PokeAPI/pokeapi.git
    git -C pokeapi sparse-checkout set data/v2/csv
    python scripts/build_tables.py pokeapi/data/v2/csv
"""

import hashlib
import re
import sqlite3
import struct
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
IMAGES = ROOT / 'images'
IMAGE_SETS = ('small_images', 'large_images', 'alt_images')  # Pokémon artwork (images/type_icons is not indexed)
EN = 9  # PokeAPI language id for English

ROMAN = {1: 'I', 2: 'II', 3: 'III', 4: 'IV', 5: 'V', 6: 'VI', 7: 'VII', 8: 'VIII', 9: 'IX'}
STATS = ['hp', 'attack', 'defense', 'sp_attack', 'sp_defense', 'speed']
TYPES = ['normal', 'fire', 'water', 'electric', 'grass', 'ice', 'fighting', 'poison', 'ground',
         'flying', 'psychic', 'bug', 'rock', 'ghost', 'dragon', 'dark', 'steel', 'fairy']

# Corrections to the scraped master, each checked against current (Gen IX) game data.
STAT_FIXES = {
    488: {'defense': 110, 'sp_defense': 120},  # Cresselia, lowered in Scarlet/Violet
    888: {'attack': 120},                       # Zacian (Hero of Many Battles), lowered in Scarlet/Violet
    889: {'attack': 120},                       # Zamazenta (Hero of Many Battles), lowered in Scarlet/Violet
}
MYTHICAL_FIXES = [809, 893]  # Melmetal, Zarude are officially Mythical
CAPTURE_RATE_FIXES = {774: 30}  # Minior: Meteor Form 30 (Core Form 255 is a battle-only form)
FRIENDSHIP_70_EXCEPTIONS = {532, 618}  # Timburr, Stunfisk kept 70 when Gen VIII lowered 70 -> 50


def load(csv_dir):
    cache = {}

    def r(name):
        if name not in cache:
            cache[name] = pd.read_csv(Path(csv_dir) / f'{name}.csv', keep_default_na=False,
                                      na_values=[''], low_memory=False)
        return cache[name]
    return r


def en(r, table, key, col='name'):
    t = r(table)
    lang = 'local_language_id' if 'local_language_id' in t.columns else 'language_id'
    out = t[t[lang] == EN].set_index(key)[col]
    return out.str.replace('\u2019', "'") if out.dtype != float else out  # straight apostrophes, as in the master


def clean_text(s):
    if not isinstance(s, str):
        return s
    s = s.replace('\u00ad\n', '').replace('\u00ad', '').replace('\f', ' ').replace('\n', ' ').replace('\u2019', "'")
    return re.sub(r'\s+', ' ', s).strip()


def strip_markup(s):
    """PokeAPI prose uses [label]{kind:identifier} links; keep the label (or the identifier)."""
    if not isinstance(s, str):
        return s

    def repl(m):
        label, target = m.group(1), m.group(2)
        if label:
            return label
        return target.split(':', 1)[-1].replace('-', ' ').title()
    return clean_text(re.sub(r'\[([^\]]*)\]\{([^}]*)\}', repl, s))


def png_size(path):
    with open(path, 'rb') as f:
        head = f.read(24)
    return struct.unpack('>II', head[16:24])


class PokeAPI:
    def __init__(self, csv_dir):
        r = self.r = load(csv_dir)
        self.species = r('pokemon_species').set_index('id')
        self.pokemon = r('pokemon').set_index('id')
        self.forms = r('pokemon_forms').set_index('id')
        self.species_name = en(r, 'pokemon_species_names', 'pokemon_species_id').str.replace('’', "'")
        self.type_id = r('types').set_index('id').identifier
        self.type_name = en(r, 'type_names', 'type_id')
        self.ability_name = en(r, 'ability_names', 'ability_id')
        self.item_name = en(r, 'item_names', 'item_id')
        self.move_name = en(r, 'move_names', 'move_id')
        self.location_name = en(r, 'location_names', 'location_id')
        self.region_name = en(r, 'region_names', 'region_id')
        fn = r('pokemon_form_names')
        fn = fn[fn.local_language_id == EN].set_index('pokemon_form_id')
        self.form_name = fn.form_name.str.replace('\u2019', "'")
        self.form_pokemon_name = fn.pokemon_name
        vg = r('version_groups').set_index('id')
        vnames = en(r, 'version_names', 'version_id')
        versions = r('versions')
        self.vg_name = {}
        for vid, row in vg.iterrows():
            vs = versions[versions.version_group_id == vid].id.map(vnames).dropna().tolist()
            self.vg_name[vid] = ' / '.join(vs) if vs else row.identifier.replace('-', ' ').title()
        self.vg_gen = vg.generation_id
        self.vg_order = vg.order
        # Defensive type chart: chart[attacking][defending] = multiplier
        eff = r('type_efficacy')
        self.chart = {}
        for row in eff.itertuples():
            self.chart.setdefault(self.type_id[row.damage_type_id], {})[self.type_id[row.target_type_id]] = row.damage_factor / 100

    def against(self, t1, t2):
        out = {}
        for atk in TYPES:
            m = self.chart[atk][t1]
            if isinstance(t2, str):
                m *= self.chart[atk][t2]
            out[f'against_{atk}'] = m
        return out

    def form_display(self, form_id):
        f = self.forms.loc[form_id]
        species_id = self.pokemon.loc[f.pokemon_id, 'species_id']
        base = self.species_name[species_id]
        full = self.form_pokemon_name.get(form_id)
        if isinstance(full, str) and full:
            return full.replace('’', "'")
        label = self.form_name.get(form_id)
        if isinstance(label, str) and label:
            return f'{base} ({label})'
        return base


# --------------------------------------------------------------------------- species master

def build_master(api):
    r = api.r
    df = pd.read_csv(DATA / 'pokemon_utf8.csv')
    # Re-runnable: drop the columns this script derives, so a rebuild starts from the scraped fields.
    derived = ['color', 'shape', 'habitat', 'base_experience', 'base_friendship', 'growth_rate',
               'egg_group_1', 'egg_group_2', 'base_total'] + [f'ev_yield_{s}' for s in STATS]
    df = df.drop(columns=[c for c in derived if c in df.columns])
    df['english_name'] = df.english_name.str.replace('’', "'")
    df['capture_rate'] = df.capture_rate.astype(str)
    for n, fixes in STAT_FIXES.items():
        for col, v in fixes.items():
            df.loc[df.national_number == n, col] = v
    df.loc[df.national_number.isin(MYTHICAL_FIXES), ['is_sublegendary', 'is_legendary', 'is_mythical']] = [0, 0, 1]
    for n, v in CAPTURE_RATE_FIXES.items():
        df.loc[df.national_number == n, 'capture_rate'] = str(v)
    df['capture_rate'] = df.capture_rate.astype(int)

    sp = api.species.loc[df.national_number]
    default_pid = r('pokemon').query('is_default == 1').set_index('species_id').id
    pids = df.national_number.map(default_pid)

    color = en(r, 'pokemon_color_names', 'pokemon_color_id')
    shape = en(r, 'pokemon_shape_prose', 'pokemon_shape_id')
    habitat = en(r, 'pokemon_habitat_names', 'pokemon_habitat_id')
    growth = en(r, 'growth_rate_prose', 'growth_rate_id').str.title().replace({'Medium': 'Medium Fast'})
    egg = en(r, 'egg_group_prose', 'egg_group_id')
    eggs = r('pokemon_egg_groups').sort_values(['species_id', 'egg_group_id'])
    eggs = eggs.groupby('species_id').egg_group_id.apply(list)
    effort = r('pokemon_stats').pivot(index='pokemon_id', columns='stat_id', values='effort')
    effort.columns = [f'ev_yield_{s}' for s in STATS]

    new = pd.DataFrame(index=df.index)
    new['color'] = sp.color_id.map(color).values
    new['shape'] = sp.shape_id.map(shape).values
    new['habitat'] = sp.habitat_id.map(habitat).map(
        lambda h: ' '.join(w[:1].upper() + w[1:] for w in h.split()) if isinstance(h, str) else h).values
    new['base_experience'] = pids.map(api.pokemon.base_experience).astype('Int64').values
    friendship = sp.base_happiness.astype(int).values
    new['base_friendship'] = [50 if f == 70 and n not in FRIENDSHIP_70_EXCEPTIONS else f
                              for f, n in zip(friendship, df.national_number)]
    new['growth_rate'] = sp.growth_rate_id.map(growth).values
    groups = df.national_number.map(eggs)
    new['egg_group_1'] = [egg[g[0]] for g in groups]
    new['egg_group_2'] = [egg[g[1]] if len(g) > 1 else None for g in groups]
    new['base_total'] = df[STATS].sum(axis=1)
    ev = effort.loc[pids].reset_index(drop=True)

    df = fix_evochains(api, df)

    order = list(df.columns)
    def after(col, cols):
        i = order.index(col) + 1
        order[i:i] = cols
    after('classification', ['color', 'shape', 'habitat'])
    after('base_egg_steps', ['base_experience', 'base_friendship', 'growth_rate', 'egg_group_1', 'egg_group_2'])
    after('speed', ['base_total'] + list(ev.columns))
    out = pd.concat([df, new, ev], axis=1)[order]
    return out


def fix_evochains(api, df):
    """evochain_1/3/5 hold the method used to obtain the species in the next column. The scraped
    text was often just 'Level'; regenerate it from PokeAPI and normalise species spellings."""
    name_fix = {'Mimejr.': 'Mime Jr.', 'Mr.mime': 'Mr. Mime'}
    ids = {v: k for k, v in api.species_name.items()}
    evo = api.r('pokemon_evolution')
    for i in (0, 2, 4, 6):
        df[f'evochain_{i}'] = df[f'evochain_{i}'].replace(name_fix)
    # Drop scrape debris: a species name sitting in a method column, or method text in a species column
    # (only the Slowpoke/Slowbro rows, which had the Galarian branch spliced onto the end).
    species = set(api.species_name)
    for i in (1, 3, 5):
        bad = df[f'evochain_{i}'].isin(species)
        df.loc[bad, [f'evochain_{i}', f'evochain_{i + 1}']] = None
    for i in (2, 4, 6):
        bad = df[f'evochain_{i}'].notna() & ~df[f'evochain_{i}'].isin(species)
        df.loc[bad, [f'evochain_{i - 1}', f'evochain_{i}']] = None
    for i in (1, 3, 5):
        col = f'evochain_{i}'
        out = []
        for cell, target in zip(df[col], df[f'evochain_{i + 1}']):
            if not isinstance(cell, str):
                out.append(cell)
                continue
            sid = ids.get(target)
            rows = evo[(evo.evolved_species_id == sid) & (evo.is_default == 1)] if sid else evo.iloc[0:0]
            base = rows[rows.region_id.isna() & rows.evolved_pokemon_form_id.isna()]
            rows = base if len(base) else rows
            texts = list(dict.fromkeys(describe_evolution(api, row) for row in rows.itertuples()))
            out.append(' or '.join(texts) if texts else re.sub(r'\s+', ' ', cell).strip())
        df[col] = out
    return df


# --------------------------------------------------------------------------- evolutions

def describe_evolution(api, e):
    def num(v):
        return int(v) if pd.notna(v) else None
    t = num(e.evolution_trigger_id)
    item = api.item_name.get(num(e.trigger_item_id))
    held = api.item_name.get(num(e.held_item_id))
    parts = []
    if t == 1:
        parts.append(f'Level {num(e.minimum_level)}' if pd.notna(e.minimum_level) else 'Level up')
    elif t == 2:
        parts.append('Trade')
    elif t == 3:
        parts.append(f'Use {item}')
    elif t == 4:
        return 'Level 20 with an empty party slot and a Poké Ball in the bag (from Nincada)'
    elif t == 5:
        spin = e.condition_expression if isinstance(e.condition_expression, str) else ''
        parts.append('Spin around ' + ('counter-clockwise' if 'SPIN_DIR 1' in spin else 'clockwise')
                     + ' for under 5 seconds' if spin else 'Spin around')
    elif t in (6, 7):
        return 'Train in the Tower of Darkness' if t == 6 else 'Train in the Tower of Waters'
    elif t == 8:
        parts.append('Land three critical hits in one battle')
    elif t == 9:
        parts.append(f'Lose at least {num(e.minimum_damage_taken)} HP in battle, then pass under the stone arch')
        loc = api.location_name.get(num(e.location_id))
        return f'{parts[0]} at {loc}' if loc else parts[0]
    elif t == 10:
        parts.append(f'Level {num(e.minimum_level)} in battle' if pd.notna(e.minimum_level) else 'Level up in battle')
    elif t in (11, 12):
        style = 'Agile' if t == 11 else 'Strong'
        parts.append(f'Use {api.move_name.get(num(e.used_move_id))} in {style} Style {num(e.minimum_move_count)} times')
    elif t == 13:
        parts.append(f'Lose at least {num(e.minimum_damage_taken)} HP from recoil damage without fainting')
    elif t == 14:
        parts.append(f'Level up after using {api.move_name.get(num(e.used_move_id))} {num(e.minimum_move_count)} times')
    elif t == 15:
        return "Defeat three Bisharp that hold a Leader's Crest"
    elif t == 16:
        return 'Level up with 999 Gimmighoul Coins in the bag'
    elif t == 17:
        return 'Feed 400 Meltan Candies (Pokémon GO)'
    else:
        parts.append('Special')
    if pd.notna(e.minimum_happiness):
        parts.append(f'with high friendship ({num(e.minimum_happiness)}+)')
    if pd.notna(e.minimum_affection):
        parts.append(f'with {num(e.minimum_affection)}+ affection hearts')
    if pd.notna(e.minimum_beauty):
        parts.append(f'with {num(e.minimum_beauty)}+ Beauty')
    if pd.notna(e.known_move_id):
        parts.append(f'while knowing {api.move_name.get(num(e.known_move_id))}')
    if pd.notna(e.known_move_type_id):
        parts.append(f'while knowing a {api.type_name.get(num(e.known_move_type_id))}-type move')
    if held:
        parts.append(f'while holding {held}')
    if pd.notna(e.trade_species_id):
        parts.append(f'for {api.species_name.get(num(e.trade_species_id))}')
    if pd.notna(e.party_species_id):
        parts.append(f'with {api.species_name.get(num(e.party_species_id))} in the party')
    if pd.notna(e.party_type_id):
        parts.append(f'with a {api.type_name.get(num(e.party_type_id))}-type Pokémon in the party')
    if pd.notna(e.relative_physical_stats):
        parts.append({1: 'with Attack > Defense', 0: 'with Attack = Defense', -1: 'with Attack < Defense'}[num(e.relative_physical_stats)])
    if pd.notna(e.minimum_steps):
        parts.append(f'after walking {num(e.minimum_steps):,} steps in Let\'s Go mode')
    if t not in (11, 12, 14) and pd.notna(e.used_move_id):
        parts.append(f'after using {api.move_name.get(num(e.used_move_id))} {num(e.minimum_move_count)} times')
    if e.needs_overworld_rain == 1:
        parts.append('while it is raining')
    if e.turn_upside_down == 1:
        parts.append('while holding the console upside down')
    if e.needs_multiplayer == 1:
        parts.append('in Union Circle')
    if e.near_special_rock == 1:
        parts.append('near a Moss Rock' if num(e.evolved_species_id) == 470 else 'near an Ice Rock')
    if pd.notna(e.location_id) and t != 9:
        parts.append(f'at {api.location_name.get(num(e.location_id))}')
    if isinstance(e.time_of_day, str):
        parts.append({'day': 'during the day', 'night': 'at night', 'dusk': 'at dusk',
                      'full-moon': 'under a full moon'}.get(e.time_of_day, e.time_of_day))
    if pd.notna(e.gender_id):
        parts.append({1: '(female only)', 2: '(male only)'}[num(e.gender_id)])
    if pd.notna(e.region_id):
        parts.append(f'in {api.region_name.get(num(e.region_id))}')
    if pd.notna(e.nature_bitmask):
        fid = num(e.evolved_pokemon_form_id)
        low_key = fid is not None and api.forms.loc[fid, 'form_identifier'] == 'low-key'
        parts.append('with a Low Key nature' if low_key else 'with an Amped nature')
    random = isinstance(e.condition_expression, str) and 'SPIN' not in e.condition_expression
    if pd.notna(e.percentage_chance):
        parts.append(f'({num(e.percentage_chance)}% chance' + (', set by its personality value)' if random else ')'))
    elif random:
        parts.append('(set by its personality value)')
    return ' '.join(p for p in parts if p)


def build_evolutions(api):
    r = api.r
    evo = r('pokemon_evolution')
    trig = en(r, 'evolution_trigger_prose', 'evolution_trigger_id')
    rows = []
    for e in evo.itertuples():
        to_sid = int(e.evolved_species_id)
        s = api.species.loc[to_sid]
        from_sid = int(s.evolves_from_species_id) if pd.notna(s.evolves_from_species_id) else None
        if from_sid is None and pd.notna(e.required_pokemon_form_id):
            from_sid = int(api.pokemon.loc[api.forms.loc[int(e.required_pokemon_form_id), 'pokemon_id'], 'species_id'])

        def form(fid):
            if pd.isna(fid):
                return None
            fid = int(fid)
            f = api.forms.loc[fid]
            if f.is_default == 1 and api.pokemon.loc[f.pokemon_id, 'is_default'] == 1:
                return None
            return api.form_display(fid)

        def n(v):
            return int(v) if pd.notna(v) else None
        rows.append({
            'evolution_id': e.id,
            'evolution_chain_id': int(s.evolution_chain_id),
            'from_national_number': from_sid,
            'from_name': api.species_name.get(from_sid),
            'from_form': form(e.required_pokemon_form_id),
            'to_national_number': to_sid,
            'to_name': api.species_name[to_sid],
            'to_form': form(e.evolved_pokemon_form_id),
            'trigger': trig[e.evolution_trigger_id],
            'min_level': n(e.minimum_level),
            'item': api.item_name.get(n(e.trigger_item_id)),
            'held_item': api.item_name.get(n(e.held_item_id)),
            'known_move': api.move_name.get(n(e.known_move_id)),
            'known_move_type': api.type_id.get(n(e.known_move_type_id)),
            'min_happiness': n(e.minimum_happiness),
            'min_affection': n(e.minimum_affection),
            'min_beauty': n(e.minimum_beauty),
            'time_of_day': e.time_of_day if isinstance(e.time_of_day, str) else None,
            'gender': {1: 'female', 2: 'male'}.get(n(e.gender_id)),
            'location': api.location_name.get(n(e.location_id)),
            'region': api.region_name.get(n(e.region_id)),
            'party_species': api.species_name.get(n(e.party_species_id)),
            'party_type': api.type_id.get(n(e.party_type_id)),
            'trade_species': api.species_name.get(n(e.trade_species_id)),
            'relative_physical_stats': n(e.relative_physical_stats),
            'needs_overworld_rain': int(e.needs_overworld_rain),
            'turn_upside_down': int(e.turn_upside_down),
            'used_move': api.move_name.get(n(e.used_move_id)),
            'min_move_count': n(e.minimum_move_count),
            'min_steps': n(e.minimum_steps),
            'min_damage_taken': n(e.minimum_damage_taken),
            'chance_percent': n(e.percentage_chance),
            'condition': describe_evolution(api, e),
            'games': api.vg_name[e.version_group_id],
            'is_primary_method': int(e.is_default),
        })
    out = pd.DataFrame(rows)
    int_cols = ['from_national_number', 'min_level', 'min_happiness', 'min_affection', 'min_beauty',
                'relative_physical_stats', 'min_move_count', 'min_steps', 'min_damage_taken', 'chance_percent']
    out[int_cols] = out[int_cols].astype('Int64')
    return out.sort_values(['evolution_chain_id', 'to_national_number', 'is_primary_method', 'evolution_id'],
                           ascending=[True, True, False, True]).reset_index(drop=True)


# --------------------------------------------------------------------------- forms

REGIONS = {'alola': 'Alola', 'galar': 'Galar', 'hisui': 'Hisui', 'paldea': 'Paldea'}


def build_forms(api, master):
    r = api.r
    stats = r('pokemon_stats').pivot(index='pokemon_id', columns='stat_id', values='base_stat')
    stats.columns = STATS
    effort = r('pokemon_stats').pivot(index='pokemon_id', columns='stat_id', values='effort')
    effort.columns = [f'ev_yield_{s}' for s in STATS]
    ptypes = r('pokemon_types').sort_values('slot').groupby('pokemon_id').type_id.apply(list)
    ftypes = r('pokemon_form_types').sort_values('slot').groupby('pokemon_form_id').type_id.apply(list)
    abil = r('pokemon_abilities')
    master_by_n = master.set_index('national_number')
    rows = []
    for fid, f in api.forms.iterrows():
        pid = int(f.pokemon_id)
        p = api.pokemon.loc[pid]
        sid = int(p.species_id)
        ident = f.form_identifier if isinstance(f.form_identifier, str) else ''
        pident = p.identifier
        types = ftypes.get(fid, ptypes[pid])
        types = [api.type_id[t] for t in types]
        if not set(types) <= set(TYPES):
            continue  # Arceus '???' form: a Gen IV-only leftover type with no place in the current chart
        a = abil[abil.pokemon_id == pid].sort_values('slot')
        regular = a[a.is_hidden == 0].ability_id.map(api.ability_name).tolist()
        hidden = a[a.is_hidden == 1].ability_id.map(api.ability_name).tolist()
        is_default_variety = int(p.is_default)
        is_default_form = int(f.is_default)
        tokens = pident.split('-')[1:]
        region = None if 'cap' in tokens else next((v for k, v in REGIONS.items() if k in tokens), None)
        is_mega = int(f.is_mega == 1 or bool(re.search(r'-mega(-[xyz])?$|-mega$', pident)) or 'mega' in ident.split('-'))
        is_gmax = int('gmax' in pident.split('-'))
        if is_default_variety and is_default_form:
            category = 'default'
        elif is_mega:
            category = 'mega'
        elif pident.endswith('-primal'):
            category = 'primal'
        elif is_gmax:
            category = 'gigantamax'
        elif 'totem' in pident.split('-'):
            category = 'totem'
        elif region:
            category = 'regional'
        elif f.is_battle_only == 1:
            category = 'battle-only'
        elif is_default_variety and types == [api.type_id[t] for t in ptypes[pid]]:
            category = 'cosmetic'
        else:
            category = 'alternate'
        row = {
            'form_id': fid,
            'pokemon_id': pid,
            'national_number': sid,
            'species_name': master_by_n.loc[sid, 'english_name'],
            'form_name': (api.form_name.get(fid) or None) if isinstance(api.form_name.get(fid), str) else None,
            'display_name': api.form_display(fid),
            'identifier': f.identifier,
            'form_category': category,
            'is_default_variety': is_default_variety,
            'is_default_form': is_default_form,
            'is_battle_only': int(f.is_battle_only),
            'is_mega': is_mega,
            'is_gigantamax': is_gmax,
            'is_regional_variant': int(region is not None and category == 'regional'),
            'region': region if category in ('regional', 'totem') else None,
            'introduced_in': api.vg_name[f.introduced_in_version_group_id],
            'introduced_gen': ROMAN[int(api.vg_gen[f.introduced_in_version_group_id])],
            'primary_type': types[0],
            'secondary_type': types[1] if len(types) > 1 else None,
        }
        row.update(stats.loc[pid].to_dict())
        row['base_total'] = int(stats.loc[pid].sum())
        row.update(effort.loc[pid].to_dict())
        row['abilities_0'] = regular[0] if len(regular) > 0 else None
        row['abilities_1'] = regular[1] if len(regular) > 1 else None
        row['abilities_hidden'] = hidden[0] if hidden else None
        row['height_m'] = p.height / 10
        row['weight_kg'] = p.weight / 10
        row['base_experience'] = p.base_experience
        row.update(api.against(types[0], types[1] if len(types) > 1 else None))
        rows.append(row)
    out = pd.DataFrame(rows)
    out['base_experience'] = out.base_experience.astype('Int64')
    # PokeAPI flags none of the forms of Koraidon's and Miraidon's ride varieties as default; use the first.
    orphan = out.groupby('pokemon_id').is_default_form.transform('sum') == 0
    first = out[orphan].sort_values('form_id').drop_duplicates('pokemon_id').index
    out.loc[first, 'is_default_form'] = 1
    # The species-level master is the verified source for the default form of each species:
    # keep both tables consistent on stats and types.
    m = master.set_index('national_number')
    d = (out.is_default_variety == 1) & (out.is_default_form == 1)
    for c in STATS + ['primary_type', 'secondary_type', 'base_total']:
        out.loc[d, c] = out.loc[d, 'national_number'].map(m[c]).values
    return out.sort_values(['national_number', 'is_default_variety', 'is_default_form', 'pokemon_id', 'form_id'],
                           ascending=[True, False, False, True, True]).reset_index(drop=True)


# --------------------------------------------------------------------------- images

# Filler words dropped from both sides before comparing an image's form label with PokeAPI's names.
FILLER = {'form', 'forme', 'mode', 'cap', 'style', 'cloak', 'pattern', 'plumage', 'breed', 'mask',
          'size', 'trim', 'flower', 'color', 'the', 'of'}
# Image label -> PokeAPI form key, where the two naming schemes differ.
ALIASES = {
    'gigantamax': 'gmax', 'sunny': 'sunshine', 'shadowrider': 'shadow', 'icerider': 'ice',
    'alolan': 'alola', 'galarian': 'galar', 'hisuian': 'hisui', 'paldean': 'paldea',
}
# Images whose label has no counterpart in PokeAPI's form names, mapped by hand after viewing them
# (PokeAPI pokemon_forms.identifier). Appearance-only variants map to the form they belong to.
# Left unmatched on purpose: Rotom Phone / Rotom Pokédex (not battle forms), Zygarde Cell / Core.
FILE_ALIASES = {
    '550Basculin-Blue.png': 'basculin-blue-striped',
    '550Basculin-Red.png': 'basculin-red-striped',
    '555Darmanitan-Galar.png': 'darmanitan-galar-standard',
    '643Reshiram-Activated.png': 'reshiram',
    '644Zekrom-Activated.png': 'zekrom',
    '646Kyurem-Black2.png': 'kyurem-black',
    '646Kyurem-White2.png': 'kyurem-white',
    '718Zygarde-10Percent.png': 'zygarde-10',
    '774Minior-Core.png': 'minior-red',
    '791Solgaleo-RadiantSunPhase.png': 'solgaleo',
    '792Lunala-FullMoonPhase.png': 'lunala',
    '802Marshadow-Alt.png': 'marshadow',
    '877Morpeko-Full.png': 'morpeko-full-belly',
    '888Zacian-Crowned_Sword.png': 'zacian-crowned',
    '889Zamazenta-Crowned_Shield.png': 'zamazenta-crowned',
}


def norm_tokens(tokens):
    toks = [re.sub(r'[^a-z0-9]', '', t.lower().replace('é', 'e')) for t in tokens]
    toks = [t for t in toks if t and t not in FILLER]
    return ''.join(toks)


def form_keys(api, form_row):
    keys = set()
    ident = api.forms.loc[form_row.form_id, 'form_identifier']
    pident = api.pokemon.loc[form_row.pokemon_id, 'identifier']
    species_ident = api.species.loc[form_row.national_number, 'identifier']
    for s in (ident, pident[len(species_ident) + 1:] if pident.startswith(species_ident + '-') else None):
        if isinstance(s, str) and s:
            keys.add(norm_tokens(s.split('-')))
    for s in (form_row.form_name, form_row.display_name):
        if isinstance(s, str) and s:
            toks = [t for t in re.split(r'[\s\-()]+', s) if t.lower() not in
                    {w.lower() for w in form_row.species_name.split()}]
            keys.add(norm_tokens(toks))
    return {k for k in keys if k}


def match_alt_images(api, forms):
    rx = re.compile(r'^(\d+)([^\d].*?)-(.+)\.png$')
    by_species = {n: g for n, g in forms.groupby('national_number')}
    keys = {row.form_id: form_keys(api, row) for row in forms.itertuples()}
    matches = {}
    by_identifier = forms.set_index('identifier').form_id
    for path in sorted((IMAGES / 'alt_images').glob('*.png')):
        if path.name in FILE_ALIASES:
            matches[path.name] = int(by_identifier[FILE_ALIASES[path.name]])
            continue
        m = rx.match(path.name)
        n, token = int(m.group(1)), m.group(3)
        raw = norm_tokens(re.split(r'[_\s]+', token))
        candidates = [raw, ALIASES.get(raw, raw)]
        # 'Curly_Mega' -> 'curlymega', 'Mega_X' -> 'megax', 'Gigantamax' -> 'gmax'
        candidates.append(raw.replace('gigantamax', 'gmax'))
        candidates = list(dict.fromkeys(candidates))
        group = by_species.get(n)
        hit = None
        if group is not None:
            # Prefer battle-relevant varieties (default form of a variety) over cosmetic duplicates
            ordered = group.sort_values(['is_default_form', 'form_id'], ascending=[False, True])
            for cand in candidates:
                for row in ordered.itertuples():
                    if cand in keys[row.form_id]:
                        hit = row.form_id
                        break
                if hit:
                    break
        matches[path.name] = hit
    return matches


def build_images(api, master, forms, alt_matches):
    fr = forms.set_index('form_id')
    default_form = forms[(forms.is_default_variety == 1) & (forms.is_default_form == 1)].set_index('national_number').form_id
    # Split by species so that every image of a species lands in the same split (no leakage),
    # stratified by primary type, deterministic (hash of the national number).
    split = {}
    for _, g in master.groupby('primary_type'):
        ns = sorted(g.national_number, key=lambda n: hashlib.md5(str(n).encode()).hexdigest())
        k = len(ns)
        for i, n in enumerate(ns):
            split[n] = 'train' if i < round(k * 0.70) else ('val' if i < round(k * 0.85) else 'test')
    rows = []
    names = master.set_index('national_number').english_name
    rx = re.compile(r'^(\d+)([^\d].*?)-(.+)\.png$')
    for image_set in IMAGE_SETS:
        for path in sorted((IMAGES / image_set).glob('*.png')):
            if image_set == 'alt_images':
                m = rx.match(path.name)
                n, label = int(m.group(1)), m.group(3).replace('_', ' ')
                fid = alt_matches.get(path.name)
            else:
                n, label = int(path.stem), None
                fid = default_form[n]
            w, h = png_size(path)
            f = fr.loc[fid] if fid is not None and not pd.isna(fid) else None
            rows.append({
                'image_file': f'{image_set}/{path.name}',
                'image_set': image_set,
                'file_name': path.name,
                'national_number': n,
                'english_name': names[n],
                'form_label': label,
                'form_id': fid,
                'pokemon_id': None if f is None else f.pokemon_id,
                'display_name': None if f is None else f.display_name,
                'primary_type': None if f is None else f.primary_type,
                'secondary_type': None if f is None else f.secondary_type,
                'width': w,
                'height': h,
                'split': split[n],
            })
    out = pd.DataFrame(rows)
    out[['form_id', 'pokemon_id']] = out[['form_id', 'pokemon_id']].astype('Int64')
    return out


# --------------------------------------------------------------------------- moves

def build_moves(api):
    r = api.r
    mv = r('moves')
    mv = mv[mv.id < 10000]
    dmg = r('move_damage_classes').set_index('id').identifier
    target = r('move_targets').set_index('id').identifier
    eff = en(r, 'move_effect_prose', 'move_effect_id', 'short_effect')
    ft = r('move_flavor_text')
    ft = ft[ft.language_id == EN].assign(order=lambda d: d.version_group_id.map(api.vg_order))
    ft = ft.assign(flavor_text=ft.flavor_text.map(clean_text))
    # Newer games replace the text of retired moves with a placeholder; keep the last real description.
    ft = ft.assign(placeholder=ft.flavor_text.str.startswith("This move can't be used") | (ft.flavor_text == 'Dummy Data'))
    flavor = ft[~ft.placeholder].sort_values('order').groupby('move_id').flavor_text.last()
    meta = r('move_meta').set_index('move_id')
    meta_cat = r('move_meta_categories').set_index('id').identifier
    ailment = en(r, 'move_meta_ailment_names', 'move_meta_ailment_id')

    def effect_text(row):
        s = eff.get(int(row.effect_id)) if pd.notna(row.effect_id) else None
        if not isinstance(s, str):
            return None
        if pd.notna(row.effect_chance):
            s = s.replace('$effect_chance', str(int(row.effect_chance)))
        return strip_markup(s)
    out = pd.DataFrame({
        'move_id': mv.id,
        'name': mv.id.map(api.move_name),
        'identifier': mv.identifier,
        'type': mv.type_id.map(api.type_id),
        'damage_class': mv.damage_class_id.map(dmg),
        # PokeAPI stores 0 instead of null for some Gen IX moves (status moves, variable power, never-miss)
        'power': mv.power.where(mv.power > 0).astype('Int64'),
        'accuracy': mv.accuracy.where(mv.accuracy > 0).astype('Int64'),
        'pp': mv.pp.astype('Int64'),
        'priority': mv.priority,
        'target': mv.target_id.map(target),
        'generation': mv.generation_id.map(ROMAN),
        'effect_chance': mv.effect_chance.astype('Int64'),
        'short_effect': [effect_text(row) for row in mv.itertuples()],
        'flavor_text': mv.id.map(flavor),
        'meta_category': mv.id.map(meta.meta_category_id).map(meta_cat),
        'ailment': mv.id.map(meta.meta_ailment_id).map(ailment),
        'ailment_chance': mv.id.map(meta.ailment_chance).astype('Int64'),
        'crit_rate': mv.id.map(meta.crit_rate).astype('Int64'),
        'drain': mv.id.map(meta.drain).astype('Int64'),
        'healing': mv.id.map(meta.healing).astype('Int64'),
        'flinch_chance': mv.id.map(meta.flinch_chance).astype('Int64'),
        'stat_chance': mv.id.map(meta.stat_chance).astype('Int64'),
        'min_hits': mv.id.map(meta.min_hits).astype('Int64'),
        'max_hits': mv.id.map(meta.max_hits).astype('Int64'),
        'min_turns': mv.id.map(meta.min_turns).astype('Int64'),
        'max_turns': mv.id.map(meta.max_turns).astype('Int64'),
    })
    out['ailment'] = out.ailment.replace({'none': None, '????': None})
    return out.reset_index(drop=True)


def build_pokemon_moves(api, forms):
    r = api.r
    pm = r('pokemon_moves')
    pm = pm[pm.move_id < 10000]
    method = en(r, 'pokemon_move_method_prose', 'pokemon_move_method_id')
    variety_name = forms[forms.is_default_form == 1].set_index('pokemon_id').display_name
    out = pd.DataFrame({
        'pokemon_id': pm.pokemon_id,
        'national_number': pm.pokemon_id.map(api.pokemon.species_id),
        'pokemon': pm.pokemon_id.map(variety_name),
        'move_id': pm.move_id,
        'move': pm.move_id.map(api.move_name),
        'method': pm.pokemon_move_method_id.map(method),
        'level': pm.level.astype('Int64'),
        'version_group': pm.version_group_id.map(r('version_groups').set_index('id').identifier),
        'generation': pm.version_group_id.map(api.vg_gen).map(ROMAN),
    })
    out.loc[out.method != 'Level up', 'level'] = pd.NA
    out['level'] = out.level.astype('Int64')
    out = out.drop_duplicates()
    order = pm.version_group_id.map(api.vg_order)
    out = out.assign(_o=order).sort_values(['national_number', 'pokemon_id', '_o', 'method', 'level', 'move'])
    return out.drop(columns='_o').reset_index(drop=True)


# --------------------------------------------------------------------------- output

def stats_long(master):
    long = master.melt(id_vars=['national_number', 'english_name'], value_vars=STATS,
                       var_name='stat_name', value_name='stat_value')
    return long.reset_index(drop=True)


def write_sqlite(path, tables):
    path.unlink(missing_ok=True)
    con = sqlite3.connect(path)
    schema = {
        'pokemon': 'national_number INTEGER PRIMARY KEY',
        'pokemon_forms': 'form_id INTEGER PRIMARY KEY',
        'moves': 'move_id INTEGER PRIMARY KEY',
        'move_methods': 'method_id INTEGER PRIMARY KEY',
        'version_groups': 'version_group_id INTEGER PRIMARY KEY',
    }
    fks = {
        'pokemon_forms': [('national_number', 'pokemon', 'national_number')],
        'pokemon_stats': [('national_number', 'pokemon', 'national_number')],
        'evolutions': [('from_national_number', 'pokemon', 'national_number'),
                       ('to_national_number', 'pokemon', 'national_number')],
        'pokemon_moves': [('national_number', 'pokemon', 'national_number'),
                          ('move_id', 'moves', 'move_id'),
                          ('method_id', 'move_methods', 'method_id'),
                          ('version_group_id', 'version_groups', 'version_group_id')],
        'images': [('national_number', 'pokemon', 'national_number'),
                   ('form_id', 'pokemon_forms', 'form_id')],
    }

    def sqltype(s):
        if pd.api.types.is_integer_dtype(s):
            return 'INTEGER'
        if pd.api.types.is_float_dtype(s):
            return 'REAL'
        return 'TEXT'
    for name, df in tables.items():
        cols = []
        for c in df.columns:
            decl = f'"{c}" {sqltype(df[c])}'
            if name in schema and schema[name].split()[0] == c:
                decl += ' PRIMARY KEY'
            cols.append(decl)
        for col, ref, refcol in fks.get(name, []):
            cols.append(f'FOREIGN KEY ("{col}") REFERENCES {ref}("{refcol}")')
        con.execute(f'CREATE TABLE {name} ({", ".join(cols)})')
        df2 = df.astype(object).where(df.notna(), None)
        con.executemany(f'INSERT INTO {name} VALUES ({", ".join("?" * len(df.columns))})',
                        df2.itertuples(index=False, name=None))
    for sql in ['CREATE INDEX ix_forms_species ON pokemon_forms(national_number)',
                'CREATE INDEX ix_forms_pokemon ON pokemon_forms(pokemon_id)',
                'CREATE INDEX ix_evo_from ON evolutions(from_national_number)',
                'CREATE INDEX ix_evo_to ON evolutions(to_national_number)',
                'CREATE INDEX ix_pm_pokemon ON pokemon_moves(pokemon_id)',
                'CREATE INDEX ix_pm_move ON pokemon_moves(move_id)',
                'CREATE INDEX ix_images_species ON images(national_number)']:
        con.execute(sql)
    con.commit()
    con.execute('VACUUM')
    con.close()


def main(csv_dir):
    api = PokeAPI(csv_dir)
    master = build_master(api)
    forms = build_forms(api, master)
    alt = match_alt_images(api, forms)
    images = build_images(api, master, forms, alt)
    pref = images.image_set.map({'large_images': 0, 'alt_images': 1, 'small_images': 2})
    best = (images.assign(_p=pref).dropna(subset=['form_id']).sort_values(['_p', 'file_name'])
            .drop_duplicates('form_id').set_index('form_id').image_file)
    forms['image_file'] = forms.form_id.map(best)
    evolutions = build_evolutions(api)
    moves = build_moves(api)
    pokemon_moves = build_pokemon_moves(api, forms)
    stats = stats_long(master)

    master.to_csv(DATA / 'pokemon_utf8.csv', index=False, float_format='%g')
    master.to_csv(DATA / 'pokemon.csv', index=False, float_format='%g', encoding='utf-16', sep='\t', lineterminator='\r\n')
    stats.to_csv(DATA / 'pokemon_stats.csv', index=False, float_format='%g')
    forms.to_csv(DATA / 'pokemon_forms.csv', index=False, float_format='%g')
    evolutions.to_csv(DATA / 'evolutions.csv', index=False, float_format='%g')
    moves.to_csv(DATA / 'moves.csv', index=False, float_format='%g')
    pokemon_moves.to_csv(DATA / 'pokemon_moves.csv', index=False, float_format='%g')
    images.to_csv(DATA / 'images.csv', index=False, float_format='%g')
    methods = pd.DataFrame({'method': sorted(pokemon_moves.method.dropna().unique())})
    methods.insert(0, 'method_id', range(1, len(methods) + 1))
    vgs = (api.r('version_groups').rename(columns={'id': 'version_group_id', 'identifier': 'version_group'})
           .assign(games=lambda d: d.version_group_id.map(api.vg_name),
                   generation=lambda d: d.generation_id.map(ROMAN))
           [['version_group_id', 'version_group', 'games', 'generation', 'order']]
           .sort_values('order').drop(columns='order'))
    learnsets = (pokemon_moves
                 .merge(methods, on='method')
                 .merge(vgs[['version_group_id', 'version_group']], on='version_group')
                 [['pokemon_id', 'national_number', 'move_id', 'method_id', 'level', 'version_group_id']])
    write_sqlite(DATA / 'pokedex.sqlite', {
        'pokemon': master, 'pokemon_stats': stats, 'pokemon_forms': forms, 'evolutions': evolutions,
        'moves': moves, 'move_methods': methods, 'version_groups': vgs, 'pokemon_moves': learnsets,
        'images': images,
    })
    unmatched = sorted(k for k, v in alt.items() if v is None)
    print(f'pokemon {master.shape}, forms {forms.shape}, evolutions {evolutions.shape}, moves {moves.shape}, '
          f'pokemon_moves {pokemon_moves.shape}, images {images.shape}')
    print(f'alt images matched to a form: {len(alt) - len(unmatched)}/{len(alt)}')
    for u in unmatched:
        print('  unmatched:', u)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'pokeapi/data/v2/csv')
