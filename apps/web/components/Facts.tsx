export default function Facts({ items }: { items: { label: string; value: React.ReactNode; note?: string }[] }) {
  return (
    <dl className="facts">
      {items.map((i) => (
        <div key={i.label}>
          <dt>{i.label}</dt>
          <dd>{i.value}{i.note && <small> {i.note}</small>}</dd>
        </div>
      ))}
    </dl>
  );
}
