import { useState } from 'react'
import {
	CartesianGrid,
	Line,
	LineChart,
	ResponsiveContainer,
	Tooltip,
	XAxis,
	YAxis,
} from 'recharts'
import type { BinParseResult, FitParseResult } from '../types'

type SubTab = 'bin' | 'fit' | 'metadata'

const FW_VERS = ['std', 'i2c_1', 'i2c_2']

export default function DataPanel() {
	const api = window.pywebview?.api
	const [subTab, setSubTab] = useState<SubTab>('bin')

	// ── .bin state ─────────────────────────────────────────────────────────────
	const [binPath, setBinPath] = useState<string | null>(null)
	const [fwVer, setFwVer] = useState('std')
	const [gainFork, setGainFork] = useState(1)
	const [gainShock, setGainShock] = useState(1)
	const [binResult, setBinResult] = useState<BinParseResult | null>(null)
	const [binError, setBinError] = useState<string | null>(null)
	const [binLoading, setBinLoading] = useState(false)
	const [binPlot, setBinPlot] = useState<'susp' | 'imu'>('susp')

	// ── .fit state ─────────────────────────────────────────────────────────────
	const [fitPath, setFitPath] = useState<string | null>(null)
	const [fitResult, setFitResult] = useState<FitParseResult | null>(null)
	const [fitError, setFitError] = useState<string | null>(null)
	const [fitLoading, setFitLoading] = useState(false)
	const [fitTab, setFitTab] = useState<'session' | 'record'>('session')

	// ── metadata state ─────────────────────────────────────────────────────────
	const [metaDir, setMetaDir] = useState<string | null>(null)
	const [metaResult, setMetaResult] = useState<{ firmware_version: string | null; device_id: string | null } | null>(null)
	const [metaError, setMetaError] = useState<string | null>(null)

	// ── .bin handlers ──────────────────────────────────────────────────────────

	const pickBin = async () => {
		if (!api) return
		const res = await api.pick_file(['Binary files (*.bin)', 'All files (*.*)'])
		if (res.ok && res.data) setBinPath(res.data)
	}

	const parseBin = async () => {
		if (!api || !binPath) return
		setBinLoading(true)
		setBinError(null)
		setBinResult(null)
		const res = await api.parse_bin(binPath, fwVer)
		if (res.ok && res.data) setBinResult(res.data)
		else setBinError(res.error ?? 'Parse failed')
		setBinLoading(false)
	}

	const exportBin = async () => {
		if (!api) return
		const res = await api.pick_save_file(['CSV files (*.csv)'])
		if (!res.ok || !res.data) return
		const exportRes = await api.export_csv('bin', res.data)
		if (!exportRes.ok) alert(exportRes.error)
	}

	// ── .fit handlers ──────────────────────────────────────────────────────────

	const pickFit = async () => {
		if (!api) return
		const res = await api.pick_file(['FIT files (*.fit)', 'All files (*.*)'])
		if (res.ok && res.data) setFitPath(res.data)
	}

	const parseFit = async () => {
		if (!api || !fitPath) return
		setFitLoading(true)
		setFitError(null)
		setFitResult(null)
		const res = await api.parse_fit(fitPath)
		if (res.ok && res.data) setFitResult(res.data)
		else setFitError(res.error ?? 'Parse failed')
		setFitLoading(false)
	}

	const exportFit = async (source: 'fit_session' | 'fit_record') => {
		if (!api) return
		const res = await api.pick_save_file(['CSV files (*.csv)'])
		if (!res.ok || !res.data) return
		const exportRes = await api.export_csv(source, res.data)
		if (!exportRes.ok) alert(exportRes.error)
	}

	// ── metadata handlers ──────────────────────────────────────────────────────

	const pickMetaDir = async () => {
		if (!api) return
		const res = await api.pick_directory()
		if (res.ok && res.data) setMetaDir(res.data)
	}

	const findMeta = async () => {
		if (!api || !metaDir) return
		setMetaError(null)
		setMetaResult(null)
		const res = await api.find_metadata(metaDir)
		if (res.ok && res.data) setMetaResult(res.data as typeof metaResult)
		else setMetaError(res.error ?? 'Not found')
	}

	// ── Chart data with gain applied ───────────────────────────────────────────

	const suspData = binResult?.susp_data.map((row) => ({
		...row,
		a0: typeof row.a0 === 'number' ? row.a0 * gainFork : row.a0,
		b0: typeof row.b0 === 'number' ? row.b0 * gainShock : row.b0,
	}))

	// ── Render ─────────────────────────────────────────────────────────────────

	return (
		<div>
			<h2 className="panel-title">Data Processing & Visualization</h2>

			<div className="tabs">
				<button className={`tab${subTab === 'bin' ? ' active' : ''}`} onClick={() => setSubTab('bin')}>
					Parse .bin
				</button>
				<button className={`tab${subTab === 'fit' ? ' active' : ''}`} onClick={() => setSubTab('fit')}>
					Parse .fit
				</button>
				<button className={`tab${subTab === 'metadata' ? ' active' : ''}`} onClick={() => setSubTab('metadata')}>
					Metadata
				</button>
			</div>

			{/* ── .bin ── */}
			{subTab === 'bin' && (
				<>
					<div className="card">
						<div className="card-title">Load Binary File</div>
						<div className="row" style={{ marginBottom: 12 }}>
							<button className="btn btn-secondary" onClick={pickBin}>Choose .bin file</button>
							{binPath && <span className="mono muted">{binPath.split('/').pop()}</span>}
						</div>
						<div className="field-row" style={{ marginBottom: 12 }}>
							<div className="field">
								<label>Firmware version</label>
								<select value={fwVer} onChange={(e) => setFwVer(e.target.value)}>
									{FW_VERS.map((v) => <option key={v} value={v}>{v}</option>)}
								</select>
							</div>
							<button
								className="btn btn-primary"
								onClick={parseBin}
								disabled={!binPath || binLoading}
							>
								{binLoading ? <span className="spinner" /> : null}
								{binLoading ? ' Parsing…' : ' Parse'}
							</button>
						</div>
						{binError && <div className="alert alert-error">{binError}</div>}
					</div>

					{binResult && (
						<>
							<div className="card">
								<div className="row" style={{ marginBottom: 12 }}>
									<span className="card-title" style={{ margin: 0 }}>
										Preview — {binResult.rows.toLocaleString()} rows · {binResult.columns.length} cols
									</span>
									<span className="spacer" />
									<button className="btn btn-ghost" onClick={exportBin}>⬇ Export CSV</button>
								</div>
								<div className="table-wrap" style={{ maxHeight: 220, overflowY: 'auto' }}>
									<table>
										<thead>
											<tr>{binResult.columns.map((c) => <th key={c}>{c}</th>)}</tr>
										</thead>
										<tbody>
											{binResult.preview.map((row, i) => (
												<tr key={i}>
													{binResult.columns.map((c) => (
														<td key={c} className="mono">
															{typeof row[c] === 'number' ? row[c].toFixed(3) : String(row[c] ?? '')}
														</td>
													))}
												</tr>
											))}
										</tbody>
									</table>
								</div>
							</div>

							{/* Charts */}
							<div className="card">
								<div className="row" style={{ marginBottom: 12 }}>
									<span className="card-title" style={{ margin: 0 }}>Charts</span>
									<div className="tabs" style={{ margin: 0, borderBottom: 'none' }}>
										<button className={`tab${binPlot === 'susp' ? ' active' : ''}`} onClick={() => setBinPlot('susp')}>Suspension</button>
										<button className={`tab${binPlot === 'imu' ? ' active' : ''}`} onClick={() => setBinPlot('imu')}>IMU</button>
									</div>
								</div>

								{binPlot === 'susp' && (
									<>
										<div className="row" style={{ marginBottom: 12, gap: 16 }}>
											<div className="field" style={{ margin: 0, flex: '0 1 140px' }}>
												<label>Fork gain (a0)</label>
												<input type="number" value={gainFork} step="0.1" onChange={(e) => setGainFork(parseFloat(e.target.value) || 1)} />
											</div>
											<div className="field" style={{ margin: 0, flex: '0 1 140px' }}>
												<label>Shock gain (b0)</label>
												<input type="number" value={gainShock} step="0.1" onChange={(e) => setGainShock(parseFloat(e.target.value) || 1)} />
											</div>
										</div>
										<div style={{ marginBottom: 16 }}>
											<div className="muted" style={{ fontSize: 11, marginBottom: 4 }}>Fork (a0)</div>
											<ResponsiveContainer width="100%" height={160}>
												<LineChart data={suspData}>
													<CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
													<XAxis dataKey="t" type="number" domain={['auto', 'auto']} tick={{ fontSize: 10 }} label={{ value: 't (s)', position: 'insideBottomRight', offset: -4, fontSize: 10 }} />
													<YAxis tick={{ fontSize: 10 }} />
													<Tooltip contentStyle={{ fontSize: 12 }} />
													<Line type="monotone" dataKey="a0" dot={false} stroke="#3b82f6" strokeWidth={1.5} />
												</LineChart>
											</ResponsiveContainer>
										</div>
										<div>
											<div className="muted" style={{ fontSize: 11, marginBottom: 4 }}>Shock (b0)</div>
											<ResponsiveContainer width="100%" height={160}>
												<LineChart data={suspData}>
													<CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
													<XAxis dataKey="t" type="number" domain={['auto', 'auto']} tick={{ fontSize: 10 }} label={{ value: 't (s)', position: 'insideBottomRight', offset: -4, fontSize: 10 }} />
													<YAxis tick={{ fontSize: 10 }} />
													<Tooltip contentStyle={{ fontSize: 12 }} />
													<Line type="monotone" dataKey="b0" dot={false} stroke="#f59e0b" strokeWidth={1.5} />
												</LineChart>
											</ResponsiveContainer>
										</div>
									</>
								)}

								{binPlot === 'imu' && (
									<>
										{(['gx', 'gy', 'gz'] as const).map((axis, idx) => (
											<div key={axis} style={{ marginBottom: idx < 2 ? 16 : 0 }}>
												<div className="muted" style={{ fontSize: 11, marginBottom: 4 }}>{axis}</div>
												<ResponsiveContainer width="100%" height={140}>
													<LineChart data={binResult.imu_data}>
														<CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
														<XAxis dataKey="t" type="number" domain={['auto', 'auto']} tick={{ fontSize: 10 }} label={{ value: 't (s)', position: 'insideBottomRight', offset: -4, fontSize: 10 }} />
														<YAxis tick={{ fontSize: 10 }} />
														<Tooltip contentStyle={{ fontSize: 12 }} />
														<Line type="monotone" dataKey={axis} dot={false} stroke={['#3b82f6', '#22c55e', '#ef4444'][idx]} strokeWidth={1.5} />
													</LineChart>
												</ResponsiveContainer>
											</div>
										))}
									</>
								)}
							</div>
						</>
					)}
				</>
			)}

			{/* ── .fit ── */}
			{subTab === 'fit' && (
				<>
					<div className="card">
						<div className="card-title">Load FIT File</div>
						<div className="row" style={{ marginBottom: 12 }}>
							<button className="btn btn-secondary" onClick={pickFit}>Choose .fit file</button>
							{fitPath && <span className="mono muted">{fitPath.split('/').pop()}</span>}
						</div>
						<button className="btn btn-primary" onClick={parseFit} disabled={!fitPath || fitLoading}>
							{fitLoading ? <span className="spinner" /> : null}
							{fitLoading ? ' Parsing…' : ' Parse'}
						</button>
						{fitError && <div className="alert alert-error" style={{ marginTop: 8 }}>{fitError}</div>}
					</div>

					{fitResult && (
						<div className="card">
							<div className="tabs" style={{ marginBottom: 12 }}>
								<button className={`tab${fitTab === 'session' ? ' active' : ''}`} onClick={() => setFitTab('session')}>
									Session ({fitResult.session.length} row{fitResult.session.length !== 1 ? 's' : ''})
								</button>
								<button className={`tab${fitTab === 'record' ? ' active' : ''}`} onClick={() => setFitTab('record')}>
									Record ({fitResult.record_rows.toLocaleString()} rows)
								</button>
							</div>

							<div className="row" style={{ marginBottom: 8 }}>
								<span className="spacer" />
								<button className="btn btn-ghost" onClick={() => exportFit(fitTab === 'session' ? 'fit_session' : 'fit_record')}>
									⬇ Export CSV
								</button>
							</div>

							{fitTab === 'session' && <FitTable cols={fitResult.session_columns} rows={fitResult.session} />}
							{fitTab === 'record' && (
								<>
									{fitResult.record_rows > 500 && (
										<div className="alert alert-info" style={{ marginBottom: 8 }}>
											Showing first 500 of {fitResult.record_rows.toLocaleString()} record rows.
										</div>
									)}
									<FitTable cols={fitResult.record_columns} rows={fitResult.record} />
								</>
							)}
						</div>
					)}
				</>
			)}

			{/* ── Metadata ── */}
			{subTab === 'metadata' && (
				<div className="card">
					<div className="card-title">Find & Parse Metadata</div>
					<p className="muted" style={{ marginBottom: 12, fontSize: 13 }}>
						Searches a local folder for a metadata.txt file and displays its contents.
					</p>
					<div className="row" style={{ marginBottom: 12 }}>
						<button className="btn btn-secondary" onClick={pickMetaDir}>Choose folder</button>
						{metaDir && <span className="mono muted">{metaDir}</span>}
					</div>
					<button className="btn btn-primary" onClick={findMeta} disabled={!metaDir} style={{ marginBottom: 12 }}>
						Search
					</button>
					{metaError && <div className="alert alert-error">{metaError}</div>}
					{metaResult && (
						<div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
							<div>
								<div className="muted" style={{ fontSize: 11, marginBottom: 4 }}>Firmware Version</div>
								<div className="mono">{metaResult.firmware_version ?? '—'}</div>
							</div>
							<div>
								<div className="muted" style={{ fontSize: 11, marginBottom: 4 }}>Device ID</div>
								<div className="mono">{metaResult.device_id ?? '—'}</div>
							</div>
						</div>
					)}
				</div>
			)}
		</div>
	)
}

function FitTable({ cols, rows }: { cols: string[]; rows: Record<string, unknown>[] }) {
	return (
		<div className="table-wrap" style={{ maxHeight: 300, overflowY: 'auto' }}>
			<table>
				<thead>
					<tr>{cols.map((c) => <th key={c}>{c}</th>)}</tr>
				</thead>
				<tbody>
					{rows.map((row, i) => (
						<tr key={i}>
							{cols.map((c) => (
								<td key={c} className="mono">
									{row[c] === null || row[c] === undefined ? '—' : String(row[c])}
								</td>
							))}
						</tr>
					))}
				</tbody>
			</table>
		</div>
	)
}
