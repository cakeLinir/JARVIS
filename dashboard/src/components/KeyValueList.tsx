import type { ReactNode } from "react";

type Item = {
  label: string;
  value: ReactNode;
};

type Props = {
  items: Item[];
};

export function KeyValueList({ items }: Props) {
  return (
    <div className="kv-list">
      {items.map(item => (
        <div className="kv-item" key={item.label}>
          <span className="kv-label">{item.label}</span>
          <span className="kv-value">{item.value}</span>
        </div>
      ))}
    </div>
  );
}
