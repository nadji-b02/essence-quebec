"""Ouvre la page publiée dans un vrai navigateur, va dans l'onglet Carte et prend des captures."""
import asyncio, os, sys, time
from playwright.async_api import async_playwright

URL = os.environ.get("URL", "https://nadji-b02.github.io/essence-quebec/") + f"?t={int(time.time())}"

async def main():
    os.makedirs("captures", exist_ok=True)
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, timezone_id="America/Toronto",
                                  geolocation={"latitude": 45.556, "longitude": -73.748}, permissions=["geolocation"],
                                  user_agent="Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Mobile Safari/537.36")
        pg = await ctx.new_page()
        erreurs = []
        pg.on("pageerror", lambda e: erreurs.append(f"pageerror: {e}"))
        pg.on("console", lambda m: erreurs.append(f"console.{m.type}: {m.text}") if m.type in ("error", "warning") else None)
        pg.on("requestfailed", lambda r: erreurs.append(f"échec: {r.url[:90]} {r.failure}"))
        pg.on("response", lambda r: erreurs.append(f"HTTP {r.status}: {r.url[:90]}") if r.status >= 400 else None)
        await pg.goto(URL, wait_until="networkidle")
        await pg.wait_for_timeout(2500)
        await pg.screenshot(path="captures/accueil.png")
        print("Heure locale :", await pg.evaluate("new Date().toString()"))
        print("Bouton prix différent :", await pg.locator("#hero [data-sig]").count())
        print("Colonnes signalement/fraîcheur :", await pg.evaluate("fetch('stations.json?t='+Date.now()).then(r=>r.json()).then(d=>{const s=d.stations; return {colonnes: s[0].length, avecDate: s.filter(x=>x[12]).length, signales: s.filter(x=>x[11]).length}})"))
        print("Ouvertes seulement :", await pg.is_checked("#openCk"))
        print("Station conseillée :", (await pg.inner_text("#hero")).replace("\n", " / ")[:220])
        print("Autres choix :", (await pg.inner_text("#list")).replace("\n", " / ")[:300])
        tout = lambda: pg.evaluate("document.querySelector('#v-list').innerText")
        cc = lambda t: [l for l in t.split("\n") if "Costco" in l or "fermé" in l.lower()][:4]
        print("Costco/fermé (ouvertes seulement) :", cc(await tout()))
        await pg.click("#openCk"); await pg.wait_for_timeout(500)
        await pg.click("#moreBtn") if await pg.is_visible("#moreBtn") else None
        print("Costco/fermé (toutes) :", cc(await tout()))
        print("Toutes (fermées incluses) :", (await pg.inner_text("#hero")).replace("\n", " / ")[:220])
        await pg.screenshot(path="captures/toutes.png")
        await pg.click("#openCk"); await pg.wait_for_timeout(300)
        await pg.click(".bnav button[data-t=map]")
        await pg.wait_for_timeout(6000)
        await pg.screenshot(path="captures/carte.png")
        tuiles = await pg.evaluate("document.querySelectorAll('.leaflet-tile-loaded').length")
        # Trajet Laval -> Québec avec le vrai serveur d'itinéraires
        await pg.click(".bnav button[data-t=route]")
        await pg.type("#rtTo", "2450 boulevard Laurier Québec", delay=40)
        await pg.wait_for_timeout(2500)
        sug = await pg.evaluate("[...document.querySelectorAll('#rtForm .sug button')].map(b=>b.textContent)")
        print("Suggestions :", sug)
        if sug:
            await pg.click("#rtForm .sug li:first-child button")
        await pg.click("#rtForm button[type=submit]")
        await pg.wait_for_timeout(9000)
        await pg.screenshot(path="captures/trajet.png")
        note = await pg.text_content("#rtNote")
        heros = (await pg.inner_text("#rtHero")).replace("\n", " / ")
        print("Trajet :", note)
        print("Arrêt conseillé :", heros[:260])
        trajet_ok = "OSRM" in (note or "")
        epingles = await pg.evaluate("document.querySelectorAll('.pin').length")
        print(f"Tuiles chargées : {tuiles} · épingles : {epingles}")
        print("\n".join(erreurs) or "Aucune erreur")
        await b.close()
        sys.exit(0 if tuiles > 0 and epingles > 0 and trajet_ok else 1)

asyncio.run(main())
