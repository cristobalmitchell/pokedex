"""Build the competitive tables of The Complete Pokédex Dataset.

    data/competitive_tiers.csv   current Smogon / Pokémon Showdown tiers for every species and form
    data/smogon_usage.csv        monthly Smogon usage statistics since November 2014

Sources:
  - Pokémon Showdown (https://github.com/smogon/pokemon-showdown, MIT): data/pokedex.ts and
    data/formats-data.ts for names, forms and tiers.
  - Smogon usage statistics (https://www.smogon.com/stats/): one text file per month, format and
    rating cutoff. Downloaded files are cached, so re-runs only fetch new months.

Usage:
    git clone --depth 1 https://github.com/smogon/pokemon-showdown.git
    python scripts/build_competitive.py pokemon-showdown [--cache .cache/smogon]

Run after build_tables.py (it maps names onto data/pokemon_forms.csv).
"""

import argparse
import json
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
STATS_URL = 'https://www.smogon.com/stats/'
HEADERS = {'User-Agent': 'pokedex-dataset-builder/1.0'}

# Formats kept: the standard Smogon tiers, doubles, National Dex, Anything Goes, 1v1, and the official
# VGC / Battle Stadium / Battle Spot rulesets, for every generation. Novelty and "other metagame"
# formats (Balanced Hackmons, Mix and Mega, randoms, ...) are left out.
CORE = re.compile(r'^(ou|ubers|uu|ru|nu|pu|zu|lc|monotype|doublesou|doublesubers|doublesuu|nationaldex'
                  r'|nationaldexubers|nationaldexuu|nationaldexmonotype|anythinggoes|1v1'
                  r'|vgc\d{4}.*|battlestadium(singles|doubles).*|battlespot(singles|doubles))$')
BASELINE = 1500  # Smogon's standard weighted cutoff
MIN_USAGE = 1.0  # keep a Pokémon in a format-month if at least 1% of teams used it (at either cutoff)
# Names Smogon used before Showdown settled on the current ones.
SMOGON_ALIASES = {'taurospaldea': 'taurospaldeacombat', 'taurospaldeafire': 'taurospaldeablaze',
                  'taurospaldeawater': 'taurospaldeaaqua'}


# --------------------------------------------------------------------------- Showdown data

def read_ts_object(path):
    """Parse a Showdown data file (a TypeScript object literal of plain data) into a dict.

    A small tokenizer turns the literal into JSON: it drops comments, quotes bare keys, converts
    single-quoted strings and removes trailing commas, never touching the inside of a string."""
    src = Path(path).read_text()
    src = src[src.index('= {') + 2:]
    out, i, n = [], 0, len(src)
    while i < n:
        c = src[i]
        if c in '"\'':
            j, buf = i + 1, []
            while src[j] != c:
                if src[j] == '\\':
                    buf.append(src[j:j + 2])
                    j += 2
                    continue
                buf.append(src[j])
                j += 1
            out.append(json.dumps(''.join(buf).replace("\\'", "'")) if c == "'" else src[i:j + 1])
            i = j + 1
        elif src.startswith('//', i):
            i = src.index('\n', i)
        elif src.startswith('/*', i):
            i = src.index('*/', i) + 2
        elif c.isalpha() or c in '_$':
            j = i
            while j < n and (src[j].isalnum() or src[j] in '_$'):
                j += 1
            word = src[i:j]
            k = j
            while k < n and src[k] in ' \t':
                k += 1
            out.append(f'"{word}"' if k < n and src[k] == ':' else word)
            i = j
        elif c.isdigit() and out and out[-1].rstrip()[-1:] in '{,':
            j = i
            while j < n and (src[j].isalnum() or src[j] == '.'):
                j += 1
            k = j
            while k < n and src[k] in ' \t':
                k += 1
            out.append(f'"{src[i:j]}"' if k < n and src[k] == ':' else src[i:j])
            i = j
        else:
            out.append(c)
            i += 1
    text = ''.join(out).rstrip().rstrip(';')
    text = re.sub(r',(\s*[}\]])', r'\1', text)
    return json.loads(text)


def to_id(s):
    return re.sub(r'[^a-z0-9]', '', str(s).lower().replace('é', 'e'))


# Words that differ between Showdown forme names and PokeAPI identifiers without changing the form.
FILLER = {'form', 'forme', 'mode', 'cap', 'style', 'cloak', 'pattern', 'plumage', 'breed', 'mask',
          'size', 'trim', 'flower', 'color', 'the', 'of', 'mane', 'wings'}
TOKEN_ALIASES = {'f': 'female', 'm': 'male', 'eared': 'eared'}
# Showdown formes whose PokeAPI identifier is not a token match.
FORME_OVERRIDES = {'darmanitangalar': 'darmanitan-galar-standard', 'zygarde10': 'zygarde-10',
                   'necrozmaultra': 'necrozma-ultra', 'eternatuseternamax': 'eternatus-eternamax',
                   'marowakalolatotem': 'marowak-totem', 'greninjabond': 'greninja-battle-bond',
                   'rockruffdusk': 'rockruff-own-tempo', 'miniormeteor': 'minior-red-meteor',
                   'mimikyutotem': 'mimikyu-totem-disguised', 'toxtricitygmax': 'toxtricity-amped-gmax',
                   'urshifugmax': 'urshifu-single-strike-gmax'}
# Not in PokeAPI, so mapped to the species only: Ogerpon's four Terastal formes.


def showdown_to_forms(pokedex, forms):
    """Map Showdown species ids to (national_number, pokemon_id, form_id) of data/pokemon_forms.csv.

    Base species map to the species' default form. A forme maps to the form of the same species whose
    identifier tokens (minus the tokens every form of the species shares, minus filler words) equal the
    forme's tokens: 'Raticate-Alola-Totem' = raticate-totem-alola, 'Tauros-Paldea-Combat' =
    tauros-paldea-combat-breed. Varieties (forms with their own battle data) are preferred."""
    default = forms[(forms.is_default_variety == 1) & (forms.is_default_form == 1)].set_index('national_number')
    by_species = {n: g.sort_values(['is_default_form', 'form_id'], ascending=[False, True])
                  for n, g in forms.groupby('national_number')}
    by_ident = forms.set_index('identifier')
    tokens, shared = {}, {}
    for n, g in by_species.items():
        shared[n] = set.intersection(*[set(i.split('-')) for i in g.identifier])
        tokens[n] = [(r.pokemon_id, r.form_id,
                      [t for t in r.identifier.split('-') if t not in shared[n] and t not in FILLER])
                     for r in g.itertuples()]
    out = {}
    for sid, e in pokedex.items():
        num = e.get('num', 0)
        if num <= 0 or num not in default.index:
            continue  # CAP and other fan-made entries
        forme = e.get('forme')
        if sid in FORME_OVERRIDES:
            r = by_ident.loc[FORME_OVERRIDES[sid]]
            out[sid] = (num, int(r.pokemon_id), int(r.form_id))
        elif not forme:
            out[sid] = (num, int(default.loc[num, 'pokemon_id']), int(default.loc[num, 'form_id']))
        else:
            key = [TOKEN_ALIASES.get(to_id(t), to_id(t)) for t in forme.split('-')]
            key = [t for t in key if t and t not in FILLER and t not in shared[num]]
            hit = next(((pid, fid) for pid, fid, k in tokens[num] if set(k) == set(key)), None) or \
                next(((pid, fid) for pid, fid, k in tokens[num] if ''.join(k) == ''.join(key)), None)
            out[sid] = (num, *(hit if hit else (None, None)))
    return out


def build_tiers(pokedex, formats_data, mapping):
    rows = []
    for sid, e in pokedex.items():
        if e.get('num', 0) <= 0 or sid not in mapping:
            continue
        fd = formats_data.get(sid, {})
        num, pid, fid = mapping[sid]
        rows.append({
            'showdown_id': sid,
            'name': e['name'],
            'national_number': num,
            'pokemon_id': pid,
            'form_id': fid,
            'tier': fd.get('tier'),
            'doubles_tier': fd.get('doublesTier'),
            'natdex_tier': fd.get('natDexTier'),
            'is_nonstandard': fd.get('isNonstandard', e.get('isNonstandard')),
        })
    out = pd.DataFrame(rows)
    out[['pokemon_id', 'form_id']] = out[['pokemon_id', 'form_id']].astype('Int64')
    return out.sort_values(['national_number', 'form_id', 'showdown_id']).reset_index(drop=True)


# --------------------------------------------------------------------------- Smogon usage stats

def fetch(url, retries=5):
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=60) as r:
                return r.read()
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)


def normalise_format(name):
    """'ou' (2014-11 .. 2017-06, before Showdown prefixed formats) means Gen VI."""
    m = re.match(r'^gen(\d)(.+)$', name)
    return (int(m.group(1)), m.group(2)) if m else (6, name)


def select_files(cache):
    index = fetch(STATS_URL).decode()
    periods = re.findall(r'href="(\d{4}-\d{2}[^"/]*)/"', index)
    wanted = []
    for period in periods:
        listing = cache / period / '_index.html'
        if not listing.exists() or period >= sorted(periods)[-1]:
            listing.parent.mkdir(parents=True, exist_ok=True)
            listing.write_bytes(fetch(f'{STATS_URL}{period}/'))
        files = re.findall(r'href="([^"/]+)-(\d+)\.txt"', listing.read_text())
        cuts = {}
        for fmt, cut in files:
            gen, base = normalise_format(fmt)
            if CORE.match(base):
                cuts.setdefault(fmt, set()).add(int(cut))
        for fmt, cs in cuts.items():
            for c in {BASELINE, max(cs)} & cs:
                wanted.append((period, fmt, c))
    return wanted


def download(cache, wanted, workers=4):
    todo = [(p, f, c) for p, f, c in wanted if not (cache / p / f'{f}-{c}.txt').exists()]

    def get(item):
        p, f, c = item
        path = cache / p / f'{f}-{c}.txt'
        path.write_bytes(fetch(f'{STATS_URL}{p}/{f}-{c}.txt'))
        time.sleep(0.1)
    with ThreadPoolExecutor(workers) as ex:
        list(ex.map(get, todo))
    return len(todo)


ROW = re.compile(r'^\s*\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*([\d.]+)%\s*\|\s*(\d+)\s*\|\s*([\d.]+)%\s*\|\s*(\d+)\s*\|\s*([\d.]+)%\s*\|')


def parse_usage(path):
    text = path.read_text(errors='replace')
    battles = re.search(r'Total battles:\s*(\d+)', text)
    rows = []
    for line in text.splitlines():
        m = ROW.match(line)
        if m:
            rows.append((int(m.group(1)), m.group(2), float(m.group(3)), int(m.group(4)), int(m.group(6))))
    return (int(battles.group(1)) if battles else None), rows


def build_usage(cache, wanted, names, min_usage=MIN_USAGE):
    by_set = {}
    for period, fmt, cut in wanted:
        by_set.setdefault((period, fmt), []).append(cut)
    rows = []
    for (period, fmt), cuts in sorted(by_set.items()):
        gen, base = normalise_format(fmt)
        top = max(cuts)
        if BASELINE not in cuts:
            continue
        battles, base_rows = parse_usage(cache / period / f'{fmt}-{BASELINE}.txt')
        top_rows = {}
        if top != BASELINE:
            _, tr = parse_usage(cache / period / f'{fmt}-{top}.txt')
            top_rows = {name: (rank, usage) for rank, name, usage, _, _ in tr}
        for rank, name, usage, raw, real in base_rows:
            t = top_rows.get(name) if top != BASELINE else (rank, usage)
            rows.append((period, gen, f'gen{gen}{base}', name, rank, usage, raw, real, battles,
                         top, t[0] if t else None, t[1] if t else None))
    out = pd.DataFrame(rows, columns=['period', 'gen', 'format', 'pokemon', 'rank', 'usage_pct', 'raw_count',
                                      'real_count', 'total_battles', 'top_cutoff', 'rank_top', 'usage_pct_top'])
    # Every file lists each Pokémon used even once (about 480 per format and month); most of that tail
    # is noise, and the full table would be 200 MB. Keep Pokémon at or above min_usage at either cutoff.
    out = out[(out.usage_pct >= min_usage) | (out.usage_pct_top >= min_usage)].reset_index(drop=True)
    ids = out.pokemon.map(to_id).replace(SMOGON_ALIASES)
    out.insert(4, 'national_number', ids.map(lambda i: names.get(i, (None, None))[0]).astype('Int64'))
    out.insert(5, 'pokemon_id', ids.map(lambda i: names.get(i, (None, None))[1]).astype('Int64'))
    out['rank_top'] = out.rank_top.astype('Int64')
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('showdown', help='path to a pokemon-showdown checkout')
    ap.add_argument('--cache', default=str(ROOT / '.cache' / 'smogon'))
    ap.add_argument('--min-usage', type=float, default=MIN_USAGE,
                    help='minimum usage %% (at either cutoff) for a row to be kept; 0 keeps everything')
    args = ap.parse_args()
    sd = Path(args.showdown)
    pokedex = read_ts_object(sd / 'data' / 'pokedex.ts')
    formats_data = read_ts_object(sd / 'data' / 'formats-data.ts')
    forms = pd.read_csv(DATA / 'pokemon_forms.csv')
    mapping = showdown_to_forms(pokedex, forms)
    tiers = build_tiers(pokedex, formats_data, mapping)
    tiers.to_csv(DATA / 'competitive_tiers.csv', index=False)

    # Smogon names are Showdown display names; index both the name and the species id.
    names = {}
    for sid, e in pokedex.items():
        if sid in mapping:
            num, pid, _ = mapping[sid]
            names[to_id(e['name'])] = (num, pid)
            names[sid] = (num, pid)
    cache = Path(args.cache)
    wanted = select_files(cache)
    fetched = download(cache, wanted)
    usage = build_usage(cache, wanted, names, args.min_usage)
    usage.to_csv(DATA / 'smogon_usage.csv', index=False, float_format='%g')
    unmatched = usage[usage.national_number.isna()].pokemon.value_counts()
    print(f'tiers {tiers.shape} ({tiers.pokemon_id.isna().sum()} forms unmapped); usage {usage.shape} from '
          f'{len(wanted)} files ({fetched} downloaded); {usage.period.nunique()} periods, {usage.format.nunique()} formats')
    print(f'usage rows without a national number: {unmatched.sum()} ({len(unmatched)} names)', unmatched.head(15).to_dict())


if __name__ == '__main__':
    main()
