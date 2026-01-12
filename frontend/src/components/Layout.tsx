import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom'
import {
    Dna, LayoutDashboard, PlayCircle, FileText,
    Settings, LogOut, User, Menu, X, Sun, Moon, HardDrive
} from 'lucide-react'
import { useState } from 'react'
import { useAuth } from '../hooks/useAuth'

const navigation = [
    { name: 'Dashboard', href: '/app', icon: LayoutDashboard },
    { name: 'Runs', href: '/app/runs', icon: PlayCircle },
    { name: 'Reports', href: '/app/reports', icon: FileText },
    { name: 'Maintenance', href: '/app/maintenance', icon: HardDrive, adminOnly: true },
    { name: 'Admin', href: '/app/admin', icon: Settings, adminOnly: true },
]

export default function Layout() {
    const [sidebarOpen, setSidebarOpen] = useState(false)
    const [darkMode, setDarkMode] = useState(false)
    const location = useLocation()
    const navigate = useNavigate()
    const { user, logout } = useAuth()

    function handleLogout() {
        logout()
        navigate('/login')
    }

    function toggleDarkMode() {
        setDarkMode(!darkMode)
        document.documentElement.classList.toggle('dark')
    }

    return (
        <div className="min-h-screen flex bg-slate-50 dark:bg-slate-900">
            {/* Sidebar */}
            <aside className={`
        fixed inset-y-0 left-0 z-50 w-64 bg-white dark:bg-slate-800 
        border-r border-slate-200 dark:border-slate-700
        transform transition-transform duration-200 ease-out
        lg:translate-x-0 lg:static
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
                <div className="flex flex-col h-full">
                    {/* Logo */}
                    <div className="flex items-center gap-3 px-6 h-16 border-b border-slate-200 dark:border-slate-700">
                        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center">
                            <Dna className="w-5 h-5 text-white" />
                        </div>
                        <span className="font-semibold text-lg tracking-tight">VGAP</span>

                        <button
                            className="lg:hidden ml-auto p-2"
                            onClick={() => setSidebarOpen(false)}
                        >
                            <X className="w-5 h-5" />
                        </button>
                    </div>

                    {/* Navigation */}
                    <nav className="flex-1 p-4 space-y-1">
                        {navigation.map((item) => {
                            // Skip admin items for non-admin users
                            if (item.adminOnly && user?.role !== 'admin') return null

                            const isActive = item.href === '/app'
                                ? location.pathname === '/app'
                                : location.pathname.startsWith(item.href)

                            return (
                                <Link
                                    key={item.name}
                                    to={item.href}
                                    className={`
                    flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm font-medium
                    transition-all duration-150
                    ${isActive
                                            ? 'bg-primary-50 dark:bg-primary-500/10 text-primary-600 dark:text-primary-400'
                                            : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700'
                                        }
                  `}
                                >
                                    <item.icon className="w-5 h-5" />
                                    {item.name}
                                </Link>
                            )
                        })}
                    </nav>

                    {/* User section */}
                    <div className="p-4 border-t border-slate-200 dark:border-slate-700">
                        <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-slate-50 dark:bg-slate-700/50">
                            <div className="w-9 h-9 rounded-full bg-gradient-to-br from-primary-400 to-primary-600 flex items-center justify-center">
                                <User className="w-4 h-4 text-white" />
                            </div>
                            <div className="flex-1 min-w-0">
                                <div className="font-medium text-sm truncate">
                                    {user?.full_name || 'User'}
                                </div>
                                <div className="text-xs text-slate-500 truncate">
                                    {user?.email}
                                </div>
                            </div>
                        </div>

                        <div className="flex gap-2 mt-3">
                            <button
                                onClick={toggleDarkMode}
                                className="flex-1 btn-ghost py-2"
                            >
                                {darkMode ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
                            </button>
                            <button
                                onClick={handleLogout}
                                className="flex-1 btn-ghost py-2 text-danger-500"
                            >
                                <LogOut className="w-4 h-4" />
                            </button>
                        </div>
                    </div>
                </div>
            </aside>

            {/* Mobile sidebar backdrop */}
            {sidebarOpen && (
                <div
                    className="fixed inset-0 bg-slate-900/50 z-40 lg:hidden"
                    onClick={() => setSidebarOpen(false)}
                />
            )}

            {/* Main content */}
            <div className="flex-1 flex flex-col min-w-0">
                {/* Top bar */}
                <header className="h-16 flex items-center gap-4 px-6 bg-white dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700">
                    <button
                        className="lg:hidden p-2 -ml-2"
                        onClick={() => setSidebarOpen(true)}
                    >
                        <Menu className="w-5 h-5" />
                    </button>

                    <div className="flex-1" />

                    <div className="text-sm text-slate-500">
                        {new Date().toLocaleDateString('en-US', {
                            weekday: 'long',
                            year: 'numeric',
                            month: 'long',
                            day: 'numeric'
                        })}
                    </div>
                </header>

                {/* Page content */}
                <main className="flex-1 p-6 overflow-auto">
                    <Outlet />
                </main>
            </div>
        </div>
    )
}
