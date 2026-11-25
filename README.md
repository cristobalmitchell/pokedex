
<center>
  <img src="dataset-cover-image.png" />
</center>

# The Complete Pokédex Dataset
Every **released Pokémon** (all **1,025 species** from Gen I Red/Green to Gen IX Scarlet/Violet and its DLC, #0001 Bulbasaur to #1025 Pecharunt) plus every **form**, **evolution method**, **move** and **learnset**. It includes **2,410 artworks** linked to the data, and the whole dataset is also available as one **SQLite database**. It is on Kaggle as [The Complete Pokédex Dataset](https://www.kaggle.com/cristobalmitchell/pokedex).

Species data is scraped from Serebii's Pokédex, with official descriptions from pokemon.com and artwork from Bulbapedia. Forms, evolutions, moves and learnsets are built from the [PokéAPI](https://github.com/PokeAPI/pokeapi) database. Both pipelines are in this repository and can be re-run.

## Files

| File | Rows | One row per |
|---|---|---|
| [`data/pokemon_utf8.csv`](#pokemon_utf8csv--species) | 1,025 | species (70 columns). **Start here** |
| `data/pokemon.csv` | 1,025 | the same data in the original UTF-16, tab-separated format (`encoding='utf-16', sep='\t'`) |
| `data/pokemon_stats.csv` | 6,150 | (species, base stat), long format for plotting |
| [`data/pokemon_forms.csv`](#pokemon_formscsv--forms) | 1,578 | form: Megas, Gigantamax, regional forms, alternate formes, cosmetic variants |
| [`data/evolutions.csv`](#evolutionscsv--evolution-methods) | 702 | evolution method |
| [`data/moves.csv`](#movescsv--moves) | 920 | move |
| [`data/pokemon_moves.csv`](#pokemon_movescsv--learnsets) | 665,810 | learnset entry (who learns what, how, in which game) |
| [`data/images.csv`](#imagescsv--image-manifest) | 2,410 | artwork |
| [`data/pokedex.sqlite`](#pokedexsqlite) | | all of the above as one database with keys |

### How the tables join
```
pokemon (national_number) ─┬─< pokemon_forms (national_number, pokemon_id, form_id) ─┬─< images (form_id)
                           ├─< evolutions (from_national_number / to_national_number)  └─< pokemon_moves (pokemon_id) >── moves (move_id)
                           └─< pokemon_stats (national_number)
```
`national_number` identifies a species. `pokemon_id` identifies a *variety*: forms with their own battle data, such as Alolan Raichu or Mega Charizard X, have their own `pokemon_id`, and learnsets are keyed on it. `form_id` identifies a single form, including cosmetic ones such as Unown B or a Vivillon pattern.

## Imagesets
The images folder holds:
* **small_images:** official artwork for all 1,025 primary forms at 215 x 215 pixels
* **large_images:** high-resolution artwork for all 1,025 primary forms, from 300 x 300 to 1280 x 1280 pixels
* **alt_images:** 360 artworks of variant forms (regional forms, Mega Evolutions including Legends: Z-A / Mega Dimension, Gigantamax, etc.), from 215 x 215 to 1280 x 1280 pixels
* **type_icons:** the 18 type icons

`data/images.csv` indexes every artwork. It gives the species, the exact form shown, that form's types, the pixel size, and a fixed `train` / `val` / `test` split.

## Notebooks and scripts
* **`pokedex.ipynb`** is the scraper that builds the species table and the imagesets.
* **`scripts/build_tables.py`** builds the companion tables and `pokedex.sqlite` from the [PokéAPI CSV database](https://github.com/PokeAPI/pokeapi/tree/master/data/v2/csv). It also adds new species fields to `pokemon_utf8.csv` / `pokemon.csv`. Re-running it produces identical files.
  ```bash
  git clone --depth 1 --filter=blob:none --sparse https://github.com/PokeAPI/pokeapi.git
  git -C pokeapi sparse-checkout set data/v2/csv
  python scripts/build_tables.py pokeapi/data/v2/csv
  ```
* **`scripts/validate.py`** runs the integrity checks: keys, stat ranges, base stat totals, EV yields, gender ratios, every `against_*` value recomputed from the type chart, agreement between tables, file names Kaggle accepts, and metadata that matches each file's columns. Run it before every upload.
* **`notebooks/pokedex_eda.ipynb`** is a starter exploratory analysis ready to fork on Kaggle. It covers type distribution, base-stat distributions, a legendary comparison, generation trends, stat correlations and a type-defence profile.

## Dataset

### `pokemon_utf8.csv`: species
All 1,025 Pokémon from Gen I to Gen IX, one row each. `pokemon_utf8.csv` (UTF-8, comma-separated, loads with a plain `pandas.read_csv()`) and `pokemon.csv` (UTF-16, tab-separated) hold identical data.

* **national_number:** The entry number of the Pokémon in the National Pokédex
* **gen:** The numbered generation in which the Pokémon was first introduced (I–IX; #899–#905 from Legends: Arceus count as Gen VIII)
* **english_name:** The English name of the Pokémon
* **japanese_name:** The original Japanese name of the Pokémon (romanized)
* **primary_type:** The primary type of the Pokémon (primary form)
* **secondary_type:** The secondary type of the Pokémon (primary form; blank for single-type Pokémon)
* **classification:** The classification of the Pokémon as described by its most recent Pokédex
* **color:** Pokédex color, used by the in-game Pokédex search
* **shape:** Pokédex body shape (e.g. Quadruped, Upright, Humanoid)
* **habitat:** Habitat from the FireRed/LeafGreen Pokédex. Only Gen I–III species have one
* **percent_male:** The percentage of the species that are male (blank if the Pokémon is genderless). Exact species ratios, always a multiple of 12.5
* **percent_female:** The percentage of the species that are female (blank if the Pokémon is genderless)
* **height_m:** Height of the Pokémon in metres
* **weight_kg:** Weight of the Pokémon in kilograms
* **capture_rate:** Capture rate of the Pokémon (3–255, integer)
* **base_egg_steps:** The number of steps required to hatch an egg of the Pokémon (hatch cycles × 256)
* **base_experience:** Base experience yield when defeated
* **base_friendship:** Friendship a newly caught Pokémon starts with, as in Gen VIII+ games
* **growth_rate:** Experience growth group (Erratic, Fast, Medium Fast, Medium Slow, Slow, Fluctuating)
* **egg_group_1 / egg_group_2:** Egg groups (Undiscovered for species that cannot breed)
* **hp / attack / defense / sp_attack / sp_defense / speed:** The six base stats
* **base_total:** Base stat total
* **ev_yield_*:** Six features with the effort values (EVs) gained for defeating the Pokémon
* **abilities_*:** Four features that denote the abilities the Pokémon can have (up to three regular abilities plus a hidden ability)
* **against_*:** Eighteen features that denote the damage multiplier taken from an attack of each type (pure type-chart multipliers for the primary form; defensive abilities such as Levitate are not factored in)
* **is_sublegendary / is_legendary / is_mythical:** Legendary status flags
* **evochain_*:** Seven features that give the evolution chain. The odd-numbered columns describe how the species in the next column is obtained (e.g. `Level 16`, `Use Thunder Stone`). `evolutions.csv` has the full branching tree
* **gigantamax:** Gigantamax form name, if the Pokémon has one
* **mega_evolution:** Mega Evolution form name, if the Pokémon has one (includes the Mega Evolutions added by Pokémon Legends: Z-A and its Mega Dimension DLC)
* **mega_evolution_alt:** Second Mega form for Pokémon with two Mega Evolutions (e.g. Mega Charizard Y, Mega Raichu Y, Mega Absol Z)
* **description:** Pokédex description from the official Pokémon website

### `pokemon_forms.csv`: forms
One row per form: 1,025 default forms, 97 Megas, 2 Primal Reversions, 34 Gigantamax forms, 58 regional forms, 12 Totem forms, 22 battle-only forms, 137 alternate formes and 191 cosmetic variants. Each row has its own **types, base stats, base stat total, EV yield, abilities, height, weight, base experience and all 18 `against_*` multipliers**, plus `image_file` pointing at its artwork.
* `form_category` is one of `default`, `mega`, `primal`, `gigantamax`, `regional`, `totem`, `battle-only`, `alternate` or `cosmetic`. Cosmetic forms share the default form's battle data.
* `is_default_form == 1` gives one row per variety, meaning one row per distinct set of battle data (1,351 rows).
* Adding `is_default_variety == 1` gives one row per species. Those 1,025 rows agree with `pokemon_utf8.csv`.

### `evolutions.csv`: evolution methods
One row per evolution method. It covers branching evolutions (Eevee, Tyrogue), regional and form-specific evolutions (Alolan Raichu, Galarian Farfetch'd → Sirfetch'd), and the older games' methods (e.g. Moss Rock locations).
* **Structured columns:** `min_level`, `item`, `held_item`, `known_move`, `min_happiness`, `time_of_day`, `gender`, `location`, `trade_species`, `used_move` / `min_move_count`, `chance_percent`, and others.
* **`condition`:** a readable sentence for each method, e.g. *"Level up with high friendship (160+) during the day"*.
* **`is_primary_method`:** marks the method used in current games.

### `moves.csv`: moves
Every move with:
* type and `damage_class` (physical / special / status)
* power, accuracy, PP, priority and target
* generation introduced
* effect text and in-game description
* battle mechanics: ailment and its chance, drain/recoil, healing, crit-rate stage, flinch chance, multi-hit and multi-turn ranges

### `pokemon_moves.csv`: learnsets
Which Pokémon variety learns which move, how (`Level up`, `Machine`, `Egg`, `Tutor`, …), at what level, and in which games (`version_group`, from Red/Green to Legends: Z-A).

### `images.csv`: image manifest
One row per artwork:
* `image_file` (e.g. `alt_images/006Charizard-Mega_X.png`)
* species and `form_id` (the form the image shows)
* `primary_type` / `secondary_type` of that form, ready to use as labels
* pixel size
* `split`

The 70 / 15 / 15 train / val / test split is assigned **by species** and stratified by primary type, so every form of a species stays in the same split.

### `pokedex.sqlite`
Every table above in one SQLite database, with primary keys, foreign keys and indexes. In the database, `pokemon_moves` uses integer keys, with `move_methods` and `version_groups` lookup tables.
```python
import sqlite3, pandas as pd
con = sqlite3.connect('data/pokedex.sqlite')
pd.read_sql("""
    SELECT f.display_name, m.name AS move, pm.level
    FROM pokemon_moves pm
    JOIN pokemon_forms f ON f.pokemon_id = pm.pokemon_id AND f.is_default_form = 1
    JOIN moves m ON m.move_id = pm.move_id
    JOIN move_methods mm ON mm.method_id = pm.method_id
    JOIN version_groups vg ON vg.version_group_id = pm.version_group_id
    WHERE f.identifier = 'charizard' AND mm.method = 'Level up' AND vg.version_group = 'scarlet-violet'
    ORDER BY pm.level""", con)
```

## Credits and licenses
* Species data: [Serebii.net](https://www.serebii.net). Pokédex descriptions: [pokemon.com](https://www.pokemon.com). Artwork: [Bulbapedia](https://bulbapedia.bulbagarden.net).
* Forms, evolutions, moves, learnsets and the species fields added in 2026 (color, shape, habitat, base experience, base friendship, growth rate, egg groups, EV yield) come from the [PokéAPI](https://github.com/PokeAPI/pokeapi) CSV database. Copyright © 2013–2023 Paul Hallett and PokéAPI contributors, used under the BSD-3-Clause license. See [`LICENSE-PokeAPI.md`](LICENSE-PokeAPI.md).
* Pokémon and Pokémon character names are trademarks of Nintendo. The artwork is © Nintendo, Creatures Inc. and GAME FREAK and is included for non-commercial research and education.

## Changelog

### 2026-11: v2, relational release
* **New tables:**
  * `pokemon_forms.csv`: 1,578 forms with their own stats, types, abilities and matchups
  * `evolutions.csv`: 702 evolution methods with structured conditions
  * `moves.csv`: 920 moves
  * `pokemon_moves.csv`: 665,810 learnset rows covering every game
  * `images.csv`: the image manifest with a fixed split
  * `pokedex.sqlite`: every table in one database
* **New species columns:** `color`, `shape`, `habitat`, `base_experience`, `base_friendship`, `growth_rate`, `egg_group_1`, `egg_group_2`, `base_total` and six `ev_yield_*`.
* **Evolution chains:** rewrote the `evochain_*` method text from structured data. 752 cells previously said only "Level" and now give the level or condition. Stray whitespace is gone, the Mime Jr. and Mr. Mime spellings are fixed, and the leftover Galarian fragments on the Slowpoke and Slowbro rows are removed.
* **Corrections** after cross-checking all 1,025 species against PokéAPI and current game data:
  * Cresselia's Defense and Special Defense (120/130 → 110/120), and Zacian's and Zamazenta's Attack (130 → 120), as changed in Scarlet/Violet
  * Melmetal and Zarude are now flagged Mythical
  * Minior's `capture_rate` is now the integer 30, its Meteor Form value; it was previously the text "30 (Meteorite)255 (Core)"
* **Artwork:**
  * `large_images/888.png` and `889.png` showed Crowned Zacian and Zamazenta, which have different types from the base forms. The large images now show the Hero forms, matching `small_images` and the stats.
  * The Crowned artwork moved to `alt_images/888Zacian-Crowned_Sword.png` and `alt_images/889Zamazenta-Crowned_Shield.png`.
* **Validation:** added `scripts/validate.py`.

### 2026: Gen IX update
* Added the 127 missing Pokémon: #899–#905 (Legends: Arceus) and #906–#1025 (Scarlet/Violet, The Teal Mask, The Indigo Disk), collected from Serebii/pokemondb and cross-verified field by field across sources
* Renamed the misspelled column `against_psychict` → `against_psychic`
* Fixed 27 rows where a regional variant's type had leaked into `primary_type`/`secondary_type` (e.g. Rattata was typed normal/dark from Alolan Rattata, and Ponyta fire/psychic from Galarian Ponyta). Types now always describe the primary form, consistent with the `against_*` columns
* Normalized `percent_male`/`percent_female` to the exact in-game gender ratios. The previous values mixed several rounding conventions, e.g. 88.14, 88.1 and 87.5 for the same 7♂:1♀ ratio
* Added the missing `Gigantamax Appletun` form
* Added the Mega Evolutions introduced in Pokémon Legends: Z-A (2025) and its Mega Dimension DLC to `mega_evolution`/`mega_evolution_alt`. 87 species now have Mega forms
* Updated `evochain_*` for species that gained new evolutions in Legends: Arceus and Scarlet/Violet (the Stantler, Ursaring, Basculin, Qwilfish, Sneasel, Scyther, Dunsparce, Girafarig, Mankey/Primeape, Pawniard/Bisharp, Applin, Wooper and Duraludon families)
* Rewrote `pokedex.ipynb` for pandas 2.x and added the Scarlet/Violet Pokédex as the primary scrape source, falling back to Sword/Shield, then Legends: Arceus, then Sun/Moon. The `against_*` columns are now computed exactly from the type chart
* Completed all imagesets through #1025:
  * small_images: official artwork, 215×215
  * large_images: high-resolution artwork, up to 1280×1280
  * new alt_images: the Legends: Z-A and Mega Dimension Mega forms plus the Gen IX alternate forms (Ogerpon masks, Terapagos forms, Palafin Hero, Bloodmoon Ursaluna, Squawkabilly plumages, Koraidon and Miraidon modes, etc.)
* Backfilled alt_images that the pre-Gen VIII curation had missed:
  * all Hisuian regional forms (Growlithe, Arcanine, Voltorb, Electrode, Typhlosion, Qwilfish, Sneasel, Samurott, Lilligant, Zorua, Zoroark, Braviary, Sliggoo, Goodra, Avalugg, Decidueye)
  * Paldean forms (the three Tauros breeds, Wooper)
  * Origin Dialga and Palkia
  * other variants: Eternamax Eternatus, Gigantamax Appletun, Cramorant Gulping/Gorging, Pumpkaboo/Gourgeist sizes, Furfrou trims, Eternal Floette, etc.
