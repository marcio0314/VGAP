import React, { useState, useEffect } from 'react'
import { Settings, Info, AlertTriangle, ChevronDown, ChevronRight, Eye } from 'lucide-react'

// Types matching Backend Pydantic Schemas
type VirusTarget = 'sars_cov_2' | 'influenza_a' | 'influenza_b' | 'rsv' | 'hmpv' | 'adenovirus' | 'generic_rna' | 'generic_dna'
type PipelineMode = 'amplicon' | 'shotgun'
// Only keeping simple primitive types here to avoid complexity. 
// Can import from shared types definition file if available later.

interface ParameterPanelProps {
    mode: PipelineMode
    onChange: (params: any) => void
}

const PRESETS: Record<string, any> = {
    'sars_cov_2': {
        virus_target: 'sars_cov_2',
        reference_set: 'sars-cov-2',
        mapper: 'minimap2',
        min_depth: 10,
        min_af: 0.5,
        consensus_min_coverage: 10,
        consensus_min_af: 0.5,
        primer_trimming: true,
    },
    'influenza_a': {
        virus_target: 'influenza_a',
        reference_set: 'influenza-a',
        mapper: 'minimap2',
        min_depth: 10,
        min_af: 0.5,
        consensus_min_coverage: 10,
        consensus_min_af: 0.5,
        per_segment_coverage_required: {
            "HA": 80.0, "NA": 80.0
        }
    },
    'influenza_b': {
        virus_target: 'influenza_b',
        reference_set: 'influenza-b',
        mapper: 'minimap2',
        min_depth: 10,
        min_af: 0.5
    },
    'rsv': {
        virus_target: 'rsv',
        reference_set: 'rsv',
        mapper: 'minimap2',
        min_depth: 10,
        min_af: 0.5
    },
    'generic_rna': {
        virus_target: 'generic_rna',
        reference_set: 'generic',
        mapper: 'minimap2',
        min_depth: 10,
        min_af: 0.5
    },
    'generic_dna': {
        virus_target: 'generic_dna',
        reference_set: 'generic',
        mapper: 'minimap2',
        min_depth: 10,
        min_af: 0.5
    }
}

export default function ParameterPanel({ mode, onChange }: ParameterPanelProps) {
    const [isOpen, setIsOpen] = useState(false)
    const [virusTarget, setVirusTarget] = useState<VirusTarget>('sars_cov_2')
    const [params, setParams] = useState<any>(PRESETS['sars_cov_2'])
    const [showPreview, setShowPreview] = useState(false)

    // Sync params on mount and when changed
    useEffect(() => {
        onChange(params)
    }, [params])

    const handlePresetChange = (target: VirusTarget) => {
        setVirusTarget(target)
        if (PRESETS[target]) {
            setParams((prev: any) => ({
                ...prev,
                ...PRESETS[target],
                mode: mode // Ensure mode matches parent
            }))
        } else {
            // Fallback or generic init
            setParams((prev: any) => ({
                ...prev,
                virus_target: target,
                mode: mode
            }))
        }
    }

    const handleChange = (field: string, value: any) => {
        setParams((prev: any) => ({ ...prev, [field]: value }))
    }

    return (
        <div className="border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden mb-6">
            <button
                type="button"
                className="w-full flex items-center justify-between p-4 bg-slate-50 dark:bg-slate-800 hover:bg-slate-100 transition-colors"
                onClick={() => setIsOpen(!isOpen)}
            >
                <div className="flex items-center gap-2 font-medium">
                    <Settings className="w-4 h-4 text-slate-500" />
                    Advanced Parameters
                </div>
                {isOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
            </button>

            {isOpen && (
                <div className="p-6 space-y-6 bg-white dark:bg-slate-900 border-t border-slate-200 dark:border-slate-700">

                    {/* Virus Target Selection */}
                    <div>
                        <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1">Viral Target</label>
                        <select
                            className="block w-full rounded-md border-slate-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm dark:bg-slate-800 dark:border-slate-600"
                            value={virusTarget}
                            onChange={(e) => handlePresetChange(e.target.value as VirusTarget)}
                        >
                            <option value="sars_cov_2">SARS-CoV-2</option>
                            <option value="influenza_a">Influenza A</option>
                            <option value="influenza_b">Influenza B</option>
                            <option value="rsv">RSV (Respiratory Syncytial Virus)</option>
                            <option value="generic_rna">Generic RNA Virus</option>
                            <option value="generic_dna">Generic DNA Virus</option>
                        </select>
                        <div className="text-xs text-slate-500 mt-1 flex items-center gap-1">
                            <Info className="w-3 h-3" />
                            Sets validated defaults for reference genome and mapping settings.
                        </div>
                    </div>

                    {/* Core Mapping */}
                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1">Min Depth (Coverage)</label>
                            <input
                                type="number"
                                className="block w-full rounded-md border-slate-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm dark:bg-slate-800 dark:border-slate-600"
                                value={params.min_depth || 10}
                                onChange={(e) => handleChange('min_depth', parseInt(e.target.value))}
                                min={1}
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1">Min Allele Frequency</label>
                            <input
                                type="number"
                                className="block w-full rounded-md border-slate-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm dark:bg-slate-800 dark:border-slate-600"
                                value={params.min_af || 0.05}
                                onChange={(e) => handleChange('min_af', parseFloat(e.target.value))}
                                step={0.01} min={0} max={1}
                            />
                        </div>
                    </div>

                    {/* Mode Specific */}
                    {mode === 'amplicon' && (
                        <div className="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                            <h4 className="font-medium text-sm text-blue-700 dark:text-blue-300 mb-2">Amplicon Settings</h4>
                            <div className="flex items-center gap-2">
                                <input
                                    type="checkbox"
                                    id="primer_trimming"
                                    checked={!!params.primer_trimming}
                                    onChange={(e) => handleChange('primer_trimming', e.target.checked)}
                                    className="rounded border-slate-300 text-primary-600 focus:ring-primary-500"
                                />
                                <label htmlFor="primer_trimming" className="text-sm">Enable Primer Trimming</label>
                            </div>
                        </div>
                    )}

                    {/* Segmented Virus Warnings */}
                    {['influenza_a', 'influenza_b'].includes(virusTarget) && (
                        <div className="p-4 bg-amber-50 dark:bg-amber-900/20 rounded-lg flex items-start gap-2 text-amber-700 dark:text-amber-400">
                            <AlertTriangle className="w-5 h-5 flex-shrink-0" />
                            <div className="text-sm">
                                <strong>Segmented Genome:</strong> Analysis will report coverage and consensus for all 8 segments individually. Ensure you use a segmented reference.
                            </div>
                        </div>
                    )}

                    {/* Preview Toggle */}
                    <div>
                        <button
                            type="button"
                            className="text-xs text-slate-500 hover:text-primary-500 flex items-center gap-1"
                            onClick={() => setShowPreview(!showPreview)}
                        >
                            <Eye className="w-3 h-3" />
                            {showPreview ? 'Hide' : 'Show'} JSON Preview
                        </button>
                        {showPreview && (
                            <pre className="mt-2 p-3 bg-slate-100 dark:bg-slate-950 rounded text-xs font-mono overflow-auto max-h-40">
                                {JSON.stringify(params, null, 2)}
                            </pre>
                        )}
                    </div>

                </div>
            )}
        </div>
    )
}
