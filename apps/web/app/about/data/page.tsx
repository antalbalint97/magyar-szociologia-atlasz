import type { Metadata } from "next";
import Link from "next/link";
import { IssueLink } from "@/components/CoverageNote";
import CoverageMeter, { Ratio } from "@/components/CoverageMeter";
import { coverageView, PAGE_TYPE_LABEL } from "@/lib/atlas/coverage";
import { recensProjectLinks, sziLeadGap } from "@/lib/atlas/notices";
import { overview } from "@/lib/atlas/overview";
import { atlas, coverageData } from "@/lib/atlas/server";
import { hu, percent } from "@/lib/atlas/vocab";

export const metadata: Metadata = { title: "Az adatokról" };

export default async function AboutData() {
  const a = await atlas();
  const v = coverageView(await coverageData());
  const o = overview(a);
  const szi = sziLeadGap(a);
  const recens = recensProjectLinks(a);
  const deferred = a.deferredMentions();
  return (
    <div className="wrap page">
      <div className="eyebrow">Módszertan és lefedettség · kiadás <code>{v.releaseId || a.info.releaseId}</code></div>
      <h1>Az adatokról</h1>
      <p className="lede" style={{ marginTop: 8 }}>
        Mit tud most az atlasz, honnan tudja, és mit nem tud még. Minden szám ennek a kiadásnak a saját lefedettségi
        jelentéséből vagy adataiból jön; minden arány mellett ott a nevező.
      </p>

      <section className="section" aria-labelledby="snapshot">
        <header><h2 id="snapshot">A forrás-snapshot</h2>{v.retrieved && <span className="aside">letöltve {v.retrieved.from.slice(0, 10)} és {v.retrieved.until.slice(0, 10)} között</span>}</header>
        <div className="split even">
          <div>
            <p>
              A pilot a TK (ELTE Társadalomtudományi Kutatóközpont) négy intézeti honlapját dolgozza fel: munkatárslistákat,
              kutatói profilokat, egységoldalakat és projektoldalakat. Összesen <strong>{hu(v.documents.total)}</strong> oldal.
              Más egyetemek, kutatóintézetek, publikációs adatbázisok és történeti források még nincsenek benne.
            </p>
            <ul className="rows compact">
              {v.sources.map((s) => (
                <li key={s.source}><strong>{s.label}</strong> — {s.long}{s.baseUrl && <> · <a href={s.baseUrl} rel="noreferrer">{s.baseUrl.replace(/^https?:\/\//, "")}</a></>}</li>
              ))}
            </ul>
          </div>
          <div className="table-scroll">
            <table className="data">
              <caption className="small muted" style={{ textAlign: "left", marginBottom: 6 }}>Letöltött oldalak forrásonként és típusonként</caption>
              <thead><tr><th>Forrás</th>{Object.keys(PAGE_TYPE_LABEL).map((t) => <th key={t} className="r">{PAGE_TYPE_LABEL[t]}</th>)}<th className="r">összesen</th></tr></thead>
              <tbody>
                {v.documents.bySource.map((s) => (
                  <tr key={s.source}><td>{s.label}</td>{Object.keys(PAGE_TYPE_LABEL).map((t) => <td key={t} className="r">{s.byType[t] ?? 0}</td>)}<td className="r">{s.total}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section className="section" aria-labelledby="model">
        <header><h2 id="model">Entitás vagy említés?</h2></header>
        <div className="cols-3">
          <div>
            <h3>Azonosított kutató</h3>
            <p>Csak az lesz kutató az atlaszban, akinek saját intézményi profiloldala van (vagy akit kézi döntés azonosít). Most: <strong>{hu(o.persons)}</strong> kutató.</p>
          </div>
          <div>
            <h3>Személyemlítés</h3>
            <p>Minden név, amely egy forrásoldalon szerepel. Egy említés akkor kötődik kutatóhoz, ha profil-link, azonosító vagy dokumentált szabály igazolja. A puszta névegyezés soha nem elég.</p>
          </div>
          <div>
            <h3>Projekt vagy projektemlítés</h3>
            <p>Projekt az, aminek saját projektoldala van ({hu(o.projects)}). A profilokon felsorolt többi cím projektemlítés marad, amíg bizonyíték nem köti egy projekthez.</p>
          </div>
        </div>
        <div className="legend-rows" style={{ marginTop: 24 }}>
          <div><div><span className="badge observed">megfigyelt</span></div><div>A forrásoldal kimondja (tagság, vezetés, részvétel). {hu(o.observedRelations)} kapcsolat.</div></div>
          <div><div><span className="badge derived">származtatott</span></div><div>Kulcsszó-szabály rendelte hozzá a profil vagy projektleírás szövegéből (témák, módszerek). {hu(o.derivedRelations)} kapcsolat. A szabályok pontosságát a <IssueLink n={15} /> méri.</div></div>
          <div><div><span className="badge open">azonosítatlan</span></div><div>Forrásban szereplő név vagy cím, bizonyított azonosítás nélkül. Nem csomópont a hálóban.</div></div>
          {deferred.length > 0 && <div><div><span className="badge open">elhalasztva</span></div><div>Kézi döntés tartja vissza, amíg egy másik kérdés el nem dől (pl. hogy egy felsorolt tevékenység projekt-e, <IssueLink n={9} />). Most {deferred.length} ilyen említés: {deferred.map((m) => `„${m.statedName}”`).join(", ")}.</div></div>}
        </div>
      </section>

      {v.available ? (
        <section className="section" aria-labelledby="resolution">
          <header><h2 id="resolution">Mennyit tudunk azonosítani?</h2><span className="aside">forrásonként, a megfigyelő oldal szerint</span></header>
          <div className="split even">
            <div>
              <h3>Személyemlítések {v.personMentionsAll && <span className="muted small">· összesen <Ratio {...v.personMentionsAll} /> azonosítva</span>}</h3>
              <CoverageMeter rows={v.personMentions} segmented caption="Azonosított említések / összes személyemlítés az adott forrás oldalain" />
            </div>
            <div>
              <h3>Projektemlítések {v.projectMentionsAll && <span className="muted small">· összesen <Ratio {...v.projectMentionsAll} /> azonosítva</span>}</h3>
              <CoverageMeter rows={v.projectMentions} segmented caption="Projekthez kötött említések / összes projektemlítés az adott forrás oldalain" />
            </div>
          </div>
          <div className="split even" style={{ marginTop: 32 }}>
            <div>
              <h3>Miért maradt nyitott egy projektemlítés?</h3>
              <table className="data">
                <tbody>{v.unresolvedProjectReasons.map((r) => <tr key={r.key}><td>{r.label}</td><td className="r">{hu(r.n)}</td></tr>)}</tbody>
              </table>
            </div>
            <div>
              <h3>Kutatók projektkapcsolattal {v.personsWithProjectsAll && <span className="muted small">· <Ratio {...v.personsWithProjectsAll} /></span>}</h3>
              <CoverageMeter rows={v.personsWithProjects} caption="Legalább egy megfigyelt projektkapcsolattal / az adott forrás profilos kutatói" />
              {v.coParticipationTies !== null && <p className="muted small">A közös projektekből adódó kutatópárok száma: {hu(v.coParticipationTies)}. Ez származtatott vetület, a nagy projektek túlsúlyával.</p>}
            </div>
          </div>
        </section>
      ) : (
        <p className="note">Ehhez a kiadáshoz nem tartozik lefedettségi jelentés (coverage.json), ezért a forrásonkénti bontás nem jeleníthető meg.</p>
      )}

      {v.fieldRows.length > 0 && (
        <section className="section" aria-labelledby="fields">
          <header><h2 id="fields">Mezők kitöltöttsége</h2><span className="aside">profilos kutatók forrásonként; egy kétprofilú kutató mindkét helyen számít</span></header>
          <div className="table-scroll">
            <table className="data">
              <thead><tr><th>Mező</th>{v.fieldRows[0].cells.map((c) => <th key={c.source} className="r">{v.personsWithProjects.find((x) => x.source === c.source)?.label ?? c.source}</th>)}</tr></thead>
              <tbody>{v.fieldRows.map((r) => (
                <tr key={r.key}><td>{r.label}</td>{r.cells.map((c) => <td key={c.source} className="r">{c.value ? <Ratio {...c.value} /> : "–"}</td>)}</tr>
              ))}</tbody>
            </table>
          </div>
          <p className="muted small">Ha egy honlap sablonja egy mezőt egyáltalán nem mutat, a 0% nem hiba, hanem a forrás sajátossága. A forrásokat csak azonos mezőkre érdemes összevetni.</p>
        </section>
      )}

      <section className="section" aria-labelledby="limits">
        <header><h2 id="limits">Ismert korlátok</h2></header>
        <ul className="rows">
          {szi && <li><strong>SZI projektvezetők és résztvevők.</strong> Az SZI {hu(szi.of)} projektjéből {hu(szi.n)} ({percent(szi.n, szi.of)}) megfigyelt vezető nélkül szerepel; ennek jelentős része egy ismert feldolgozási hiány: a régi oldalsablon címsor alatt sorolja a neveket (<IssueLink n={31} />).</li>}
          {recens && <li><strong>CSS-RECENS projektek.</strong> A profilok ritkán linkelnek projektoldalra: {hu(recens.of)} kutatóból {hu(recens.n)} ({percent(recens.n, recens.of)}) kapcsolódik projekthez. Ez a gyűjtés, nem a kutatócsoport jellemzője.</li>}
          <li><strong>Korábbi munkatársak és külső partnerek</strong> csak említésként szerepelnek, mert az atlasz a jelenlegi munkatárslistákból indul (<IssueLink n={28} />).</li>
          <li><strong>A témák kulcsszó-szabályokból származnak</strong>, nem a kutatók saját besorolásai; a szabályok pontossága még nincs mérve (<IssueLink n={15} />).</li>
          <li><strong>Nem minden „projekt” projekt.</strong> Egyes felsorolt tevékenységek (adatfelvételi programok, hírlevelek, hálózatok) típusa nyitott (<IssueLink n={9} />).</li>
          <li><strong>Nincs rangsor.</strong> Az atlasz nem számol központiságot és nem rangsorol kutatókat, amíg az elemzési alkalmasság nincs eldöntve (<IssueLink n={17} />).</li>
          <li><strong>Nincs történeti réteg.</strong> Az adatok a gyűjtés napján érvényes állapotot mutatják; a korábbi intézményi tagságok, az intézményi utódlás és a témavezetői kapcsolatok későbbi források feldolgozásával érkeznek.</li>
          {v.sentinels.missing.length > 0 && <li><strong>Hiányzó ellenőrző személyek:</strong> {v.sentinels.missing.join(", ")} — ismert hiány (<IssueLink n={13} />).</li>}
        </ul>
        {v.blindSpots.length > 0 && (
          <details className="evidence" style={{ marginTop: 12 }}>
            <summary>A lefedettségi jelentés vakfoltjai (eredeti, angol nyelvű megjegyzések)</summary>
            <div className="evidence-body"><ul>{v.blindSpots.map((b) => <li key={b} lang="en">{b}</li>)}</ul></div>
          </details>
        )}
      </section>

      <section className="section" aria-labelledby="repro">
        <header><h2 id="repro">Reprodukálhatóság</h2></header>
        <p>
          Minden kiadás a letöltött oldalakból újraépíthető; a kanonikus fájlok az igazság forrásai, a gráfadatbázis csak
          vetület. Az atlasz minden kapcsolatánál megmutatja a forrásoldalt, a letöltés dátumát és az idézett szövegrészt.{" "}
          <Link href="/network">Kezdd a hálózattal</Link>, vagy nézd meg a <a href="https://github.com/antalbalint97/magyar-szociologia-atlasz" rel="noreferrer">forráskódot</a>.
        </p>
      </section>
    </div>
  );
}
