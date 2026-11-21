"""Heures d'ouverture des stations, tirées d'OpenStreetMap (tag opening_hours).

- Une fois par semaine, on interroge Overpass pour toutes les stations-service du Québec
  et on garde les heures dans data/heures.json (clé : position de la station de la Régie).
- À chaque mise à jour, on ajoute les heures (texte OSM brut) à site/stations.json (11e champ).
Usage : python scripts/heures.py [--stats]
"""
import json, math, os, sys, time, urllib.parse, urllib.request

CACHE = "data/heures.json"
STATIONS = "site/stations.json"
MAX_AGE = 7 * 86400
DIST_MAX = 0.15  # km
OVERPASS = "https://overpass-api.de/api/interpreter"
QUERY = '[out:json][timeout:180];area["ISO3166-2"="CA-QC"]->.q;nwr["amenity"="fuel"](area.q);out center tags;'


def dist(a, b, c, d):
    r = math.pi / 180
    h = math.sin((c - a) * r / 2) ** 2 + math.cos(a * r) * math.cos(c * r) * math.sin((d - b) * r / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def osm_fuel():
    data = urllib.parse.urlencode({"data": QUERY}).encode()
    req = urllib.request.Request(OVERPASS, data=data, headers={"User-Agent": "essence-quebec (projet personnel)"})
    els = json.load(urllib.request.urlopen(req, timeout=240))["elements"]
    out = []
    for e in els:
        lat = e.get("lat") or (e.get("center") or {}).get("lat")
        lon = e.get("lon") or (e.get("center") or {}).get("lon")
        t = e.get("tags", {})
        if lat is None:
            continue
        out.append({"lat": lat, "lon": lon, "oh": t.get("opening_hours", ""), "nom": t.get("brand") or t.get("name") or ""})
    return out


def key(s):
    return f"{s[4]:.5f},{s[5]:.5f}"


def rafraichir(stations):
    pois = osm_fuel()
    grille = {}
    for p in pois:
        grille.setdefault((round(p["lat"], 2), round(p["lon"], 2)), []).append(p)
    heures = {}
    for s in stations:
        best, bd = None, DIST_MAX
        for dy in (-0.01, 0, 0.01):
            for dx in (-0.01, 0, 0.01):
                for p in grille.get((round(s[4] + dy, 2), round(s[5] + dx, 2)), []):
                    d = dist(s[4], s[5], p["lat"], p["lon"])
                    if d < bd:
                        best, bd = p, d
        if best and best["oh"]:
            heures[key(s)] = best["oh"]
    return pois, heures


def main():
    with open(STATIONS, encoding="utf-8") as f:
        data = json.load(f)
    stations = data["stations"]
    stats = "--stats" in sys.argv
    try:
        with open(CACHE, encoding="utf-8") as f:
            cache = json.load(f)
    except Exception:
        cache = {"maj": 0, "heures": {}}
    if stats or time.time() - cache.get("maj", 0) > MAX_AGE:
        try:
            pois, heures = rafraichir(stations)
            cache = {"maj": int(time.time()), "heures": heures}
            os.makedirs("data", exist_ok=True)
            with open(CACHE, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            print(f"OSM : {len(pois)} stations, {sum(1 for p in pois if p['oh'])} avec heures · associées à la Régie : {len(heures)}/{len(stations)}")
            if stats:
                for s in stations:
                    if "costco" in (s[0] + s[1]).lower():
                        print("COSTCO", s[2][:50], "→", heures.get(key(s), "(aucune heure)"))
                import collections
                print("Exemples :", collections.Counter(heures.values()).most_common(8))
        except Exception as e:
            print("Heures OSM indisponibles :", e)
    h = cache.get("heures", {})
    for s in stations:
        while len(s) < 11:
            s.append("")
        s[10] = h.get(key(s), "")
    with open(STATIONS, "w", encoding="utf-8") as f:
        f.write('{"ts":"%s","source":"%s","stations":[\n' % (data.get("ts", ""), data.get("source", "")))
        f.write(",\n".join(json.dumps(s, ensure_ascii=False, separators=(",", ":")) for s in stations))
        f.write("\n]}\n")


if __name__ == "__main__":
    main()
