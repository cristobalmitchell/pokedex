
<center>
  <img src="https://www.dylanlf.com/quiz/banner2.png" />
</center>

# The Complete Pokédex Dataset
Web scraping pipeline for collecting Pokémon data from Serebii's Pokédex, with official descriptions from pokemon.com and artwork from Bulbapedia. This dataset is available at Kaggle under [The Complete Pokédex Dataset](https://www.kaggle.com/cristobalmitchell/pokedex)

The dataset covers **every released Pokémon** — all **1,025 species** from Gen I (Red/Green) through Gen IX (Scarlet/Violet and its DLC), #0001 Bulbasaur to #1025 Pecharunt.

## Imagesets
The output imagesets can be found in the images folder and includes the following .png files
* **small_images:** Official artwork for all 1,025 primary forms with 215 x 215 pixel dimensions
* **large_images:** High-resolution artwork for all 1,025 primary forms ranging from 300 x 300 to 1280 x 1280 pixel dimensions
* **alt_images:** Variant-form artwork (regional forms, Mega Evolutions incl. Legends: Z-A / Mega Dimension, Gigantamax, etc.) ranging from 215 x 215 to 1280 x 1280 pixel dimensions

## Notebooks
* **`pokedex.ipynb`** — the reproducible scraper that builds the dataset and imagesets.
* **`notebooks/pokedex_eda.ipynb`** — a starter exploratory analysis (type distribution, base-stat distributions, legendary comparison, generation trends, stat correlations, type-defence profile) ready to fork on Kaggle.

## Dataset
The dataset ships in two identical files: **`data/pokemon_utf8.csv`** (UTF-8, comma-separated — loads with a plain `pandas.read_csv()`, recommended) and **`data/pokemon.csv`** (the original UTF-16, tab-separated format, `encoding='utf-16', sep='\t'`). A tidy long-format of the base stats is in **`data/pokemon_stats.csv`**. Each contains all 1,025 pokémon from Gen I - Gen IX with the following fields

* **national_number:** The entry number of the Pokémon in the National Pokédex
* **gen:** The numbered generation which the Pokémon was first introduced (I–IX; #899–#905 from Legends: Arceus count as Gen VIII)
* **english_name:** The English name of the Pokémon
* **japanese_name:** The Original Japanese name of the Pokémon (romanized)
* **primary_type:** The Primary Type of the Pokémon (primary form)
* **secondary_type:** The Secondary Type of the Pokémon (primary form; blank for mono-typed Pokémon)
* **classification:** The Classification of the Pokémon as described by its most recent Pokédex
* **percent_male:** The percentage of the species that are male (blank if the Pokémon is genderless). Exact species ratios — always a multiple of 12.5
* **percent_female:** The percentage of the species that are female (blank if the Pokémon is genderless)
* **height_m:** Height of the Pokémon in metres
* **weight_kg:** The Weight of the Pokémon in kilograms
* **capture_rate:** Capture Rate of the Pokémon
* **base_egg_steps:** The number of steps required to hatch an egg of the Pokémon (hatch cycles × 256)
* **hp:** The Base HP of the Pokémon
* **attack:** The Base Attack of the Pokémon
* **defense:** The Base Defense of the Pokémon
* **sp_attack:** The Base Special Attack of the Pokémon
* **sp_defense:** The Base Special Defense of the Pokémon
* **speed:** The Base Speed of the Pokémon
* **abilities_*:** Four features that denote abilities that the Pokémon is capable of having (up to three regular abilities plus a hidden ability)
* **against_*:** Eighteen features that denote the amount of damage taken against an attack of a particular type (pure type-chart multipliers for the primary form; defensive abilities such as Levitate are not factored in)
* **is_sublegendary:** Denotes if the Pokémon is sublegendary
* **is_legendary:** Denotes if the Pokémon is legendary
* **is_mythical:** Denotes if the Pokémon is mythical
* **evochain_*:** Seven features that indicate the evolutionary chain and triggers
* **gigantamax:** Form of Pokémon if gigantamax capable
* **mega_evolution:** Form of Pokémon if mega evolution capable (includes the Mega Evolutions added by Pokémon Legends: Z-A and its Mega Dimension DLC)
* **mega_evolution_alt:** Alternative Mega form for Pokémon with two Mega Evolutions (e.g. Mega Charizard Y, Mega Raichu Y, Mega Absol Z)
* **description:** Pokédex description from official Pokémon website

## Changelog

### 2026 — Gen IX update
* Added the 127 missing Pokémon: #899–#905 (Legends: Arceus) and #906–#1025 (Scarlet/Violet, The Teal Mask, The Indigo Disk), collected from Serebii/pokemondb and cross-verified field-by-field across sources
* Renamed misspelled column `against_psychict` → `against_psychic`
* Fixed 27 rows where a regional variant's type had leaked into `primary_type`/`secondary_type` (e.g. Rattata was typed normal/dark from Alolan Rattata; Ponyta fire/psychic from Galarian Ponyta). Types now always describe the primary form, consistent with the `against_*` columns
* Normalized `percent_male`/`percent_female` to the exact in-game species gender ratios (the previous values mixed several rounded display conventions, e.g. 88.14/88.1/87.5 for the same 7♂:1♀ ratio)
* Added the missing `Gigantamax Appletun` form
* Added the Mega Evolutions introduced in Pokémon Legends: Z-A (2025) and its Mega Dimension DLC to `mega_evolution`/`mega_evolution_alt` — 87 species now have Mega forms
* Updated `evochain_*` for species that gained new evolutions in Legends: Arceus / Scarlet/Violet (Stantler, Ursaring, Basculin, Qwilfish, Sneasel, Scyther, Dunsparce, Girafarig, Mankey/Primeape, Pawniard/Bisharp, Applin, Wooper and Duraludon families)
* Rewrote `pokedex.ipynb` for pandas 2.x, added the Scarlet/Violet Pokédex as the primary scrape source with a Sword/Shield → Legends: Arceus → Sun/Moon fallback chain, and switched the `against_*` columns to exact type-chart computation
* Completed all imagesets through #1025: small_images (official artwork, 215×215), large_images (high-resolution artwork, up to 1280×1280) and new alt_images for the Legends: Z-A / Mega Dimension Mega forms plus the Gen IX alternate forms (Ogerpon masks, Terapagos forms, Palafin Hero, Bloodmoon Ursaluna, Squawkabilly plumages, Koraidon/Miraidon modes, etc.)
* Backfilled alt_images the pre-Gen VIII curation had missed: all Hisuian regional forms (Growlithe, Arcanine, Voltorb, Electrode, Typhlosion, Qwilfish, Sneasel, Samurott, Lilligant, Zorua, Zoroark, Braviary, Sliggoo, Goodra, Avalugg, Decidueye), Paldean forms (the three Tauros breeds, Wooper), Origin Dialga/Palkia, and other variants (Eternamax Eternatus, Gigantamax Appletun, Cramorant Gulping/Gorging, Pumpkaboo/Gourgeist sizes, Furfrou trims, Eternal Floette, etc.)
