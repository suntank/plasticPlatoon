import argparse
import sys
from pathlib import Path

from PIL import Image, ImageChops


def _parse_hex_rgb(value: str) -> tuple[int, int, int]:
    s = value.strip()
    if s.startswith("#"):
        s = s[1:]
    if len(s) != 6:
        raise ValueError(f"Expected 6-digit hex color like #046000, got: {value!r}")
    r = int(s[0:2], 16)
    g = int(s[2:4], 16)
    b = int(s[4:6], 16)
    return r, g, b


def _gamma_lut(gamma: float) -> list[int]:
    if gamma <= 0:
        raise ValueError("gamma must be > 0")
    lut: list[int] = []
    for i in range(256):
        x = i / 255.0
        y = pow(x, gamma)
        lut.append(int(round(y * 255.0)))
    return lut


def _process_image(img: Image.Image, gamma: float, multiply_rgb: tuple[int, int, int]) -> Image.Image:
    # Resize to 256x256 with bilinear filtering
    if img.size != (256, 256):
        img = img.resize((256, 256), Image.Resampling.BILINEAR)

    rgba = img.convert("RGBA")
    a = rgba.getchannel("A")

    rgb = rgba.convert("RGB")
    if gamma != 1.0:
        lut = _gamma_lut(gamma)
        rgb = rgb.point(lut * 3)

    mult = ImageChops.multiply(rgb, Image.new("RGB", rgb.size, multiply_rgb))
    black = Image.new("RGB", rgb.size, (0, 0, 0))
    keep_mask = a.point(lambda v: 0 if v == 0 else 255)
    mult = Image.composite(mult, black, keep_mask)

    r, g, b = mult.split()
    return Image.merge("RGBA", (r, g, b, a))


def _iter_pngs(root: Path):
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() == ".png":
            yield p


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--in-place", action="store_true", default=True)
    parser.add_argument("--backup-suffix", default=None)
    parser.add_argument("--gamma", type=float, default=0.89)
    parser.add_argument("--multiply", type=str, default="#046000")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)

    root = args.root
    if not root.exists() or not root.is_dir():
        print(f"Root directory not found: {root}", file=sys.stderr)
        return 2

    if args.in_place and args.out is not None:
        print("Use either --in-place or --out, not both", file=sys.stderr)
        return 2

    out_root: Path | None
    if args.in_place:
        out_root = None
    else:
        out_root = args.out if args.out is not None else root.with_name(root.name + "_homogenized")

    multiply_rgb = _parse_hex_rgb(args.multiply)

    any_found = False
    for src in _iter_pngs(root):
        any_found = True
        rel = src.relative_to(root)

        if out_root is None:
            dst = src
        else:
            dst = out_root / rel

        if not args.overwrite and out_root is not None and dst.exists():
            continue

        if args.dry_run:
            print(f"{src} -> {dst}")
            continue

        try:
            with Image.open(src) as im:
                out = _process_image(im, gamma=args.gamma, multiply_rgb=multiply_rgb)

            if out_root is not None:
                dst.parent.mkdir(parents=True, exist_ok=True)
                out.save(dst, format="PNG")
            else:
                backup = src.with_name(src.name + args.backup_suffix) if args.backup_suffix else None
                if backup is not None and backup.exists() and not args.overwrite:
                    print(f"Backup exists, skipping (use --overwrite to force): {backup}", file=sys.stderr)
                    continue
                if backup is not None and not backup.exists():
                    src.replace(backup)
                    out.save(src, format="PNG")
                else:
                    out.save(src, format="PNG")
        except Exception as e:
            print(f"Failed: {src} ({e})", file=sys.stderr)

    if not any_found:
        print("No PNGs found.", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
