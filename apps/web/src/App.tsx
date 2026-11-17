const GH = "https://github.com/zamdevio/dsweb";

export default function App() {
  return (
    <div className="page">
      <div className="grain" aria-hidden />
      <header className="hero">
        <img className="mark" src="/dsweb.png" width={88} height={88} alt="dsweb" />
        <p className="brand">dsweb</p>
        <h1 className="headline">DeepSeek web, from your terminal.</h1>
        <p className="lede">
          Unofficial CLI and local OpenAI-compatible proxy for chat.deepseek.com —
          not the Platform API, not affiliated with DeepSeek.
        </p>
        <div className="cta">
          <a className="btn primary" href={`${GH}#quick-start`}>
            Quick start
          </a>
          <a className="btn ghost" href={GH}>
            GitHub
          </a>
        </div>
      </header>

      <section className="strip" aria-label="capabilities">
        <p>
          <code>./dsweb ask</code>
          <span>one-shot</span>
        </p>
        <p>
          <code>./dsweb serve</code>
          <span>OpenAI /v1</span>
        </p>
        <p>
          <code>./dsweb cloudflared</code>
          <span>public tunnel</span>
        </p>
      </section>

      <footer className="foot">
        <span>MIT · thedsweb.pages.dev</span>
        <a href={`${GH}/blob/main/docs/overview.md`}>legal / unofficial</a>
      </footer>
    </div>
  );
}
