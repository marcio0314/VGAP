import { Link } from 'react-router-dom'
import {
    Dna, Shield, BarChart3, Clock, ChevronRight,
    FlaskConical, GitBranch, FileText
} from 'lucide-react'

export default function Landing() {
    return (
        <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white dark:from-slate-900 dark:to-slate-800">
            {/* Navigation */}
            <nav className="fixed top-0 inset-x-0 z-50 glass border-b border-slate-200/50 dark:border-slate-700/50">
                <div className="section flex items-center justify-between h-16">
                    <div className="flex items-center gap-2">
                        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center">
                            <Dna className="w-5 h-5 text-white" />
                        </div>
                        <span className="font-semibold text-lg tracking-tight">VGAP</span>
                    </div>

                    <div className="flex items-center gap-4">
                        <Link
                            to="/login"
                            className="btn-ghost"
                        >
                            Sign In
                        </Link>
                        <Link
                            to="/login"
                            className="btn-primary"
                        >
                            Get Started
                        </Link>
                    </div>
                </div>
            </nav>

            {/* Hero Section */}
            <section className="pt-32 pb-20 section">
                <div className="max-w-4xl mx-auto text-center">
                    <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary-50 dark:bg-primary-500/10 text-primary-600 dark:text-primary-400 text-sm font-medium mb-8">
                        <FlaskConical className="w-4 h-4" />
                        Production-Grade Viral Genomics
                    </div>

                    <h1 className="text-5xl md:text-6xl font-bold tracking-tight text-balance mb-6">
                        Viral Genomics
                        <span className="bg-gradient-to-r from-primary-500 to-primary-700 bg-clip-text text-transparent">
                            {' '}Analysis Platform
                        </span>
                    </h1>

                    <p className="text-xl text-slate-600 dark:text-slate-400 max-w-2xl mx-auto mb-10 text-balance">
                        End-to-end platform for viral genome analysis. From raw FASTQ files to
                        publication-ready reports with complete reproducibility.
                    </p>

                    <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                        <Link to="/login" className="btn-primary text-base px-8 py-3">
                            Start Analysis
                            <ChevronRight className="w-5 h-5" />
                        </Link>
                        <a href="#features" className="btn-secondary text-base px-8 py-3">
                            Learn More
                        </a>
                    </div>
                </div>
            </section>

            {/* Stats Section */}
            <section className="py-16 border-y border-slate-200 dark:border-slate-700 bg-slate-50/50 dark:bg-slate-800/50">
                <div className="section">
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
                        {[
                            { value: '100%', label: 'Reproducible' },
                            { value: '<10min', label: 'Per Sample' },
                            { value: '50+', label: 'Quality Metrics' },
                            { value: 'HIPAA', label: 'Compliant' },
                        ].map((stat, i) => (
                            <div key={i} className="text-center">
                                <div className="text-3xl md:text-4xl font-bold text-slate-900 dark:text-white mb-2">
                                    {stat.value}
                                </div>
                                <div className="text-slate-500 dark:text-slate-400 text-sm">
                                    {stat.label}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            {/* Features Section */}
            <section id="features" className="py-24 section">
                <div className="text-center mb-16">
                    <h2 className="text-3xl md:text-4xl font-bold mb-4">
                        Complete Analysis Pipeline
                    </h2>
                    <p className="text-slate-600 dark:text-slate-400 max-w-2xl mx-auto">
                        Every step from quality control to lineage assignment,
                        designed for scientific rigor and reproducibility.
                    </p>
                </div>

                <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {[
                        {
                            icon: Shield,
                            title: 'Pre-flight Validation',
                            description: 'Comprehensive input validation with clear error messages. Catch problems before they waste compute.',
                            color: 'text-success-500',
                        },
                        {
                            icon: BarChart3,
                            title: 'Quality Control',
                            description: 'Automated QC with fastp, host removal, and contamination detection. 50+ metrics per sample.',
                            color: 'text-primary-500',
                        },
                        {
                            icon: GitBranch,
                            title: 'Variant Calling',
                            description: 'Amplicon-aware calling with ivar or shotgun with bcftools. Full annotation and filtering.',
                            color: 'text-warning-500',
                        },
                        {
                            icon: Dna,
                            title: 'Lineage Assignment',
                            description: 'Pangolin and Nextclade integration for SARS-CoV-2. Extensible to other viruses.',
                            color: 'text-danger-500',
                        },
                        {
                            icon: FileText,
                            title: 'Publication Reports',
                            description: 'Generate HTML reports with interactive figures. Export data in standard formats.',
                            color: 'text-primary-600',
                        },
                        {
                            icon: Clock,
                            title: 'Full Provenance',
                            description: 'Complete audit trail with checksums, software versions, and random seeds.',
                            color: 'text-slate-500',
                        },
                    ].map((feature, i) => (
                        <div
                            key={i}
                            className="card p-6 card-hover"
                        >
                            <feature.icon className={`w-10 h-10 ${feature.color} mb-4`} />
                            <h3 className="text-lg font-semibold mb-2">{feature.title}</h3>
                            <p className="text-slate-600 dark:text-slate-400 text-sm">
                                {feature.description}
                            </p>
                        </div>
                    ))}
                </div>
            </section>

            {/* CTA Section */}
            <section className="py-24 section">
                <div className="card bg-gradient-to-br from-primary-600 to-primary-800 p-12 text-center text-white">
                    <h2 className="text-3xl md:text-4xl font-bold mb-4">
                        Ready to Analyze?
                    </h2>
                    <p className="text-primary-100 max-w-xl mx-auto mb-8">
                        Get started with your first analysis in minutes.
                        Upload your FASTQ files and let VGAP do the rest.
                    </p>
                    <Link
                        to="/login"
                        className="inline-flex items-center gap-2 bg-white text-primary-600 px-8 py-3 rounded-xl font-medium hover:bg-primary-50 transition-colors"
                    >
                        Get Started Free
                        <ChevronRight className="w-5 h-5" />
                    </Link>
                </div>
            </section>

            {/* Footer */}
            <footer className="py-12 border-t border-slate-200 dark:border-slate-700">
                <div className="section">
                    <div className="flex flex-col md:flex-row items-center justify-between gap-4">
                        <div className="flex items-center gap-2 text-slate-500 text-sm">
                            <Dna className="w-5 h-5" />
                            <span>VGAP — Viral Genomics Analysis Platform</span>
                        </div>
                        <div className="text-slate-400 text-sm">
                            © 2026 VGAP. All rights reserved.
                        </div>
                    </div>
                </div>
            </footer>
        </div>
    )
}
