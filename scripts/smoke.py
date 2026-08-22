"""Canli duman testi. CI'da CALISMAZ - elle calistirilir.

Amac: kaynaklarin hala ayakta ve semalarinin bozulmamis oldugunu dogrulamak.
Fixture testleri gecip bu sifir donuyorsa sema degismis demektir.

    python scripts/smoke.py
"""
from __future__ import annotations

import sys

from watcher.dedupe import merge
from watcher.outreach import draft
from watcher.score import evaluate
from watcher.sources import cityexpert, fourzida, halooglasi


def main() -> int:
    all_listings = []
    failures = 0

    for module in (cityexpert, fourzida, halooglasi):
        result = module.fetch()
        if result.error:
            print(f"  {result.source:12} -> HATA: {result.error}")
            failures += 1
        elif not result.listings:
            print(f"  {result.source:12} -> 0 ilan (SEMA DEGISMIS OLABILIR)")
            failures += 1
        else:
            print(f"  {result.source:12} -> {len(result.listings)} ilan")
        all_listings.extend(result.listings)

    groups = merge(all_listings)
    saved = len(all_listings) - len(groups)
    print(f"\n{len(all_listings)} ilan -> {len(groups)} tekil daire "
          f"({saved} kopya elendi)")

    passing, rejected = [], {}
    for group in groups:
        evaluation = evaluate(group.primary)
        if evaluation.passed:
            passing.append((group, evaluation))
        else:
            reason = evaluation.reject_reason.split(" (")[0]
            rejected[reason] = rejected.get(reason, 0) + 1

    passing.sort(key=lambda pair: pair[1].score, reverse=True)
    print(f"filtreden gecen: {len(passing)}")
    if rejected:
        print("elenenler: " + ", ".join(f"{k}={v}" for k, v in sorted(rejected.items())))

    print("\n--- en iyi 8 ---")
    for group, evaluation in passing[:8]:
        listing = group.primary
        commute = f"~{evaluation.commute_minutes}dk" if evaluation.commute_minutes else "?"
        flags = ",".join(evaluation.flags) or "-"
        print(f"  [{evaluation.score:3}] {listing.price_eur:>4}EUR "
              f"{str(listing.m2 or '?'):>3}m2 {commute:>6} "
              f"{(listing.municipality or '-')[:16]:<16} {flags[:32]:<32}")
        print(f"        {listing.url}")

    if passing:
        print("\n--- ornek taslak (en iyi ilan) ---")
        print(draft(passing[0][0]).serbian)

    return 1 if failures == 3 else 0


if __name__ == "__main__":
    sys.exit(main())
