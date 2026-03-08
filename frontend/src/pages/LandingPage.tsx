import { Link } from 'react-router-dom'
import { FaChartLine, FaHeartPulse, FaMapLocationDot } from 'react-icons/fa6'
import { useSensorData } from '../app/providers/SensorDataProvider'

export function LandingPage() {
  const { loading } = useSensorData()
  const studyHref = `${import.meta.env.BASE_URL}weathersens_study.pdf`
  const flowVideoHref = `${import.meta.env.BASE_URL}PerfectlyAlignedWeatherFlow.mp4`
  const uiPreviewHref = `${import.meta.env.BASE_URL}map-preview.png`
  const sensorPhotoHref = `${import.meta.env.BASE_URL}sensor.png`

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

          <div className="landing-page__cta-group">
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

            <a
              className="landing-page__secondary-cta"
              href={studyHref}
              target="_blank"
              rel="noreferrer"
            >
              Our Research
            </a>
          </div>

          <a className="landing-page__scroll-cue" href="#project-info">
            Scroll to read more
          </a>
        </div>
      </section>

      <section className="landing-page__content" id="project-info" aria-label="Project information">
        <section className="landing-page__summary-grid" aria-label="Key project points">
          <article className="landing-page__panel landing-page__summary-panel">
            <div className="landing-page__panel-heading">
              <span className="landing-page__panel-icon" aria-hidden="true">
                <FaMapLocationDot />
              </span>
              <h2>Problem</h2>
            </div>
            <p>
              <strong>Poor air quality</strong> causes more than 300,000 deaths annually in the EU
              alone. On top of that, <strong>rising heat stress</strong> is intensifying with climate
              change, while cities still lack sufficiently detailed data to know where resources
              should be focused.
            </p>
          </article>

          <article className="landing-page__panel landing-page__summary-panel">
            <div className="landing-page__panel-heading">
              <span className="landing-page__panel-icon" aria-hidden="true">
                <FaChartLine />
              </span>
              <h2>Solution</h2>
            </div>
            <p>
              WeatherSens combines <strong>sensor measurements</strong>, our own modelling pipeline,
              and open-source environmental data to produce <strong>detailed local insight</strong> that is far more actionable than coarse regional measurements alone.
            </p>
            <div className="landing-page__mini-flow" aria-label="Solution pipeline overview">
              <span className="landing-page__mini-flow-node">Stations</span>
              <span className="landing-page__mini-flow-arrow" aria-hidden="true">↓</span>
              <span className="landing-page__mini-flow-node">Combined Data</span>
              <span className="landing-page__mini-flow-arrow" aria-hidden="true">↓</span>
              <span className="landing-page__mini-flow-node landing-page__mini-flow-node--accent">
                Insights
              </span>
            </div>
          </article>

          <article className="landing-page__panel landing-page__summary-panel">
            <div className="landing-page__panel-heading">
              <span className="landing-page__panel-icon" aria-hidden="true">
                <FaHeartPulse />
              </span>
              <h2>Target Group</h2>
            </div>
            <p>
              <strong>Cities and wellbeing services counties</strong> can use this to target
              preventive action where the real problems are. That supports
              <strong> regulatory compliance</strong> and can return value many times over the annual
              cost of the service through better-targeted long-term action.
            </p>
          </article>
        </section>

        <article className="landing-page__panel landing-page__panel--wide landing-page__feature-block">
          <div className="landing-page__feature-media">
            <video
              className="landing-page__video"
              src={flowVideoHref}
              autoPlay
              muted
              loop
              playsInline
              controls
            >
              Your browser does not support the video tag.
            </video>
          </div>
          <div className="landing-page__feature-notes">
            <p className="landing-page__feature-kicker">Model Flow</p>
            <h2>How the pipeline moves from observations to surfaces.</h2>
            <p>
              The animation summarizes the modelling path from sparse measurements and processing
              steps to the final gridded visualization shown in the interface.
            </p>
            <ul className="landing-page__feature-list">
              <li>Sensor observations anchor the local state of the system</li>
              <li>Interpolation fills spatial gaps between measurement locations</li>
              <li>Processed outputs are delivered into a map-ready visual layer</li>
            </ul>
          </div>
        </article>

        <article className="landing-page__panel landing-page__panel--wide landing-page__feature-block landing-page__feature-block--reverse">
          <div className="landing-page__feature-media">
            <img
              className="landing-page__feature-image"
              src={uiPreviewHref}
              alt="WeatherSens interface preview"
            />
          </div>
          <div className="landing-page__feature-notes">
            <p className="landing-page__feature-kicker">Interface Preview</p>
            <h2>What users can understand from the map at a glance.</h2>
            <p>
              The UI is designed to make localized conditions legible quickly through a map-first
              view rather than a table-heavy dashboard, covering both air-quality stress and
              temperature-driven urban health signals.
            </p>
            <ul className="landing-page__feature-list">
              <li>Spatial surfaces show where heat islands, PM2.5, and other temperature patterns differ by area</li>
              <li>Timeline playback exposes temporal shifts across the day</li>
              <li>Compact controls keep the focus on geographic interpretation and city health context</li>
            </ul>
          </div>
        </article>

        <article className="landing-page__panel landing-page__panel--wide landing-page__proof-block">
          <div className="landing-page__proof-copy">
            <p className="landing-page__feature-kicker">Technical Feasibility</p>
            <h2>Grounded in real sensor hardware.</h2>
            <p>
              WeatherSens is built around real environmental sensing hardware used to collect local
              measurements in the field. The sensor platform shown here predates the hackathon and
              demonstrates the practical data-collection basis of the system.
            </p>
            <p>
              The hackathon work focused on turning those measurements into an integrated pipeline
              for interpolation, modelling, API delivery, and map-based decision support.
            </p>
          </div>
          <figure className="landing-page__proof-media">
            <img
              className="landing-page__proof-image"
              src={sensorPhotoHref}
              alt="Environmental sensor hardware mounted outdoors"
            />
            <figcaption className="landing-page__proof-caption">
              Environmental sensor hardware used in the WeatherSens workflow.
            </figcaption>
          </figure>
        </article>
      </section>
    </main>
  )
}
