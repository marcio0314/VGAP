import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Dna, Eye, EyeOff, AlertCircle } from 'lucide-react'
import { useAuth } from '../hooks/useAuth'

export default function Login() {
    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')
    const [showPassword, setShowPassword] = useState(false)
    const [error, setError] = useState('')
    const [isLoading, setIsLoading] = useState(false)

    const { login } = useAuth()
    const navigate = useNavigate()

    async function handleSubmit(e: React.FormEvent) {
        e.preventDefault()
        setError('')
        setIsLoading(true)

        try {
            await login(email, password)
            navigate('/app')
        } catch (err: any) {
            const detail = err.response?.data?.detail
            setError(typeof detail === 'string' ? detail : JSON.stringify(detail))
        } finally {
            setIsLoading(false)
        }
    }

    return (
        <div className="min-h-screen flex">
            {/* Left Panel - Form */}
            <div className="flex-1 flex items-center justify-center p-8">
                <div className="w-full max-w-md">
                    <Link to="/" className="inline-flex items-center gap-2 mb-8 text-slate-600 hover:text-slate-900 transition-colors">
                        <Dna className="w-6 h-6 text-primary-500" />
                        <span className="font-semibold text-lg">VGAP</span>
                    </Link>

                    <h1 className="text-3xl font-bold mb-2">Welcome back</h1>
                    <p className="text-slate-600 dark:text-slate-400 mb-8">
                        Sign in to your account to continue
                    </p>

                    {error && (
                        <div className="flex items-start gap-3 p-4 rounded-xl bg-danger-50 dark:bg-danger-500/10 text-danger-600 dark:text-danger-400 mb-6">
                            <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
                            <span className="text-sm">{error}</span>
                        </div>
                    )}

                    <form onSubmit={handleSubmit} className="space-y-5">
                        <div>
                            <label htmlFor="email" className="label">Email</label>
                            <input
                                id="email"
                                type="email"
                                className="input"
                                placeholder="you@example.com"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                required
                                autoFocus
                            />
                        </div>

                        <div>
                            <label htmlFor="password" className="label">Password</label>
                            <div className="relative">
                                <input
                                    id="password"
                                    type={showPassword ? 'text' : 'password'}
                                    className="input pr-12"
                                    placeholder="••••••••"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    required
                                />
                                <button
                                    type="button"
                                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors"
                                    onClick={() => setShowPassword(!showPassword)}
                                >
                                    {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                                </button>
                            </div>
                        </div>

                        <button
                            type="submit"
                            className="btn-primary w-full py-3"
                            disabled={isLoading}
                        >
                            {isLoading ? (
                                <div className="animate-spin rounded-full h-5 w-5 border-t-2 border-b-2 border-white"></div>
                            ) : (
                                'Sign In'
                            )}
                        </button>
                    </form>

                    <p className="mt-8 text-center text-sm text-slate-500">
                        Need access? Contact your administrator.
                    </p>
                </div>
            </div>

            {/* Right Panel - Decorative */}
            <div className="hidden lg:flex flex-1 bg-gradient-to-br from-primary-600 to-primary-800 items-center justify-center p-12">
                <div className="max-w-lg text-white">
                    <div className="w-16 h-16 rounded-2xl bg-white/10 backdrop-blur-xl flex items-center justify-center mb-8">
                        <Dna className="w-8 h-8" />
                    </div>

                    <h2 className="text-3xl font-bold mb-4">
                        Viral Genomics Analysis Platform
                    </h2>

                    <p className="text-primary-100 text-lg mb-8">
                        Production-grade analysis pipeline for viral genomics research.
                        From raw reads to publication-ready results.
                    </p>

                    <div className="space-y-4">
                        {[
                            'End-to-end analysis pipeline',
                            'Complete reproducibility',
                            'Publication-ready reports',
                            'Full audit trail',
                        ].map((feature, i) => (
                            <div key={i} className="flex items-center gap-3">
                                <div className="w-6 h-6 rounded-full bg-white/20 flex items-center justify-center">
                                    <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                                    </svg>
                                </div>
                                <span>{feature}</span>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    )
}
