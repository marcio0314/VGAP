import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import {
    FileText, Download, RefreshCw, Calendar, ChevronDown,
    File, Image, Table, Package
} from 'lucide-react'
import { reportsApi, runsApi } from '../utils/api'
import { format } from 'date-fns'

export default function Reports() {
    const [selectedRun, setSelectedRun] = useState<string>('')
    const [reportFormat, setReportFormat] = useState<'html' | 'pdf'>('html')
    const [generatedReport, setGeneratedReport] = useState<any>(null)

    const { data: runsData, isLoading: runsLoading } = useQuery({
        queryKey: ['runs', { status: 'completed' }],
        queryFn: () => runsApi.list({ status: 'completed', limit: 100 }),
    })

    const generateMutation = useMutation({
        mutationFn: () => reportsApi.generate(selectedRun, {
            format: reportFormat,
            include_figures: true,
            include_tables: true,
            include_provenance: true,
        }),
        onSuccess: (response) => {
            setGeneratedReport(response.data)
        },
    })

    const runs = runsData?.data?.items || []

    return (
        <div className="space-y-6">
            {/* Header */}
            <div>
                <h1 className="text-2xl font-bold">Reports</h1>
                <p className="text-slate-500 mt-1">
                    Generate and download analysis reports
                </p>
            </div>

            {/* Report Generator */}
            <div className="card p-6">
                <h2 className="text-lg font-semibold mb-4">Generate Report</h2>

                <div className="grid md:grid-cols-3 gap-4 mb-6">
                    {/* Run Selection */}
                    <div>
                        <label className="label">Select Run</label>
                        <div className="relative">
                            <select
                                className="input pr-10 appearance-none"
                                value={selectedRun}
                                onChange={(e) => setSelectedRun(e.target.value)}
                                disabled={runsLoading}
                            >
                                <option value="">Choose a completed run...</option>
                                {runs.map((run: any) => (
                                    <option key={run.id} value={run.id}>
                                        {run.name} ({run.sample_count} samples)
                                    </option>
                                ))}
                            </select>
                            <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400 pointer-events-none" />
                        </div>
                    </div>

                    {/* Format Selection */}
                    <div>
                        <label className="label">Report Format</label>
                        <div className="flex gap-2">
                            <button
                                className={`flex-1 py-2.5 px-4 rounded-lg border-2 transition-all ${reportFormat === 'html'
                                        ? 'border-primary-500 bg-primary-50 dark:bg-primary-500/10 text-primary-700'
                                        : 'border-slate-200 dark:border-slate-700'
                                    }`}
                                onClick={() => setReportFormat('html')}
                            >
                                HTML
                            </button>
                            <button
                                className={`flex-1 py-2.5 px-4 rounded-lg border-2 transition-all ${reportFormat === 'pdf'
                                        ? 'border-primary-500 bg-primary-50 dark:bg-primary-500/10 text-primary-700'
                                        : 'border-slate-200 dark:border-slate-700'
                                    }`}
                                onClick={() => setReportFormat('pdf')}
                            >
                                PDF
                            </button>
                        </div>
                    </div>

                    {/* Generate Button */}
                    <div>
                        <label className="label">&nbsp;</label>
                        <button
                            className="btn-primary w-full"
                            onClick={() => generateMutation.mutate()}
                            disabled={!selectedRun || generateMutation.isPending}
                        >
                            {generateMutation.isPending ? (
                                <>
                                    <RefreshCw className="w-4 h-4 animate-spin" />
                                    Generating...
                                </>
                            ) : (
                                <>
                                    <FileText className="w-4 h-4" />
                                    Generate Report
                                </>
                            )}
                        </button>
                    </div>
                </div>

                {/* Generated Report */}
                {generatedReport && (
                    <div className="bg-success-50 dark:bg-success-500/10 rounded-xl p-4">
                        <div className="flex items-center justify-between">
                            <div>
                                <div className="font-medium text-success-700 dark:text-success-400">
                                    Report Generated Successfully
                                </div>
                                <div className="text-sm text-success-600 dark:text-success-300">
                                    Generated at {format(new Date(generatedReport.generated_at), 'PPpp')}
                                </div>
                            </div>
                            <a
                                href={generatedReport.download_url}
                                className="btn-primary"
                                download
                            >
                                <Download className="w-4 h-4" />
                                Download
                            </a>
                        </div>
                    </div>
                )}
            </div>

            {/* Quick Downloads */}
            {selectedRun && (
                <div className="card p-6">
                    <h2 className="text-lg font-semibold mb-4">Quick Downloads</h2>

                    <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
                        <DownloadCard
                            title="Full Report"
                            description="Complete HTML report"
                            icon={FileText}
                            href={reportsApi.download(selectedRun, 'latest', 'html')}
                        />
                        <DownloadCard
                            title="Variant Summary"
                            description="TSV file with all variants"
                            icon={Table}
                            href={reportsApi.exports(selectedRun, 'variants')}
                        />
                        <DownloadCard
                            title="Lineage Summary"
                            description="TSV file with lineages"
                            icon={Table}
                            href={reportsApi.exports(selectedRun, 'lineages')}
                        />
                        <DownloadCard
                            title="Complete Package"
                            description="ZIP with all outputs"
                            icon={Package}
                            href={reportsApi.package(selectedRun)}
                        />
                    </div>
                </div>
            )}

            {/* Recent Reports */}
            <div className="card">
                <div className="p-6 border-b border-slate-200 dark:border-slate-700">
                    <h2 className="text-lg font-semibold">Completed Runs</h2>
                </div>

                {runsLoading ? (
                    <div className="p-6 space-y-3">
                        {[...Array(3)].map((_, i) => (
                            <div key={i} className="skeleton h-16 rounded-lg" />
                        ))}
                    </div>
                ) : runs.length > 0 ? (
                    <div className="divide-y divide-slate-100 dark:divide-slate-800">
                        {runs.slice(0, 10).map((run: any) => (
                            <div
                                key={run.id}
                                className="flex items-center gap-4 p-4 hover:bg-slate-50 dark:hover:bg-slate-800/50"
                            >
                                <div className="w-10 h-10 rounded-xl bg-success-100 dark:bg-success-500/20 flex items-center justify-center">
                                    <FileText className="w-5 h-5 text-success-500" />
                                </div>

                                <div className="flex-1 min-w-0">
                                    <div className="font-medium">{run.name}</div>
                                    <div className="text-sm text-slate-500">
                                        {run.sample_count} samples · {format(new Date(run.completed_at), 'MMM d, yyyy')}
                                    </div>
                                </div>

                                <button
                                    className="btn-ghost"
                                    onClick={() => setSelectedRun(run.id)}
                                >
                                    Generate
                                </button>

                                <a
                                    href={reportsApi.package(run.id)}
                                    className="btn-secondary"
                                    download
                                >
                                    <Download className="w-4 h-4" />
                                </a>
                            </div>
                        ))}
                    </div>
                ) : (
                    <div className="p-12 text-center text-slate-500">
                        No completed runs available for reporting
                    </div>
                )}
            </div>
        </div>
    )
}

function DownloadCard({ title, description, icon: Icon, href }: {
    title: string
    description: string
    icon: any
    href: string
}) {
    return (
        <a
            href={href}
            className="flex items-start gap-3 p-4 rounded-xl border border-slate-200 dark:border-slate-700 hover:border-primary-500 hover:bg-primary-50 dark:hover:bg-primary-500/10 transition-all"
            download
        >
            <div className="w-10 h-10 rounded-lg bg-slate-100 dark:bg-slate-700 flex items-center justify-center flex-shrink-0">
                <Icon className="w-5 h-5 text-slate-500" />
            </div>
            <div>
                <div className="font-medium">{title}</div>
                <div className="text-sm text-slate-500">{description}</div>
            </div>
        </a>
    )
}
