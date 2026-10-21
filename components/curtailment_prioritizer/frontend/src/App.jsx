
import { useCallback, useEffect, useState } from 'react';
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
  Scale,
  Sun,
} from 'lucide-react';
import './App.css';

const API_BASE = '/api';

const PLANTS = [
  { id: '6470900542', name: 'Laugfs Solar', capacity: 1 },
  { id: '6470900534', name: 'Irish & Eco Solar', capacity: 1 },
  { id: '6470900607', name: 'Dimo Solar / Thunkama', capacity: 1 },
  { id: '6470900828', name: 'Chandrikawewa Floating Solar', capacity: 1 },
  { id: '6470900836', name: 'Kiriibbanwewa Floating Solar', capacity: 1 },
];

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

function thresholdWasExceeded(data) {
  if (!data || typeof data !== 'object') return false;
  return (
    data.threshold_exceeded === true ||
    data.thresholdExceeded === true ||
    ['THRESHOLD_EXCEEDED', 'EXCEEDED', 'THRESHOLD_EXCEEDED_RED'].includes(data.threshold_status) ||
    data.operating_status === 'THRESHOLD_EXCEEDED' ||
    data.status === 'THRESHOLD_EXCEEDED'
  );
}

function StatusBadge({ status }) {
  const variant =
    status === 'TARGET_MET' ||
    status === 'NO_ACTION_REQUIRED'
      ? 'success'
      : status === 'TARGET_NOT_MET' ||
          status === 'INSUFFICIENT_DATA'
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
  const [scenarioId] = useState('S0001');
  const [operatorAuthorized, setOperatorAuthorized] = useState(false);

  const [assessment, setAssessment] = useState(null);
  const [assessmentLoading, setAssessmentLoading] = useState(false);
  const [assessmentError, setAssessmentError] = useState('');

  const [ranking, setRanking] = useState([]);
  const [rankingLoading, setRankingLoading] = useState(false);
  const [rankingError, setRankingError] = useState('');
  const [rankingStatus, setRankingStatus] = useState('not-loaded');

  const fetchRanking = useCallback(async () => {
    setRankingLoading(true);
    setRankingError('');
    setRankingStatus('loading');

    try {
      const response = await fetch(
        `${API_BASE}/fairness/ranking?recent_days=30`,
        { headers: { Accept: 'application/json' } },
      );

      const body = await response.json().catch(() => ({}));

      if (!response.ok) {
        const detail =
          typeof body.detail === 'string'
            ? body.detail
            : `Fairness ranking request failed (HTTP ${response.status}).`;

        throw new Error(detail);
      }

      // Support either a direct list or a wrapped API response.
      const records = Array.isArray(body)
        ? body
        : body.rankings ?? body.ranking ?? body.results ?? [];

      if (!Array.isArray(records) || records.length === 0) {
        throw new Error('The API returned no ranking records.');
      }

      setRanking(records);
      setRankingStatus('loaded');
    } catch (err) {
      setRanking([]);
      setRankingStatus('unavailable');
      setRankingError(
        err instanceof TypeError
          ? 'Could not connect to the API. Check that the backend is running.'
          : err.message || 'The fairness ranking could not be loaded.',
      );
    } finally {
      setRankingLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRanking();
  }, [fetchRanking]);

  async function runAssessment(event) {
    event.preventDefault();

    const id = scenarioId.trim();

    if (!id) {
      setAssessmentError('Enter a scenario ID before running the assessment.');
      return;
    }

    setAssessmentLoading(true);
    setAssessmentError('');
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
          ? body.detail
              .map((item) => item.msg || JSON.stringify(item))
              .join('; ')
          : typeof body.detail === 'string'
            ? body.detail
            : body.detail
              ? JSON.stringify(body.detail)
              : `Request failed with HTTP ${response.status}`;

        throw new Error(detail);
      }

      setAssessment(body);
    } catch (err) {
      setAssessmentError(
        err instanceof TypeError
          ? 'Could not connect to the API. Check that FastAPI is running.'
          : err.message || 'The assessment could not be completed.',
      );
    } finally {
      setAssessmentLoading(false);
    }
  }

  const recommendations = assessment?.recommendations ?? [];
  const proposed = assessment?.proposed_total_reduction_mw;
  const target = assessment?.target_reduction_mw;
  const shortfall = assessment?.remaining_shortfall_mw;
  const targetMet = assessment?.target_met;
  const hasAssessment = Boolean(assessment);

  const knownPlants = new Set(PLANTS.map((plant) => plant.id));
  const validRanking = ranking.filter((item) =>
    knownPlants.has(String(item.ac_number)),
  );

  const rankingHasFivePlants = validRanking.length === PLANTS.length;
  const rankingHasValidOrder =
    rankingHasFivePlants &&
    validRanking.every(
      (item) =>
        Number.isFinite(item.priority_rank) &&
        item.priority_rank > 0 &&
        item.ranking_status !== 'provisional_incomplete_history',
    );
  const rankingHistoryIncomplete =
    validRanking.some(
      (item) =>
        item.priority_rank == null ||
        item.ranking_status === 'provisional_incomplete_history' ||
        item.history_coverage === 'no_events_recorded_history_unverified',
    ) || !rankingHasFivePlants;
  const thresholdExceeded = thresholdWasExceeded(assessment);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#overview" aria-label="Solavera home">
          <span className="brand-mark">
            <Zap size={22} fill="currentColor" />
          </span>
          <span className="brand-copy">
            <strong>SOLAVERA</strong>
            <small>SOLAR INTELLIGENCE</small>
          </span>
        </a>

        <div className="sidebar-section-label">WORKSPACE</div>

        <nav className="sidebar-nav" aria-label="Main navigation">
          <a className="nav-item active" href="#overview">
            <Activity size={18} />
            <span>Overview</span>
            <span className="nav-indicator" />
          </a>

          <a className="nav-item" href="#generation">
            <Sun size={18} />
            <span>Solar plants</span>
          </a>

          <a className="nav-item" href="#ranking">
            <Scale size={18} />
            <span>Fairness ranking</span>
          </a>

          <a className="nav-item" href="#assessment">
            <SlidersHorizontal size={18} />
            <span>Assessment</span>
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
              <small>Human review required</small>
            </div>
          </div>
          <div className="sidebar-version">SOLAR CURTAILMENT ANALYTICS</div>
        </div>
      </aside>

      <main className="main-content" id="overview">
        <header className="topbar">
          <div className="breadcrumb">
            <span>Workspace</span>
            <ChevronRight size={14} />
            <strong>Solar curtailment analytics</strong>
          </div>

          <div className="topbar-right">
            <span className="environment-label">
              <span className="environment-dot" />
              {rankingStatus === 'loaded'
                ? 'Ranking data loaded'
                : 'Data status'}
            </span>
            <div className="avatar">SL</div>
          </div>
        </header>

        <section className="page-heading">
          <div>
            <div className="eyebrow">
              <span className="eyebrow-line" />
              SOLAR ENERGY MANAGEMENT
            </div>

            <h1>
              Curtailment <span>intelligence.</span>
            </h1>

            <p>
              Monitor five solar plants, review historical curtailment
              patterns, and support fairer future curtailment decisions.
            </p>
          </div>

          <button
            className="icon-button"
            onClick={fetchRanking}
            disabled={rankingLoading}
            title="Refresh fairness ranking"
            aria-label="Refresh fairness ranking"
          >
            {rankingLoading ? (
              <LoaderCircle size={18} className="spin" />
            ) : (
              <RefreshCw size={18} />
            )}
          </button>
        </section>

        {thresholdExceeded && (
          <section className="threshold-alert" role="alert" aria-live="assertive">
            <AlertCircle size={22} />
            <div>
              <strong>THRESHOLD EXCEEDED</strong>
              <p>
                The assessment API reported an operating threshold exceedance.
                Review operating conditions and recommendations before taking action.
              </p>
            </div>
          </section>
        )}

        <section className="metrics-grid" aria-label="Dashboard metrics">
          <MetricCard
            icon={Sun}
            label="Solar plants"
            value={String(PLANTS.length)}
            detail="Plants in the study"
            accent
          />

          <MetricCard
            icon={Gauge}
            label="Installed capacity"
            value="5 MW"
            detail="Five plants × 1 MW each"
          />

          <MetricCard
            icon={Scale}
            label="Plants ranked"
            value={`${validRanking.filter((item) => item.priority_rank != null).length} / 5`}
            detail={
              rankingStatus === 'loaded'
                ? 'Plants with a valid priority rank'
                : 'Awaiting valid ranking data'
            }
          />

          <MetricCard
            icon={Activity}
            label="Assessment status"
            value={hasAssessment ? 'Ready' : 'Not run'}
            detail={
              hasAssessment
                ? statusLabel(assessment.assessment_status)
                : 'No new assessment executed'
            }
          />
        </section>

        <section className="panel recommendations-panel" id="generation">
          <div className="panel-heading recommendations-heading">
            <div>
              <div className="section-kicker">01 / SOLAR PORTFOLIO</div>
              <h2>Plant overview</h2>
              <p>Five plants included in the fairness-prioritisation study.</p>
            </div>
            <div className="table-count">{PLANTS.length} plants</div>
          </div>

          <div className="table-scroll">
            <table className="recommendations-table">
              <thead>
                <tr>
                  <th>PLANT</th>
                  <th>ACCOUNT NUMBER</th>
                  <th>CAPACITY</th>
                  <th>RANKING STATUS</th>
                </tr>
              </thead>

              <tbody>
                {PLANTS.map((plant) => {
                  const record = validRanking.find(
                    (item) => String(item.ac_number) === plant.id,
                  );

                  return (
                    <tr key={plant.id}>
                      <td>
                        <div className="plant-cell">
                          <span className="plant-icon">
                            <Leaf size={17} />
                          </span>
                          <div>
                            <strong>{plant.name}</strong>
                            <small>Solar power plant</small>
                          </div>
                        </div>
                      </td>

                      <td>{plant.id}</td>
                      <td className="numeric-cell">
                        {formatMW(plant.capacity)}
                      </td>

                      <td>
                        {record && record.priority_rank != null ? (
                          <span className="status-badge success">
                            <span className="status-dot" />
                            Ranked #{record.priority_rank}
                          </span>
                        ) : record ? (
                          <span className="status-badge warning">
                            <span className="status-dot" />
                            History incomplete
                          </span>
                        ) : (
                          <span className="status-badge neutral">
                            <span className="status-dot" />
                            Awaiting data
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>

        <section className="panel recommendations-panel" id="ranking">
          <div className="panel-heading recommendations-heading">
            <div>
              <div className="section-kicker">02 / HISTORICAL FAIRNESS</div>
              <h2>Fairness ranking</h2>
              <p>
                Plants with a lower historical curtailment burden receive
                higher priority for future curtailment.
              </p>
            </div>

            <button
              className="icon-button"
              onClick={fetchRanking}
              disabled={rankingLoading}
              title="Refresh ranking"
              aria-label="Refresh ranking"
            >
              {rankingLoading ? (
                <LoaderCircle size={17} className="spin" />
              ) : (
                <RefreshCw size={17} />
              )}
            </button>
          </div>

          {rankingLoading ? (
            <div className="empty-state">
              <LoaderCircle size={24} className="spin" />
              <strong>Loading historical ranking</strong>
              <p>Retrieving the latest ranking from the API.</p>
            </div>
          ) : rankingError ? (
            <div className="empty-state">
              <div className="empty-icon">
                <AlertCircle size={24} />
              </div>
              <strong>Ranking data unavailable</strong>
              <p>{rankingError}</p>
              <p>
                The dashboard has not substituted sample rankings for missing
                historical evidence.
              </p>
            </div>
          ) : validRanking.length === 0 ? (
            <div className="empty-state">
              <div className="empty-icon">
                <Scale size={24} />
              </div>
              <strong>No ranking records available</strong>
              <p>
                A ranking will appear when the API returns usable historical
                curtailment data for the target plants.
              </p>
            </div>
          ) : (
            <>
              <div className={`result-banner ${rankingHistoryIncomplete ? 'ranking-warning' : ''}`}>
                {rankingHasValidOrder ? (
                  <CheckCircle2 size={19} />
                ) : (
                  <AlertCircle size={19} />
                )}
                <div>
                  <strong>
                    {rankingHasValidOrder
                      ? 'Provisional priority order available'
                      : 'Historical data incomplete — ranking unavailable'}
                  </strong>
                  <p>
                    {rankingHasValidOrder
                      ? 'A provisional order was returned. Verify historical coverage and obtain approval of the fairness weights before operational use.'
                      : 'Records were returned, but one or more plants have no recorded event history. No priority order is presented; missing records must not be interpreted as zero curtailment.'}
                  </p>
                </div>
              </div>

              <div className="table-scroll">
                <table className="recommendations-table">
                  <thead>
                    <tr>
                      <th>PRIORITY</th>
                      <th>PLANT</th>
                      <th>HISTORICAL ENERGY</th>
                      <th>EVENTS</th>
                      <th>BURDEN SCORE</th>
                      <th>DATA COVERAGE</th>
                    </tr>
                  </thead>

                  <tbody>
                    {[...validRanking]
                      .sort(
                        (a, b) =>
                          (a.priority_rank ?? Infinity) -
                          (b.priority_rank ?? Infinity),
                      )
                      .map((record) => {
                        const plant = PLANTS.find(
                          (item) =>
                            item.id === String(record.ac_number),
                        );

                        return (
                          <tr key={record.ac_number}>
                            <td>
                              <span className={`rank-pill ${record.priority_rank == null ? 'rank-unavailable' : ''}`}>
                                {record.priority_rank == null
                                  ? '—'
                                  : String(record.priority_rank).padStart(2, '0')}
                              </span>
                            </td>

                            <td>
                              <div className="plant-cell">
                                <span className="plant-icon">
                                  <Leaf size={17} />
                                </span>
                                <div>
                                  <strong>
                                    {record.plant_name ?? plant?.name ?? record.ac_number}
                                  </strong>
                                  <small>{record.ac_number}</small>
                                </div>
                              </div>
                            </td>

                            <td className="numeric-cell">
                              {record.energy_history_known === false
                                ? 'Unknown'
                                : record.historical_energy_mwh != null
                                  ? `${formatNumber(record.historical_energy_mwh, 2)} MWh`
                                  : '—'}
                            </td>

                            <td className="numeric-cell">
                              {formatNumber(record.event_count, 0)}
                            </td>

                            <td className="numeric-cell">
                              {formatNumber(record.burden_score, 3)}
                            </td>
                            <td>
                              <span className={`status-badge ${record.history_coverage === 'recorded_events_found' ? 'neutral' : 'warning'}`}>
                                <span className="status-dot" />
                                {record.history_coverage === 'recorded_events_found'
                                  ? 'Events found; completeness unverified'
                                  : 'History unverified'}
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                  </tbody>
                </table>
              </div>

              <p className="muted-copy">
                Ranking scores are decision-support indicators. The current
                dataset contains 116 deduplicated working records, but event
                history is unverified for plants with no recorded events.
                Missing records are not evidence of zero curtailment. No
                automatic curtailment commands are issued.
              </p>
            </>
          )}
        </section>

        <section className="workspace-grid">
          <article className="panel assessment-panel" id="assessment">
            <div className="panel-heading">
              <div>
                <div className="section-kicker">03 / SCENARIO ASSESSMENT</div>
                <h2>Reduction assessment</h2>
                <p>
                  Run the existing scenario assessment to review its
                  recommendations.
                </p>
              </div>

              <div className="panel-icon">
                <SlidersHorizontal size={19} />
              </div>
            </div>

            <form onSubmit={runAssessment}>
              <div className="authorization-note">
                <div className="authorization-icon">
                  <ShieldCheck size={19} />
                </div>

                <div className="authorization-copy">
                  <strong>Operator review required</strong>
                  <p>
                    This assessment generates recommendations only. It does
                    not send curtailment commands to any plant.
                  </p>
                </div>

                <label className="switch">
                  <input
                    type="checkbox"
                    checked={operatorAuthorized}
                    onChange={(event) =>
                      setOperatorAuthorized(event.target.checked)
                    }
                    disabled={assessmentLoading}
                    aria-label="Set operator authorisation flag"
                  />
                  <span className="switch-track" />
                </label>
              </div>

              <button
                className="primary-button"
                type="submit"
                disabled={assessmentLoading}
              >
                {assessmentLoading ? (
                  <>
                    <LoaderCircle size={17} className="spin" />
                    Preparing assessment
                  </>
                ) : (
                  <>
                    Run assessment
                    <ArrowUpRight size={17} />
                  </>
                )}
              </button>
            </form>

            {assessmentError && (
              <div className="error-banner" role="alert">
                <AlertCircle size={18} />
                <div>
                  <strong>Assessment failed</strong>
                  <p>{assessmentError}</p>
                </div>
              </div>
            )}

            {hasAssessment && (
              <div className="result-banner">
                <CheckCircle2 size={19} />
                <div>
                  <strong>Assessment completed</strong>
                  <p>
                    Scenario {assessment.event_id} ·{' '}
                    {recommendations.length} recommendation
                    {recommendations.length === 1 ? '' : 's'} returned.
                  </p>
                </div>
                <StatusBadge status={assessment.assessment_status} />
              </div>
            )}

            <div className="assessment-footnote">
              <Clock3 size={14} />
              Recommendations are advisory and require operational review.
            </div>
          </article>

          <article className="panel outcome-panel">
            <div className="panel-heading">
              <div>
                <div className="section-kicker">04 / ASSESSMENT RESULTS</div>
                <h2>Reduction overview</h2>
                <p>
                  {hasAssessment
                    ? `Scenario ${assessment.event_id}`
                    : 'Run an assessment to view its results.'}
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
                  <strong>
                    {hasAssessment ? formatMW(proposed) : '—'}
                  </strong>
                </div>

                <div className="legend-row">
                  <span className="legend-swatch target-swatch" />
                  <span>Required reduction</span>
                  <strong>{hasAssessment ? formatMW(target) : '—'}</strong>
                </div>

                <div className="legend-row">
                  <span className="legend-swatch shortfall-swatch" />
                  <span>Remaining shortfall</span>
                  <strong>
                    {hasAssessment ? formatMW(shortfall) : '—'}
                  </strong>
                </div>
              </div>
            </div>

            <div
              className={`outcome-message ${
                hasAssessment && !targetMet ? 'needs-attention' : ''
              }`}
            >
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
                        : 'Reduction target remains unmet'}
                    </strong>
                    <p>
                      {targetMet
                        ? 'The proposed allocation reaches the calculated target within the model tolerance.'
                        : 'Review the available generation, recommendations, and assessment limitations.'}
                    </p>
                  </div>
                </>
              ) : (
                <>
                  <CircleHelp size={18} />
                  <div>
                    <strong>Awaiting assessment</strong>
                    <p>Results will appear here after execution.</p>
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
                <span>Operator authorisation</span>
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

        {hasAssessment && (
          <section className="panel rationale-panel">
            <div className="panel-heading">
              <div>
                <div className="section-kicker">05 / EXPLAINABILITY</div>
                <h2>Assessment rationale</h2>
                <p>Reasons supplied by the assessment engine.</p>
              </div>

              <div className="panel-icon">
                <CircleHelp size={19} />
              </div>
            </div>

            {recommendations.length > 0 ? (
              <div className="rationale-list">
                {recommendations.map((plant) => (
                  <div
                    className="rationale-item"
                    key={plant.plant_id}
                  >
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
                No plant-level rationale was returned for this assessment.
              </p>
            )}

            {assessment.limitations?.length > 0 && (
              <div className="limitations-box">
                <div className="limitations-heading">
                  <AlertCircle size={17} />
                  <strong>Assumptions and limitations</strong>
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
            <strong>
              Explainable decision support · Human oversight required
            </strong>
            <p>
              Fairness rankings depend on available historical records.
              Scenario recommendations should be reviewed against operational
              evidence before use. This dashboard does not issue curtailment
              commands.
            </p>
          </div>

          <button
            className="icon-button"
            onClick={() => {
              setAssessment(null);
              setAssessmentError('');
            }}
            title="Clear assessment results"
            aria-label="Clear assessment results"
          >
            <RefreshCw size={17} />
          </button>
        </section>

        <footer className="page-footer">
          <span>SOLAVERA · SOLAR INTELLIGENCE</span>
          <span>CURTAILMENT FAIRNESS & ANALYTICS</span>
        </footer>
      </main>
    </div>
  );
}

export default App;
