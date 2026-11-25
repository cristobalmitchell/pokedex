# The Complete Pokédex Dataset

Every **released Pokémon** (all 1,025 species from Red/Green to Scarlet/Violet and its DLC) with every **form**, **evolution**, **move**, **learnset**, **ability**, **item**, **Pokédex entry** and **wild encounter**. It also includes **520,661 monthly Smogon usage records since 2014**, current competitive tiers, **7,696 images** across seven art styles and **2,024 cries**, all linked by key and packaged as one SQLite database.

## What's inside

**Pokémon**

| File | Rows | One row per |
|---|---|---|
| `pokemon_utf8.csv` | 1,025 | species: types, stats, abilities, type matchups, breeding, EV yield, evolution chain, Megas, names, description (72 columns) |
| `pokemon_forms.csv` | 1,578 | form: 97 Megas, 34 Gigantamax, 58 regional forms, alternate formes and cosmetic variants, each with its own stats, types and abilities |
| `evolutions.csv` | 702 | evolution method |
| `pokemon_stats.csv` | 6,150 | (species, base stat), long format |

**Battle**

| File | Rows | One row per |
|---|---|---|
| `moves.csv` | 920 | move: type, category, power, accuracy, PP, effects |
| `pokemon_moves.csv` | 665,810 | learnset entry, every game from Red/Green to Legends: Z-A |
| `abilities.csv` / `pokemon_abilities.csv` | 314 / 2,943 | ability with its effect / who can have it |
| `natures.csv` / `type_chart.csv` | 25 / 324 | nature / (attacking type, defending type) |
| `competitive_tiers.csv` | 1,380 | Pokémon Showdown entry with its current Smogon tiers |
| `smogon_usage.csv` | 520,661 | (month, format, Pokémon) usage share for every Pokémon on at least 1% of teams, across 170 formats and 152 monthly periods (Nov 2014 – Oct 2026) |

**World**

| File | Rows | One row per |
|---|---|---|
| `pokedex_entries.csv` | 98,396 | Pokédex entry, every game, 11 languages |
| `pokemon_names.csv` | 12,300 | (species, language) name and category |
| `encounters.csv` | 117,585 | wild encounter: game, location, method, levels, rate, conditions |
| `items.csv` / `machines.csv` | 2,221 / 2,508 | item / TM, HM or TR per game |
| `pokedex_numbers.csv` / `version_groups.csv` | 8,010 / 32 | regional dex number / game lookup |

**Images and audio**

| File | Rows | One row per |
|---|---|---|
| `images.csv` | 7,696 | image: species, exact form shown, types, size, fixed train/val/test split |
| `cries.csv` | 2,024 | cry: species, form, format, duration, split |
| `pokedex.sqlite` | | all of the above, with primary and foreign keys |

**Image folders:**
- `small_images` (215 px official artwork)
- `large_images` (up to 1280 px)
- `alt_images` (360 alternate forms)
- `shiny_images` (shiny artwork)
- `home_images` and `home_shiny_images` (Pokémon HOME 3D renders)
- `animated_sprites` (animated GIFs)

**Audio folders:** `cries` (current) and `cries_legacy` (the original Gen I–V cries).

## Quick start

```python
import pandas as pd
pokemon = pd.read_csv('/kaggle/input/pokedex/pokemon_utf8.csv')
usage = pd.read_csv('/kaggle/input/pokedex/smogon_usage.csv')
ou = usage[(usage.format == 'gen9ou') & (usage.period == '2026-10')].nsmallest(10, 'rank')
ou.merge(pokemon[['national_number', 'primary_type', 'base_total']], on='national_number')
```

```python
import sqlite3
con = sqlite3.connect('/kaggle/input/pokedex/pokedex.sqlite')
pd.read_sql('''
    SELECT e.game, e.location, e.method, e.min_level, e.max_level, e.rarity
    FROM encounters e JOIN pokemon p ON p.national_number = e.national_number
    WHERE p.english_name = 'Dratini' AND e.game IN ('FireRed', 'HeartGold')''', con)
```

## Ideas
- **Image classification:** predict type from artwork. The split is by species, so forms of one Pokémon never leak across splits. Seven art styles make it a domain-shift benchmark (official art → 3D renders → pixel sprites), and the shiny/normal pairs support colour-transfer work.
- **Audio:** classify cries by species, type or generation, or compare the original and current cries.
- **Competitive play:** forecast monthly usage, find when the metagame shifted, link usage to stats, typings and abilities, and build teams from learnsets.
- **NLP and translation:** Pokédex entries across 38 games and 11 languages.
- **Tabular modelling:** legendary classification, stat archetypes, clustering.
- **Graphs:** evolution trees.
- **SQL practice:** the 23 tables of `pokedex.sqlite`, joined by keys.

## Quality
- **Validation:** `scripts/validate.py` checks every table. It checks keys, foreign keys and value ranges. It recomputes the type matchups from the type chart and confirms that species, forms, abilities, names, images and cries agree across tables. It also checks that file names are Kaggle-safe and that every column is documented.
- **Corrections:** the species table was cross-checked against PokéAPI and current game data. Version 3 corrected abilities on 34 species and categories on 19.

## License
- **Dataset:** [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/). Credit *"The Complete Pokédex Dataset by Cristobal Mitchell"*, use it non-commercially, and share derived datasets under the same license.
- **Third-party material** keeps its own terms, listed below and in the repository's `DATA_LICENSE.md`.
- **Code:** the build scripts and notebooks on GitHub are MIT-licensed.
- **No affiliation:** not affiliated with or endorsed by Nintendo, The Pokémon Company, Creatures Inc., GAME FREAK inc., PokéAPI or Smogon.

## Sources and credits
- **Species data:** Serebii.net
- **Pokédex descriptions:** pokemon.com
- **Bundled artwork:** Bulbapedia
- **Forms, evolutions, moves, learnsets, abilities, items, Pokédex entries, encounters and the added species fields:** [PokéAPI](https://github.com/PokeAPI/pokeapi). Copyright © 2013–2023 Paul Hallett and PokéAPI contributors, BSD-3-Clause.
- **Shiny, HOME and animated sprites, and cries:** [PokéAPI sprites](https://github.com/PokeAPI/sprites) and [cries](https://github.com/PokeAPI/cries)
- **Tiers:** [Pokémon Showdown](https://github.com/smogon/pokemon-showdown) (MIT)
- **Usage statistics:** [Smogon](https://www.smogon.com/stats/)
- **Trademarks:** Pokémon and Pokémon character names are trademarks of Nintendo. Artwork and cries are © Nintendo, Creatures Inc. and GAME FREAK and are included for non-commercial research and education.

**Companion dataset:** [The Complete Pokémon TCG Dataset](https://www.kaggle.com/datasets/cristobalmitchell/pokemon-tcg) has every English trading card, linked to these species by Pokédex number.

The pipeline is reproducible: `bash scripts/build_all.sh` rebuilds everything from the sources. It's on [GitHub](https://github.com/cristobalmitchell/pokedex).
