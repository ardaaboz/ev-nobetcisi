"""Proje geneli sabitler. Ortam degiskenleri .env'den okunur."""
import os

from dotenv import load_dotenv

load_dotenv()

# Tip Fakultesi, Dr Subotica 8, Savski Venac (Nominatim ile dogrulandi)
FACULTY_LAT = 44.7974
FACULTY_LNG = 20.4611

PRICE_TARGET_EUR = 400    # ideal butce
PRICE_SOFT_EUR = 500      # bu ustu "esnek" etiketi alir
PRICE_CEILING_EUR = 550   # bu ustu tamamen elenir

USER_AGENT = "belgrade-rental-watcher/1.0 (personal use)"
HTTP_TIMEOUT = 10.0
INTER_SOURCE_DELAY = 1.0

MAX_NOTIFICATIONS_PER_RUN = 8
# Canli olcumde gecen ilanlarin medyan skoru 34 idi; 45 esigi yarisindan
# fazlasini kesiyordu. Ilke: iyi ilani kacirmak, fazladan ilan gostermekten
# pahali. Ust sinira takilanlar artik kaybolmadigi icin (bkz. pipeline.run)
# daha genis bir esik guvenli.
SCORE_THRESHOLD = 40

# Sirpcada sifatlar ve meslek adlari cinsiyete gore cekimleniyor
# (uredan/uredna, student/studentkinja). Yanlis cekim mesajin anadili
# olmayan biri tarafindan yazildigini ilk cumlede ele verir.
USER_GENDER = os.getenv("USER_GENDER", "f")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

DB_PATH = os.getenv("DB_PATH", "state/listings.db")
