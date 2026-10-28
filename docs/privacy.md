# Privacy and publication boundary

## No vehicle credentials

This companion has no cloud login and does not request, import or store account
passwords, OTPs, access/refresh tokens, manufacturer certificates, device keys or
vehicle PINs. Existing source-integration authentication stays with that source.
No vehicle controls, manufacturer endpoints or APK/provisioning resources are
bundled.

The local adapter selects only the configured device/entry/vehicle and projects
timestamps, location and relevant status values. It discards unrelated source
fields and replaces the source vehicle identifier with a local constant for its
own observation-store record.

## Precise history

Precise current location/history is available only through the authenticated HA
WebSocket API to an active administrator with the relevant companion and
source-device entity permission. It is not published as sensor attributes,
static JSON, logs or an external map URL.

Recording is off by default. When enabled, history is private HA storage with a
fixed seven-day rolling retention and bounded sample count. Expiry runs without
fresh cloud samples and after restart. Disabling recording hides history and
stops ingestion, but does not mean immediate deletion; use confirmed deletion or
remove the config entry to erase it sooner.

Do not disable/remove files manually to bypass permission or expiry checks.
Protect HA's host, administrators, backups and any exported diagnostics.

## Maps and screenshots

Only generic geography belongs under `/local/`. Routes remain private.
The bundled frontend does not send an owner's coordinates or viewport to
external tile/CDN services. An external attribution link opens only on user action.

Manual screenshots are generated from fictional readings, positions and events.
They are labelled synthetic. No live HA account, VIN, phone, owner hostname,
family wallpaper or original vehicle photograph is included.

## Publication checks

The allowlist scanner rejects unexpected binaries, certificates/private-key
files, JWT/GitHub tokens, personal workstation paths and private endpoint
patterns. It also checks PNG metadata and has a fresh source-only Git-history
boundary. Local owner-specific known-material scans can run separately without
putting their inputs into this repository.

Scans reduce accidental disclosure; they are not a claim that arbitrary future
contributions are secret-free. Never commit real credentials to a test fixture.
Report a disclosure privately; do not paste it into a public issue.
