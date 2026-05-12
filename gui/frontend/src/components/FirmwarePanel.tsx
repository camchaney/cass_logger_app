import { useCallback, useEffect, useRef, useState } from 'react'
import type { DeviceStatus, FirmwareDownloadStatus, FirmwareFlashStatus, FirmwareState } from '../types'

const VARIANTS = ['std', 'i2c_1', 'i2c_2']

interface Props {
	status: DeviceStatus
}

type FlowStep = 'idle' | 'downloading' | 'flashing' | 'done' | 'error'

export default function FirmwarePanel({ status }: Props) {
	const api = window.pywebview?.api

	const [fwState, setFwState] = useState<FirmwareState | null>(null)
	const [variant, setVariant] = useState<string>('std')
	const [flowStep, setFlowStep] = useState<FlowStep>('idle')
	const [dlStatus, setDlStatus] = useState<FirmwareDownloadStatus | null>(null)
	const [flashStatus, setFlashStatus] = useState<FirmwareFlashStatus | null>(null)
	const [downloadTaskId, setDownloadTaskId] = useState<string | null>(null)
	const [flashTaskId, setFlashTaskId] = useState<string | null>(null)
	const [pendingRtcSync, setPendingRtcSync] = useState(false)
	const [rtcSyncing, setRtcSyncing] = useState(false)
	const [rtcSyncMsg, setRtcSyncMsg] = useState<string | null>(null)
	const dlPollRef = useRef<ReturnType<typeof setInterval> | null>(null)
	const flashPollRef = useRef<ReturnType<typeof setInterval> | null>(null)
	const rtcSyncInProgressRef = useRef(false)

	// Default to first available variant from manifest once loaded
	useEffect(() => {
		if (fwState?.available_variants.length) setVariant(fwState.available_variants[0])
	}, [fwState?.available_variants])

	// Poll firmware manifest until it resolves from 'unknown'
	const fwStatePollRef = useRef<ReturnType<typeof setInterval> | null>(null)
	useEffect(() => {
		if (!api) return
		const check = async () => {
			const res = await api.get_firmware_state()
			if (!res.ok || !res.data) return
			setFwState(res.data)
			if (res.data.state !== 'unknown' && fwStatePollRef.current) {
				clearInterval(fwStatePollRef.current)
				fwStatePollRef.current = null
			}
		}
		check()
		fwStatePollRef.current = setInterval(check, 2000)
		return () => { if (fwStatePollRef.current) clearInterval(fwStatePollRef.current) }
	}, [api])

	// Poll download status
	useEffect(() => {
		if (!downloadTaskId || !api) return
		dlPollRef.current = setInterval(async () => {
			const res = await api.get_firmware_download_status(downloadTaskId)
			if (!res.ok || !res.data) return
			setDlStatus(res.data)
			if (res.data.status === 'done') {
				if (dlPollRef.current) clearInterval(dlPollRef.current)
				// Automatically proceed to flash
				startFlash(downloadTaskId)
			} else if (res.data.status === 'error') {
				if (dlPollRef.current) clearInterval(dlPollRef.current)
				setFlowStep('error')
			}
		}, 500)
		return () => { if (dlPollRef.current) clearInterval(dlPollRef.current) }
	}, [downloadTaskId, api])

	// Poll flash status
	useEffect(() => {
		if (!flashTaskId || !api) return
		flashPollRef.current = setInterval(async () => {
			const res = await api.get_firmware_flash_status(flashTaskId)
			if (!res.ok || !res.data) return
			setFlashStatus(res.data)
			if (res.data.status === 'done') {
				if (flashPollRef.current) clearInterval(flashPollRef.current)
				setFlowStep('done')
				setPendingRtcSync(true)
			} else if (res.data.status === 'error') {
				if (flashPollRef.current) clearInterval(flashPollRef.current)
				setFlowStep('error')
			}
		}, 500)
		return () => { if (flashPollRef.current) clearInterval(flashPollRef.current) }
	}, [flashTaskId, api])

	// Auto-sync RTC once device reconnects after a successful flash.
	// Uses a ref to prevent concurrent calls — state-based guards would re-trigger
	// the effect and potentially loop. Waits 3 s after connect so the device has
	// time to fully boot before we send a serial command. Retries once if the
	// first attempt fails with a "not connected" error (race with App.tsx's
	// check_alive poll calling disconnect() between our get_status and set_rtc_time).
	useEffect(() => {
		if (!pendingRtcSync || !status.connected || rtcSyncInProgressRef.current || !api) return
		rtcSyncInProgressRef.current = true
		setRtcSyncing(true)
		const doSync = async () => {
			// Stabilisation delay — device may have just come back from reboot
			await new Promise(res => setTimeout(res, 3000))
			let res = await api.set_rtc_time()
			if (!res.ok && res.error?.toLowerCase().includes('not connected')) {
				// Race with the status poll — wait a bit and retry once
				await new Promise(r => setTimeout(r, 3000))
				res = await api.set_rtc_time()
			}
			rtcSyncInProgressRef.current = false
			setRtcSyncing(false)
			setPendingRtcSync(false)
			setRtcSyncMsg(res.ok ? 'RTC synced to current time.' : `RTC sync failed: ${res.error}`)
		}
		doSync()
	}, [pendingRtcSync, status.connected, api])

	const startFlash = useCallback(async (dlTaskId: string) => {
		if (!api) return
		setFlowStep('flashing')
		const res = await api.start_firmware_flash(dlTaskId, variant)
		if (res.ok && res.data) {
			setFlashTaskId(res.data)
		} else {
			setFlowStep('error')
		}
	}, [api, variant])

	const handleUpdate = async () => {
		if (!api) return
		setFlowStep('downloading')
		setDlStatus(null)
		setFlashStatus(null)
		setDownloadTaskId(null)
		setFlashTaskId(null)
		const res = await api.start_firmware_download(variant)
		if (res.ok && res.data) {
			setDownloadTaskId(res.data)
		} else {
			setFlowStep('error')
		}
	}

	const handleReset = () => {
		setFlowStep('idle')
		setDlStatus(null)
		setFlashStatus(null)
		setDownloadTaskId(null)
		setFlashTaskId(null)
		setPendingRtcSync(false)
		setRtcSyncing(false)
		setRtcSyncMsg(null)
	}

	const updateAvailable = fwState?.latest_version != null

	return (
		<div>
			<div className="panel-title">Firmware</div>

			<div className="card">
				<div className="card-title">Device Firmware</div>
				<div style={{ display: 'grid', gridTemplateColumns: 'max-content 1fr', columnGap: 16, rowGap: 6 }}>
					<span className="muted" style={{ fontSize: 12 }}>Installed version</span>
					<span className="mono">{status.connected ? (status.fw_ver ?? '—') : '—'}</span>
					<span className="muted" style={{ fontSize: 12 }}>Latest available</span>
					<span className="mono">
						{fwState?.state === 'unknown' ? (
							<span className="muted">Checking…</span>
						) : fwState?.latest_version ? (
							fwState.latest_version
						) : (
							'—'
						)}
					</span>
					{fwState?.installed_version && (
						<>
							<span className="muted" style={{ fontSize: 12 }}>Last flashed</span>
							<span className="mono">{fwState.installed_version}</span>
						</>
					)}
				</div>
				{fwState?.changelog && (
					<p className="muted" style={{ fontSize: 12, marginTop: 10 }}>{fwState.changelog}</p>
				)}
				{fwState?.state === 'error' && (
					<div className="alert alert-warning" style={{ marginTop: 10, marginBottom: 0 }}>
						Could not reach firmware update server. Check your internet connection.
					</div>
				)}
			</div>

			{flowStep === 'idle' && (
				<div className="card">
					<div className="card-title">Flash Firmware</div>

					<div className="field" style={{ marginBottom: 16 }}>
						<label>Firmware variant</label>
						<select value={variant} onChange={(e) => setVariant(e.target.value)}>
							{(fwState?.available_variants.length ? fwState.available_variants : VARIANTS).map((v) => (
								<option key={v} value={v}>{v}</option>
							))}
						</select>
					</div>

					{!updateAvailable && fwState?.state === 'ready' && (
						<div className="alert alert-info" style={{ marginBottom: 12 }}>
							No firmware available from the update server yet.
						</div>
					)}

					<div className="row">
						<button
							className="btn btn-primary"
							onClick={handleUpdate}
							disabled={!updateAvailable || !status.connected}
						>
							{fwState?.state === 'unknown' ? 'Checking…' : `Flash v${fwState?.latest_version ?? '…'}`}
						</button>
						{!status.connected && (
							<span className="muted" style={{ fontSize: 12 }}>
								Device not connected — make sure it's plugged in before flashing.
							</span>
						)}
					</div>
				</div>
			)}

			{(flowStep === 'downloading' || flowStep === 'flashing') && (
				<div className="card">
					<div className="card-title">
						{flowStep === 'downloading' ? 'Downloading firmware…' : 'Flashing firmware…'}
					</div>

					{flowStep === 'downloading' && dlStatus && (
						<div style={{ marginBottom: 12 }}>
							<div className="progress-wrap" style={{ marginBottom: 6 }}>
								<div className="progress-bar" style={{ width: `${Math.round(dlStatus.progress * 100)}%` }} />
							</div>
							<span className="muted" style={{ fontSize: 12 }}>
								{dlStatus.total_bytes
									? `${(dlStatus.downloaded_bytes / 1024).toFixed(0)} / ${(dlStatus.total_bytes / 1024).toFixed(0)} KB`
									: 'Downloading…'}
							</span>
						</div>
					)}

					{flowStep === 'flashing' && flashStatus && (
						<div>
							<div className="row" style={{ marginBottom: 8 }}>
								<span className="spinner spinner-dark" />
								<span style={{ fontSize: 13 }}>
									{flashStatus.stage === 'rebooting' ? 'Rebooting device into bootloader…' : 'Writing firmware…'}
								</span>
							</div>
							{flashStatus.output && (
								<pre style={{
									fontSize: 11,
									fontFamily: "'SF Mono', 'Fira Code', monospace",
									background: 'var(--bg)',
									border: '1px solid var(--border)',
									borderRadius: 'var(--radius)',
									padding: '8px 10px',
									margin: 0,
									whiteSpace: 'pre-wrap',
									color: 'var(--text-muted)',
								}}>
									{flashStatus.output}
								</pre>
							)}
							<p className="muted" style={{ fontSize: 12, marginTop: 8, marginBottom: 0 }}>
								If the device doesn't reboot automatically, press the PROGRAM button on the logger.
							</p>
						</div>
					)}
				</div>
			)}

			{flowStep === 'done' && (
				<div className="card">
					<div className="alert alert-success" style={{ marginBottom: 12 }}>
						Firmware flashed successfully. The device is rebooting.
					</div>
					{rtcSyncing && (
						<div className="row muted" style={{ fontSize: 13, marginBottom: 12 }}>
							<span className="spinner spinner-dark" /> Waiting for device to reconnect to sync RTC…
						</div>
					)}
					{rtcSyncMsg && (
						<div className={`alert ${rtcSyncMsg.startsWith('RTC synced') ? 'alert-success' : 'alert-warning'}`} style={{ marginBottom: 12 }}>
							{rtcSyncMsg}
						</div>
					)}
					<button className="btn btn-secondary" onClick={handleReset}>Done</button>
				</div>
			)}

			{flowStep === 'error' && (
				<div className="card">
					<div className="alert alert-error" style={{ marginBottom: 12 }}>
						{flashStatus?.error ?? dlStatus?.error ?? 'An error occurred during the firmware update.'}
					</div>
					<button className="btn btn-secondary" onClick={handleReset}>Try Again</button>
				</div>
			)}
		</div>
	)
}
