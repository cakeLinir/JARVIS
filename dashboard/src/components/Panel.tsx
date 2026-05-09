import type { ReactNode } from "react";

type Props = {
  title: string;
  children: ReactNode;
  actions?: ReactNode;
};

export function Panel({ title, children, actions }: Props) {
  return (
    <section className="panel">
      <div className="panel-heading">
        <h2>{title}</h2>
        {actions ? <div className="panel-actions">{actions}</div> : null}
      </div>
      {children}
    </section>
  );
}
