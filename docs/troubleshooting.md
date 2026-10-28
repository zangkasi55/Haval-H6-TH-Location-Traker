# Troubleshooting

| Symptom | Check |
| --- | --- |
| Source missing during setup | Configure the Thailand GWM integration first; this is a companion, not a cloud login |
| Selected source unsupported | Use its actual GWM vehicle device and a supported normalized coordinator; legacy region must be `tha` |
| Source unavailable after restart | Wait for the original integration to load; the local check rebinds without signing in |
| No current car marker | Check manufacturer timestamp and valid GPS, not the recent HTTP/HA poll time |
| Empty history | Opt in to recording; no earlier journeys are imported |
| Card not found | Register the exact versioned JavaScript module resource, then reload the browser |
| Vehicle not found in card | Add the companion config entry and its status sensor; `device_id` refers to its companion device |
| Not authorized | An active admin plus companion/source device permissions are required; do not weaken the checks |
| Map data unavailable | Provision a compatible local PMTiles v3 archive and verify 206 byte-range responses |
| Stop is unconfirmed | The full ordered power/driver-door sequence is missing; lock/engine/timer proxies are not used |
| Door duration seems short | It is sampled first-open/first-closed evidence; stale periods are not extended |
| History storage error | Check HA disk access/space and logs; private payloads are deliberately not logged |

## Safe refresh

Refresh reads the source integration's **existing local cache**. It does not wake
the car, call a manufacturer status request, force login or take over a phone
session. A stale manufacturer fix remains stale after a local refresh.

Use the source integration's own normal troubleshooting for authentication,
connected-service expiry or cloud availability. Never paste passwords, PINs,
tokens, certificates or precise journeys into a public issue.

## Report a reproducible issue

Include HA version, this integration's version, source integration/domain/version,
the visible non-secret error code, whether GPS/power fields are present and a
synthetic reproduction if possible. Redact device/account identifiers, source
storage, personal network settings, coordinates and screenshots before sharing.

The supported legacy adapter is optional compatibility, not a distribution of its
private provisioning material. Do not install a second account integration or
copy credentials between domains to fix this tracker.
