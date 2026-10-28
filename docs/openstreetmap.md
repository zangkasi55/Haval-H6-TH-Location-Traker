# Local OpenStreetMap

All rendering libraries are served by HA. Vehicle viewports and routes are not
sent to a third-party tile server. Supply a **generic local PMTiles v3 archive**
compatible with the Protomaps basemap schema.

## Obtain a country archive

Use your own licensed source or
[Protomaps published generic builds](https://maps.protomaps.com/), following the
provider's current terms. With the official
[go-pmtiles extractor](https://github.com/protomaps/go-pmtiles), verify the
downloaded tool's published release checksum, then extract a fixed country area:

```text
pmtiles extract <generic-planet-build.pmtiles-URL> thailand.pmtiles --bbox=97.3,5.4,105.7,20.5 --maxzoom=13 --download-threads=2
```

Choose the provider's actual published build URL; the placeholder is not a
credential or an owner-specific request. Generic fixed-country data does not
depend on anyone's route or home position. Keep the source URL/build date, extent,
checksum and data-license record with the archive.

**Never bulk-scrape or prefetch the OSM Foundation's public raster tiles.**
Use a provider/source that permits the required extraction/offline use.

## Install

Put the resulting file at:

```text
<HA configuration>/www/gwm-maps/thailand.pmtiles
```

The default card requests `/local/gwm-maps/thailand.pmtiles`. HA/proxy must
support byte ranges, including an HTTP **206** response for `bytes=0-7`.
Missing/corrupt archives or failed range requests produce a visible map error.
The tracker does not silently download another map.

```yaml
type: custom:haval-journey-card
map_archive: /local/gwm-maps/thailand.pmtiles
```

Same-host local XYZ data is also supported:

```yaml
type: custom:haval-journey-card
local_tile_url: /local/offline-osm/{z}/{x}/{y}.png
```

Use an appropriately licensed OSM-derived source. External URLs, traversal and
query-bearing archive paths are rejected. The generic archive may be publicly
served under `/local/`; never put real history, coordinates or credentials there.

## Licensing

The card retains visible **OpenStreetMap contributors** and **Protomaps**
attribution. Map data/Produced Works must comply with
[OSM copyright and ODbL](https://www.openstreetmap.org/copyright).
The repository's MIT source license does not replace those obligations.
Bundled runtime notices are in the component's `frontend/vendor/LICENSES.txt`.

The manual screenshots and browser tests instead use an in-memory tiny
**fictional** PMTiles/MVT fixture. That is a renderer test, not a real Thailand
country basemap or an owner's journey, and needs no external download.
