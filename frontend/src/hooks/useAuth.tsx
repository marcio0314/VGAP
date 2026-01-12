import { createContext, useContext, useState, ReactNode } from 'react'

interface User {
    id: string
    email: string
    full_name: string
    role: string
    is_active: boolean
}

interface AuthContextType {
    user: User | null
    isAuthenticated: boolean
    isLoading: boolean
    login: (email: string, password: string) => Promise<void>
    logout: () => void
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
    // Authentication disabled - always provide a default admin user
    const defaultUser: User = {
        id: 'default-user',
        email: 'admin@vgap.local',
        full_name: 'VGAP User',
        role: 'admin',
        is_active: true,
    }

    const [user] = useState<User | null>(defaultUser)
    const [isLoading] = useState(false)

    async function login(_email: string, _password: string) {
        // No-op - authentication disabled
    }

    function logout() {
        // No-op - authentication disabled
    }

    return (
        <AuthContext.Provider
            value={{
                user,
                isAuthenticated: true, // Always authenticated
                isLoading,
                login,
                logout,
            }}
        >
            {children}
        </AuthContext.Provider>
    )
}

export function useAuth() {
    const context = useContext(AuthContext)
    if (context === undefined) {
        throw new Error('useAuth must be used within an AuthProvider')
    }
    return context
}
