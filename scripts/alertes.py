"""Alertes de prix.

1. L'appli publie la configuration de chaque alerte (activée ou désactivée) dans un
   sujet ntfy « registre ». On lit les nouveaux messages à chaque exécution.
2. Pour chaque alerte active, on cherche la station la moins chère dans le rayon choisi.
   Si le prix passe sous le seuil, on envoie une notification ntfy au sujet personnel
   de la personne (une seule fois, jusqu'à ce que le prix remonte au-dessus du seuil).

L'état est gardé dans data/alertes.json (zone arrondie à environ 2 km, sujet aléatoire,
aucune donnée personnelle).
"""
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.request

NTFY = "https://ntfy.sh"
REGISTRE = "essence-qc-reg-k7q2m9x4p1"
ETAT = "data/alertes.json"
STATIONS = "site/stations.json"
CARBURANTS = ["Régulier", "Super", "Diesel"]
SUJET_OK = re.compile(r"^essence-[a-z0-9]{12,32}$")
EXPIRATION = 90 * 86400
MAX_ALERTES = 500


def lire_registre(depuis):
    url = f"{NTFY}/{REGISTRE}/json?poll=1&since={depuis}"
    req = urllib.request.Request(url, headers={"User-Agent": "essence-quebec"})
    lignes = urllib.request.urlopen(req, timeout=30).read().decode("utf-8").splitlines()
    msgs = []
    for l in lignes:
        try:
            m = json.loads(l)
        except ValueError:
            continue
        if m.get("event") == "message":
            msgs.append(m)
    return sorted(msgs, key=lambda m: m.get("time", 0))


def valider(cfg):
    if not isinstance(cfg, dict) or not SUJET_OK.match(str(cfg.get("topic", ""))):
        return None
    if cfg.get("on") is False:
        return {"topic": cfg["topic"], "on": False}
    try:
        a = {"topic": cfg["topic"], "on": True,
             "lat": round(float(cfg["lat"]), 2), "lon": round(float(cfg["lon"]), 2),
             "r": int(cfg["r"]), "f": int(cfg["f"]), "s": round(float(cfg["s"]), 1)}
    except (KeyError, TypeError, ValueError):
        return None
    if not (44 < a["lat"] < 63 and -80 < a["lon"] < -56):
        return None
    if a["r"] not in (3, 5, 10, 25) or a["f"] not in (0, 1, 2) or not (50 <= a["s"] <= 400):
        return None
    return a


def distance(a, b, c, d):
    r = math.pi / 180
    h = math.sin((c - a) * r / 2) ** 2 + math.cos(a * r) * math.cos(c * r) * math.sin((d - b) * r / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def envoyer(sujet, titre, message, clic):
    corps = json.dumps({"topic": sujet, "title": titre, "message": message,
                        "tags": ["fuelpump"], "click": clic, "priority": 4}).encode("utf-8")
    req = urllib.request.Request(NTFY + "/", data=corps, method="POST",
                                 headers={"User-Agent": "essence-quebec"})
    urllib.request.urlopen(req, timeout=30).read()


def fmt(p):
    return f"{p:.1f}".replace(".", ",")


def main(prix_frais):
    maintenant = int(time.time())
    try:
        with open(ETAT, encoding="utf-8") as f:
            etat = json.load(f)
    except Exception:
        etat = {"depuis": maintenant - 12 * 3600, "vus": [], "alertes": {}}
    avant = json.dumps(etat, sort_keys=True)

    # 1. Nouvelles configurations
    try:
        msgs = lire_registre(etat["depuis"])
    except Exception as e:
        print("Registre illisible :", e)
        msgs = []
    vus = set(etat.get("vus", []))
    for m in msgs:
        if m.get("id") in vus:
            continue
        try:
            cfg = valider(json.loads(m.get("message", "")))
        except ValueError:
            cfg = None
        if not cfg:
            continue
        t = cfg["topic"]
        if not cfg["on"]:
            etat["alertes"].pop(t, None)
            continue
        ancien = etat["alertes"].get(t)
        cle = ("lat", "lon", "r", "f", "s")
        if ancien and all(ancien.get(k) == cfg[k] for k in cle):
            ancien["vu"] = m["time"]
        elif ancien or len(etat["alertes"]) < MAX_ALERTES:
            etat["alertes"][t] = dict(cfg, vu=m["time"], sous=False, envoi=0)
    if msgs:
        etat["depuis"] = msgs[-1]["time"]
        etat["vus"] = [m["id"] for m in msgs if m["time"] == msgs[-1]["time"]]
    for t in [t for t, a in etat["alertes"].items() if maintenant - a.get("vu", 0) > EXPIRATION]:
        del etat["alertes"][t]
    print(f"{len(msgs)} message(s) au registre, {len(etat['alertes'])} alerte(s) active(s)")

    # 2. Vérification des prix
    if prix_frais and etat["alertes"]:
        with open(STATIONS, encoding="utf-8") as f:
            stations = json.load(f)["stations"]
        repo = os.environ.get("GITHUB_REPOSITORY", "/")
        owner, name = repo.split("/", 1)
        appli = f"https://{owner.lower()}.github.io/{name}/" if owner else ""
        envoyees = 0
        for t, a in etat["alertes"].items():
            meilleur = None
            for s in stations:
                p = s[6 + a["f"]]
                vu = s[11].get(str(a["f"])) if len(s) > 11 and s[11] else None
                if vu:
                    p = vu[0]  # prix vu à la pompe et signalé : plus fiable que celui déclaré
                if p is None:
                    continue
                d = distance(a["lat"], a["lon"], s[4], s[5])
                if d <= a["r"] and (meilleur is None or (p, d) < (meilleur[0], meilleur[1])):
                    meilleur = (p, d, s)
            if meilleur is None:
                continue
            p, d, s = meilleur
            if p <= a["s"] and not a["sous"]:
                nom = s[0] if s[0] and s[0].lower() != "aucun" else s[1]
                try:
                    envoyer(t, f"{CARBURANTS[a['f']]} à {fmt(p)} ¢ près de chez toi",
                            f"{nom}, {s[2]} (≈ {fmt(d)} km). Ton seuil : {fmt(a['s'])} ¢.", appli)
                    a["sous"], a["envoi"] = True, maintenant
                    envoyees += 1
                except Exception as e:
                    print("Notification non envoyée :", e)
            elif a["sous"] and p > a["s"] + 0.5:
                a["sous"] = False
        print(f"{envoyees} notification(s) envoyée(s)")

    if json.dumps(etat, sort_keys=True) != avant:
        os.makedirs(os.path.dirname(ETAT), exist_ok=True)
        with open(ETAT, "w", encoding="utf-8") as f:
            json.dump(etat, f, ensure_ascii=False, indent=1, sort_keys=True)
        print("État des alertes mis à jour")


if __name__ == "__main__":
    main(len(sys.argv) > 1 and sys.argv[1] == "success")
