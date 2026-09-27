# Contributing to brscan

Issues and pull requests are welcome for protocol correctness, error handling, documentation, and offline tests.

## Development rules

- Keep the executable dependency-free and compatible with Python 3.9 or newer.
- Do not add scanner credentials, private hostnames, private IP addresses, scanned images, or other personal data to commits or tests.
- Do not run live scans as part of automated tests. Use deterministic byte fixtures and fake sockets.
- Preserve the protocol provenance and acknowledgments in the README. This project contains an independent implementation based on reverse-engineering; it does not vendor code from the referenced projects.
- Keep macOS-only behavior behind the existing `sips` and `open` subprocess boundaries so the offline test suite runs on Linux too.

## Checks

Run the test suite with the standard library:

```sh
python3 -m unittest discover -s tests -v
```

The same command is run by GitHub Actions on macOS and Linux with Python 3.9 and a current supported Python version. Tests must not contact a scanner or any other network service.

When changing the wire protocol, include a small synthetic fixture test that explains the framing or malformed case being covered. Describe any real-device validation separately from the offline test results.
