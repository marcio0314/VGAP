import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import {
    ArrowLeft, ArrowRight, Upload, Dna, Settings,
    CheckCircle, AlertCircle, X, Plus, File
} from 'lucide-react'
import { runsApi, uploadApi } from '../utils/api'

type Step = 'mode' | 'samples' | 'settings' | 'review'

interface SampleFile {
    id: string
    name: string
    r1: File
    r2?: File
    metadata: {
        sample_id: string
        collection_date?: string
        location?: string
    }
}

export default function CreateRun() {
    const navigate = useNavigate()
    const [step, setStep] = useState<Step>('mode')
    const [runName, setRunName] = useState('')
    const [mode, setMode] = useState<'amplicon' | 'shotgun'>('amplicon')
    const [primerScheme, setPrimerScheme] = useState('ARTIC-V5.3.2')
    const [samples, setSamples] = useState<SampleFile[]>([])
    const [uploadProgress, setUploadProgress] = useState<Record<string, number>>({})
    const [error, setError] = useState('')

    const createRunMutation = useMutation({
        mutationFn: async () => {
            // Create run
            const runData = {
                name: runName,
                mode,
                primer_scheme: mode === 'amplicon' ? primerScheme : null,
                samples: samples.map(s => ({
                    r1_filename: s.r1.name,
                    r2_filename: s.r2?.name,
                    metadata: s.metadata,
                })),
            }

            const response = await runsApi.create(runData)
            return response.data
        },
        onSuccess: (data) => {
            navigate(`/app/runs/${data.id}`)
        },
        onError: (err: any) => {
            setError(err.response?.data?.detail || 'Failed to create run')
        },
    })

    const steps: { key: Step; label: string; icon: any }[] = [
        { key: 'mode', label: 'Mode', icon: Settings },
        { key: 'samples', label: 'Samples', icon: Dna },
        { key: 'settings', label: 'Settings', icon: Settings },
        { key: 'review', label: 'Review', icon: CheckCircle },
    ]

    const currentStepIndex = steps.findIndex(s => s.key === step)

    const canProceed = () => {
        switch (step) {
            case 'mode':
                return runName.length > 0
            case 'samples':
                return samples.length > 0
            case 'settings':
                return mode === 'shotgun' || primerScheme.length > 0
            case 'review':
                return true
            default:
                return false
        }
    }

    const nextStep = () => {
        const idx = currentStepIndex
        if (idx < steps.length - 1) {
            setStep(steps[idx + 1].key)
        } else {
            createRunMutation.mutate()
        }
    }

    const prevStep = () => {
        const idx = currentStepIndex
        if (idx > 0) {
            setStep(steps[idx - 1].key)
        }
    }

    const addSample = (r1: File, r2?: File) => {
        const sampleId = r1.name.replace(/_R[12].*\.fastq.*$/i, '').replace(/\.fastq.*$/i, '')

        setSamples(prev => [...prev, {
            id: crypto.randomUUID(),
            name: sampleId,
            r1,
            r2,
            metadata: {
                sample_id: sampleId,
            },
        }])
    }

    const removeSample = (id: string) => {
        setSamples(prev => prev.filter(s => s.id !== id))
    }

    const handleFileDrop = (e: React.DragEvent) => {
        e.preventDefault()
        const files = Array.from(e.dataTransfer.files)
        processFiles(files)
    }

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files) {
            const files = Array.from(e.target.files)
            processFiles(files)
        }
    }

    const processFiles = (files: File[]) => {
        // Group by sample ID
        const groups: Record<string, { r1?: File; r2?: File }> = {}

        files.forEach(file => {
            const name = file.name
            const sampleId = name.replace(/_R[12].*\.fastq.*$/i, '').replace(/\.fastq.*$/i, '')

            if (!groups[sampleId]) {
                groups[sampleId] = {}
            }

            if (/_R1/i.test(name) || /_1\.fastq/i.test(name)) {
                groups[sampleId].r1 = file
            } else if (/_R2/i.test(name) || /_2\.fastq/i.test(name)) {
                groups[sampleId].r2 = file
            } else {
                groups[sampleId].r1 = file
            }
        })

        Object.entries(groups).forEach(([_, files]) => {
            if (files.r1) {
                addSample(files.r1, files.r2)
            }
        })
    }

    return (
        <div className="max-w-4xl mx-auto">
            {/* Header */}
            <div className="mb-8">
                <button
                    onClick={() => navigate('/app/runs')}
                    className="inline-flex items-center gap-1 text-slate-500 hover:text-slate-700 mb-4"
                >
                    <ArrowLeft className="w-4 h-4" />
                    Back to runs
                </button>
                <h1 className="text-2xl font-bold">Create New Analysis</h1>
            </div>

            {/* Progress Steps */}
            <div className="mb-8">
                <div className="flex items-center justify-between">
                    {steps.map((s, i) => (
                        <div key={s.key} className="flex items-center">
                            <div className={`
                flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium
                ${step === s.key
                                    ? 'bg-primary-100 dark:bg-primary-500/20 text-primary-700 dark:text-primary-400'
                                    : i < currentStepIndex
                                        ? 'bg-success-100 dark:bg-success-500/20 text-success-700 dark:text-success-400'
                                        : 'bg-slate-100 dark:bg-slate-700 text-slate-500'
                                }
              `}>
                                {i < currentStepIndex ? (
                                    <CheckCircle className="w-4 h-4" />
                                ) : (
                                    <s.icon className="w-4 h-4" />
                                )}
                                {s.label}
                            </div>

                            {i < steps.length - 1 && (
                                <div className={`w-16 h-0.5 mx-2 ${i < currentStepIndex ? 'bg-success-500' : 'bg-slate-200 dark:bg-slate-700'
                                    }`} />
                            )}
                        </div>
                    ))}
                </div>
            </div>

            {/* Error */}
            {error && (
                <div className="flex items-start gap-3 p-4 rounded-xl bg-danger-50 dark:bg-danger-500/10 text-danger-600 mb-6">
                    <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
                    <span className="text-sm">{error}</span>
                    <button onClick={() => setError('')} className="ml-auto">
                        <X className="w-4 h-4" />
                    </button>
                </div>
            )}

            {/* Step Content */}
            <div className="card p-8 mb-6">
                {step === 'mode' && (
                    <div className="space-y-6">
                        <div>
                            <label className="label">Run Name</label>
                            <input
                                type="text"
                                className="input"
                                placeholder="e.g., Batch_2026_01_11"
                                value={runName}
                                onChange={(e) => setRunName(e.target.value)}
                                autoFocus
                            />
                        </div>

                        <div>
                            <label className="label">Pipeline Mode</label>
                            <div className="grid grid-cols-2 gap-4">
                                <button
                                    className={`p-6 rounded-xl border-2 text-left transition-all ${mode === 'amplicon'
                                            ? 'border-primary-500 bg-primary-50 dark:bg-primary-500/10'
                                            : 'border-slate-200 dark:border-slate-700 hover:border-slate-300'
                                        }`}
                                    onClick={() => setMode('amplicon')}
                                >
                                    <div className="font-semibold mb-1">Amplicon</div>
                                    <div className="text-sm text-slate-500">
                                        For tiled amplicon sequencing (ARTIC, Midnight, etc.)
                                    </div>
                                </button>

                                <button
                                    className={`p-6 rounded-xl border-2 text-left transition-all ${mode === 'shotgun'
                                            ? 'border-primary-500 bg-primary-50 dark:bg-primary-500/10'
                                            : 'border-slate-200 dark:border-slate-700 hover:border-slate-300'
                                        }`}
                                    onClick={() => setMode('shotgun')}
                                >
                                    <div className="font-semibold mb-1">Shotgun</div>
                                    <div className="text-sm text-slate-500">
                                        For metagenomic or capture-based sequencing
                                    </div>
                                </button>
                            </div>
                        </div>
                    </div>
                )}

                {step === 'samples' && (
                    <div className="space-y-6">
                        <div
                            className="border-2 border-dashed border-slate-300 dark:border-slate-600 rounded-xl p-12 text-center hover:border-primary-500 transition-colors"
                            onDrop={handleFileDrop}
                            onDragOver={(e) => e.preventDefault()}
                        >
                            <Upload className="w-12 h-12 text-slate-400 mx-auto mb-4" />
                            <p className="text-lg font-medium mb-2">
                                Drop FASTQ files here
                            </p>
                            <p className="text-sm text-slate-500 mb-4">
                                or click to browse
                            </p>
                            <input
                                type="file"
                                className="hidden"
                                id="file-input"
                                multiple
                                accept=".fastq,.fastq.gz,.fq,.fq.gz"
                                onChange={handleFileSelect}
                            />
                            <label htmlFor="file-input" className="btn-secondary cursor-pointer">
                                Browse Files
                            </label>
                        </div>

                        {samples.length > 0 && (
                            <div>
                                <h3 className="font-medium mb-3">{samples.length} Samples</h3>
                                <div className="space-y-2 max-h-64 overflow-y-auto">
                                    {samples.map((sample) => (
                                        <div
                                            key={sample.id}
                                            className="flex items-center gap-3 p-3 bg-slate-50 dark:bg-slate-800 rounded-lg"
                                        >
                                            <File className="w-5 h-5 text-slate-400" />
                                            <div className="flex-1 min-w-0">
                                                <div className="font-medium truncate">{sample.name}</div>
                                                <div className="text-xs text-slate-500">
                                                    {sample.r1.name}
                                                    {sample.r2 && ` + ${sample.r2.name}`}
                                                </div>
                                            </div>
                                            <button
                                                className="p-1 hover:bg-slate-200 dark:hover:bg-slate-700 rounded"
                                                onClick={() => removeSample(sample.id)}
                                            >
                                                <X className="w-4 h-4" />
                                            </button>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                )}

                {step === 'settings' && (
                    <div className="space-y-6">
                        {mode === 'amplicon' && (
                            <div>
                                <label className="label">Primer Scheme</label>
                                <select
                                    className="input"
                                    value={primerScheme}
                                    onChange={(e) => setPrimerScheme(e.target.value)}
                                >
                                    <optgroup label="ARTIC">
                                        <option value="ARTIC-V5.3.2">ARTIC V5.3.2</option>
                                        <option value="ARTIC-V4.1">ARTIC V4.1</option>
                                        <option value="ARTIC-V3">ARTIC V3</option>
                                    </optgroup>
                                    <optgroup label="Midnight">
                                        <option value="Midnight-1200">Midnight 1200bp</option>
                                        <option value="Midnight-IDT">Midnight IDT</option>
                                    </optgroup>
                                    <optgroup label="Other">
                                        <option value="swift">Swift Amplicon</option>
                                        <option value="custom">Custom</option>
                                    </optgroup>
                                </select>
                            </div>
                        )}

                        <div>
                            <label className="label">Description (optional)</label>
                            <textarea
                                className="input h-24 resize-none"
                                placeholder="Notes about this analysis run..."
                            />
                        </div>
                    </div>
                )}

                {step === 'review' && (
                    <div className="space-y-6">
                        <h3 className="font-semibold text-lg">Review Your Analysis</h3>

                        <div className="grid grid-cols-2 gap-6">
                            <div>
                                <div className="text-sm text-slate-500 mb-1">Run Name</div>
                                <div className="font-medium">{runName}</div>
                            </div>
                            <div>
                                <div className="text-sm text-slate-500 mb-1">Mode</div>
                                <div className="font-medium capitalize">{mode}</div>
                            </div>
                            <div>
                                <div className="text-sm text-slate-500 mb-1">Samples</div>
                                <div className="font-medium">{samples.length} samples</div>
                            </div>
                            {mode === 'amplicon' && (
                                <div>
                                    <div className="text-sm text-slate-500 mb-1">Primer Scheme</div>
                                    <div className="font-medium">{primerScheme}</div>
                                </div>
                            )}
                        </div>

                        <div className="bg-primary-50 dark:bg-primary-500/10 p-4 rounded-xl">
                            <div className="flex items-start gap-3">
                                <CheckCircle className="w-5 h-5 text-primary-500 mt-0.5" />
                                <div>
                                    <div className="font-medium text-primary-700 dark:text-primary-400">
                                        Ready to Start
                                    </div>
                                    <div className="text-sm text-primary-600 dark:text-primary-300">
                                        Click "Create Run" to begin. You can start the analysis from the run details page.
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                )}
            </div>

            {/* Navigation */}
            <div className="flex justify-between">
                <button
                    className="btn-secondary"
                    onClick={prevStep}
                    disabled={currentStepIndex === 0}
                >
                    <ArrowLeft className="w-4 h-4" />
                    Back
                </button>

                <button
                    className="btn-primary"
                    onClick={nextStep}
                    disabled={!canProceed() || createRunMutation.isPending}
                >
                    {step === 'review' ? (
                        createRunMutation.isPending ? 'Creating...' : 'Create Run'
                    ) : (
                        <>
                            Next
                            <ArrowRight className="w-4 h-4" />
                        </>
                    )}
                </button>
            </div>
        </div>
    )
}
