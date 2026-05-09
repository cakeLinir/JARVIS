import type { ReactNode } from "react";

export type Column<T> = {
  key: string;
  label: string;
  render: (row: T) => ReactNode;
};

type Props<T> = {
  rows: T[];
  columns: Column<T>[];
  emptyText?: string;
};

export function DataTable<T>({ rows, columns, emptyText = "Keine Einträge." }: Props<T>) {
  if (rows.length === 0) {
    return <div className="empty">{emptyText}</div>;
  }

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map(column => (
              <th key={column.key}>{column.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {columns.map(column => (
                <td key={column.key}>{column.render(row)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
