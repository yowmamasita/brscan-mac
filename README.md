# brscan

`brscan` is a small, native macOS command-line scanner for a Brother network scanner that speaks the brscan4-era protocol. It uses only the Python standard library and talks directly to TCP port 54921, so it does not install a Brother driver or require Rosetta. This is an unofficial, unaffiliated project and is not endorsed by Brother.

Recorded pre-release testing was performed only with the Brother DCP-7055W documented in the protocol notes below. No live hardware rerun was performed for the final `v0.1.0` release. Other Brother models may use a different protocol and are unverified.

## Requirements

- macOS with `python3` available on `PATH`, version 3.9 or newer; the executable selects it through its `#!/usr/bin/env python3` shebang
- A network-reachable, supported Brother scanner
- The macOS `sips` command for colour-to-PNG, greyscale or black-and-white-to-JPEG, and all TIFF/HEIC output
- For `--open`, the macOS `/usr/bin/open` command

No Python packages, Brother software, USB driver, or system service are required.

## Installation

Clone this repository, then install the single executable somewhere on your `PATH`:

```sh
git clone https://github.com/yowmamasita/brscan-mac.git
cd brscan-mac
mkdir -p "$HOME/.local/bin"
install -m 755 brscan "$HOME/.local/bin/brscan"
```

If `$HOME/.local/bin` is not already on your `PATH`, add it in your shell startup file, for example:

```sh
export PATH="$HOME/.local/bin:$PATH"
```

Check the installed version:

```sh
brscan --version
```

The program does not configure the scanner, change network settings, or store credentials.

## Scanner host configuration

The scanner host must be explicit. Supply `--host`, set `BRSCAN_HOST`, or set `BRSCAN_IP`:

```sh
brscan --host scanner.local output.pdf
BRSCAN_HOST=scanner.local brscan output.pdf
BRSCAN_IP=your-scanner-ip brscan output.pdf
```

Configuration is resolved in this order:

1. An explicit `--host` is used by itself. It is never silently replaced by or followed by an environment value.
2. Without `--host`, `BRSCAN_HOST` is tried first. If it is unreachable and `BRSCAN_IP` is also set, the IP is tried as the environment-configured fallback.
3. Without `BRSCAN_HOST`, `BRSCAN_IP` is used by itself.
4. If none is set, the command exits before opening a network connection.

Use a host name or IP address for the scanner you intend to operate. `brscan` does not perform mDNS, subnet, or other device discovery.

## Usage

```text
brscan [options] [output]
```

Examples:

```sh
# A4 colour scan to a timestamped PDF
brscan --host scanner.local

# Greyscale scan at 200 dpi
brscan --host scanner.local -m gray -r 200 homework.pdf

# One-bit scan to a PNG
brscan --host scanner.local -m bw -r 300 document.png

# Three flatbed pages into one PDF; the command prompts between pages
brscan --host scanner.local -n 3 book.pdf

# Query scanner status and maximum scan area
brscan --host scanner.local --info
```

Options:

| Option | Description |
| --- | --- |
| `--host HOST` | Scanner host or IP. Required unless `BRSCAN_HOST` or `BRSCAN_IP` is set. |
| `-m`, `--mode {color,gray,bw}` | Scan mode. The default is `color`. |
| `-r`, `--resolution DPI` | Resolution: `100`, `150`, `200`, `300`, `600`, or `1200`. The default is `300`. |
| `-s`, `--size {a4,letter,a5,full}` | Scan area. The default is `a4`. `full` uses the scanner-reported glass area. |
| `-n`, `--pages COUNT` | Positive number of flatbed pages. The default is `1`. |
| `-b`, `--brightness 0..100` | Brightness. The default is `50`. |
| `-c`, `--contrast 0..100` | Contrast. The default is `50`. |
| `-q`, `--quiet` | Suppress progress updates. |
| `--info` | Negotiate with the scanner and print its status and scan area. |
| `--open` | Open the output with macOS after a successful scan. |
| `--version` | Print `brscan 0.1.0`. |
| `-h`, `--help` | Show command help. |

The optional output suffix selects the format. Supported formats are `.pdf`, `.jpg`, `.jpeg`, `.png`, `.tif`, `.tiff`, and `.heic`. A name without a suffix is written as PDF. PDF encoding is native for all three scan modes. Colour JPEG output passes the scanner's JPEG data through unchanged, while greyscale and black-and-white PNG output is encoded natively. Colour-to-PNG, greyscale or black-and-white-to-JPEG, and all TIFF/HEIC output use macOS `sips`. Multiple pages produce one PDF or numbered image files such as `book-1.png`. Existing output paths are overwritten, so choose a destination carefully.

## Uninstallation

Remove the installed executable and, if you added it only for `brscan`, remove the corresponding `PATH` line:

```sh
rm -f "$HOME/.local/bin/brscan"
```

Scans already written to your own output directory are not removed by uninstalling the command.

## Compatibility and limitations

Recorded pre-release testing covers the Brother DCP-7055W only. No live hardware rerun was performed for final `v0.1.0`; the release verification uses offline synthetic fixtures. It is intended for a network-connected flatbed workflow using that model's observed protocol.

The command does not support:

- USB connections
- automatic document feeders (ADF)
- OCR or text extraction
- scanner discovery or automatic host selection
- Brother driver installation or vendor-specific configuration

`-n` repeats flatbed scans and prompts before each additional page; it does not operate an ADF. Scanning at high resolution can require substantial memory because image data is assembled before output is written.

## Troubleshooting

- **“scanner host is required”**: pass `--host scanner.local`, or set `BRSCAN_HOST`/`BRSCAN_IP` in the environment.
- **Connection failure**: check that the scanner is powered on, reachable from this Mac, and permits TCP port 54921. Verify the host with a separate network diagnostic before retrying.
- **Scanner busy**: wait for another scan or job to finish and try again.
- **`sips` error**: macOS `sips` is required for colour-to-PNG, greyscale or black-and-white-to-JPEG, and all TIFF/HEIC output; use native PDF, colour JPEG, or greyscale/black-and-white PNG when conversion is unavailable.
- **Permission error writing output**: choose an output path where your user can create files.
- **Malformed response or image error**: the command closes the connection and reports the protocol or image boundary that failed. Keep the error text with the scanner model and requested options when reporting a bug.

The program validates the host, page count, resolution, brightness, contrast, and output suffix before it opens a scanner connection. A failed validation therefore cannot trigger a scan.

## Privacy and safety

The command sends scan settings to, and receives image data from, the host you configure on your local network. It does not contact a cloud service, collect telemetry, or upload images. Output files remain on the local filesystem. Treat scanner images and host values as private, and do not commit scans or private network details to a public checkout.

## Protocol notes

These notes record the behavior observed from the DCP-7055W during the original reverse-engineering work (2026-09-27):

1. Connect → `+OK 200\r\n` (busy: `-NG 401`).
2. Send `ESC I \n R=300,300 \n M=CGRAY \n D=SIN \n 0x80` → reply `00 <len> 00 "xdpi,ydpi,adf,w_mm,w_px,h_mm,h_px,"`.
   The recorded glass is 209×291 mm (300 dpi: 2480×3437 px).
3. Send `ESC X \n R= M= C= J=MID B=50 N=50 A=0,0,w,h D=SIN G=1 L=128 \n 0x80` (Latin-1, not UTF-8).
4. Data chunks contain a one-byte type, nine header bytes (`07 00 <page:2> 84 …`), a two-byte little-endian length, and a payload.
   - `0x64` JPEG: concatenate payloads into one JFIF (`M=CGRAY C=JPEG`).
   - `0x42` PackBits line / `0x40` raw line: greyscale (`M=GRAY64 C=RLENGTH`, 8 bpp) or black-and-white (`M=TEXT C=RLENGTH`, 1 bpp, `1 = black`).
   - `0x82` plus five bytes ends a page; `0x80` ends the scan.
   - `GRAY64` with `C=JPEG` returns no data on this model.

The implementation was built from protocol reverse engineering. It does not vendor code from either reference project. See the acknowledgments for the research sources.

## Acknowledgments

Protocol research and interoperability work in [corsmith/mfc-7820n](https://github.com/corsmith/mfc-7820n) and [pietern/brother-scand](https://github.com/pietern/brother-scand) informed this implementation. Their repositories retain their own licenses and copyright notices; this project does not claim ownership of their code.

## License

MIT; see [LICENSE](LICENSE).
