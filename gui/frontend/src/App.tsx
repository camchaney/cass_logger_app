import { useCallback, useEffect, useRef, useState } from 'react'
import type { DeviceStatus } from './types'
import ConfigPanel from './components/ConfigPanel'
import DataPanel from './components/DataPanel'
import DevicePanel from './components/DevicePanel'
import FilesPanel from './components/FilesPanel'

type Panel = 'device' | 'files' | 'data' | 'config'

const NAV: { id: Panel; label: string; icon: string }[] = [
	{ id: 'device', label: 'Device', icon: '🔌' },
	{ id: 'files', label: 'Files', icon: '📁' },
	{ id: 'data', label: 'Data', icon: '📊' },
	{ id: 'config', label: 'Config', icon: '⚙️' },
]

function getApi() {
	return window.pywebview?.api ?? null
}

export default function App() {
	const [panel, setPanel] = useState<Panel>('device')
	const [status, setStatus] = useState<DeviceStatus>({ connected: false })
	const [connecting, setConnecting] = useState(false)
	const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

	const refreshStatus = useCallback(async () => {
		const api = getApi()
		if (!api) return
		const res = await api.get_status()
		if (res.ok && res.data) setStatus(res.data)
	}, [])

	useEffect(() => {
		// PyWebView fires a 'pywebviewready' event when the bridge is available
		const onReady = () => {
			refreshStatus()
			pollRef.current = setInterval(refreshStatus, 5000)
		}
		window.addEventListener('pywebviewready', onReady)
		// Also try immediately in case the event already fired (dev hot-reload)
		if (window.pywebview?.api) onReady()
		return () => {
			window.removeEventListener('pywebviewready', onReady)
			if (pollRef.current) clearInterval(pollRef.current)
		}
	}, [refreshStatus])

	const handleConnect = async () => {
		const api = getApi()
		if (!api) return
		setConnecting(true)
		const res = await api.connect()
		if (res.ok) await refreshStatus()
		else setStatus({ connected: false, error: res.error ?? undefined })
		setConnecting(false)
	}

	const handleDisconnect = async () => {
		const api = getApi()
		if (!api) return
		await api.disconnect()
		setStatus({ connected: false })
	}

	const statusLabel = connecting
		? 'Connecting…'
		: status.connected
		? `${status.fw_ver ?? 'Connected'} · ${status.device_id ?? ''}`
		: status.error ?? 'Not connected'

	return (
		<div className="layout">
			<header className="header">
				<span className="header-title">Cass Logger</span>
				<div className="header-status">
					<div
						className={`status-dot ${
							connecting ? 'connecting' : status.connected ? 'connected' : 'disconnected'
						}`}
					/>
					<span className="status-text">{statusLabel}</span>
					{status.connected ? (
						<button className="btn btn-secondary" onClick={handleDisconnect}>
							Disconnect
						</button>
					) : (
						<button
							className="btn btn-primary"
							onClick={handleConnect}
							disabled={connecting}
						>
							{connecting ? <span className="spinner" /> : null}
							{connecting ? 'Connecting…' : 'Connect'}
						</button>
					)}
				</div>
			</header>

			<nav className="sidebar">
				{NAV.map((n) => (
					<button
						key={n.id}
						className={`nav-item${panel === n.id ? ' active' : ''}`}
						onClick={() => setPanel(n.id)}
					>
						<span className="nav-icon">{n.icon}</span>
						{n.label}
					</button>
				))}
			</nav>

			<main className="content">
				{panel === 'device' && (
					<DevicePanel
						status={status}
						onConnected={refreshStatus}
					/>
				)}
				{panel === 'files' && <FilesPanel connected={status.connected} />}
				{panel === 'data' && <DataPanel />}
				{panel === 'config' && (
					<ConfigPanel connected={status.connected} onRefresh={refreshStatus} />
				)}
			</main>
		</div>
	)
}
