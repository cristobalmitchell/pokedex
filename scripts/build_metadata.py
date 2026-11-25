"""Write dataset-metadata.json (Kaggle) with a description of every column of every CSV.

The Kaggle description comes from docs/kaggle_description.md. Every column must be documented
here; the script stops on an undocumented column, and validate.py checks the result.

Usage:
    python scripts/build_metadata.py
"""

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'

TYPES = ['normal', 'fire', 'water', 'electric', 'grass', 'ice', 'fighting', 'poison', 'ground',
         'flying', 'psychic', 'bug', 'rock', 'ghost', 'dragon', 'dark', 'steel', 'fairy']
STATN = {'hp': 'HP', 'attack': 'Attack', 'defense': 'Defense', 'sp_attack': 'Special Attack',
         'sp_defense': 'Special Defense', 'speed': 'Speed'}
LANGS = ('en English, ja-hrkt Japanese (kana), ja Japanese (kanji), ja-roma official romanized Japanese, '
         'ko Korean, zh-hant / zh-hans Chinese (traditional / simplified), fr French, de German, '
         'es Spanish (Spain), es-419 Spanish (Latin America), it Italian')
I, N, S = 'integer', 'number', 'string'

# Columns that mean the same thing wherever they appear.
COMMON = {
    'national_number': ('National Pokédex number (1–1025) of the species. Joins to pokemon_utf8.csv.', I),
    'pokemon_id': ('Variety id (PokeAPI pokemon id): forms with their own battle data, e.g. Alolan Raichu. '
                   'Joins to pokemon_forms.csv.', I),
    'form_id': ('Form id. Joins to pokemon_forms.csv.', I),
    'display_name': ('Display name of the form (e.g. "Mega Charizard X").', S),
    'english_name': ('English species name.', S),
    'primary_type': ('Primary type.', S),
    'secondary_type': ('Secondary type (blank for single-type forms).', S),
    'base_total': ('Base stat total (sum of the six base stats).', I),
    'abilities_0': ('First regular ability (current games).', S),
    'abilities_1': ('Second regular ability (blank if none).', S),
    'abilities_hidden': ('Hidden ability (blank if none).', S),
    'height_m': ('Height in metres.', N),
    'weight_kg': ('Weight in kilograms.', N),
    'base_experience': ('Base experience yield when defeated (blank where no game has a value yet, '
                        'e.g. some Legends: Z-A Megas).', I),
    'generation': ('Generation (I–IX).', S),
    'version_group': ('Game group slug (e.g. scarlet-violet, legends-za). Joins to version_groups.csv.', S),
    'split': ('Fixed train / val / test split (70/15/15), assigned by species and stratified by primary type: '
              'every image and cry of a species is in the same split.', S),
    'language': (f'Language code: {LANGS}.', S),
    'move_id': ('Move id. Joins to moves.csv.', I),
    'item_id': ('Item id. Joins to items.csv.', I),
    'ability_id': ('Ability id. Joins to abilities.csv.', I),
}
for s, n in STATN.items():
    COMMON[s] = (f'Base {n} stat.', I)
    COMMON[f'ev_yield_{s}'] = (f'{n} effort values (EVs) gained for defeating this Pokémon.', I)
for t in TYPES:
    art = 'an' if t[0] in 'aeiou' else 'a'
    COMMON[f'against_{t}'] = (f'Damage multiplier taken from {art} {t.title()}-type move (0, 0.25, 0.5, 1, 2 or 4; '
                              f'pure type chart, abilities not applied).', N)

DOCS = {
    'pokemon_utf8.csv': {
        'gen': ('Generation the Pokémon was introduced (I–IX; #899–905 from Legends: Arceus count as Gen VIII).', S),
        'japanese_name': ('Japanese name, romanized phonetically (e.g. Iorofu).', S),
        'japanese_name_kana': ('Japanese name in katakana (e.g. イオルブ).', S),
        'japanese_name_official': ('Official romanized Japanese name, the trademark spelling (e.g. Eolb).', S),
        'primary_type': ('Primary type of the primary form.', S),
        'secondary_type': ('Secondary type of the primary form (blank for single-type Pokémon).', S),
        'classification': ('Category from the current English Pokédex (e.g. "Seed Pokémon").', S),
        'color': ('Pokédex color, used by the in-game Pokédex search (e.g. Green, Red).', S),
        'shape': ('Pokédex body shape (e.g. Quadruped, Upright, Humanoid, Wings).', S),
        'habitat': ('Habitat from the FireRed/LeafGreen Pokédex (e.g. Grassland, Forest). Gen I–III species only.', S),
        'percent_male': ('Percentage of the species that is male (blank if genderless); exact ratio, a multiple of 12.5.', N),
        'percent_female': ('Percentage of the species that is female (blank if genderless).', N),
        'capture_rate': ('Base capture rate, 3–255 (higher is easier). Minior uses its Meteor Form value.', I),
        'base_egg_steps': ('Steps required to hatch an egg (hatch cycles × 256).', I),
        'base_friendship': ('Friendship a newly caught Pokémon starts with, as in Gen VIII+ games (most species 50).', I),
        'growth_rate': ('Experience growth group: Erratic, Fast, Medium Fast, Medium Slow, Slow or Fluctuating.', S),
        'egg_group_1': ('First egg group (Undiscovered for species that cannot breed).', S),
        'egg_group_2': ('Second egg group (blank if only one).', S),
        'abilities_0': ('First regular ability of the primary form in current games.', S),
        'abilities_2': ('Always blank: no species has a third regular ability. Kept so older notebooks keep working.', S),
        'is_sublegendary': ('1 if the Pokémon is sub-legendary, else 0.', I),
        'is_legendary': ('1 if the Pokémon is legendary, else 0.', I),
        'is_mythical': ('1 if the Pokémon is mythical, else 0.', I),
        'evochain_0': ('Evolution chain: first species listed.', S),
        'evochain_1': ('How the species in evochain_2 is obtained (e.g. "Level 16", "Use Thunder Stone"). '
                       'evolutions.csv has the full branching tree.', S),
        'evochain_2': ('Evolution chain: second species listed.', S),
        'evochain_3': ('How the species in evochain_4 is obtained.', S),
        'evochain_4': ('Evolution chain: third species listed.', S),
        'evochain_5': ('How the species in evochain_6 is obtained (branched chains).', S),
        'evochain_6': ('Evolution chain: additional species (branched chains).', S),
        'gigantamax': ('Gigantamax form name if the Pokémon has one, else blank.', S),
        'mega_evolution': ('Mega Evolution form name if the Pokémon has one (incl. Legends: Z-A / Mega Dimension).', S),
        'mega_evolution_alt': ('Second Mega form for Pokémon with two (e.g. Mega Charizard Y).', S),
        'description': ('Pokédex description from the official Pokémon website.', S),
    },
    'pokemon_stats.csv': {
        'stat_name': ('hp, attack, defense, sp_attack, sp_defense or speed.', S),
        'stat_value': ('Base stat value.', I),
    },
    'pokemon_forms.csv': {
        'form_id': ('Unique form id (PokeAPI pokemon_forms id). Primary key.', I),
        'pokemon_id': ('Variety id (PokeAPI pokemon id): forms that share battle data share this id. '
                       'Joins to pokemon_moves.csv and pokemon_abilities.csv.', I),
        'species_name': ('English species name.', S),
        'form_name': ('Form label (e.g. "Mega X", "Alolan Form"); blank for unnamed default forms.', S),
        'display_name': ('Full display name (e.g. "Mega Charizard X", "Alolan Raichu").', S),
        'identifier': ('Lower-case slug (e.g. charizard-mega-x).', S),
        'form_category': ('default, mega, primal, gigantamax, regional, totem, battle-only (e.g. Zen Mode), alternate '
                          '(separate variety, e.g. Rotom-Heat) or cosmetic (same battle data as the default, e.g. Unown B).', S),
        'is_default_variety': ('1 if the form belongs to the default variety of the species.', I),
        'is_default_form': ('1 if this is the default form of its variety. is_default_form == 1 gives one row per '
                            'variety; add is_default_variety == 1 for one row per species.', I),
        'is_battle_only': ('1 if the form only exists in battle (Megas, Zen Mode, ...).', I),
        'is_mega': ('1 for Mega Evolutions (incl. Legends: Z-A and Mega Dimension).', I),
        'is_gigantamax': ('1 for Gigantamax forms.', I),
        'is_regional_variant': ('1 for regional forms (Alolan, Galarian, Hisuian, Paldean).', I),
        'region': ('Region of a regional or totem form.', S),
        'introduced_in': ('Games the form was introduced in (e.g. "X / Y").', S),
        'introduced_gen': ('Generation the form was introduced in (I–IX).', S),
        'abilities_0': ('First regular ability (blank for 9 Mega Dimension Megas not yet in a game with abilities).', S),
        'image_file': ('Bundled artwork for this form, relative to images/ (e.g. "alt_images/006Charizard-Mega_X.png").', S),
    },
    'evolutions.csv': {
        'evolution_id': ('Unique id of this evolution method.', I),
        'evolution_chain_id': ('Evolution family id; every species in a family shares it.', I),
        'from_national_number': ('National number of the species that evolves.', I),
        'from_name': ('Name of the species that evolves.', S),
        'from_form': ('Form required to evolve, when not the default (e.g. "Galarian Farfetch\'d").', S),
        'to_national_number': ('National number of the species it evolves into.', I),
        'to_name': ('Name of the species it evolves into.', S),
        'to_form': ('Form produced, when not the default (e.g. "Alolan Raichu").', S),
        'trigger': ('Evolution trigger (Level up, Use item, Trade or Linking Cord, Spin, ...).', S),
        'min_level': ('Minimum level.', I),
        'item': ('Item used on the Pokémon (e.g. Thunder Stone).', S),
        'held_item': ('Item the Pokémon must hold.', S),
        'known_move': ('Move the Pokémon must know.', S),
        'known_move_type': ('Type of a move the Pokémon must know.', S),
        'min_happiness': ('Minimum friendship.', I),
        'min_affection': ('Minimum affection hearts (Gen VI–VII).', I),
        'min_beauty': ('Minimum Beauty (Feebas).', I),
        'time_of_day': ('day, night, dusk or full-moon.', S),
        'gender': ('Required gender (female or male).', S),
        'location': ('Location where the Pokémon must level up.', S),
        'region': ('Region where the method applies (e.g. Alola for Alolan Raichu).', S),
        'party_species': ('Species that must be in the party.', S),
        'party_type': ('Type of a Pokémon that must be in the party.', S),
        'trade_species': ('Species it must be traded for.', S),
        'relative_physical_stats': ('Tyrogue: 1 = Attack > Defense, 0 = equal, -1 = Attack < Defense.', I),
        'needs_overworld_rain': ('1 if it must be raining.', I),
        'turn_upside_down': ('1 if the console must be held upside down (Inkay).', I),
        'used_move': ('Move that must be used a number of times.', S),
        'min_move_count': ('Times used_move must be used.', I),
        'min_steps': ("Steps to walk in Let's Go mode.", I),
        'min_damage_taken': ('HP that must be lost first.', I),
        'chance_percent': ('Chance of this outcome when random (e.g. Maushold Family of Three, 1%).', I),
        'condition': ('The method as one readable sentence.', S),
        'games': ('Games in which this method was recorded.', S),
        'is_primary_method': ('1 = method used in current games; 0 = legacy or game-specific alternative.', I),
    },
    'moves.csv': {
        'move_id': ('Unique move id. Primary key.', I),
        'name': ('English move name.', S),
        'identifier': ('Lower-case slug (e.g. thunder-punch).', S),
        'type': ('Move type.', S),
        'damage_class': ('physical, special or status.', S),
        'power': ('Base power (blank for status and variable-power moves).', I),
        'accuracy': ('Accuracy in percent (blank if the move never misses).', I),
        'pp': ('Power points.', I),
        'priority': ('Priority bracket (-7 to +5).', I),
        'target': ('What the move targets (e.g. selected-pokemon, all-opponents).', S),
        'generation': ('Generation the move was introduced.', S),
        'effect_chance': ('Chance (%) of the secondary effect.', I),
        'short_effect': ('Short description of the effect (blank for some recent moves).', S),
        'flavor_text': ('In-game description from the most recent game that has one.', S),
        'meta_category': ('Effect category (damage, ailment, damage+lower, heal, ...).', S),
        'ailment': ('Status condition the move can cause (e.g. Paralysis).', S),
        'ailment_chance': ('Chance (%) of the ailment (0 = always, for status moves).', I),
        'crit_rate': ('Critical-hit stage bonus.', I),
        'drain': ('HP drained (+) or recoil (-) as % of damage dealt.', I),
        'healing': ("HP healed as % of the user's max HP.", I),
        'flinch_chance': ('Chance (%) to flinch.', I),
        'stat_chance': ('Chance (%) of the stat change.', I),
        'min_hits': ('Minimum hits (multi-hit moves).', I),
        'max_hits': ('Maximum hits (multi-hit moves).', I),
        'min_turns': ('Minimum turns (multi-turn moves).', I),
        'max_turns': ('Maximum turns (multi-turn moves).', I),
    },
    'pokemon_moves.csv': {
        'pokemon': ('Variety name (e.g. "Alolan Raichu").', S),
        'move': ('English move name.', S),
        'method': ('How it is learned: Level up, Machine (TM/TR/HM), Egg, Tutor, Train, Move reminder, ...', S),
        'level': ('Level it is learned at (Level up only; 0 or 1 = on evolution / at start).', I),
    },
    'abilities.csv': {
        'name': ('English ability name ("As One" appears twice: the Glastrier and Spectrier versions).', S),
        'identifier': ('Lower-case slug.', S),
        'generation': ('Generation the ability was introduced.', S),
        'short_effect': ('Short description of the effect.', S),
        'effect': ('Full description of the effect.', S),
        'flavor_text': ('In-game description from the most recent game.', S),
        'species_count': ('Number of species whose default form can have the ability.', I),
    },
    'pokemon_abilities.csv': {
        'pokemon': ('Variety name.', S),
        'ability': ('English ability name.', S),
        'slot': ('1 or 2 = regular ability, 3 = hidden ability.', I),
        'is_hidden': ('1 if this is the hidden ability.', I),
    },
    'items.csv': {
        'name': ('English item name.', S),
        'identifier': ('Lower-case slug.', S),
        'category': ('Item category (e.g. Mega Stones, TM materials, Dynamax crystals, Picnic).', S),
        'pocket': ('Bag pocket: Items, Medicine, Poké Balls, Battle Items, Berries, Mail, TMs and HMs or Key Items.', S),
        'cost': ('Shop price in Pokédollars (0 = cannot be bought).', I),
        'fling_power': ('Base power when used with Fling.', I),
        'fling_effect': ('Extra effect when flung.', S),
        'short_effect': ('Short description of the effect.', S),
        'effect': ('Full description of the effect.', S),
        'flavor_text': ('In-game description from the most recent game.', S),
    },
    'natures.csv': {
        'nature_id': ('Nature id.', I),
        'name': ('Nature name.', S),
        'increased_stat': ('Stat raised by 10% (blank for neutral natures).', S),
        'decreased_stat': ('Stat lowered by 10% (blank for neutral natures).', S),
        'likes_flavor': ('Favourite berry flavor.', S),
        'hates_flavor': ('Disliked berry flavor.', S),
        'is_neutral': ('1 for the five natures that change no stat.', I),
    },
    'type_chart.csv': {
        'attacking_type': ('Type of the attacking move.', S),
        'defending_type': ('Type of the defending Pokémon.', S),
        'multiplier': ('Damage multiplier (0, 0.5, 1 or 2; Gen VI+ chart).', N),
    },
    'pokedex_entries.csv': {
        'species': ('English species name.', S),
        'game': ('Game the entry is from (e.g. "Scarlet").', S),
        'text': ('Pokédex entry text.', S),
    },
    'pokemon_names.csv': {
        'name': ('Species name in that language.', S),
        'genus': ('Species category in that language (e.g. "Seed Pokémon"); blank for ja-roma.', S),
    },
    'encounters.csv': {
        'encounter_id': ('Unique encounter id.', I),
        'pokemon': ('Variety name.', S),
        'game': ('Game (e.g. "Pearl").', S),
        'region': ('Region of the location.', S),
        'location': ('Location (e.g. "Route 201").', S),
        'area': ('Part of the location, when it has several (e.g. "Mount Mortar (1F)").', S),
        'method': ('How it is encountered (e.g. "Walking in tall grass or a cave", "Fishing with a Super Rod", "Surfing").', S),
        'min_level': ('Minimum level.', I),
        'max_level': ('Maximum level.', I),
        'rarity': ('Encounter slot rate in percent.', I),
        'conditions': ('Conditions that must hold, joined with "; " (time of day, season, swarms, Max Raid difficulty, ...).', S),
    },
    'pokedex_numbers.csv': {
        'pokedex': ('Pokédex name (e.g. "Kanto", "Original Johto", "Blueberry", "Lumiose").', S),
        'pokedex_identifier': ('Pokédex slug.', S),
        'region': ('Region of the Pokédex (blank for the National and other non-regional dexes).', S),
        'number': ('Number of the species in that Pokédex.', I),
    },
    'machines.csv': {
        'machine': ('Machine name (TM01, HM05, TR12, ...).', S),
        'move': ('English move name.', S),
    },
    'version_groups.csv': {
        'version_group_id': ('Version group id.', I),
        'games': ('Games in the group (e.g. "Scarlet / Violet").', S),
        'order': ('Release order.', I),
    },
    'images.csv': {
        'image_file': ('Path relative to images/ (e.g. "small_images/001.png"). Primary key.', S),
        'image_set': ('small_images (215 px), large_images (300–1280 px), alt_images (alternate forms), '
                      'shiny_images (shiny artwork), home_images and home_shiny_images (Pokémon HOME 3D renders, '
                      '512 px) or animated_sprites (GIF battle sprites).', S),
        'file_name': ('File name.', S),
        'form_label': ('Form label parsed from an alt_images file name (e.g. "Mega X").', S),
        'form_id': ('Form the image shows; joins to pokemon_forms.csv. Blank for 4 non-battle variants.', I),
        'width': ('Width in pixels.', I),
        'height': ('Height in pixels.', I),
    },
    'cries.csv': {
        'audio_file': ('Path relative to audio/ (e.g. "cries/0025-pikachu.ogg"). Primary key.', S),
        'cry_set': ('cries (current cry) or cries_legacy (original Gen I–V cry).', S),
        'file_name': ('File name.', S),
        'format': ('ogg (Vorbis) or mp3.', S),
        'duration_s': ('Duration in seconds.', N),
        'sample_rate': ('Sample rate in Hz.', I),
        'channels': ('Number of audio channels.', I),
    },
    'competitive_tiers.csv': {
        'showdown_id': ('Pokémon Showdown species id (e.g. ogerponwellspring).', S),
        'name': ('Pokémon Showdown name (e.g. "Ogerpon-Wellspring").', S),
        'form_id': ('Matching form; blank for Ogerpon\'s Tera formes, which PokeAPI does not list.', I),
        'tier': ('Current Smogon singles tier (Uber, OU, UUBL, UU, RU, NU, PU, ZU, LC, NFE, Illegal, ...).', S),
        'doubles_tier': ('Current Smogon doubles tier (DUber, DOU, DUU, ...; in brackets = unranked).', S),
        'natdex_tier': ('Current National Dex tier.', S),
        'is_nonstandard': ('Why the Pokémon is not in current standard play: Past (not in Gen IX), Future, LGPE, ...', S),
    },
    'smogon_usage.csv': {
        'period': ('Month of the statistics (YYYY-MM; a few special periods such as 2020-11-H1 cover half months '
                   'or DLC launches).', S),
        'gen': ('Generation of the format (1–9).', I),
        'format': ('Smogon format (e.g. gen9ou, gen9vgc2026regf). Unprefixed formats before July 2017 are Gen VI.', S),
        'pokemon': ('Pokémon name as used by Smogon (e.g. "Ogerpon-Wellspring").', S),
        'pokemon_id': ('Matching variety id (blank when the form is not in PokeAPI).', I),
        'rank': ('Usage rank at the 1500 rating cutoff.', I),
        'usage_pct': ('Weighted usage % at the 1500 cutoff: share of teams with the Pokémon.', N),
        'raw_count': ('Number of teams with the Pokémon (unweighted).', I),
        'real_count': ('Number of times it was actually sent into battle.', I),
        'total_battles': ('Battles in the format that month.', I),
        'top_cutoff': ('Highest rating cutoff Smogon published for the format that month (1630, 1695, 1760 or 1825).', I),
        'rank_top': ('Usage rank at the top cutoff (blank if not used there).', I),
        'usage_pct_top': ('Weighted usage % among the highest-rated players (top cutoff).', N),
    },
}

RESOURCES = {
    'pokemon_utf8.csv': 'One row per species: all 1,025 Pokémon (Gen I–IX), UTF-8. The recommended starting file (72 columns).',
    'pokemon.csv': "Identical data in the original UTF-16, tab-separated format (encoding='utf-16', sep='\\t'), kept for older notebooks.",
    'pokemon_stats.csv': 'The six base stats in long format: one row per (species, stat).',
    'pokemon_forms.csv': 'One row per form (1,578): Megas, Gigantamax, regional forms, alternate formes and cosmetic variants, each with its own types, stats, abilities, matchups and artwork.',
    'evolutions.csv': 'One row per evolution method (702), with structured conditions and a readable sentence.',
    'moves.csv': 'Every move (920): type, category, power, accuracy, PP, priority, effects and battle mechanics.',
    'pokemon_moves.csv': 'Learnsets: who learns which move, how and at what level, in every game from Red/Green to Legends: Z-A.',
    'abilities.csv': 'Every ability (314) with its effect and in-game text.',
    'pokemon_abilities.csv': 'Which ability each variety can have, in which slot (regular or hidden).',
    'items.csv': 'Every item (2,221): category, bag pocket, price, Fling data and effect text.',
    'natures.csv': 'The 25 natures: stat raised, stat lowered and berry flavors.',
    'type_chart.csv': 'The 18 × 18 type chart, one row per (attacking type, defending type).',
    'pokedex_entries.csv': 'Every Pokédex entry from every game, in 11 languages (98,396 entries).',
    'pokemon_names.csv': 'Species names and categories in 12 languages.',
    'encounters.csv': 'Where and how each Pokémon can be caught in each game, with levels, rates and conditions (117,585 rows).',
    'pokedex_numbers.csv': 'Each species\' number in every regional Pokédex.',
    'machines.csv': 'Which move each TM, HM and TR teaches in each game.',
    'version_groups.csv': 'Lookup of game groups used by the learnset and machine tables.',
    'images.csv': 'Manifest of every image: species, the exact form shown, its types, size and a fixed species-level train/val/test split.',
    'cries.csv': 'Manifest of every cry (current and original Gen I–V): species, form, format, duration and split.',
    'competitive_tiers.csv': 'Current Smogon tiers (singles, doubles, National Dex) for every species and form, from Pokémon Showdown.',
    'smogon_usage.csv': 'Monthly Smogon usage statistics, November 2014 to October 2026: 170 standard formats of every generation (OU to ZU, Ubers, LC, Monotype, Doubles, National Dex, VGC, Battle Stadium), every Pokémon on at least 1% of teams, at the standard and top-ladder rating cutoffs.',
}


def fields(name):
    sep, enc = ('\t', 'utf-16') if name == 'pokemon.csv' else (',', 'utf-8')
    cols = list(pd.read_csv(DATA / name, nrows=0, sep=sep, encoding=enc).columns)
    out = []
    for c in cols:
        desc = DOCS.get(name, {}).get(c) or COMMON.get(c)
        if desc is None:
            raise SystemExit(f'{name}: column {c} is not documented in build_metadata.py')
        out.append({'name': c, 'description': desc[0], 'type': desc[1]})
    return out


def main():
    path = ROOT / 'dataset-metadata.json'
    meta = json.loads(path.read_text())
    meta['title'] = 'The Complete Pokédex Dataset (Gen I–IX)'
    meta['subtitle'] = '1,025 Pokémon: forms, moves, Smogon usage, artwork, cries & SQL'
    meta['description'] = (ROOT / 'docs' / 'kaggle_description.md').read_text()
    meta['userSpecifiedSources'] = (
        'Serebii.net (species stats, breeding, legendary status), pokemon.com (Pokédex descriptions), Bulbapedia '
        '(bundled artwork), the PokéAPI CSV database (https://github.com/PokeAPI/pokeapi, BSD-3-Clause; forms, '
        'evolutions, moves, learnsets, abilities, items, Pokédex entries, encounters and the added species fields), '
        'PokéAPI sprites and cries (https://github.com/PokeAPI/sprites, https://github.com/PokeAPI/cries), '
        'Pokémon Showdown (https://github.com/smogon/pokemon-showdown, MIT; tiers) and Smogon usage statistics '
        '(https://www.smogon.com/stats/). Built with the reproducible pipeline in scripts/ and checked by scripts/validate.py.')
    resources = []
    for name, desc in RESOURCES.items():
        r = {'path': name, 'description': desc}  # Kaggle layout: data files sit at the dataset root
        if name != 'pokemon.csv':
            r['schema'] = {'fields': fields(name)}
        resources.append(r)
    resources.append({'path': 'pokedex.sqlite',
                      'description': 'Every table in one SQLite database with primary and foreign keys (pokemon_utf8.csv '
                                     'is the table `pokemon`; learnsets and Smogon usage use integer keys with lookup tables).'})
    on_disk = {p.name for p in DATA.glob('*.csv')}
    missing = on_disk - set(RESOURCES)
    if missing:
        raise SystemExit(f'CSV files without a resource description: {sorted(missing)}')
    meta['resources'] = [r for r in resources if r['path'] == 'pokedex.sqlite' or r['path'] in on_disk]
    path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + '\n')
    n = sum(len(r.get('schema', {}).get('fields', [])) for r in meta['resources'])
    print(f'dataset-metadata.json: {len(meta["resources"])} resources, {n} documented columns; '
          f'subtitle {len(meta["subtitle"])} chars')


if __name__ == '__main__':
    main()
