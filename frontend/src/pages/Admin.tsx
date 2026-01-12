import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
    Users, Database, Activity, Shield, Plus, Search,
    RefreshCw, CheckCircle, XCircle, ChevronDown, Clock,
    User, Mail, Calendar, MoreHorizontal, AlertTriangle,
    Trash2, HardDrive
} from 'lucide-react'
import { adminApi, maintenanceApi } from '../utils/api'
import { format, formatDistanceToNow } from 'date-fns'

type Tab = 'users' | 'databases' | 'audit' | 'status' | 'maintenance'

export default function Admin() {
    const [activeTab, setActiveTab] = useState<Tab>('users')

    return (
        <div className="space-y-6">
            {/* Header */}
            <div>
                <h1 className="text-2xl font-bold">Administration</h1>
                <p className="text-slate-500 mt-1">
                    Manage users, databases, and system settings
                </p>
            </div>

            {/* Tabs */}
            <div className="flex border-b border-slate-200 dark:border-slate-700 overflow-x-auto">
                {[
                    { key: 'users', label: 'Users', icon: Users },
                    { key: 'databases', label: 'Databases', icon: Database },
                    { key: 'audit', label: 'Audit Log', icon: Activity },
                    { key: 'status', label: 'System Status', icon: Shield },
                    { key: 'maintenance', label: 'Maintenance', icon: Trash2 },
                ].map((tab) => (
                    <button
                        key={tab.key}
                        className={`flex items-center gap-2 px-6 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${activeTab === tab.key
                            ? 'border-primary-500 text-primary-600'
                            : 'border-transparent text-slate-500 hover:text-slate-700'
                            }`}
                        onClick={() => setActiveTab(tab.key as Tab)}
                    >
                        {/* @ts-ignore */}
                        <tab.icon className="w-4 h-4" />
                        {tab.label}
                    </button>
                ))}
            </div>

            {/* Tab Content */}
            <div className="card">
                {activeTab === 'users' && <UsersTab />}
                {activeTab === 'databases' && <DatabasesTab />}
                {activeTab === 'audit' && <AuditLogTab />}
                {activeTab === 'status' && <SystemStatusTab />}
                {activeTab === 'maintenance' && <MaintenanceTab />}
            </div>
        </div>
    )
}

function MaintenanceTab() {
    const [step, setStep] = useState<'preview' | 'confirm' | 'execute'>('preview')
    const [previewData, setPreviewData] = useState<any>(null)
    const [cleanupResult, setCleanupResult] = useState<any>(null)

    const previewMutation = useMutation({
        mutationFn: () => maintenanceApi.preview(),
        onSuccess: (data) => {
            setPreviewData(data.data)
        }
    })

    const executeMutation = useMutation({
        mutationFn: () => maintenanceApi.execute(true),
        onSuccess: (data) => {
            setCleanupResult(data.data)
            setStep('execute')
        }
    })

    const handlePreview = () => {
        previewMutation.mutate()
        setStep('confirm')
    }

    const formatBytes = (bytes: number) => {
        if (bytes === 0) return '0 B'
        const k = 1024
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
        const i = Math.floor(Math.log(bytes) / Math.log(k))
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
    }

    return (
        <div className="p-6 space-y-8">
            <div>
                <h2 className="text-lg font-semibold mb-2 flex items-center gap-2">
                    <Trash2 className="w-5 h-5 text-slate-500" />
                    System Cleanup
                </h2>
                <p className="text-slate-500 max-w-2xl">
                    Safely remove temporary files, cached artifacts, and intermediate processing data.
                    This will NOT delete your source code, reference databases, or active configurations.
                </p>
            </div>

            {/* Step 1: Initial State / Preview Button */}
            {step === 'preview' && (
                <div className="bg-slate-50 dark:bg-slate-800/50 rounded-xl p-8 text-center border border-slate-200 dark:border-slate-700">
                    <div className="w-16 h-16 bg-slate-100 dark:bg-slate-700 rounded-full flex items-center justify-center mx-auto mb-4">
                        <Trash2 className="w-8 h-8 text-slate-400" />
                    </div>
                    <h3 className="font-medium text-lg mb-2">Ready to Clean</h3>
                    <p className="text-slate-500 mb-6">
                        Click below to scan for cleanable files. No files will be deleted yet.
                    </p>
                    <button
                        className="btn-primary"
                        onClick={handlePreview}
                        disabled={previewMutation.isPending}
                    >
                        {previewMutation.isPending ? 'Scanning...' : 'Scan System'}
                    </button>
                </div>
            )}

            {/* Step 2: Confirmation Screen */}
            {step === 'confirm' && (
                <div className="space-y-6">
                    {previewData && (
                        <div className="grid gap-4">
                            <div className="flex items-center justify-between p-4 bg-primary-50 dark:bg-primary-500/10 rounded-xl border border-primary-100 dark:border-primary-500/20">
                                <div className="flex items-center gap-3">
                                    <HardDrive className="w-5 h-5 text-primary-500" />
                                    <div>
                                        <div className="font-medium text-primary-900 dark:text-primary-100">Total reclaimable space</div>
                                        <div className="text-sm text-primary-700 dark:text-primary-300">
                                            Found in logs, temp files, and caches
                                        </div>
                                    </div>
                                </div>
                                <div className="text-2xl font-bold text-primary-600 dark:text-primary-400">
                                    {previewData.total_size_human}
                                </div>
                            </div>

                            <div className="border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden">
                                <table className="table w-full">
                                    <thead className="bg-slate-50 dark:bg-slate-800">
                                        <tr>
                                            <th className="px-4 py-3 text-left text-sm font-medium text-slate-500">Item</th>
                                            <th className="px-4 py-3 text-left text-sm font-medium text-slate-500">Description</th>
                                            <th className="px-4 py-3 text-right text-sm font-medium text-slate-500">Size</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
                                        {previewData.items.map((item: any) => (
                                            <tr key={item.path}>
                                                <td className="px-4 py-3 font-mono text-sm">{item.path}</td>
                                                <td className="px-4 py-3 text-sm text-slate-500">{item.description}</td>
                                                <td className="px-4 py-3 text-right text-sm font-medium">{item.size_human}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>

                            <div className="p-4 bg-slate-50 dark:bg-slate-800 rounded-xl">
                                <h4 className="text-sm font-medium text-slate-500 mb-2 uppercase tracking-wider">Protected Assets (Will NOT be touched)</h4>
                                <div className="flex flex-wrap gap-2">
                                    {previewData.protected.map((p: string) => (
                                        <span key={p} className="px-2 py-1 bg-white dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded text-xs font-mono text-slate-500">
                                            {p}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        </div>
                    )}

                    <div className="flex gap-3 justify-end pt-4 border-t border-slate-200 dark:border-slate-700">
                        <button
                            className="btn-secondary"
                            onClick={() => setStep('preview')}
                        >
                            Cancel
                        </button>
                        <button
                            className="btn-danger"
                            onClick={() => executeMutation.mutate()}
                            disabled={executeMutation.isPending}
                        >
                            {executeMutation.isPending ? 'Cleaning...' : 'Confirm Cleanup'}
                        </button>
                    </div>
                </div>
            )}

            {/* Step 3: Success Result */}
            {step === 'execute' && cleanupResult && (
                <div className="text-center py-12">
                    <div className="w-16 h-16 bg-success-100 dark:bg-success-500/20 rounded-full flex items-center justify-center mx-auto mb-4">
                        <CheckCircle className="w-8 h-8 text-success-500" />
                    </div>
                    <h3 className="font-bold text-xl mb-2">Cleanup Complete</h3>
                    <p className="text-slate-500 mb-6">
                        Successfully reclaimed <span className="font-bold text-slate-900 dark:text-white">{cleanupResult.space_freed_human}</span> of disk space.
                    </p>
                    <button
                        className="btn-primary"
                        onClick={() => {
                            setStep('preview')
                            setPreviewData(null)
                            setCleanupResult(null)
                        }}
                    >
                        Done
                    </button>
                </div>
            )}
        </div>
    )
}

function UsersTab() {
    const [showCreateModal, setShowCreateModal] = useState(false)
    const [searchQuery, setSearchQuery] = useState('')
    const queryClient = useQueryClient()

    const { data, isLoading, refetch } = useQuery({
        queryKey: ['admin-users'],
        queryFn: () => adminApi.users(),
    })

    const users = data?.data?.items || []

    const filteredUsers = users.filter((user: any) => {
        if (!searchQuery) return true
        const q = searchQuery.toLowerCase()
        return (
            user.email.toLowerCase().includes(q) ||
            user.full_name.toLowerCase().includes(q)
        )
    })

    return (
        <div>
            {/* Header */}
            <div className="flex items-center justify-between p-6 border-b border-slate-200 dark:border-slate-700">
                <div className="relative flex-1 max-w-sm">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
                    <input
                        type="text"
                        className="input pl-10"
                        placeholder="Search users..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                    />
                </div>
                <button className="btn-primary" onClick={() => setShowCreateModal(true)}>
                    <Plus className="w-4 h-4" />
                    Add User
                </button>
            </div>

            {/* Users List */}
            {isLoading ? (
                <div className="p-6 space-y-3">
                    {[...Array(5)].map((_, i) => (
                        <div key={i} className="skeleton h-16 rounded-lg" />
                    ))}
                </div>
            ) : (
                <table className="table">
                    <thead>
                        <tr>
                            <th>User</th>
                            <th>Role</th>
                            <th>Status</th>
                            <th>Created</th>
                            <th className="w-12"></th>
                        </tr>
                    </thead>
                    <tbody>
                        {filteredUsers.map((user: any) => (
                            <tr key={user.id}>
                                <td>
                                    <div className="flex items-center gap-3">
                                        <div className="w-10 h-10 rounded-full bg-gradient-to-br from-primary-400 to-primary-600 flex items-center justify-center text-white font-medium">
                                            {user.full_name.charAt(0).toUpperCase()}
                                        </div>
                                        <div>
                                            <div className="font-medium">{user.full_name}</div>
                                            <div className="text-sm text-slate-500">{user.email}</div>
                                        </div>
                                    </div>
                                </td>
                                <td>
                                    <span className={`badge ${user.role === 'admin' ? 'badge-danger' :
                                        user.role === 'analyst' ? 'badge-info' :
                                            'badge-neutral'
                                        }`}>
                                        {user.role}
                                    </span>
                                </td>
                                <td>
                                    {user.is_active ? (
                                        <span className="badge-success">Active</span>
                                    ) : (
                                        <span className="badge-neutral">Inactive</span>
                                    )}
                                </td>
                                <td className="text-sm text-slate-500">
                                    {format(new Date(user.created_at), 'MMM d, yyyy')}
                                </td>
                                <td>
                                    <button className="p-2 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg">
                                        <MoreHorizontal className="w-4 h-4" />
                                    </button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            )}

            {/* Create User Modal */}
            {showCreateModal && (
                <CreateUserModal onClose={() => setShowCreateModal(false)} onSuccess={refetch} />
            )}
        </div>
    )
}

function CreateUserModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
    const [formData, setFormData] = useState({
        email: '',
        full_name: '',
        password: '',
        role: 'analyst',
    })
    const [error, setError] = useState('')

    const createMutation = useMutation({
        mutationFn: () => adminApi.createUser(formData),
        onSuccess: () => {
            onSuccess()
            onClose()
        },
        onError: (err: any) => {
            const detail = err.response?.data?.detail
            setError(typeof detail === 'string' ? detail : JSON.stringify(detail))
        },
    })

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50">
            <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-elevated w-full max-w-md p-6">
                <h2 className="text-xl font-semibold mb-4">Create User</h2>

                {error && (
                    <div className="flex items-center gap-2 p-3 bg-danger-50 text-danger-600 rounded-xl mb-4">
                        <AlertTriangle className="w-4 h-4" />
                        {error}
                    </div>
                )}

                <div className="space-y-4">
                    <div>
                        <label className="label">Full Name</label>
                        <input
                            type="text"
                            className="input"
                            value={formData.full_name}
                            onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                        />
                    </div>
                    <div>
                        <label className="label">Email</label>
                        <input
                            type="email"
                            className="input"
                            value={formData.email}
                            onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                        />
                    </div>
                    <div>
                        <label className="label">Password</label>
                        <input
                            type="password"
                            className="input"
                            value={formData.password}
                            onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                        />
                    </div>
                    <div>
                        <label className="label">Role</label>
                        <select
                            className="input"
                            value={formData.role}
                            onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                        >
                            <option value="viewer">Viewer</option>
                            <option value="analyst">Analyst</option>
                            <option value="admin">Admin</option>
                        </select>
                    </div>
                </div>

                <div className="flex justify-end gap-3 mt-6">
                    <button className="btn-secondary" onClick={onClose}>Cancel</button>
                    <button
                        className="btn-primary"
                        onClick={() => createMutation.mutate()}
                        disabled={createMutation.isPending}
                    >
                        {createMutation.isPending ? 'Creating...' : 'Create User'}
                    </button>
                </div>
            </div>
        </div>
    )
}

function DatabasesTab() {
    const { data, isLoading, refetch } = useQuery({
        queryKey: ['admin-databases'],
        queryFn: () => adminApi.databases(),
    })

    const updateMutation = useMutation({
        mutationFn: (name: string) => adminApi.updateDatabase(name),
        onSuccess: () => refetch(),
    })

    const databases = data?.data || []

    return (
        <div className="p-6">
            <div className="flex items-center justify-between mb-6">
                <h2 className="text-lg font-semibold">Reference Databases</h2>
                <button className="btn-ghost" onClick={() => refetch()}>
                    <RefreshCw className="w-4 h-4" />
                    Refresh
                </button>
            </div>

            {isLoading ? (
                <div className="space-y-3">
                    {[...Array(3)].map((_, i) => (
                        <div key={i} className="skeleton h-20 rounded-xl" />
                    ))}
                </div>
            ) : (
                <div className="grid gap-4">
                    {databases.map((db: any) => (
                        <div
                            key={db.name}
                            className="flex items-center justify-between p-4 bg-slate-50 dark:bg-slate-800/50 rounded-xl"
                        >
                            <div className="flex items-center gap-4">
                                <div className="w-12 h-12 rounded-xl bg-primary-100 dark:bg-primary-500/20 flex items-center justify-center">
                                    <Database className="w-6 h-6 text-primary-500" />
                                </div>
                                <div>
                                    <div className="font-medium">{db.name}</div>
                                    <div className="text-sm text-slate-500">
                                        Version: {db.version} · Updated: {formatDistanceToNow(new Date(db.updated_at), { addSuffix: true })}
                                    </div>
                                </div>
                            </div>
                            <button
                                className="btn-secondary"
                                onClick={() => updateMutation.mutate(db.name)}
                                disabled={updateMutation.isPending}
                            >
                                {updateMutation.isPending ? (
                                    <RefreshCw className="w-4 h-4 animate-spin" />
                                ) : (
                                    'Update'
                                )}
                            </button>
                        </div>
                    ))}
                </div>
            )}
        </div>
    )
}

function AuditLogTab() {
    const { data, isLoading } = useQuery({
        queryKey: ['admin-audit'],
        queryFn: () => adminApi.auditLog({ limit: 50 }),
    })

    const logs = data?.data?.items || []

    return (
        <div>
            {isLoading ? (
                <div className="p-6 space-y-3">
                    {[...Array(10)].map((_, i) => (
                        <div key={i} className="skeleton h-12 rounded-lg" />
                    ))}
                </div>
            ) : logs.length > 0 ? (
                <table className="table">
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>User</th>
                            <th>Action</th>
                            <th>Resource</th>
                            <th>Details</th>
                        </tr>
                    </thead>
                    <tbody>
                        {logs.map((log: any) => (
                            <tr key={log.id}>
                                <td className="text-sm">
                                    {format(new Date(log.created_at), 'MMM d, HH:mm:ss')}
                                </td>
                                <td className="text-sm">{log.user_email || 'System'}</td>
                                <td>
                                    <span className={`badge ${log.action.includes('create') ? 'badge-success' :
                                        log.action.includes('delete') ? 'badge-danger' :
                                            log.action.includes('update') ? 'badge-warning' :
                                                'badge-neutral'
                                        }`}>
                                        {log.action}
                                    </span>
                                </td>
                                <td className="text-sm font-mono">{log.resource_type}</td>
                                <td className="text-sm text-slate-500 truncate max-w-xs">
                                    {log.details || '-'}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            ) : (
                <div className="p-12 text-center text-slate-500">
                    No audit logs available
                </div>
            )}
        </div>
    )
}

function SystemStatusTab() {
    const { data, isLoading, refetch } = useQuery({
        queryKey: ['admin-status'],
        queryFn: () => adminApi.status(),
        refetchInterval: 30000,
    })

    const status = data?.data || {}

    return (
        <div className="p-6">
            <div className="flex items-center justify-between mb-6">
                <h2 className="text-lg font-semibold">System Health</h2>
                <button className="btn-ghost" onClick={() => refetch()}>
                    <RefreshCw className="w-4 h-4" />
                    Refresh
                </button>
            </div>

            {isLoading ? (
                <div className="grid md:grid-cols-2 gap-4">
                    {[...Array(4)].map((_, i) => (
                        <div key={i} className="skeleton h-24 rounded-xl" />
                    ))}
                </div>
            ) : (
                <div className="grid md:grid-cols-2 gap-4">
                    <StatusCard
                        name="Database"
                        status={status.database}
                        icon={Database}
                    />
                    <StatusCard
                        name="Redis"
                        status={status.redis}
                        icon={Activity}
                    />
                    <StatusCard
                        name="Workers"
                        status={status.workers_active > 0 ? 'healthy' : 'degraded'}
                        icon={Users}
                        detail={`${status.workers_active || 0} active`}
                    />
                    <StatusCard
                        name="Disk"
                        status={status.disk_usage_percent < 90 ? 'healthy' : 'warning'}
                        icon={Database}
                        detail={`${status.disk_usage_percent || 0}% used`}
                    />
                </div>
            )}
        </div>
    )
}

function StatusCard({ name, status, icon: Icon, detail }: {
    name: string
    status: string
    icon: any
    detail?: string
}) {
    const isHealthy = status === 'healthy'

    return (
        <div className={`p-4 rounded-xl border ${isHealthy
            ? 'border-success-200 dark:border-success-500/30 bg-success-50 dark:bg-success-500/10'
            : 'border-danger-200 dark:border-danger-500/30 bg-danger-50 dark:bg-danger-500/10'
            }`}>
            <div className="flex items-center gap-3">
                <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${isHealthy ? 'bg-success-100 dark:bg-success-500/20' : 'bg-danger-100 dark:bg-danger-500/20'
                    }`}>
                    <Icon className={`w-5 h-5 ${isHealthy ? 'text-success-500' : 'text-danger-500'}`} />
                </div>
                <div>
                    <div className="font-medium">{name}</div>
                    <div className="text-sm ${isHealthy ? 'text-success-600' : 'text-danger-600'}">
                        {detail || status}
                    </div>
                </div>
                <div className="ml-auto">
                    {isHealthy ? (
                        <CheckCircle className="w-6 h-6 text-success-500" />
                    ) : (
                        <XCircle className="w-6 h-6 text-danger-500" />
                    )}
                </div>
            </div>
        </div>
    )
}
