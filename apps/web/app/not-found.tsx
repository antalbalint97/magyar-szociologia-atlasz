import Link from "next/link";

export default function NotFound() {
  return (
    <div className="wrap page">
      <h1>Nincs ilyen elem ebben a kiadásban</h1>
      <p className="lede" style={{ marginTop: 12 }}>
        Lehet, hogy az azonosító egy korábbi kiadásból származik, vagy az elem nem része a jelenlegi TK-snapshotnak.
      </p>
      <p><Link href="/">Vissza a kezdőlapra</Link> · <Link href="/search">Keresés</Link></p>
    </div>
  );
}
