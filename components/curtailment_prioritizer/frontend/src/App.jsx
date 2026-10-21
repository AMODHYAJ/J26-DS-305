
import { useState } from 'react';
import {
  Activity,
  AlertCircle,
  ArrowDownRight,
  ArrowUpRight,
  CheckCircle2,
  ChevronRight,
  CircleHelp,
  Clock3,
  Gauge,
  Leaf,
  LoaderCircle,
  RefreshCw,
  ShieldCheck,
  SlidersHorizontal,
  Zap,
} from 'lucide-react';
import './App.css';

const API_BASE = '/api';

function formatMW(value) {
  return typeof value === 'number' && Number.isFinite(value)
    ? `${value.toLocaleString(undefined, {
        minimumFractionDigits: 0,
        maximumFractionDigits: 3,
      })} MW`
    : '—';
}

function formatNumber(value, digits = 1) {
  return typeof value === 'number' && Number.isFinite(value)
    ? value.toLocaleString(undefined, {
        maximumFractionDigits: digits,
      })
    : '—';
}

function statusLabel(status) {
  return (
    {
      TARGET_MET: 'Target met',
      TARGET_NOT_MET: 'Target not met',
      NO_ACTION_REQUIRED: 'No action required',
      RAMP_DOWN_WARNING: 'Ramp-down warning',
      INSUFFICIENT_DATA: 'Insufficient data',
      ASSESSMENT_COMPLETE: 'Assessment complete',
    }[status] || status?.replaceAll('_', ' ') || 'Unknown'
  );
}

function StatusBadge({ status }) {
  const variant =
    status === 'TARGET_MET' || status === 'NO_ACTION_REQUIRED'
      ? 'success'
      : status === 'TARGET_NOT_MET' || status === 'INSUFFICIENT_DATA'
        ? 'warning'
        : 'neutral';

  return (
    <span className={`status-badge ${variant}`}>
      <span className="status-dot" />
      {statusLabel(status)}
    </span>
  );
}

function MetricCard({ icon: Icon, label, value, detail, accent = false }) {
  return (
    <article className={`metric-card ${accent ? 'metric-accent' : ''}`}>
      <div className="metric-top">
        <span className="metric-label">{label}</span>
        <span className="metric-icon">
          <Icon size={18} />
        </span>
      </div>
      <div className="metric-value">{value}</div>
      <div className="metric-detail">{detail}</div>
    </article>
  );
}

function App() {
  // Temporary demo scenario until Component 1 warning integration is connected.
  const [scenarioId] = useState('S0001');


  const [operatorAuthorized, setOperatorAuthorized] = useState(false);
  const [assessment, setAssessment] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function runAssessment(event) {
    event.preventDefault();

    const id = scenarioId.trim();

    if (!id) {
      setError('Enter a scenario ID before running the assessment.');
      return;
    }

    setLoading(true);
    setError('');
    setAssessment(null);

    try {
      const response = await fetch(
        `${API_BASE}/assess/${encodeURIComponent(id)}?operator_authorized=${operatorAuthorized}`,
        {
          method: 'POST',
          headers: { Accept: 'application/json' },
        },
      );

      const body = await response.json().catch(() => ({}));

      if (!response.ok) {
        const detail = Array.isArray(body.detail)
          ? body.detail.map((item) => item.msg || JSON.stringify(item)).join('; ')
          : typeof body.detail === 'string'
            ? body.detail
            : body.detail
              ? JSON.stringify(body.detail)
              : `Request failed with HTTP ${response.status}`;

        throw new Error(detail);
      }

      setAssessment(body);
    } catch (err) {
      setError(
        err instanceof TypeError
          ? 'Could not connect to the API. Check that FastAPI is running at http://127.0.0.1:8000.'
          : err.message || 'The assessment could not be completed.',
      );
    } finally {
      setLoading(false);
    }
  }

  const recommendations = assessment?.recommendations ?? [];
  const proposed = assessment?.proposed_total_reduction_mw;
  const target = assessment?.target_reduction_mw;
  const shortfall = assessment?.remaining_shortfall_mw;
  const targetMet = assessment?.target_met;
  const hasAssessment = Boolean(assessment);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#overview" aria-label="Curtailment Intelligence home">
          <span className="brand-mark">
            <Zap size={22} fill="currentColor" />
          </span>
          <span className="brand-copy">
            <strong>SOLAVERA</strong>
            <small>GRID INTELLIGENCE</small>
          </span>
        </a>

        <div className="sidebar-section-label">WORKSPACE</div>
        <nav className="sidebar-nav" aria-label="Main navigation">
          <a className="nav-item active" href="#overview">
            <Activity size={18} />
            <span>Overview</span>
            <span className="nav-indicator" />
          </a>
          <a className="nav-item" href="#assessment">
            <SlidersHorizontal size={18} />
            <span>Assessment</span>
          </a>
          <a className="nav-item" href="#recommendations">
            <Leaf size={18} />
            <span>Plant priorities</span>
          </a>
          <a className="nav-item" href="#methodology">
            <CircleHelp size={18} />
            <span>Methodology</span>
          </a>
        </nav>

        <div className="sidebar-bottom">
          <div className="system-card">
            <span className="system-pulse" />
            <div>
              <strong>Decision support</strong>
              <small>Control commands disabled</small>
            </div>
          </div>
          <div className="sidebar-version">COMPONENT 04 · PROTOTYPE</div>
        </div>
      </aside>

      <main className="main-content" id="overview">
        <header className="topbar">
          <div className="breadcrumb">
            <span>Components</span>
            <ChevronRight size={14} />
            <strong>Curtailment prioritisation</strong>
          </div>
          <div className="topbar-right">
            <span className="environment-label">
              <span className="environment-dot" />
              Synthetic environment
            </span>
            <div className="avatar">C4</div>
          </div>
        </header>

        <section className="page-heading">
          <div>
            <div className="eyebrow">
              <span className="eyebrow-line" />
              DISTRIBUTION CONTROL CENTRE
            </div>
            <h1> Curtailment <span>intelligence.</span></h1>
            <p>
              Explainable, plant-level prioritisation for distribution
              network loading scenarios.
            </p>
          </div>
          <div className="heading-status">
            <span className="live-dot" />
            Prototype online
          </div>
        </section>

        <section className="metrics-grid" aria-label="Assessment metrics">
          <MetricCard
            icon={Gauge}
            label="Required reduction"
            value={hasAssessment ? formatMW(target) : '—'}
            detail="Calculated target"
            accent
          />
          <MetricCard
            icon={ArrowDownRight}
            label="Proposed reduction"
            value={hasAssessment ? formatMW(proposed) : '—'}
            detail="Sum of recommendations"
          />
          <MetricCard
            icon={AlertCircle}
            label="Remaining shortfall"
            value={hasAssessment ? formatMW(shortfall) : '—'}
            detail="Unmet reduction target"
          />
          <MetricCard
            icon={Leaf}
            label="Plants prioritised"
            value={hasAssessment ? String(recommendations.length) : '—'}
            detail="Eligible recommendations"
          />
        </section>

        <section className="workspace-grid">
          <article className="panel assessment-panel" id="assessment">
            <div className="panel-heading">
              <div>
                <div className="section-kicker">01 / GRID WARNING</div>
                <h2>Active grid warning</h2>
                <p>
                  Review the thermal threshold warning and initiate a
                  plant-level reduction assessment.
                </p>
              </div>
              <div className="panel-icon">
                <SlidersHorizontal size={19} />
              </div>
            </div>


<form onSubmit={runAssessment}>
  <div className="section-kicker">01 / GRID WARNING</div>

  <div className="authorization-note">
    <div className="authorization-icon">
      <AlertCircle size={19} />
    </div>

    <div className="authorization-copy">
      <strong>Thermal threshold warning</strong>
      <p>
        Demo warning for interface testing. Component 1 is not
        connected yet, so this is not a live grid alert.
      </p>
    </div>
  </div>

  <div className="field-label">Assessment status</div>
  <p className="field-hint">
    A curtailment assessment will be prepared using the temporary
    synthetic scenario when you initiate it.
  </p>

  <div className="authorization-note">
    <div className="authorization-icon">
      <ShieldCheck size={19} />
    </div>

    <div className="authorization-copy">
      <strong>Operator review required</strong>
      <p>
        This action generates recommendations only. It does not
        send curtailment commands to any plant.
      </p>
    </div>

    <label className="switch">
      <input
        type="checkbox"
        checked={operatorAuthorized}
        onChange={(event) =>
          setOperatorAuthorized(event.target.checked)
        }
        disabled={loading}
        aria-label="Set operator authorisation flag"
      />
      <span className="switch-track" />
    </label>
  </div>

  <button
    className="primary-button"
    type="submit"
    disabled={loading}
  >
    {loading ? (
      <>
        <LoaderCircle size={17} className="spin" />
        Preparing reduction overview
      </>
    ) : (
      <>
        Start Reduction Overview
        <ArrowUpRight size={17} />
      </>
    )}
  </button>
</form>


            {error && (
              <div className="error-banner" role="alert">
                <AlertCircle size={18} />
                <div>
                  <strong>Assessment failed</strong>
                  <p>{error}</p>
                </div>
              </div>
            )}

            {hasAssessment && (
              <div className="result-banner">
                <CheckCircle2 size={19} />
                <div>
                  <strong>Assessment returned successfully</strong>
                  <p>
                    Scenario {assessment.event_id} ·{' '}
                    {recommendations.length} plant recommendation
                    {recommendations.length === 1 ? '' : 's'} returned.
                  </p>
                </div>
                <StatusBadge status={assessment.assessment_status} />
              </div>
            )}

            <div className="assessment-footnote">
              <Clock3 size={14} />
              Recommendations are advisory and require appropriate operational
              review.
            </div>
          </article>

          <article className="panel outcome-panel">
            <div className="panel-heading">
              <div>
                <div className="section-kicker">02 / ASSESSMENT OUTCOME</div>
                <h2>Reduction overview</h2>
                <p>
                  {hasAssessment
                    ? `Scenario ${assessment.event_id}`
                    : 'Run a scenario to populate the assessment results.'}
                </p>
              </div>
              {hasAssessment && (
                <StatusBadge status={assessment.assessment_status} />
              )}
            </div>

            <div className="outcome-visual">
              <div className="outcome-ring">
                <div className="ring-inner">
                  <span className="ring-number">
                    {hasAssessment
                      ? targetMet
                        ? '100%'
                        : target > 0
                          ? `${formatNumber((proposed / target) * 100, 0)}%`
                          : '—'
                      : '—'}
                  </span>
                  <span className="ring-caption">Target coverage</span>
                </div>
              </div>
              <div className="outcome-legend">
                <div className="legend-row">
                  <span className="legend-swatch proposed-swatch" />
                  <span>Proposed reduction</span>
                  <strong>{hasAssessment ? formatMW(proposed) : '—'}</strong>
                </div>
                <div className="legend-row">
                  <span className="legend-swatch target-swatch" />
                  <span>Required reduction</span>
                  <strong>{hasAssessment ? formatMW(target) : '—'}</strong>
                </div>
                <div className="legend-row">
                  <span className="legend-swatch shortfall-swatch" />
                  <span>Remaining shortfall</span>
                  <strong>{hasAssessment ? formatMW(shortfall) : '—'}</strong>
                </div>
              </div>
            </div>

            <div className={`outcome-message ${hasAssessment && !targetMet ? 'needs-attention' : ''}`}>
              {hasAssessment ? (
                <>
                  {targetMet ? (
                    <CheckCircle2 size={18} />
                  ) : (
                    <AlertCircle size={18} />
                  )}
                  <div>
                    <strong>
                      {targetMet
                        ? 'Proposed reduction meets the target'
                        : 'The reduction target remains unmet'}
                    </strong>
                    <p>
                      {targetMet
                        ? 'The proposed allocation reaches the calculated target within the model tolerance.'
                        : 'Eligible plant output was insufficient to meet the full target, or the model returned a partial assessment.'}
                    </p>
                  </div>
                </>
              ) : (
                <>
                  <CircleHelp size={18} />
                  <div>
                    <strong>Awaiting scenario</strong>
                    <p>Assessment results will appear here after execution.</p>
                  </div>
                </>
              )}
            </div>

            <div className="mini-stat-row">
              <div>
                <span>Scenario ID</span>
                <strong>{hasAssessment ? assessment.event_id : '—'}</strong>
              </div>
              <div>
                <span>Authorisation flag</span>
                <strong>
                  {hasAssessment
                    ? assessment.operator_authorized
                      ? 'True'
                      : 'False'
                    : '—'}
                </strong>
              </div>
            </div>
          </article>
        </section>

        <section className="panel recommendations-panel" id="recommendations">
          <div className="panel-heading recommendations-heading">
            <div>
              <div className="section-kicker">03 / PRIORITY ALLOCATION</div>
              <h2>Plant recommendations</h2>
              <p>
                Plants are displayed in the priority order returned by the
                assessment engine.
              </p>
            </div>
            <div className="table-count">
              {hasAssessment ? recommendations.length : 0} recommendations
            </div>
          </div>

          {!hasAssessment ? (
            <div className="empty-state">
              <div className="empty-icon">
                <Leaf size={24} />
              </div>
              <strong>No assessment results yet</strong>
              <p>Run a scenario to see its ranked plant recommendations.</p>
            </div>
          ) : recommendations.length === 0 ? (
            <div className="empty-state">
              <div className="empty-icon">
                <CheckCircle2 size={24} />
              </div>
              <strong>No plant reductions recommended</strong>
              <p>
                This scenario returned no plant recommendations. Check its
                assessment status and limitations for context.
              </p>
            </div>
          ) : (
            <div className="table-scroll">
              <table className="recommendations-table">
                <thead>
                  <tr>
                    <th>PRIORITY</th>
                    <th>PLANT</th>
                    <th>AVAILABLE GENERATION</th>
                    <th>PROPOSED REDUCTION</th>
                    <th>ALLOCATION</th>
                  </tr>
                </thead>
                <tbody>
                  {recommendations.map((plant) => {
                    const allocation =
                      plant.available_generation_mw > 0
                        ? Math.min(
                            100,
                            (plant.recommended_reduction_mw /
                              plant.available_generation_mw) *
                              100,
                          )
                        : 0;

                    return (
                      <tr key={`${plant.plant_id}-${plant.priority_rank}`}>
                        <td>
                          <span className="rank-pill">
                            {String(plant.priority_rank).padStart(2, '0')}
                          </span>
                        </td>
                        <td>
                          <div className="plant-cell">
                            <span className="plant-icon">
                              <Leaf size={17} />
                            </span>
                            <div>
                              <strong>{plant.plant_name}</strong>
                              <small>{plant.plant_id}</small>
                            </div>
                          </div>
                        </td>
                        <td className="numeric-cell">
                          {formatMW(plant.available_generation_mw)}
                        </td>
                        <td className="numeric-cell reduction-value">
                          {formatMW(plant.recommended_reduction_mw)}
                        </td>
                        <td>
                          <div className="allocation-cell">
                            <div className="allocation-track">
                              <div
                                className="allocation-fill"
                                style={{ width: `${allocation}%` }}
                              />
                            </div>
                            <span>{formatNumber(allocation, 0)}%</span>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {hasAssessment && (
          <section className="panel rationale-panel">
            <div className="panel-heading">
              <div>
                <div className="section-kicker">04 / EXPLAINABILITY</div>
                <h2>Why these plants?</h2>
                <p>Rationale supplied by the assessment engine.</p>
              </div>
              <div className="panel-icon">
                <CircleHelp size={19} />
              </div>
            </div>

            {recommendations.length > 0 ? (
              <div className="rationale-list">
                {recommendations.map((plant) => (
                  <div className="rationale-item" key={plant.plant_id}>
                    <div className="rationale-rank">
                      {String(plant.priority_rank).padStart(2, '0')}
                    </div>
                    <div>
                      <strong>{plant.plant_name}</strong>
                      <p>{plant.reason}</p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="muted-copy">
                No plant-level rationale was returned for this scenario.
              </p>
            )}

            {assessment.limitations?.length > 0 && (
              <div className="limitations-box">
                <div className="limitations-heading">
                  <AlertCircle size={17} />
                  <strong>Model assumptions and limitations</strong>
                </div>
                <ul>
                  {assessment.limitations.map((limitation, index) => (
                    <li key={`${index}-${limitation}`}>{limitation}</li>
                  ))}
                </ul>
              </div>
            )}
          </section>
        )}

        <section className="methodology-strip" id="methodology">
          <div className="methodology-icon">
            <ShieldCheck size={20} />
          </div>
          <div>
            <strong>Explainable decision support · Human oversight required</strong>
            <p>
              This prototype uses synthetic scenario data and an assumed
              contribution score. Recommendations are not validated electrical
              power-flow results and do not issue curtailment commands.
            </p>
          </div>
          <button
            className="icon-button"
            onClick={() => {
              setAssessment(null);
              setError('');
            }}
            title="Clear assessment results"
            aria-label="Clear assessment results"
          >
            <RefreshCw size={17} />
          </button>
        </section>

        <footer className="page-footer">
          <span>SOLAVERA · GRID INTELLIGENCE</span>
          <span>COMPONENT 04 / CURTAILMENT PRIORITISATION</span>
        </footer>
      </main>
    </div>
  );
}

export default App;
