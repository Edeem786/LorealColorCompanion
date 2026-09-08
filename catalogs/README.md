# Product catalogs

Put one JSON list per makeup category here: `blush.json`, `lip.json`, `eyeshadow.json`, etc. Files are read on request, so changes require refreshing the browser, not restarting Flask. Empty lists appear as unavailable categories; `lip.json` contains the supplied 52 lipsticks. Their source category `lipstick` is preserved in `source_category` and mapped to `lip` for compatibility with existing preferences. Names, IDs and color values are unchanged. The optional `color_source` metadata is retained in the catalog but is not displayed on product cards.

Each product requires a unique `id`, `product_name`, `shade_name`, `category` matching its filename, and `color` containing normalized **OKLab** `L`, `a`, `b`. RGB data must be converted first. Optional metadata such as `color_source` is preserved.

```json
[
  {
    "id": "unique_product_shade_id",
    "product_name": "Product name",
    "shade_name": "Shade name",
    "category": "lip",
    "color": {"L": 0.6, "a": 0.12, "b": 0.04},
    "color_source": "estimated"
  }
]
```

`blush.json` is the user's supplied 26-product test catalog, copied without changing its color values. The values are treated as OKLab based on the existing project convention. All supplied colors are estimated, not verified measurements; some may exceed the displayable sRGB gamut. The browser's preview may be clipped and should not be treated as an exact product swatch. Sparse/distant preference evidence can leave products unscored; the app does not fabricate positive matches.

Catalog inclusion is not a live stock check or verification of product names/availability. Add or remove products here to control the candidate inventory. Recommendations only use products in the selected category, and preferences stay separate by category.
