# Sony 209 integration validation

Source: Sony branch integrated with upstream CleanYourTV v2.2.0,
`8a8249f1cd300f85205b9101018f54cc1594f58d`, 19 October 2026.
Version: 2.4.0-sony-cn-preview / 209, minSdk 26, targetSdk 34.

## Verified locally

- Direct official SDK pipeline: resource compilation/linking, javac, D8, zipalign and APK v2/v3
  signature verification. This does not run Gradle, R8 or lint.
- All 42 existing upstream CardsTest/CardFeatureTest JVM tests passed on JDK17 through
  JUnitCore with Android SDK classes: label/caption rules, parser limits, decision serialization,
  card ordering/clashes and the failure guard. Test libraries are not shipped in the APK.
- Nine actual-source geometry combinations: four/five/six columns at three densities.
- Theme shell relative/absolute path, reset and malformed JSON checks passed with stubbed device
  calls. Shipped JSON parsed; bash syntax checked. PowerShell runtime was not tested.
- Sony initial eight-package order, four columns/two rows, saved preference keys, original recovery
  activity source and XML checks passed. All 46 default string names have Chinese resources and
  matching format arguments.
- Normal and isolated APK metadata checked. The isolated application ID is
  com.gathin.tvhome.contribtest, with no HOME intent filter.

## Integration choices

Sony FOCUS_SCALE=1.12, launcher_layout/app_order and the recovery entry are preserved.
Accepted module cards replace only their matching TV component before package deduplication;
ordinary Android and HOME entries still appear. The card-name collision set includes those
extra visible app names, while card eligibility still requires a LEANBACK entry.

Package-change broadcasts defer refresh while a Sony tile move is in progress, then refresh
after save/cancel; on resume the list is refreshed normally. Module prompts wait until movement
ends. Cancel/pause reloads keep approved module cards. Animation cancellation and popup cleanup
both run on pause.

## Not verified on TV

No installation or device command was performed. Module discovery/prompt/UI, real package
broadcasts during moves, persistence, settings/input return, wallpaper and performance remain
pending on the Sony. The 206 screenshot and historical 85 MiB PSS do not validate build 209.
The current memory/CPU/frame cost, including module cards, remains unmeasured. Normal APKs
from this contribution workspace have a test key and must not replace the working launcher.

Before deployment, use an isolated package, verify the working HOME/order remains intact,
exercise module on/off, confirmation/cancellation, signing/name changes, app install/update/remove
with and without a pending move, and remove the temporary package afterward.
