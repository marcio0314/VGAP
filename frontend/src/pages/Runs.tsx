import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
    Search, Filter, Plus, ChevronDown, PlayCircle,
    CheckCircle, XCircle, Clock, MoreHorizontal,
    Trash2, Download, RefreshCw
} from 'lucide-react'
import { runsApi } from '../utils/api'
import { format, formatDistanceToNow } from 'date-fns'

const statusConfig: Record<string, { icon: any; color: string; bg: string; text: string }> = {
    completed: { icon: CheckCircle, color: 'text-success-500', bg: 'bg-success-100 dark:bg-success-500/20', text: 'Completed' },
    running: { icon: PlayCircle, color: 'text-primary-500', bg: 'bg-primary-100 dark:bg-primary-500/20', text: 'Running' },
    failed: { icon: XCircle, color: 'text-danger-500', bg: 'bg-danger-100 dark:bg-danger-500/20', text: 'Failed' },
    pending: { icon: Clock, color: 'text-slate-400', bg: 'bg-slate-100 dark:bg-slate-700', text: 'Pending' },
    queued: { icon: Clock, color: 'text-warning-500', bg: 'bg-warning-100 dark:bg-warning-500/20', text: 'Queued' },
    cancelled: { icon: XCircle, color: 'text-slate-400', bg: 'bg-slate-100 dark:bg-slate-700', text: 'Cancelled' },
}

export default function Runs() {
    const [statusFilter, setStatusFilter] = useState<string>('')
    const [searchQuery, setSearchQuery] = useState('')
    const [page, setPage] = useState(0)
    const limit = 20

    const queryClient = useQueryClient()

    const { data, isLoading, refetch } = useQuery({
        queryKey: ['runs', { status: statusFilter, skip: page * limit, limit }],
        queryFn: () => runsApi.list({ status: statusFilter || undefined, skip: page * limit, limit }),
        refetchInterval: 10000, // Refresh every 10 seconds
    })

    const runs = data?.data?.items || []
    const total = data?.data?.total || 0
    const totalPages = Math.ceil(total / limit)

    // Filter by search locally
    const filteredRuns = runs.filter((run: any) => {
        if (!searchQuery) return true
        const query = searchQuery.toLowerCase()
        return (
            run.name.toLowerCase().includes(query) ||
            run.run_code.toLowerCase().includes(query)
        )
    })

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold">Analysis Runs</h1>
                    <p className="text-slate-500 mt-1">
                        {total} total runs
                    </p>
                </div>
                <div className="flex items-center gap-3">
                    <button onClick={() => refetch()} className="btn-ghost">
                        <RefreshCw className="w-4 h-4" />
                    </button>
                    <Link to="/app/runs/new" className="btn-primary">
                        <Plus className="w-4 h-4" />
                        New Analysis
                    </Link>
                </div>
            </div>

            {/* Filters */}
            <div className="card p-4">
                <div className="flex flex-col sm:flex-row gap-4">
                    {/* Search */}
                    <div className="flex-1 relative">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
                        <input
                            type="text"
                            className="input pl-10"
                            placeholder="Search runs..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                        />
                    </div>

                    {/* Status Filter */}
                    <div className="relative">
                        <select
                            className="input pr-10 appearance-none cursor-pointer min-w-[160px]"
                            value={statusFilter}
                            onChange={(e) => {
                                setStatusFilter(e.target.value)
                                setPage(0)
                            }}
                        >
                            <option value="">All Statuses</option>
                            <option value="pending">Pending</option>
                            <option value="queued">Queued</option>
                            <option value="running">Running</option>
                            <option value="completed">Completed</option>
                            <option value="failed">Failed</option>
                            <option value="cancelled">Cancelled</option>
                        </select>
                        <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400 pointer-events-none" />
                    </div>
                </div>
            </div>

            {/* Runs Table */}
            <div className="card overflow-hidden">
                {isLoading ? (
                    <div className="p-8 space-y-4">
                        {[...Array(5)].map((_, i) => (
                            <div key={i} className="skeleton h-16 rounded-lg" />
                        ))}
                    </div>
                ) : filteredRuns.length > 0 ? (
                    <>
                        <table className="table">
                            <thead>
                                <tr>
                                    <th>Run</th>
                                    <th>Status</th>
                                    <th>Progress</th>
                                    <th>Samples</th>
                                    <th>Created</th>
                                    <th className="w-12"></th>
                                </tr>
                            </thead>
                            <tbody>
                                {filteredRuns.map((run: any) => {
                                    const config = statusConfig[run.status] || statusConfig.pending
                                    const StatusIcon = config.icon

                                    return (
                                        <tr key={run.id}>
                                            <td>
                                                <Link
                                                    to={`/app/runs/${run.id}`}
                                                    className="block group"
                                                >
                                                    <div className="font-medium group-hover:text-primary-600 transition-colors">
                                                        {run.name}
                                                    </div>
                                                    <div className="text-sm text-slate-500">
                                                        {run.run_code}
                                                    </div>
                                                </Link>
                                            </td>
                                            <td>
                                                <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${config.bg} ${config.color}`}>
                                                    <StatusIcon className="w-3.5 h-3.5" />
                                                    {config.text}
                                                </div>
                                            </td>
                                            <td>
                                                {run.status === 'running' ? (
                                                    <div className="w-32">
                                                        <div className="progress-bar">
                                                            <div
                                                                className="progress-bar-fill"
                                                                style={{ width: `${run.progress || 0}%` }}
                                                            />
                                                        </div>
                                                        <div className="text-xs text-slate-500 mt-1">
                                                            {run.progress || 0}% - {run.current_stage || 'processing'}
                                                        </div>
                                                    </div>
                                                ) : run.status === 'completed' ? (
                                                    <span className="text-success-500 text-sm">100%</span>
                                                ) : (
                                                    <span className="text-slate-400 text-sm">—</span>
                                                )}
                                            </td>
                                            <td>
                                                <span className="text-slate-600 dark:text-slate-400">
                                                    {run.sample_count} samples
                                                </span>
                                            </td>
                                            <td>
                                                <div className="text-sm">
                                                    {format(new Date(run.created_at), 'MMM d, yyyy')}
                                                </div>
                                                <div className="text-xs text-slate-400">
                                                    {formatDistanceToNow(new Date(run.created_at), { addSuffix: true })}
                                                </div>
                                            </td>
                                            <td>
                                                <RunActions run={run} onRefresh={refetch} />
                                            </td>
                                        </tr>
                                    )
                                })}
                            </tbody>
                        </table>

                        {/* Pagination */}
                        {totalPages > 1 && (
                            <div className="flex items-center justify-between p-4 border-t border-slate-200 dark:border-slate-700">
                                <div className="text-sm text-slate-500">
                                    Showing {page * limit + 1} to {Math.min((page + 1) * limit, total)} of {total}
                                </div>
                                <div className="flex gap-2">
                                    <button
                                        className="btn-ghost px-3 py-1.5"
                                        disabled={page === 0}
                                        onClick={() => setPage(p => Math.max(0, p - 1))}
                                    >
                                        Previous
                                    </button>
                                    <button
                                        className="btn-ghost px-3 py-1.5"
                                        disabled={page >= totalPages - 1}
                                        onClick={() => setPage(p => p + 1)}
                                    >
                                        Next
                                    </button>
                                </div>
                            </div>
                        )}
                    </>
                ) : (
                    <div className="p-12 text-center">
                        <PlayCircle className="w-12 h-12 text-slate-300 mx-auto mb-4" />
                        <h3 className="text-lg font-medium mb-2">No runs found</h3>
                        <p className="text-slate-500 mb-6">
                            {statusFilter ? `No ${statusFilter} runs` : 'Start your first analysis'}
                        </p>
                        <Link to="/app/runs/new" className="btn-primary">
                            <Plus className="w-4 h-4" />
                            Create Run
                        </Link>
                    </div>
                )}
            </div>
        </div>
    )
}

function RunActions({ run, onRefresh }: { run: any; onRefresh: () => void }) {
    const [open, setOpen] = useState(false)
    const queryClient = useQueryClient()

    const cancelMutation = useMutation({
        mutationFn: () => runsApi.cancel(run.id),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['runs'] })
            onRefresh()
        },
    })

    const startMutation = useMutation({
        mutationFn: () => runsApi.start(run.id),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['runs'] })
            onRefresh()
        },
    })

    return (
        <div className="relative">
            <button
                className="p-2 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-colors"
                onClick={() => setOpen(!open)}
            >
                <MoreHorizontal className="w-4 h-4" />
            </button>

            {open && (
                <>
                    <div
                        className="fixed inset-0 z-10"
                        onClick={() => setOpen(false)}
                    />
                    <div className="absolute right-0 mt-1 w-48 bg-white dark:bg-slate-800 rounded-xl shadow-elevated border border-slate-200 dark:border-slate-700 z-20 py-1">
                        <Link
                            to={`/app/runs/${run.id}`}
                            className="flex items-center gap-2 px-4 py-2 text-sm hover:bg-slate-50 dark:hover:bg-slate-700"
                            onClick={() => setOpen(false)}
                        >
                            View Details
                        </Link>

                        {run.status === 'pending' && (
                            <button
                                className="flex items-center gap-2 px-4 py-2 text-sm hover:bg-slate-50 dark:hover:bg-slate-700 w-full text-left text-primary-600"
                                onClick={() => {
                                    startMutation.mutate()
                                    setOpen(false)
                                }}
                            >
                                <PlayCircle className="w-4 h-4" />
                                Start Run
                            </button>
                        )}

                        {(run.status === 'running' || run.status === 'queued') && (
                            <button
                                className="flex items-center gap-2 px-4 py-2 text-sm hover:bg-slate-50 dark:hover:bg-slate-700 w-full text-left text-danger-600"
                                onClick={() => {
                                    cancelMutation.mutate()
                                    setOpen(false)
                                }}
                            >
                                <XCircle className="w-4 h-4" />
                                Cancel
                            </button>
                        )}

                        {run.status === 'completed' && (
                            <a
                                href={`/api/v1/reports/${run.id}/package`}
                                className="flex items-center gap-2 px-4 py-2 text-sm hover:bg-slate-50 dark:hover:bg-slate-700"
                                download
                            >
                                <Download className="w-4 h-4" />
                                Download Results
                            </a>
                        )}
                    </div>
                </>
            )}
        </div>
    )
}
