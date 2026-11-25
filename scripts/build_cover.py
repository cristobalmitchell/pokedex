"""Render dataset-cover-image.png (1280 x 640), the Kaggle cover of The Complete Pokédex Dataset.

A navy gradient with a faint mosaic of the official artwork, the title, a one-line summary computed
from the data, and a row of legendary Pokémon along the bottom edge.

Usage (needs Pillow):
    python scripts/build_cover.py
"""

import random
from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
W, H = 1280, 640
TOP, BOTTOM = (12, 14, 30), (29, 19, 53)   # navy gradient
INK, SUBTLE, ACCENT = (255, 255, 255), (220, 224, 235), (57, 135, 229)
BOLD = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
REGULAR = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
HEROES = [150, 249, 384, 483, 643, 716, 791, 888, 1007]  # Mewtwo ... Koraidon


def gradient():
    im = Image.new('RGB', (W, H))
    px = im.load()
    for y in range(H):
        t = y / (H - 1)
        c = tuple(round(a + (b - a) * t) for a, b in zip(TOP, BOTTOM))
        for x in range(W):
            px[x, y] = c
    return im.convert('RGBA')


def mosaic(base, tile=72, alpha=0.09, seed=7):
    files = sorted((ROOT / 'images' / 'small_images').glob('*.png'))
    rng = random.Random(seed)
    layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    for y in range(-tile // 2, H, tile):
        for x in range(-tile // 2 + (y // tile % 2) * tile // 2, W, tile):
            sprite = Image.open(rng.choice(files)).convert('RGBA').resize((tile - 8, tile - 8), Image.LANCZOS)
            a = sprite.getchannel('A').point(lambda v: int(v * alpha))
            sprite.putalpha(a)
            layer.alpha_composite(sprite, (x + 4, y + 4))
    base.alpha_composite(layer)


def fit_font(path, text, width, start):
    size = start
    while size > 10:
        f = ImageFont.truetype(path, size)
        if f.getlength(text) <= width:
            return f
        size -= 2
    return ImageFont.truetype(path, size)


def heroes(base, height=225, overlap=0.30):
    imgs = []
    for n in HEROES:
        im = Image.open(ROOT / 'images' / 'large_images' / f'{n:03d}.png').convert('RGBA')
        im = im.crop(im.getbbox())
        im = im.resize((round(im.width * height / im.height), height), Image.LANCZOS)
        imgs.append(im)
    step = (W + 40) / len(imgs)
    for i, im in enumerate(imgs):
        cx = -20 + step * (i + 0.5)
        base.alpha_composite(im, (round(cx - im.width / 2), H - height + 18))


def main():
    m = pd.read_csv(ROOT / 'data' / 'pokemon_utf8.csv')
    forms = pd.read_csv(ROOT / 'data' / 'pokemon_forms.csv')
    tables = len([p for p in (ROOT / 'data').glob('*.csv') if p.name != 'pokemon.csv'])
    subtitle = f'{len(m):,} Pokémon  ·  {len(forms):,} forms  ·  {tables} tables  ·  art & cries'

    im = gradient()
    mosaic(im)
    heroes(im)
    d = ImageDraw.Draw(im)
    title = fit_font(BOLD, 'The Complete Pokédex', 1130, 96)
    for text, y in (('The Complete Pokédex', 62), ('Dataset', 152)):
        w = title.getlength(text)
        d.text(((W - w) / 2, y), text, font=title, fill=INK)
    w = title.getlength('Dataset')
    d.rounded_rectangle(((W - w) / 2 + 40, 244, (W + w) / 2 - 40, 250), radius=3, fill=ACCENT)
    sub = fit_font(REGULAR, subtitle, 1080, 36)
    d.text(((W - sub.getlength(subtitle)) / 2, 278), subtitle, font=sub, fill=SUBTLE)
    im.convert('RGB').save(ROOT / 'dataset-cover-image.png', optimize=True)
    print('dataset-cover-image.png:', subtitle)


if __name__ == '__main__':
    main()
