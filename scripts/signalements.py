"""Prix vus à la pompe et fraîcheur des prix déclarés à la Régie.

1. Signalements. Quand quelqu'un voit à la pompe un prix différent de celui déclaré à la Régie,
   l'appli publie {"k": "lat,lon", "f": carburant, "p": prix} sur le sujet ntfy SIGNAL.
   On les ajoute à stations.json (colonne 11) : {"0": [prix vu, heure, prix Régie au moment du signalement]}.
   Un signalement tombe dès que la station change son prix à la Régie, ou après 48 h.
   Un signalement égal au prix de la Régie efface le signalement précédent (confirmation).
2. Fraîcheur. Colonne 12 : heure (secondes) du dernier changement des prix déclarés par la station,
   calculée en comparant avec la version publiée juste avant.
"""
import json
import os
import time
import urllib.request

NTFY = "https://ntfy.sh"
SIGNAL = "essence-qc-sig-r4n8w2v6t3"
STATIONS = "site/stations.json"
ETAT = "data/signalements.json"
DUREE = 48 * 3600


def cle(s):
    return f"{s[4]:.5f},{s[5]:.5f}"


def pareil(a, b):
    return (a is None and b is None) or (a is not None and b is not None and abs(a - b) < 0.05)


def lire(depuis):
    url = f"{NTFY}/{SIGNAL}/json?poll=1&since={depuis}"
    req = urllib.request.Request(url, headers={"User-Agent": "essence-quebec"})
    msgs = []
    for l in urllib.request.urlopen(req, timeout=30).read().decode("utf-8").splitlines():
        try:
            m = json.loads(l)
        except ValueError:
            continue
        if m.get("event") == "message":
            msgs.append(m)
    return sorted(msgs, key=lambda m: m.get("time", 0))


def en_ligne():
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if "/" not in repo:
        return None
    owner, name = repo.split("/", 1)
    url = f"https://{owner.lower()}.github.io/{name}/stations.json?t={int(time.time())}"
    try:
        return json.load(urllib.request.urlopen(url, timeout=20)).get("stations")
    except Exception as e:
        print("Version en ligne indisponible :", e)
        return None


def main():
    with open(STATIONS, encoding="utf-8") as f:
        data = json.load(f)
    stations = data["stations"]
    par_cle = {cle(s): s for s in stations}
    maintenant = int(time.time())

    try:
        with open(ETAT, encoding="utf-8") as f:
            etat = json.load(f)
    except (OSError, ValueError):
        etat = {"depuis": "48h", "vus": [], "sig": {}}
    avant = json.dumps(etat, sort_keys=True)

    # 1. Nouveaux signalements
    try:
        msgs = [m for m in lire(etat["depuis"]) if m["id"] not in etat["vus"]]
    except Exception as e:
        print("Signalements illisibles :", e)
        msgs = []
    for m in msgs:
        try:
            x = json.loads(m.get("message", ""))
            k, f, p = str(x["k"]), int(x["f"]), round(float(x["p"]), 1)
        except (ValueError, KeyError, TypeError):
            continue
        s = par_cle.get(k)
        if s is None or f not in (0, 1, 2) or not 80 <= p <= 300:
            continue
        regie = s[6 + f]
        if regie is not None and abs(p - regie) > 60:
            continue
        sig = etat["sig"].setdefault(k, {})
        if pareil(p, regie):
            sig.pop(str(f), None)
        else:
            sig[str(f)] = [p, int(m["time"]), regie]
        print(f"Signalement : {s[0]} {s[2]} · {['régulier', 'super', 'diesel'][f]} {p} (Régie {regie})")
    if msgs:
        etat["depuis"] = msgs[-1]["time"]
        etat["vus"] = [m["id"] for m in msgs if m["time"] == msgs[-1]["time"]]

    # Fin des signalements : la station a changé son prix à la Régie, ou 48 h sont passées.
    for k in list(etat["sig"]):
        s = par_cle.get(k)
        for f, (p, t, regie) in list(etat["sig"][k].items()):
            if s is None or maintenant - t > DUREE or not pareil(s[6 + int(f)], regie):
                del etat["sig"][k][f]
        if not etat["sig"][k]:
            del etat["sig"][k]

    # 2. Fraîcheur des prix déclarés
    live = en_ligne()
    prec = {cle(s): s for s in live} if live else None
    for s in stations:
        while len(s) < 13:
            s.append(None)
        s[11] = etat["sig"].get(cle(s)) or None
        if prec is None:
            continue  # garde la valeur déjà présente (ou inconnue)
        p = prec.get(cle(s))
        meme = p is not None and all(pareil(s[i], p[i]) for i in (6, 7, 8))
        s[12] = p[12] if meme and len(p) > 12 and p[12] else maintenant

    with open(STATIONS, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"{len(etat['sig'])} station(s) avec un prix signalé")

    if json.dumps(etat, sort_keys=True) != avant:
        os.makedirs(os.path.dirname(ETAT), exist_ok=True)
        with open(ETAT, "w", encoding="utf-8") as f:
            json.dump(etat, f, ensure_ascii=False, indent=1, sort_keys=True)


if __name__ == "__main__":
    main()
