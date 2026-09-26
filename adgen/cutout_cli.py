"""Command line for product cutouts (no API calls).

Usage:
    python -m adgen.cutout_cli build inputs/products/sneaker.jpg inputs/masks/sneaker_mask.png --name sneaker [--view overhead]
    python -m adgen.cutout_cli approve sneaker --verified-by "Your Name"     # human action after review
    python -m adgen.cutout_cli check inputs/products/sneaker.jpg              # what preflight will see
"""

import argparse
import sys
from pathlib import Path

from adgen import config
from adgen.cutout import VIEWS, approve, build_draft, load_approved_cutout
from adgen.errors import CutoutError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build, approve and check exact-pixel product cutouts.")
    parser.add_argument("--cutouts-dir", default=str(config.CUTOUTS_DIR), help="Cutout directory (default: cutouts/)")
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build", help="Build an UNVERIFIED draft cutout from the reference and a human-made mask")
    b.add_argument("reference")
    b.add_argument("mask")
    b.add_argument("--name", required=True)
    b.add_argument("--view", default="overhead", choices=VIEWS)
    b.add_argument("--mask-source", default="manual", help="How the mask was made (recorded in metadata)")
    a = sub.add_parser("approve", help="Human approval of a reviewed draft")
    a.add_argument("name")
    a.add_argument("--verified-by", required=True)
    c = sub.add_parser("check", help="Load the approved cutout for a reference image and re-verify lineage")
    c.add_argument("reference")
    args = parser.parse_args(argv)

    cdir = Path(args.cutouts_dir)
    try:
        if args.command == "build":
            path = build_draft(Path(args.reference), Path(args.mask), args.name, args.view, cutouts_dir=cdir,
                               mask_source=args.mask_source)
            print(f"DRAFT written: {path} (+ .json). Review it, then run: approve {args.name} --verified-by ...")
        elif args.command == "approve":
            print(f"APPROVED: {approve(args.name, args.verified_by, cutouts_dir=cdir)}")
        else:
            cutout = load_approved_cutout(Path(args.reference), cutouts_dir=cdir)
            m = cutout.metadata
            print(f"OK {cutout.path.name}: {m['cutout_size'][0]}x{m['cutout_size'][1]}, view={m['view']}, "
                  f"verified_by={m['verified_by']}, opaque_pixels={m['opaque_pixels']}")
        return 0
    except CutoutError as e:
        print(f"ERROR (CutoutError): {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
