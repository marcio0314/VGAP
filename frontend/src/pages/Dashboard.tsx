import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
    Activity, Clock, CheckCircle, XCircle, PlayCircle,
    ArrowRight, Plus, Dna
} from 'lucide-react'
import { runsApi, adminApi } from '../utils/api'
import { format, formatDistanceToNow } from 'date-fns'

const statusConfig: Record<string, { icon: any; color: string; bg: string }> = {
    completed: { icon: CheckCircle, color: 'text-success-500', bg: 'bg-success-100 dark:bg-success-500/20' },
    running: { icon: PlayCircle, color: 'text-primary-500', bg: 'bg-primary-100 dark:bg-primary-500/20' },
    failed: { icon: XCircle, color: 'text-danger-500', bg: 'bg-danger-100 dark:bg-danger-500/20' },
    pending: { icon: Clock, color: 'text-slate-400', bg: 'bg-slate-100 dark:bg-slate-700' },
    queued: { icon: Clock, color: 'text-warning-500', bg: 'bg-warning-100 dark:bg-warning-500/20' },
}

export default function Dashboard() {
    const { data: runsData, isLoading: runsLoading } = useQuery({
        queryKey: ['runs', { limit: 5 }],
        queryFn: () => runsApi.list({ limit: 5 }),
    })

    const { data: statusData } = useQuery({
        queryKey: ['status'],
        queryFn: () => adminApi.status(),
        refetchInterval: 30000,
    })

    const runs = runsData?.data?.items || []
    const status = statusData?.data

    // Calculate stats
    const totalRuns = runsData?.data?.total || 0
    const completedRuns = runs.filter((r: any) => r.status === 'completed').length
    const runningRuns = runs.filter((r: any) => r.status === 'running').length

    return (
        <div className="space-y-8">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold">Dashboard</h1>
                    <p className="text-slate-500 mt-1">
                        Overview of your analysis pipeline
                    </p>
                </div>
                <Link to="/app/runs/new" className="btn-primary">
                    <Plus className="w-4 h-4" />
                    New Analysis
                </Link>
            </div>

            {/* Stats Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <StatCard
                    title="Total Runs"
                    value={totalRuns.toString()}
                    icon={Activity}
                    color="primary"
                />
                <StatCard
                    title="Completed"
                    value={completedRuns.toString()}
                    icon={CheckCircle}
                    color="success"
                />
                <StatCard
                    title="Running"
                    value={runningRuns.toString()}
                    icon={PlayCircle}
                    color="warning"
                />
                <StatCard
                    title="Workers"
                    value={status?.workers_active?.toString() || '0'}
                    icon={Dna}
                    color="primary"
                    subtitle={typeof status?.status === 'string' ? status.status : 'Loading...'}
                />
            </div>

            {/* System Status */}
            {status && (
                <div className="card p-6">
                    <h2 className="text-lg font-semibold mb-4">System Status</h2>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <StatusIndicator
                            label="Database"
                            status={status.database}
                        />
                        <StatusIndicator
                            label="Redis"
                            status={status.redis}
                        />
                        <StatusIndicator
                            label="Workers"
                            status={status.workers_active > 0 ? 'healthy' : 'degraded'}
                        />
                        <StatusIndicator
                            label="Storage"
                            status={status.disk_usage_percent < 90 ? 'healthy' : 'warning'}
                            subtitle={`${status.disk_usage_percent}% used`}
                        />
                    </div>
                </div>
            )}

            {/* Recent Runs */}
            <div className="card">
                <div className="flex items-center justify-between p-6 border-b border-slate-200 dark:border-slate-700">
                    <h2 className="text-lg font-semibold">Recent Runs</h2>
                    <Link
                        to="/app/runs"
                        className="text-sm text-primary-600 hover:text-primary-700 font-medium flex items-center gap-1"
                    >
                        View All
                        <ArrowRight className="w-4 h-4" />
                    </Link>
                </div>

                {runsLoading ? (
                    <div className="p-6 space-y-4">
                        {[...Array(3)].map((_, i) => (
                            <div key={i} className="skeleton h-16 rounded-lg" />
                        ))}
                    </div>
                ) : runs.length > 0 ? (
                    <div className="divide-y divide-slate-100 dark:divide-slate-800">
                        {runs.map((run: any) => {
                            const config = statusConfig[run.status] || statusConfig.pending
                            const StatusIcon = config.icon

                            return (
                                <Link
                                    key={run.id}
                                    to={`/app/runs/${run.id}`}
                                    className="flex items-center gap-4 p-4 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
                                >
                                    <div className={`w-10 h-10 rounded-xl ${config.bg} flex items-center justify-center`}>
                                        <StatusIcon className={`w-5 h-5 ${config.color}`} />
                                    </div>

                                    <div className="flex-1 min-w-0">
                                        <div className="font-medium truncate">
                                            {typeof run.name === 'object' ? JSON.stringify(run.name) : run.name}
                                        </div>
                                        <div className="text-sm text-slate-500">
                                            {typeof run.run_code === 'object' ? JSON.stringify(run.run_code) : run.run_code} · {run.sample_count} samples
                                        </div>
                                    </div>

                                    <div className="text-right">
                                        <div className="text-sm font-medium capitalize">
                                            {typeof run.status === 'object' ? JSON.stringify(run.status) : run.status}
                                        </div>
                                        <div className="text-xs text-slate-400">
                                            {run.created_at ? formatDistanceToNow(new Date(run.created_at), { addSuffix: true }) : ''}
                                        </div>
                                    </div>

                                    {run.status === 'running' && run.progress > 0 && (
                                        <div className="w-24">
                                            <div className="progress-bar">
                                                <div
                                                    className="progress-bar-fill"
                                                    style={{ width: `${run.progress}%` }}
                                                />
                                            </div>
                                            <div className="text-xs text-slate-400 text-center mt-1">
                                                {run.progress}%
                                            </div>
                                        </div>
                                    )}
                                </Link>
                            )
                        })}
                    </div>
                ) : (
                    <div className="p-12 text-center">
                        <Dna className="w-12 h-12 text-slate-300 mx-auto mb-4" />
                        <h3 className="text-lg font-medium mb-2">No runs yet</h3>
                        <p className="text-slate-500 mb-6">
                            Start your first analysis to see it here
                        </p>
                        <Link to="/app/runs/new" className="btn-primary">
                            <Plus className="w-4 h-4" />
                            Create First Run
                        </Link>
                    </div>
                )}
            </div>
        </div>
    )
}

function StatCard({ title, value, icon: Icon, color, subtitle }: {
    title: string
    value: string
    icon: any
    color: 'primary' | 'success' | 'warning' | 'danger'
    subtitle?: string
}) {
    const colors = {
        primary: 'text-primary-500 bg-primary-100 dark:bg-primary-500/20',
        success: 'text-success-500 bg-success-100 dark:bg-success-500/20',
        warning: 'text-warning-500 bg-warning-100 dark:bg-warning-500/20',
        danger: 'text-danger-500 bg-danger-100 dark:bg-danger-500/20',
    }

    return (
        <div className="card p-5">
            <div className="flex items-start justify-between">
                <div>
                    <div className="text-sm text-slate-500 mb-1">{title}</div>
                    <div className="text-2xl font-bold">{value}</div>
                    {subtitle && (
                        <div className="text-xs text-slate-400 mt-1 capitalize">
                            {typeof subtitle === 'object' ? JSON.stringify(subtitle) : subtitle}
                        </div>
                    )}
                </div>
                <div className={`w-10 h-10 rounded-xl ${colors[color]} flex items-center justify-center`}>
                    <Icon className="w-5 h-5" />
                </div>
            </div>
        </div>
    )
}

function StatusIndicator({ label, status, subtitle }: {
    label: string
    status: string
    subtitle?: string
}) {
    const isHealthy = status === 'healthy'

    return (
        <div className="flex items-center gap-3">
            <div className={`w-3 h-3 rounded-full ${isHealthy
                ? 'bg-success-500'
                : status === 'warning'
                    ? 'bg-warning-500'
                    : 'bg-danger-500'
                }`} />
            <div>
                <div className="text-sm font-medium">{label}</div>
                <div className="text-xs text-slate-400 capitalize">
                    {typeof subtitle === 'object' ? JSON.stringify(subtitle) : (subtitle || (typeof status === 'string' ? status : JSON.stringify(status)))}
                </div>
            </div>
        </div>
    )
}
