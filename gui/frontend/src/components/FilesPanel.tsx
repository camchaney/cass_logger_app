import { useEffect, useRef, useState } from 'react'
import type { FileEntry, TaskStatus } from '../types'

interface Props {
	connected: boolean
}

function fmtBytes(b: number) {
	if (b < 1024) return `${b} B`
	if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`
	return `${(b / 1048576).toFixed(1)} MB`
}

export default function FilesPanel({ connected }: Props) {
	const api = window.pywebview?.api

	const [files, setFiles] = useState<FileEntry[]>([])
	const [loadingFiles, setLoadingFiles] = useState(false)
	const [filesError, setFilesError] = useState<string | null>(null)

	const [downloading, setDownloading] = useState(false)
	const [taskStatus, setTaskStatus] = useState<TaskStatus | null>(null)
	const [downloadMsg, setDownloadMsg] = useState<{ ok: boolean; text: string } | null>(null)
	const [downloadPath, setDownloadPath] = useState<string | null>(null)
	const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

	const [confirmDelete, setConfirmDelete] = useState(false)
	const [deleteMsg, setDeleteMsg] = useState<{ ok: boolean; text: string } | null>(null)

	const loadFiles = async () => {
		if (!api) return
		setLoadingFiles(true)
		setFilesError(null)
		const res = await api.list_files()
		if (res.ok && res.data) {
			setFiles(res.data)
		} else {
			setFilesError(res.error ?? 'Failed to list files')
		}
		setLoadingFiles(false)
	}

	useEffect(() => {
		if (connected) loadFiles()
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [connected])

	const startDownload = async () => {
		if (!api) return
		const dirRes = await api.pick_directory()
		if (!dirRes.ok || !dirRes.data) return

		setDownloading(true)
		setDownloadMsg(null)
		setTaskStatus(null)
		setDownloadPath(null)

		const res = await api.start_download(dirRes.data)
		if (!res.ok || !res.data) {
			setDownloadMsg({ ok: false, text: res.error ?? 'Failed to start download' })
			setDownloading(false)
			return
		}
		const taskId = res.data

		pollRef.current = setInterval(async () => {
			const st = await api.get_task_status(taskId)
			if (st.ok && st.data) {
				setTaskStatus(st.data)
				if (st.data.status === 'done') {
					clearInterval(pollRef.current!)
					setDownloading(false)
					if (st.data.result) setDownloadPath(st.data.result)
					setDownloadMsg({
						ok: true,
						text: st.data.error
							? st.data.error
							: `Saved to ${st.data.result}`,
					})
				} else if (st.data.status === 'error') {
					clearInterval(pollRef.current!)
					setDownloading(false)
					setDownloadMsg({ ok: false, text: st.data.error ?? 'Download failed' })
				}
			}
		}, 800)
	}

	useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current) }, [])

	const doDelete = async () => {
		if (!api) return
		setDeleteMsg(null)
		const res = await api.delete_all_files()
		if (res.ok) {
			setDeleteMsg({ ok: true, text: res.data ?? 'All files deleted' })
			setFiles([])
			setConfirmDelete(false)
		} else {
			setDeleteMsg({ ok: false, text: res.error ?? 'Delete failed' })
			setConfirmDelete(false)
		}
	}

	if (!connected) {
		return (
			<div>
				<h2 className="panel-title">File Management</h2>
				<div className="alert alert-info">Connect to a device to manage files.</div>
			</div>
		)
	}

	const progress = taskStatus
		? taskStatus.total > 0
			? taskStatus.current / taskStatus.total
			: taskStatus.progress
		: 0

	return (
		<div>
			<h2 className="panel-title">File Management</h2>

			{/* File list */}
			<div className="card">
				<div className="row" style={{ marginBottom: 12 }}>
					<span className="card-title" style={{ margin: 0 }}>Logger Files</span>
					<span className="spacer" />
					<button className="btn btn-secondary" onClick={loadFiles} disabled={loadingFiles}>
						{loadingFiles ? <span className="spinner spinner-dark" /> : '↺'} Refresh
					</button>
				</div>

				{filesError && <div className="alert alert-error">{filesError}</div>}

				{files.length === 0 && !loadingFiles && !filesError && (
					<div className="muted">No files on device.</div>
				)}

				{files.length > 0 && (
					<div className="table-wrap">
						<table>
							<thead>
								<tr>
									<th>#</th>
									<th>Filename</th>
									<th>Size</th>
								</tr>
							</thead>
							<tbody>
								{files.map((f, i) => (
									<tr key={f.name}>
										<td className="muted">{i + 1}</td>
										<td className="mono">{f.name}</td>
										<td>{fmtBytes(f.size)}</td>
									</tr>
								))}
							</tbody>
						</table>
					</div>
				)}
			</div>

			{/* Download */}
			<div className="card">
				<div className="card-title">Download All</div>
				<p className="muted" style={{ marginBottom: 12, fontSize: 13 }}>
					Downloads all files to a timestamped folder you choose, plus a metadata.txt.
				</p>

				{downloading && taskStatus && (
					<div style={{ marginBottom: 12 }}>
						<div className="muted" style={{ marginBottom: 6, fontSize: 12 }}>
							Downloading file {taskStatus.current} of {taskStatus.total}…
						</div>
						<div className="progress-wrap">
							<div className="progress-bar" style={{ width: `${progress * 100}%` }} />
						</div>
					</div>
				)}

				{downloadMsg && (
					<div className={`alert ${downloadMsg.ok ? 'alert-success' : 'alert-error'}`} style={{ marginBottom: 8 }}>
						{downloadMsg.text}
					</div>
				)}

				<div className="row" style={{ gap: 8 }}>
					<button
						className="btn btn-primary"
						onClick={startDownload}
						disabled={downloading || files.length === 0}
					>
						{downloading ? <span className="spinner" /> : '⬇'}
						{downloading ? ' Downloading…' : ' Download All'}
					</button>
					{downloadPath && !downloading && (
						<button
							className="btn btn-secondary"
							onClick={() => api?.open_folder(downloadPath)}
						>
							Open Folder
						</button>
					)}
				</div>
			</div>

			{/* Delete */}
			<div className="card">
				<div className="card-title">Delete All Files</div>
				<p className="muted" style={{ marginBottom: 12, fontSize: 13 }}>
					Permanently removes all files from the SD card. This cannot be undone.
				</p>

				{deleteMsg && (
					<div className={`alert ${deleteMsg.ok ? 'alert-success' : 'alert-error'}`} style={{ marginBottom: 8 }}>
						{deleteMsg.text}
					</div>
				)}

				{!confirmDelete ? (
					<button
						className="btn btn-danger"
						onClick={() => setConfirmDelete(true)}
						disabled={files.length === 0}
					>
						🗑 Delete All Files
					</button>
				) : (
					<div className="alert alert-warning" style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
						<span>Are you sure? This will delete all {files.length} file(s).</span>
						<button className="btn btn-danger" onClick={doDelete}>Yes, Delete All</button>
						<button className="btn btn-secondary" onClick={() => setConfirmDelete(false)}>Cancel</button>
					</div>
				)}
			</div>
		</div>
	)
}
