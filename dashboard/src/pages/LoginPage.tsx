export function LoginPage() {
  return (
    <main className="login-shell">
      <section className="login-card">
        <h1>JARVIS Dashboard</h1>
        <p>
          Melde dich mit Discord an. Der Zugriff wird serverseitig gegen die
          erlaubten Discord User-IDs und Rollen geprüft.
        </p>
        <a className="discord-button" href="/dashboard/auth/discord/start">
          Mit Discord einloggen
        </a>
        <p className="muted">
          Das Dashboard speichert keinen Token im Local Storage. Die Session läuft über ein HttpOnly Cookie.
        </p>
      </section>
    </main>
  );
}
