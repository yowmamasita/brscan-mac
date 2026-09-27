# Changelog

All notable changes to `brscan` are documented here.

## [0.1.0] - 2026-09-27

First public source release.

- Added explicit scanner host configuration through `--host`, `BRSCAN_HOST`, or `BRSCAN_IP`.
- Added native PDF output for all modes, colour JPEG passthrough, native greyscale/black-and-white PNG output, and macOS `sips` conversion for colour-to-PNG, greyscale/black-and-white-to-JPEG, and all TIFF/HEIC output.
- Added validation and useful errors for scanner protocol, image data, and output conversion failures.
- Added offline unit tests and a macOS/Linux GitHub Actions matrix.
- Documented the unofficial/unaffiliated status, DCP-7055W compatibility boundary, recorded pre-release testing, protocol notes, limitations, installation, and privacy behavior. No live hardware rerun was performed for final `v0.1.0`.
