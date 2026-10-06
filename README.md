# Zelles Serif

The typeface pzelles.com and rankingparty.nyc are set in. One repo, one source
of truth: push a change here and every site that links the stylesheet picks it
up without a deploy.

It is a display cut of [Gentium Book Plus](https://software.sil.org/gentium/)
by SIL International: a flared serif with calligraphic and inscriptional roots,
warm and open. The cut widens the source by 3%, which opens the counters and
gives the capitals a more generous inscriptional proportion at heading sizes,
closes the bowls the source leaves hanging, and pins the three sets of vertical
metrics to the same numbers so every browser draws the same line box.

Four styles: Regular, Italic, Bold, Bold Italic.

## Using it on a site

Link the stylesheet from jsDelivr, which serves this repo straight from GitHub:

```html
<link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/pzelle/zelles-serif@main/zelles-serif.css">
```

```css
font-family: 'Zelles Serif', 'Times New Roman', Times, serif;
```

`@main` follows this branch; jsDelivr refreshes branch URLs within about 12
hours of a push. To force it sooner, open
`https://purge.jsdelivr.net/gh/pzelle/zelles-serif@main/zelles-serif.css`
(and the same path for each `.woff2`). To pin a site to an exact release
instead, tag a version here and reference `@v1.0.0`.

Weights: the family ships 400 and 700 only. Browsers resolve `font-weight: 500`
to Regular and `600` to Bold, so Tailwind's `font-medium` reads as regular and
`font-semibold` as bold.

## Files

`zelles-serif-{regular,italic,bold,bolditalic}.woff2`

The web cut, and what sites load. Latin, Greek, punctuation, currency,
fractions, arrows, math and the f-ligatures: 1,404 characters, about 95 KB per
style. A page pulls only the styles it sets.

`zelles-serif-bold.ttf`

The same cut as TrueType, for share-image renderers (Next.js OG routes,
Satori) that cannot read WOFF2.

`full/zelles-serif-*.ttf`

The complete family: everything above plus Cyrillic, the phonetic alphabet and
the rest of the extended Latin ranges, 2,783 characters. Install these to use
the family in desktop apps.

## Rebuilding

```sh
pip install "fonttools[woff]"
python3 scripts/build-font.py
```

The script downloads the source once into `.font-cache/` (git-ignored) and
writes both sets of files. Three constants at the top control the result:

- `FAMILY`: the family name. Change it and rebuild to rename the whole family,
  then update `zelles-serif.css`.
- `WIDTH`: how much wider than the source. `1.0` is the source untouched,
  `1.03` is the current cut. Past about `1.08` the verticals grow heavy enough
  to flatten the stroke contrast.
- `WEB_RANGES`: what goes in the web cut. Add `(0x0400, 0x04FF)` to put
  Cyrillic on the web.

## Closed bowls

The source draws a few letters as a bowl beside a stem and stops the bowl's
lower terminal just short, which reads as a notch at heading sizes. The build
runs those terminals into the stem: `P`, `Þ`, `Ƥ` and the small-capital forms
of `p`, `þ` and `ƥ`, listed in `OPEN_BOWLS` in the build script.

## Typographic extras

The family has drawn small capitals. Turn them on with
`font-variant-caps: small-caps; font-feature-settings: 'smcp' 1, 'c2sc' 1`.

Stylistic sets `ss01`, `ss05` and `ss11` carry single-storey and alternate
letterforms from the source; `ss01` (alternate `a` and `g`) reads as more
calligraphic. Reach for it with `font-feature-settings: 'ss01' 1`.

## License

The source is under the SIL Open Font License 1.1, copied here as `OFL.txt`,
and this cut is under the same license. The OFL reserves the names "Gentium"
and "SIL", which is why the modified family carries a different name. Keep
`OFL.txt` alongside the font files if you pass them on.
