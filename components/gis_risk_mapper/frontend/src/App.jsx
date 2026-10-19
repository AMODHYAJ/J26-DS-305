import { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle, Search, Zap,
} from 'lucide-react';
import {
  MapContainer, TileLayer, CircleMarker, Tooltip as MapTooltip,
  useMap,
} from 'react-leaflet';
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import 'leaflet/dist/leaflet.css';
import './App.css';

const DATA_URL = '/data/transformer_risk.json';
const TIER_COLORS = { High: '#FF8F87', Medium: '#E4C58A', Low: '#D7FA75' };
const number = (value, digits = 0) =>
  typeof value === 'number' && Number.isFinite(value)
    ? value.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits })
    : '—';
const percentage = (value, digits = 1) =>
  typeof value === 'number' && Number.isFinite(value) ? `${number(value * 100, digits)}%` : '—';
const tierOf = (item) => item.synthetic_summary?.tier ?? 'Unknown';
const probOf = (item) => item.synthetic_day_prediction?.predicted_export_probability ?? null;
const rankOf = (item) => item.synthetic_summary?.priority_rank ?? Number.MAX_SAFE_INTEGER;

function MapAutoFit({ locations }) {
  const map = useMap();
  const coordsKey = locations.map((point) => `${point.id}:${point.latitude}:${point.longitude}`).join('|');
  useEffect(() => {
    if (locations.length === 1) {
      map.setView([locations[0].latitude, locations[0].longitude], 12);
    } else if (locations.length > 1) {
      map.fitBounds(locations.map((point) => [point.latitude, point.longitude]), {
        padding: [36, 36], maxZoom: 13,
      });
    }
  }, [map, coordsKey]); // coordsKey reflects filter changes
  return null;
}

function Pill({ tier }) {
  return <span className={`tier-pill tier-${String(tier).toLowerCase()}`}>{tier || 'Unknown'}</span>;
}

function Stat({ label, value, detail, tone }) {
  return (
    <div className={`stat-card ${tone ? `stat-${tone}` : ''}`}>
      <div className="stat-top">
        <span className="stat-label">{label}</span>
      </div>
      <div className="stat-value">{value}</div>
      <div className="stat-detail">{detail}</div>
    </div>
  );
}

export default function App() {
  const [payload, setPayload] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [csc, setCsc] = useState('All');
  const [feeder, setFeeder] = useState('All');
  const [tier, setTier] = useState('All');
  const [sort, setSort] = useState('rank');
  const [selectedId, setSelectedId] = useState(null);

  useEffect(() => {
    let active = true;
    fetch(DATA_URL, { cache: 'no-store' })
      .then((response) => {
        if (!response.ok) throw new Error(`Data file not available (HTTP ${response.status}).`);
        return response.json();
      })
      .then((data) => {
        if (!Array.isArray(data.transformers) || !data.metadata) {
          throw new Error('Unexpected JSON structure. Regenerate the file with predict_risk.py.');
        }
        if (active) setPayload(data);
      })
      .catch((e) => { if (active) setError(e.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const transformers = payload?.transformers ?? [];
  const cscOptions = useMemo(() => [...new Set(transformers.map((t) => t.csc).filter(Boolean))].sort(), [transformers]);
  const feederOptions = useMemo(() => [...new Set(transformers.filter((t) => csc === 'All' || t.csc === csc).map((t) => t.feeder).filter(Boolean))].sort(), [transformers, csc]);

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    const result = transformers.filter((t) =>
      (csc === 'All' || t.csc === csc) &&
      (feeder === 'All' || t.feeder === feeder) &&
      (tier === 'All' || tierOf(t) === tier) &&
      (!term || [t.sin, t.csc, t.feeder, t.section, t.gss].some((v) => String(v ?? '').toLowerCase().includes(term)))
    );
    result.sort((a, b) => {
      if (sort === 'probability') return (probOf(b) ?? -1) - (probOf(a) ?? -1) || rankOf(a) - rankOf(b);
      if (sort === 'solar') return (b.solar_kw ?? -1) - (a.solar_kw ?? -1) || rankOf(a) - rankOf(b);
      return rankOf(a) - rankOf(b);
    });
    return result;
  }, [transformers, csc, feeder, tier, search, sort]);

  const chosen = filtered.find((t) => t.id === selectedId) ?? filtered[0] ?? null;
  const locations = useMemo(() => filtered.filter((t) =>
    t.has_coordinates && Number.isFinite(t.latitude) && Number.isFinite(t.longitude)
  ), [filtered]);
  const predictedPositive = filtered.filter((t) => t.synthetic_day_prediction?.predicted_export_event === 1).length;
  const highCount = filtered.filter((t) => tierOf(t) === 'High').length;
  const breakdown = useMemo(() => {
    const groups = new Map();
    for (const item of filtered) {
      if (!groups.has(item.csc)) groups.set(item.csc, { name: item.csc, Low: 0, Medium: 0, High: 0 });
      const t = tierOf(item);
      if (t in groups.get(item.csc)) groups.get(item.csc)[t] += 1;
    }
    return Array.from(groups.values()).sort((a, b) => a.name.localeCompare(b.name));
  }, [filtered]);

  const goTo = (id) => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  const clearFilters = () => { setSearch(''); setCsc('All'); setFeeder('All'); setTier('All'); setSort('rank'); };

  if (loading) return <div className="loading-screen">Preparing your C3 dashboard…</div>;
  if (error || !payload) return (
    <div className="error-screen">
      <AlertTriangle size={36} />
      <h1>Dashboard data not found</h1>
      <p>{error || 'No data loaded.'}</p>
      <code>python components/gis_risk_mapper/predict_risk.py --output components/gis_risk_mapper/frontend/public/data/transformer_risk.json</code>
      <p>Run this command from your repository root, then refresh the page. Keep the JSON local and Git-ignored.</p>
    </div>
  );

  const metadata = payload.metadata;
  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand-row">
          <div className="brand-symbol"><Zap size={20} fill="currentColor" /></div>
          <div><strong>SOLAVERA</strong><span>GRID INTELLIGENCE </span></div>
        </div>
        <nav className="header-nav" aria-label="Dashboard navigation">
          <button className="nav-active" onClick={() => goTo('overview')}>Overview</button>
          <button onClick={() => goTo('gis-map')}>GIS Map</button>
          <button onClick={() => goTo('rankings')}>Rankings</button>
          <button onClick={() => goTo('methodology')}>Methodology</button>
        </nav>
        <div className="header-right">

        </div>
      </header>

      <main className="main-content">
        <section id="overview" className="page-intro">
          <div>
            <div className="eyebrow"><span className="eyebrow-dot" /> DISTRIBUTION NETWORK INTELLIGENCE </div>
            <h1>Transformer <span>Intelligence </span></h1>
            <p>Explore predicted midday export conditions and spatial priorities across the CEB study area.</p>
          </div>
          <div className="snapshot-box"><span>ACTIVE SIMULATION</span><strong>Day {metadata.simulated_day_index}</strong><small>{metadata.simulated_date} · 11:00–14:00 window</small><div className="snapshot-bottom">SYNTHETIC SCENARIO <span>↗</span></div></div>
        </section>

        <div className="notice"><AlertTriangle size={17} /><span><strong>Research simulation</strong> — Predictions, exposure tiers and scores use synthetic operating scenarios, not measured reverse power flow or validated operational risk.</span><span className="notice-tag">SYNTHETIC</span></div>

        <section className="stats-grid" aria-label="Dashboard statistics">
          <Stat label="Total transformers" value={number(filtered.length)} detail={`of ${transformers.length} CEB records · filtered`} />
          <Stat label="Mapped locations" value={number(locations.length)} detail={`of ${filtered.length} current transformer records`} tone="blue" />
          <Stat label="Predicted export" value={number(predictedPositive)} detail="simulation day · 11:00–14:00" tone="purple" />
          <Stat label="High exposure tier" value={number(highCount)} detail="49-day simulated summary" tone="lime" />
        </section>

        <section className="filters-panel" aria-label="Transformer filters">
          <div className="panel-heading"><div><strong>Explore transformers</strong></div><button className="text-button" onClick={clearFilters}>Reset filters</button></div>
          <div className="filter-grid">
            <label className="search-control"><span>Search transformer</span><div className="search-input"><Search size={17} /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="SIN, section or feeder…" /></div></label>
            <label><span>CSC area</span><select value={csc} onChange={(e) => { setCsc(e.target.value); setFeeder('All'); }}><option>All</option>{cscOptions.map((v) => <option key={v}>{v}</option>)}</select></label>
            <label><span>Feeder</span><select value={feeder} onChange={(e) => setFeeder(e.target.value)}><option>All</option>{feederOptions.map((v) => <option key={v}>{v}</option>)}</select></label>
            <label><span>Exposure tier</span><select value={tier} onChange={(e) => setTier(e.target.value)}><option>All</option>{['High','Medium','Low'].map((v) => <option key={v}>{v}</option>)}</select></label>
          </div>
        </section>

        <section id="gis-map" className="map-detail-grid">
          <div className="panel map-panel">
            <div className="panel-header"><div><h2>Transformer GIS map</h2><p>Only transformers with CEB-provided geographic coordinates</p></div><span className="mini-counter">{locations.length} locations</span></div>
            {locations.length ? (
              <div className="map-wrap">
                <MapContainer center={[6.8, 80.7]} zoom={10} scrollWheelZoom={false} className="leaflet-map">
                  <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                  <MapAutoFit locations={locations} />
                  {locations.map((point) => (
                    <CircleMarker key={point.id} center={[point.latitude, point.longitude]}
                      radius={point.id === chosen?.id ? 10 : 6}
                      pathOptions={{ color: '#212322', weight: point.id === chosen?.id ? 3 : 1.8, fillColor: TIER_COLORS[tierOf(point)] || '#999A9B', fillOpacity: 0.94 }}
                      eventHandlers={{ click: () => setSelectedId(point.id) }}>
                      <MapTooltip direction="top"><strong>{point.sin}</strong> · {point.csc}<br />Tier: {tierOf(point)} · Rank #{rankOf(point)}</MapTooltip>
                    </CircleMarker>
                  ))}
                </MapContainer>
                <div className="map-legend">{['Low','Medium','High'].map((t) => <span key={t}><i style={{ background: TIER_COLORS[t] }} />{t}</span>)}</div>
              </div>
            ) : <div className="map-empty"><strong>No mapped locations</strong><span>Try broadening your filters. Unmapped transformers remain in the table.</span></div>}
            <div className="map-footnote">Map coverage: {metadata.mapped_count} of {metadata.transformer_count} total transformers. Missing coordinates are never estimated.</div>
          </div>

          <div className="panel detail-panel">
            <div className="panel-header"><div><h2>Transformer details</h2><p>Click a marker or ranked table row</p></div></div>
            {chosen ? <>
              <div className="detail-title"><div><span>TRANSFORMER</span><h3>{chosen.sin}</h3><p>{chosen.csc} · {chosen.feeder}</p></div><Pill tier={tierOf(chosen)} /></div>
              <div className="detail-highlight"><span>Simulated midday export probability</span><strong>{percentage(probOf(chosen))}</strong><small>Random Forest · {chosen.synthetic_day_prediction?.date}</small></div>
              <div className="detail-metrics">
                <div><span>Exposure priority</span><strong>#{number(chosen.synthetic_summary?.priority_rank)}</strong></div>
                <div><span>Simulated exposure score</span><strong>{number(chosen.synthetic_summary?.exposure_score, 3)}</strong></div>
                <div><span>Transformer rating</span><strong>{number(chosen.kva)} kVA</strong></div>
                <div><span>Connected solar</span><strong>{number(chosen.solar_kw, 2)} kW</strong></div>
                <div><span>Simulated export frequency</span><strong>{percentage(chosen.synthetic_summary?.export_frequency)}</strong></div>
                <div><span>Map coordinates</span><strong>{chosen.has_coordinates ? 'Available' : 'Unavailable'}</strong></div>
              </div>
              <div className="detail-note">The tier and exposure score summarize the full synthetic period. The probability applies only to the selected simulated day.</div>
            </> : <div className="detail-empty">No transformers match these filters.</div>}
          </div>
        </section>

        <section className="panel chart-panel">
          <div className="panel-header"><div><h2>Simulated exposure distribution</h2><p>Counts of Low / Medium / High tiers by CSC within current filters</p></div></div>
          {breakdown.length ? <div className="chart-wrap"><ResponsiveContainer width="100%" height="100%"><BarChart data={breakdown} margin={{ top: 8, right: 12, bottom: 0, left: -16 }}><CartesianGrid strokeDasharray="3 6" vertical={false} stroke="#383B39" /><XAxis dataKey="name" tick={{ fill: '#A6A8A3', fontSize: 12 }} axisLine={false} tickLine={false} /><YAxis allowDecimals={false} tick={{ fill: '#A6A8A3', fontSize: 12 }} axisLine={false} tickLine={false} /><Tooltip contentStyle={{ background: '#282B29', border: '1px solid #454844', borderRadius: 12, color: '#F4F5EE' }} cursor={{ fill: '#ffffff08' }} /><Legend iconType="circle" wrapperStyle={{ color: '#D5D7CE', fontSize: 12 }} /><Bar dataKey="Low" stackId="tiers" fill={TIER_COLORS.Low} /><Bar dataKey="Medium" stackId="tiers" fill={TIER_COLORS.Medium} /><Bar dataKey="High" stackId="tiers" fill={TIER_COLORS.High} radius={[4,4,0,0]} /></BarChart></ResponsiveContainer></div> : <p className="empty-inline">No data for this selection.</p>}
        </section>

        <section id="rankings" className="panel rankings-panel">
          <div className="panel-header"><div><h2>Transformer priority rankings</h2><p>All transformers included, whether mapped or unmapped</p></div><label className="sort-control"><select value={sort} onChange={(e) => setSort(e.target.value)} aria-label="Sort transformers"><option value="rank">Priority rank</option><option value="probability">Predicted probability</option><option value="solar">Connected solar capacity</option></select></label></div>
          <div className="table-scroll"><table><thead><tr><th>Rank</th><th>Transformer</th><th>CSC / feeder</th><th>Rating</th><th>Solar capacity</th><th>Exposure tier</th><th>Predicted export</th><th>Mapped</th></tr></thead><tbody>{filtered.map((item) => <tr key={item.id} className={chosen?.id === item.id ? 'selected-row' : ''} onClick={() => setSelectedId(item.id)}><td className="rank-cell">#{number(item.synthetic_summary?.priority_rank)}</td><td><strong>{item.sin}</strong></td><td>{item.csc}<small>{item.feeder}</small></td><td>{number(item.kva)} kVA</td><td>{number(item.solar_kw, 2)} kW</td><td><Pill tier={tierOf(item)} /></td><td><strong>{percentage(probOf(item))}</strong></td><td>{item.has_coordinates ? <span className="mapped-text">Yes</span> : <span className="muted">—</span>}</td></tr>)}</tbody></table>{filtered.length === 0 && <p className="empty-inline">No matching transformers. Reset your filters to see all records.</p>}</div>
          <div className="table-footer">Showing {filtered.length} of {transformers.length} transformers · Click any row to inspect its details</div>
        </section>

        <section id="methodology" className="methodology-panel"><div><h2>Methodology & data provenance</h2></div><p><strong>Real CEB attributes:</strong> transformer identifiers, connected PV capacities, ratings, feeder details and available coordinates. <strong>Synthetic:</strong> simulated demand and PV conditions, exposure tiers, ranking and Random Forest export probabilities. Forecast inputs are limited to 10:00 and preceding simulated days; the target window is 11:00–14:00. The unverified <code>Loads.xlsx</code> is not used in this dashboard.</p><p><strong>Research limitation:</strong> these are simulated-condition results, not observations or validated operational risk probabilities. No prediction accuracy on real CEB measurements is implied.</p></section>
        <footer className="page-footer"><span>S-GISM © 2026 · C3 Research Prototype</span><span>CEB infrastructure · Local and confidential</span></footer>
      </main>
    </div>
  );
}
