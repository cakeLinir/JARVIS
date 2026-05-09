type Props = {
  data: unknown;
};

export function JsonDetails({ data }: Props) {
  return (
    <details className="json-details">
      <summary>Rohdaten / Diagnose-JSON</summary>
      <pre>{JSON.stringify(data, null, 2)}</pre>
    </details>
  );
}
