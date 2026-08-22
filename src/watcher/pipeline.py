"""Pipeline birlestirme: fetch -> filtre/skor -> dedupe -> store -> bildir.

Bu modul kaynaklari ve bildiriciyi disaridan aliyor (dependency injection);
boylece testlerde gercek HTTP veya Telegram cagrisi yapilmadan tum akis
dogrulanabiliyor.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Protocol

from . import config
from .dedupe import merge
from .models import SourceResult
from .outreach import draft as make_draft
from .score import evaluate
from .store import Store


class Notifier(Protocol):
    def send_listing(self, group, evaluation, draft) -> None: ...
    def send_text(self, text: str) -> None: ...


@dataclass
class RunReport:
    fetched: int = 0
    passed: int = 0
    new: int = 0
    notified: int = 0
    silent: bool = False
    errors: list[str] = field(default_factory=list)


def _collect(
    sources: list[Callable[[], SourceResult]], report: RunReport
) -> list:
    listings = []
    for index, fetch in enumerate(sources):
        if index and config.INTER_SOURCE_DELAY:
            time.sleep(config.INTER_SOURCE_DELAY)
        result = fetch()
        if result.error:
            report.errors.append(f"{result.source}: {result.error}")
        elif not result.listings:
            # Sessiz olum bu sistemdeki en tehlikeli hata modu: kaynak ayakta
            # gorunur ama sema degistigi icin hicbir sey donmez.
            report.errors.append(f"{result.source}: sonuc bos - sema degismis olabilir")
        listings.extend(result.listings)
    return listings


def run(
    store: Store,
    sources: list[Callable[[], SourceResult]],
    notifier: Notifier,
) -> RunReport:
    report = RunReport()
    report.silent = store.is_first_run()

    all_listings = _collect(sources, report)
    report.fetched = len(all_listings)

    evaluated = []
    for group in merge(all_listings):
        evaluation = evaluate(group.primary)
        if evaluation.passed and evaluation.score >= config.SCORE_THRESHOLD:
            evaluated.append((group, evaluation))

    report.passed = len(evaluated)
    evaluated.sort(key=lambda pair: pair[1].score, reverse=True)

    fresh = [(g, e) for g, e in evaluated if not store.is_known(g.primary.fingerprint)]
    report.new = len(fresh)

    # Ilk kosu: hepsini kaydet ama hicbirini bildirme. Amac gecmis ilanlarla
    # telefonu bombalamamak; bu ilanlar zaten "gorulmus" sayilacak.
    if report.silent:
        for group, evaluation in fresh:
            store.record(group, evaluation)
        return report

    # ONEMLI: sadece BILDIRDIGIMIZ ilanlar kaydedilir.
    # Onceden hepsi kaydediliyordu, bu yuzden ust sinira takilanlar bir sonraki
    # kosuda is_known olup fresh'ten dusuyordu ve bir daha ASLA bildirilmiyordu.
    # Kaydetmeyince bir sonraki kosuda tekrar aday oluyorlar.
    cap = config.MAX_NOTIFICATIONS_PER_RUN
    for group, evaluation in fresh[:cap]:
        store.record(group, evaluation)
        notifier.send_listing(group, evaluation, make_draft(group))
        store.mark_notified(group.primary.fingerprint)
        report.notified += 1

    overflow = len(fresh) - cap
    if overflow > 0:
        notifier.send_text(f"+{overflow} ilan daha eslesti, bir sonraki kosuda gelecek.")

    return report
