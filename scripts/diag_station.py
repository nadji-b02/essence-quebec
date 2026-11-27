"""Diagnostic : suit le prix d'une station dans les fichiers de la Régie au fil de la journée.
Usage : python scripts/diag_station.py "texte à chercher" HEURE_DEBUT_UTC (ex. 14)"""
import datetime as dt, io, sys, statistics, urllib.request
import openpyxl
sys.path.insert(0, "scripts")
from maj import BASE, norm, price

q = norm(sys.argv[1]); debut = int(sys.argv[2])
now = dt.datetime.now(dt.timezone.utc).replace(second=0, microsecond=0)
t = now.replace(hour=debut, minute=0)
entete_vue = False
while t <= now:
    url = BASE.format(t)
    try:
        data = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "essence-quebec (projet personnel)"}), timeout=60).read()
    except Exception as e:
        print(f"{t:%H:%M} UTC : indisponible ({e})"); t += dt.timedelta(minutes=10); continue
    rows = list(openpyxl.load_workbook(io.BytesIO(data), read_only=True).worksheets[0].iter_rows(values_only=True))
    hi = next(i for i, r in enumerate(rows[:10]) if r and any(norm(c) == "latitude" for c in r))
    head = [norm(c) for c in rows[hi]]
    if not entete_vue:
        print("Colonnes du fichier :", head); entete_vue = True
    ir, irg, ia = head.index("prix regulier"), head.index("region"), head.index("adresse")
    region = [price(r[ir]) for r in rows[hi+1:] if r and norm(r[irg]) == "monteregie" and price(r[ir])]
    hits = [r for r in rows[hi+1:] if r and q in norm(" ".join(str(c) for c in r if c is not None))]
    loc = (dt.datetime.combine(t.date(), t.time()) - dt.timedelta(hours=5)).strftime("%H:%M")
    print(f"{loc} (heure locale) · médiane Montérégie {statistics.median(region):.1f} · "
          + " | ".join(f"{r[0]} {r[ia]} : {price(r[ir])} {[c for c in r if isinstance(c, (dt.datetime, dt.date))]}" for r in hits))
    t += dt.timedelta(minutes=10)
