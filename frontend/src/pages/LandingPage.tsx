import { Link } from 'react-router-dom'
import { useSensorData } from '../app/providers/SensorDataProvider'

export function LandingPage() {
  const { loading } = useSensorData()

  return (
    <main className="landing-page" aria-label="About WeatherSens">
      <section className="landing-page__hero-preview">
        <div className="landing-page__hero-overlay">
          <img
            className="landing-page__logo"
            src="/weathersenslogo_trsparent.png"
            alt="WeatherSens"
          />
          <p className="landing-page__tagline">
            Real-time environmental intelligence for healthier and more resilient cities.
          </p>

          {loading ? (
            <button className="landing-page__map-cta landing-page__map-cta--loading" disabled>
              <span className="landing-page__loading-spinner" />
              Loading map data...
            </button>
          ) : (
            <Link className="landing-page__map-cta" to="/map">
              Open Live Map
            </Link>
          )}

          <a className="landing-page__scroll-cue" href="#project-info">
            Scroll to read more
          </a>
        </div>
      </section>

      <section className="landing-page__content" id="project-info" aria-label="Project information">
        <article className="landing-page__panel">
          <h2>About The Project</h2>
          <p>
            WeatherSens visualizes urban air quality and temperature dynamics across Helsinki using
            sensor data interpolation, timeline playback, and interactive map analytics.
          </p>
        </article>

        <article className="landing-page__panel">
          <h2>What We Show</h2>
          <p>
            The live map combines station readings with interpolated surfaces to reveal neighborhood
            differences in PM2.5 risk and urban heat behavior over time.
          </p>
        </article>

        <article className="landing-page__panel">
          <h2>Why It Matters</h2>
          <p>
            The platform helps stakeholders identify localized environmental stress areas and
            communicate data-driven interventions for public health and climate adaptation.
          </p>
        </article>
      </section>
    </main>
  )
}
