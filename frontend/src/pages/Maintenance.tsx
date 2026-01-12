import { useState, useEffect } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { HardDrive, Trash2, AlertTriangle, RefreshCw, CheckCircle, Database, Server } from 'lucide-react'
import { maintenanceApi } from '../utils/api'
import { formatDistanceToNow } from 'date-fns'

export default function Maintenance() {
    const [policy, setPolicy] = useState({
        delete_temp_files: true,
        delete_orphaned_uploads: false,
        retention_days_runs: 5,
        retention_days_reports: 14,
        prune_docker_images: false,
        prune_docker_volumes: false,
    })

    const [cleanupStep, setCleanupStep] = useState<'idle' | 'preview' | 'confirming' | 'executing' | 'done'>('idle')
    const [previewData, setPreviewData] = useState<any>(null)
    const [cleanupResult, setCleanupResult] = useState<any>(null)

    // Usage Query
    const { data: usageData, isLoading: isLoadingUsage, refetch: refetchUsage } = useQuery({
        queryKey: ['disk-usage'],
        queryFn: () => maintenanceApi.usage(),
        refetchInterval: 30000,
    })

    // Preview Mutation
    const previewMutation = useMutation({
        mutationFn: (currentPolicy: any) => maintenanceApi.preview(currentPolicy),
        onSuccess: (res) => {
            setPreviewData(res.data)
            setCleanupStep('preview')
        },
    })

    // Execute Mutation
    const executeMutation = useMutation({
        mutationFn: (data: { policy: any; confirm: boolean }) => maintenanceApi.execute(data.policy, data.confirm),
        onSuccess: (res) => {
            setCleanupResult(res.data)
            setCleanupStep('done')
            refetchUsage()
        },
    })

    const handleGeneratePreview = () => {
        previewMutation.mutate(policy)
    }

    const handleExecuteCleanup = () => {
        executeMutation.mutate({ policy, confirm: true })
    }

    const formatBytes = (bytes: number) => {
        if (bytes === 0) return '0 B'
        const k = 1024
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
        const i = Math.floor(Math.log(bytes) / Math.log(k))
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
    }

    const stats = usageData?.data?.local || {}
    const dockerStats = usageData?.data?.docker?.usage || []

    // Parse Docker Stats (images, containers, volumes, build cache)
    const dockerTotalSize = dockerStats.reduce((acc: number, item: any) => {
        // Size string parsing is tricky without proper bytes, checking if size is available
        // The API returns typed data or raw? backend uses --format json
        // usually size is a string "22.57GB". Using simplified logic or assuming 0 if difficult
        return acc // detailed parsing omitted for brevity
    }, 0)

    const dockerReclaimable = usageData?.data?.docker?.status === "unavailable" ? "N/A" : "Check Console"

    return (
        <div className="space-y-6">
            <h1 className="text-2xl font-bold flex items-center gap-2">
                <HardDrive className="w-6 h-6" />
                System Maintenance
            </h1>

            {/* Disk Usage Overview */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="card p-6">
                    <h3 className="font-medium text-slate-500 mb-2 flex items-center gap-2">
                        <HardDrive className="w-4 h-4" /> Local Data (/data)
                    </h3>
                    {isLoadingUsage ? (
                        <div className="skeleton h-8 w-24"></div>
                    ) : (
                        <div>
                            <div className="text-3xl font-bold">{formatBytes(stats.total_used || 0)}</div>
                            <div className="text-sm text-slate-500">of {formatBytes(stats.total_capacity || 0)} used</div>
                            <div className="mt-4 space-y-2 text-sm">
                                <div className="flex justify-between">
                                    <span>Temp</span>
                                    <span className="font-mono">{formatBytes(stats.temp?.size_bytes || 0)}</span>
                                </div>
                                <div className="flex justify-between">
                                    <span>Uploads</span>
                                    <span className="font-mono">{formatBytes(stats.uploads?.size_bytes || 0)}</span>
                                </div>
                                <div className="flex justify-between">
                                    <span>Results</span>
                                    <span className="font-mono">{formatBytes(stats.results?.size_bytes || 0)}</span>
                                </div>
                            </div>
                        </div>
                    )}
                </div>

                <div className="card p-6">
                    <h3 className="font-medium text-slate-500 mb-2 flex items-center gap-2">
                        <Server className="w-4 h-4" /> Docker Storage
                    </h3>
                    {isLoadingUsage ? (
                        <div className="skeleton h-8 w-24"></div>
                    ) : (
                        <div>
                            <div className="text-lg font-medium text-slate-700 dark:text-slate-300">
                                Docker Artifacts
                            </div>
                            <div className="text-sm text-slate-500 mt-1">
                                Inspect "docker system df" output for details.
                            </div>
                            {usageData?.data?.docker?.usage ? (
                                <div className="mt-4 text-xs font-mono bg-slate-100 dark:bg-slate-800 p-2 rounded max-h-32 overflow-auto">
                                    {JSON.stringify(usageData.data.docker.usage, null, 2)}
                                </div>
                            ) : (
                                <div className="mt-4 text-warning-600 flex items-center gap-1 text-sm">
                                    <AlertTriangle className="w-4 h-4" /> Unavailable
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>

            {/* Cleanup Wizard */}
            <div className="card p-6">
                <h2 className="text-xl font-bold mb-6 flex items-center gap-2">
                    <Trash2 className="w-5 h-5" />
                    Cleanup Wizard
                </h2>

                <div className="space-y-6">
                    {/* Settings Form */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                        <div className="space-y-4">
                            <h3 className="font-medium border-b pb-2">File Retention</h3>

                            <div>
                                <label className="label">Run Retention (Days)</label>
                                <input
                                    type="range" min="1" max="30" step="1"
                                    value={policy.retention_days_runs}
                                    onChange={(e) => setPolicy({ ...policy, retention_days_runs: parseInt(e.target.value) })}
                                    className="w-full"
                                />
                                <div className="text-right text-sm text-slate-500">Keep last {policy.retention_days_runs} days</div>
                            </div>

                            <div>
                                <label className="label">Report Retention (Days)</label>
                                <input
                                    type="range" min="1" max="60" step="1"
                                    value={policy.retention_days_reports}
                                    onChange={(e) => setPolicy({ ...policy, retention_days_reports: parseInt(e.target.value) })}
                                    className="w-full"
                                />
                                <div className="text-right text-sm text-slate-500">Keep last {policy.retention_days_reports} days</div>
                            </div>

                            <label className="flex items-center gap-2 cursor-pointer">
                                <input
                                    type="checkbox"
                                    checked={policy.delete_temp_files}
                                    onChange={(e) => setPolicy({ ...policy, delete_temp_files: e.target.checked })}
                                    className="checkbox"
                                />
                                <span>Delete Temp Files (Older than 1h)</span>
                            </label>

                            <label className="flex items-center gap-2 cursor-pointer">
                                <input
                                    type="checkbox"
                                    checked={policy.delete_orphaned_uploads}
                                    onChange={(e) => setPolicy({ ...policy, delete_orphaned_uploads: e.target.checked })}
                                    className="checkbox"
                                />
                                <span>Delete Orphaned Uploads (Older than 24h)</span>
                            </label>
                        </div>

                        <div className="space-y-4">
                            <h3 className="font-medium border-b pb-2 text-danger-600">Docker Cleanup (Destructive)</h3>

                            <div className="bg-danger-50 dark:bg-danger-900/10 p-4 rounded-lg border border-danger-100 dark:border-danger-900/20">
                                <label className="flex items-center gap-2 cursor-pointer mb-2">
                                    <input
                                        type="checkbox"
                                        checked={policy.prune_docker_images}
                                        onChange={(e) => setPolicy({ ...policy, prune_docker_images: e.target.checked })}
                                        className="checkbox checkbox-error"
                                    />
                                    <span className="font-medium text-danger-700 dark:text-danger-400">Prune Unused Images & Build Cache</span>
                                </label>
                                <p className="text-xs text-danger-600/80 ml-6">
                                    Equivalent to `docker system prune -f`. Frees significant space but requires re-pulling images if needed later.
                                </p>
                            </div>

                            <div className="bg-danger-50 dark:bg-danger-900/10 p-4 rounded-lg border border-danger-100 dark:border-danger-900/20">
                                <label className="flex items-center gap-2 cursor-pointer mb-2">
                                    <input
                                        type="checkbox"
                                        checked={policy.prune_docker_volumes}
                                        onChange={(e) => setPolicy({ ...policy, prune_docker_volumes: e.target.checked })}
                                        disabled={!policy.prune_docker_images}
                                        className="checkbox checkbox-error"
                                    />
                                    <span className={`font-medium ${!policy.prune_docker_images ? 'text-slate-400' : 'text-danger-700 dark:text-danger-400'}`}>
                                        Prune Unused Volumes
                                    </span>
                                </label>
                                <p className="text-xs text-danger-600/80 ml-6">
                                    WARNING: Deletes any volume not currently mounted by a container. Irreversible data loss if not careful.
                                </p>
                            </div>
                        </div>
                    </div>

                    {/* Actions */}
                    <div className="flex justify-end pt-6 border-t border-slate-200 dark:border-slate-700">
                        {cleanupStep === 'idle' && (
                            <button
                                className="btn-primary"
                                onClick={handleGeneratePreview}
                                disabled={previewMutation.isPending}
                            >
                                {previewMutation.isPending ? 'Scanning...' : 'Scan & Preview'}
                            </button>
                        )}

                        {(cleanupStep === 'preview' || cleanupStep === 'confirming') && (
                            <div className="flex gap-3">
                                <button className="btn-ghost" onClick={() => { setCleanupStep('idle'); setPreviewData(null); }}>
                                    Cancel
                                </button>
                                <button
                                    className="btn-danger"
                                    onClick={handleExecuteCleanup}
                                    disabled={executeMutation.isPending}
                                >
                                    {executeMutation.isPending ? 'Cleaning...' : 'Confirm & Execute Cleanup'}
                                </button>
                            </div>
                        )}

                        {cleanupStep === 'done' && (
                            <button className="btn-primary" onClick={() => { setCleanupStep('idle'); setCleanupResult(null); }}>
                                Done
                            </button>
                        )}
                    </div>
                </div>
            </div>

            {/* Preview Results */}
            {cleanupStep === 'preview' && previewData && (
                <div className="card p-6 bg-slate-50 dark:bg-slate-800/50">
                    <h3 className="font-bold mb-4">Cleanup Preview</h3>
                    <div className="space-y-2">
                        <div className="flex justify-between font-medium">
                            <span>Files to delete:</span>
                            <span>{previewData.files_to_delete.length}</span>
                        </div>
                        <div className="flex justify-between font-medium text-success-600">
                            <span>Space to reclaim (Files):</span>
                            <span>{formatBytes(previewData.total_size_reclaimable)}</span>
                        </div>
                        {previewData.docker_warning && (
                            <div className="alert alert-warning mt-4">
                                <AlertTriangle className="w-5 h-5" />
                                <span>{previewData.docker_warning}</span>
                            </div>
                        )}
                    </div>

                    {previewData.files_to_delete.length > 0 && (
                        <div className="mt-4 max-h-60 overflow-y-auto border rounded bg-white dark:bg-slate-900 p-2 text-xs font-mono">
                            {previewData.files_to_delete.map((f: any, i: number) => (
                                <div key={i} className="flex justify-between py-1 border-b last:border-0 border-slate-100 dark:border-slate-800">
                                    <span className="truncate mr-4">{f.path}</span>
                                    <span className="whitespace-nowrap">{formatBytes(f.size)}</span>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* Execution Report */}
            {cleanupStep === 'done' && cleanupResult && (
                <div className="card p-6 bg-success-50 dark:bg-success-900/10 border-success-200">
                    <div className="flex items-center gap-3 text-success-700 dark:text-success-400 mb-4">
                        <CheckCircle className="w-6 h-6" />
                        <h3 className="font-bold">Cleanup Triggered Successfully</h3>
                    </div>

                    <div className="space-y-2 text-sm">
                        <p><strong>Local Files Deleted:</strong> {cleanupResult.local_cleanup?.deleted_count}</p>
                        <p><strong>Space Reclaimed (Local):</strong> {formatBytes(cleanupResult.local_cleanup?.reclaimed_bytes || 0)}</p>

                        {cleanupResult.docker_task_id && (
                            <p className="flex items-center gap-2 mt-2">
                                <Server className="w-4 h-4" />
                                <strong>Docker Prune:</strong> Task started (ID: {cleanupResult.docker_task_id}).
                                Check logs for completion.
                            </p>
                        )}

                        {cleanupResult.local_cleanup?.errors?.length > 0 && (
                            <div className="mt-4 text-danger-600">
                                <strong>Errors:</strong>
                                <ul className="list-disc ml-5">
                                    {cleanupResult.local_cleanup.errors.map((e: string, i: number) => (
                                        <li key={i}>{e}</li>
                                    ))}
                                </ul>
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    )
}
