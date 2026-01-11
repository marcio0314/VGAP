import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { api } from '../utils/api'

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
    const [user, setUser] = useState<User | null>(null)
    const [isLoading, setIsLoading] = useState(true)

    useEffect(() => {
        // Check for existing token
        const token = localStorage.getItem('vgap_token')
        if (token) {
            fetchUser(token)
        } else {
            setIsLoading(false)
        }
    }, [])

    async function fetchUser(token: string) {
        try {
            api.defaults.headers.common['Authorization'] = `Bearer ${token}`
            const response = await api.get('/auth/me')
            setUser(response.data)
        } catch (error) {
            localStorage.removeItem('vgap_token')
            delete api.defaults.headers.common['Authorization']
        } finally {
            setIsLoading(false)
        }
    }

    async function login(email: string, password: string) {
        const response = await api.post('/auth/login', { email, password })
        const { access_token } = response.data

        localStorage.setItem('vgap_token', access_token)
        api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`

        await fetchUser(access_token)
    }

    function logout() {
        localStorage.removeItem('vgap_token')
        delete api.defaults.headers.common['Authorization']
        setUser(null)
    }

    return (
        <AuthContext.Provider
            value={{
                user,
                isAuthenticated: !!user,
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
