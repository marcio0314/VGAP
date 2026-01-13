import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
    ArrowLeft, PlayCircle, XCircle, CheckCircle, Clock,
    Download, FileText, BarChart3, Dna, RefreshCw,
    ChevronDown, ChevronUp, AlertTriangle, Activity
} from 'lucide-react'
import { runsApi, reportsApi, samplesApi } from '../utils/api'
import { format, formatDistanceToNow } from 'date-fns'

const statusConfig: Record<string, { icon: any; color: string; bg: string; text: string }> = {
    completed: { icon: CheckCircle, color: 'text-success-500', bg: 'bg-success-100 dark:bg-success-500/20', text: 'Completed' },
    running: { icon: PlayCircle, color: 'text-primary-500', bg: 'bg-primary-100 dark:bg-primary-500/20', text: 'Running' },
    failed: { icon: XCircle, color: 'text-danger-500', bg: 'bg-danger-100 dark:bg-danger-500/20', text: 'Failed' },
    pending: { icon: Clock, color: 'text-slate-400', bg: 'bg-slate-100 dark:bg-slate-700', text: 'Pending' },
    queued: { icon: Clock, color: 'text-warning-500', bg: 'bg-warning-100 dark:bg-warning-500/20', text: 'Queued' },
    cancelled: { icon: XCircle, color: 'text-slate-400', bg: 'bg-slate-100 dark:bg-slate-700', text: 'Cancelled' },
}

const sampleStatusConfig: Record<string, { color: string; text: string }> = {
    pending: { color: 'text-slate-400', text: 'Pending' },
    processing: { color: 'text-primary-500', text: 'Processing' },
    qc_complete: { color: 'text-primary-500', text: 'QC Complete' },
    mapping_complete: { color: 'text-primary-500', text: 'Mapping' },
    variants_complete: { color: 'text-primary-500', text: 'Variants' },
    complete: { color: 'text-success-500', text: 'Completed' },
    completed: { color: 'text-success-500', text: 'Completed' },
    failed: { color: 'text-danger-500', text: 'Failed' },
}

export default function RunDetail() {
    const { id } = useParams<{ id: string }>()
    const queryClient = useQueryClient()
    const [activeTab, setActiveTab] = useState('samples')
    const [expandedSample, setExpandedSample] = useState<string | null>(null)

    const { data: runData, isLoading, refetch } = useQuery({
        queryKey: ['run', id],
        queryFn: () => runsApi.get(id!),
        refetchInterval: (data) => {
            const status = data?.data?.status
            return status === 'running' || status === 'queued' ? 3000 : false
        },
    })

    const { data: statusData } = useQuery({
        queryKey: ['run-status', id],
        queryFn: () => runsApi.status(id!),
        enabled: runData?.data?.status === 'running' || runData?.data?.status === 'queued',
        refetchInterval: 2000,
    })

    const startMutation = useMutation({
        mutationFn: () => runsApi.start(id!),
        onSuccess: () => refetch(),
    })

    const cancelMutation = useMutation({
        mutationFn: () => runsApi.cancel(id!),
        onSuccess: () => refetch(),
    })

    const generateReportMutation = useMutation({
        mutationFn: () => reportsApi.generate(id!, { format: 'html' }),
    })

    if (isLoading) {
        return (
            <div className="space-y-6">
                <div className="skeleton h-8 w-64 rounded-lg" />
                <div className="skeleton h-48 rounded-2xl" />
                <div className="skeleton h-96 rounded-2xl" />
            </div>
        )
    }

    const run = runData?.data
    if (!run) {
        return (
            <div className="text-center py-12">
                <h2 className="text-xl font-medium mb-2">Run not found</h2>
                <Link to="/app/runs" className="text-primary-600">Back to runs</Link>
            </div>
        )
    }

    const config = statusConfig[run.status] || statusConfig.pending
    const StatusIcon = config.icon
    const samples = run.samples || []
    const liveStatus = statusData?.data || {}

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-start justify-between">
                <div>
                    <Link
                        to="/app/runs"
                        className="inline-flex items-center gap-1 text-slate-500 hover:text-slate-700 mb-2"
                    >
                        <ArrowLeft className="w-4 h-4" />
                        Back to runs
                    </Link>
                    <h1 className="text-2xl font-bold">{run.name}</h1>
                    <p className="text-slate-500 mt-1">{run.run_code}</p>
                </div>

                <div className="flex items-center gap-3">
                    <button onClick={() => refetch()} className="btn-ghost">
                        <RefreshCw className="w-4 h-4" />
                    </button>

                    {run.status === 'pending' && (
                        <button
                            className="btn-primary"
                            onClick={() => startMutation.mutate()}
                            disabled={startMutation.isPending}
                        >
                            <PlayCircle className="w-4 h-4" />
                            Start Analysis
                        </button>
                    )}

                    {(run.status === 'running' || run.status === 'queued') && (
                        <button
                            className="btn-danger"
                            onClick={() => cancelMutation.mutate()}
                            disabled={cancelMutation.isPending}
                        >
                            <XCircle className="w-4 h-4" />
                            Cancel
                        </button>
                    )}

                    {run.status === 'completed' && (
                        <>
                            <a
                                href={reportsApi.exports(id!, 'report')}
                                className="btn-success"
                                target="_blank"
                                rel="noopener noreferrer"
                            >
                                <FileText className="w-4 h-4" />
                                View Report
                            </a>
                            <button
                                className="btn-secondary"
                                onClick={() => generateReportMutation.mutate()}
                                disabled={generateReportMutation.isPending}
                            >
                                <RefreshCw className="w-4 h-4" />
                                Regenerate
                            </button>
                            <a
                                href={reportsApi.package(id!)}
                                className="btn-primary"
                                download
                            >
                                <Download className="w-4 h-4" />
                                Download Zip
                            </a>
                        </>
                    )}
                </div>
            </div>

            {/* Status Card */}
            <div className="card p-6">
                <div className="flex items-center gap-6">
                    <div className={`w-16 h-16 rounded-2xl ${config.bg} flex items-center justify-center`}>
                        <StatusIcon className={`w-8 h-8 ${config.color}`} />
                    </div>

                    <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                            <span className={`text-lg font-semibold ${config.color}`}>
                                {config.text}
                            </span>
                            {run.status === 'running' && (
                                <span className="text-sm text-slate-500">
                                    <span className="text-sm text-slate-500 font-mono">
                                        {liveStatus.current_stage ? liveStatus.current_stage.toUpperCase().replace('_', ' ') : (run.current_stage || 'Processing...')}
                                    </span>
                                </span>
                            )}
                        </div>

                        {run.status === 'running' && (
                            <div className="w-full max-w-md">
                                <div className="progress-bar h-3">
                                    <div
                                        className="progress-bar-fill"
                                        style={{ width: `${liveStatus.progress || run.progress || 0}%` }}
                                    />
                                </div>
                                <div className="text-sm text-slate-500 mt-1">
                                    {liveStatus.progress || run.progress || 0}% complete
                                </div>
                            </div>
                        )}

                        {run.status === 'failed' && run.error_message && (
                            <div className="flex items-start gap-2 text-danger-600 mt-2">
                                <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                                <span className="text-sm">{run.error_message}</span>
                            </div>
                        )}
                    </div>

                    <div className="text-right text-sm text-slate-500">
                        <div>Created {formatDistanceToNow(new Date(run.created_at), { addSuffix: true })}</div>
                        {run.completed_at && (
                            <div>Completed {formatDistanceToNow(new Date(run.completed_at), { addSuffix: true })}</div>
                        )}
                    </div>
                </div>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <StatCard
                    label="Samples"
                    value={samples.length.toString()}
                    icon={Dna}
                />
                <StatCard
                    label="Mode"
                    value={run.mode}
                    icon={Activity}
                />
                <StatCard
                    label="Completed"
                    value={samples.filter((s: any) => s.status === 'completed').length.toString()}
                    icon={CheckCircle}
                    color="success"
                />
                <StatCard
                    label="Failed"
                    value={samples.filter((s: any) => s.status === 'failed').length.toString()}
                    icon={XCircle}
                    color="danger"
                />
            </div>

            {/* Tabs */}
            <div className="card">
                <div className="flex border-b border-slate-200 dark:border-slate-700">
                    {['samples', 'details', 'provenance'].map((tab) => (
                        <button
                            key={tab}
                            className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors ${activeTab === tab
                                ? 'border-primary-500 text-primary-600'
                                : 'border-transparent text-slate-500 hover:text-slate-700'
                                }`}
                            onClick={() => setActiveTab(tab)}
                        >
                            {tab.charAt(0).toUpperCase() + tab.slice(1)}
                        </button>
                    ))}
                </div>

                <div className="p-6">
                    {activeTab === 'samples' && (
                        <SamplesTable
                            samples={samples}
                            runId={id!}
                            expandedSample={expandedSample}
                            setExpandedSample={setExpandedSample}
                        />
                    )}

                    {activeTab === 'details' && (
                        <RunDetails run={run} />
                    )}

                    {activeTab === 'provenance' && (
                        <ProvenanceView runId={id!} />
                    )}
                </div>
            </div>
        </div>
    )
}

function StatCard({ label, value, icon: Icon, color = 'primary' }: {
    label: string
    value: string
    icon: any
    color?: 'primary' | 'success' | 'danger'
}) {
    const colors = {
        primary: 'text-primary-500 bg-primary-100 dark:bg-primary-500/20',
        success: 'text-success-500 bg-success-100 dark:bg-success-500/20',
        danger: 'text-danger-500 bg-danger-100 dark:bg-danger-500/20',
    }

    return (
        <div className="card p-4">
            <div className="flex items-center gap-3">
                <div className={`w-10 h-10 rounded-xl ${colors[color]} flex items-center justify-center`}>
                    <Icon className="w-5 h-5" />
                </div>
                <div>
                    <div className="text-2xl font-bold">{value}</div>
                    <div className="text-sm text-slate-500">{label}</div>
                </div>
            </div>
        </div>
    )
}

function SamplesTable({ samples, runId, expandedSample, setExpandedSample }: {
    samples: any[]
    runId: string
    expandedSample: string | null
    setExpandedSample: (id: string | null) => void
}) {
    if (!samples.length) {
        return (
            <div className="text-center py-8 text-slate-500">
                No samples in this run
            </div>
        )
    }

    return (
        <div className="space-y-2">
            {samples.map((sample: any) => {
                const isExpanded = expandedSample === sample.id
                const statusCfg = sampleStatusConfig[sample.status] || sampleStatusConfig.pending

                return (
                    <div key={sample.id} className="border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden">
                        <button
                            className="w-full flex items-center gap-4 p-4 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
                            onClick={() => setExpandedSample(isExpanded ? null : sample.id)}
                        >
                            <div className="flex-1 text-left">
                                <div className="font-medium">{sample.sample_id}</div>
                                <div className="text-sm text-slate-500">
                                    {sample.metadata?.collection_date || 'No date'}
                                </div>
                            </div>

                            <span className={`text-sm font-medium ${statusCfg.color}`}>
                                {statusCfg.text}
                            </span>

                            {sample.lineage && (
                                <span className="badge-info">
                                    {(() => {
                                        console.log(`Debug sample ${sample.sample_id} lineage:`, sample.lineage, typeof sample.lineage);
                                        if (typeof sample.lineage === 'object' && sample.lineage) {
                                            return sample.lineage.nextclade_clade || sample.lineage.pangolin_lineage || '-';
                                        }
                                        return String(sample.lineage);
                                    })()}
                                </span>
                            )}

                            {isExpanded ? (
                                <ChevronUp className="w-5 h-5 text-slate-400" />
                            ) : (
                                <ChevronDown className="w-5 h-5 text-slate-400" />
                            )}
                        </button>

                        {isExpanded && (
                            <SampleDetails sample={sample} runId={runId} />
                        )}
                    </div>
                )
            })}
        </div>
    )
}

function SampleDetails({ sample, runId }: { sample: any; runId: string }) {
    const { data: qcData } = useQuery({
        queryKey: ['sample-qc', sample.id],
        queryFn: () => samplesApi.qc(sample.id),
        enabled: sample.status === 'completed' || sample.status === 'complete',
    })

    const qc = qcData?.data || {}

    return (
        <div className="p-4 bg-slate-50 dark:bg-slate-800/50 border-t border-slate-200 dark:border-slate-700">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div>
                    <div className="text-slate-500">Mean Depth</div>
                    <div className="font-medium">{qc.mean_depth?.toFixed(1) || '—'}x</div>
                </div>
                <div>
                    <div className="text-slate-500">Coverage 10x</div>
                    <div className="font-medium">{qc.coverage_10x ? `${(qc.coverage_10x * 100).toFixed(1)}%` : '—'}</div>
                </div>
                <div>
                    <div className="text-slate-500">Q30 Rate</div>
                    <div className="font-medium">{qc.q30_rate ? `${(qc.q30_rate * 100).toFixed(1)}%` : '—'}</div>
                </div>
                <div>
                    <div className="text-slate-500">Variants</div>
                    <div className="font-medium">{sample.variant_count || '—'}</div>
                </div>
            </div>

            {sample.status === 'completed' && (
                <div className="flex gap-2 mt-4">
                    <a
                        href={`/api/v1/samples/${sample.id}/consensus`}
                        className="btn-ghost text-sm py-1.5"
                        download
                    >
                        <Download className="w-4 h-4" />
                        Consensus
                    </a>
                    <a
                        href={`/api/v1/samples/${sample.id}/vcf`}
                        className="btn-ghost text-sm py-1.5"
                        download
                    >
                        <Download className="w-4 h-4" />
                        VCF
                    </a>
                </div>
            )}
        </div>
    )
}

function RunDetails({ run }: { run: any }) {
    return (
        <div className="space-y-6">
            <div>
                <h3 className="font-medium mb-3">Configuration</h3>
                <dl className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                        <dt className="text-slate-500">Mode</dt>
                        <dd className="font-medium">{run.mode}</dd>
                    </div>
                    <div>
                        <dt className="text-slate-500">Primer Scheme</dt>
                        <dd className="font-medium">{run.primer_scheme || 'N/A'}</dd>
                    </div>
                    <div>
                        <dt className="text-slate-500">Created</dt>
                        <dd className="font-medium">{format(new Date(run.created_at), 'PPpp')}</dd>
                    </div>
                    <div>
                        <dt className="text-slate-500">Started</dt>
                        <dd className="font-medium">{run.started_at ? format(new Date(run.started_at), 'PPpp') : 'Not started'}</dd>
                    </div>
                    <div>
                        <dt className="text-slate-500">Completed</dt>
                        <dd className="font-medium">{run.completed_at ? format(new Date(run.completed_at), 'PPpp') : 'Not completed'}</dd>
                    </div>
                </dl>
            </div>

            {run.description && (
                <div>
                    <h3 className="font-medium mb-2">Description</h3>
                    <p className="text-slate-600 dark:text-slate-400">{run.description}</p>
                </div>
            )}
        </div>
    )
}

function ProvenanceView({ runId }: { runId: string }) {
    const { data, isLoading } = useQuery({
        queryKey: ['provenance', runId],
        queryFn: () => runsApi.provenance(runId),
    })

    if (isLoading) {
        return <div className="skeleton h-48 rounded-lg" />
    }

    const provenance = data?.data

    if (!provenance) {
        return (
            <div className="text-center py-8 text-slate-500">
                Provenance not yet available
            </div>
        )
    }

    return (
        <div className="space-y-6">
            <div>
                <h3 className="font-medium mb-3">Software Versions</h3>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
                    {provenance.software?.map((sw: any) => (
                        <div key={sw.name} className="bg-slate-50 dark:bg-slate-800 p-3 rounded-lg">
                            <div className="font-medium">{sw.name}</div>
                            <div className="text-slate-500 font-mono text-xs">{sw.version}</div>
                        </div>
                    ))}
                </div>
            </div>

            <div>
                <h3 className="font-medium mb-3">Run ID</h3>
                <code className="text-sm bg-slate-100 dark:bg-slate-800 px-3 py-2 rounded-lg block">
                    {provenance.run_id}
                </code>
            </div>
        </div>
    )
}
