import type { CSSProperties, ReactNode } from "react";

type Props = {
  title: string;
  children: ReactNode;
  actions?: ReactNode;
  style?: CSSProperties;
};

export function Panel({ title, children, actions, style }: Props) {
  return (
    <section className="panel" style={style}>
      <div className="panel-heading">
        <h2>{title}</h2>
        {actions ? <div className="panel-actions">{actions}</div> : null}
      </div>
      {children}
    </section>
  );
}
