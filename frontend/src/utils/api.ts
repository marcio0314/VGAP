import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

export const api = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
})

// Request interceptor
api.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem('vgap_token')
        if (token) {
            config.headers.Authorization = `Bearer ${token}`
        }
        return config
    },
    (error) => Promise.reject(error)
)

// Response interceptor
api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401) {
            localStorage.removeItem('vgap_token')
            window.location.href = '/login'
        }
        return Promise.reject(error)
    }
)

// API functions
export const authApi = {
    login: (email: string, password: string) =>
        api.post('/auth/login', { email, password }),
    me: () => api.get('/auth/me'),
    refresh: () => api.post('/auth/refresh'),
}

export const runsApi = {
    list: (params?: { skip?: number; limit?: number; status?: string }) =>
        api.get('/runs', { params }),
    get: (id: string) => api.get(`/runs/${id}`),
    create: (data: any) => api.post('/runs', data),
    start: (id: string) => api.post(`/runs/${id}/start`),
    cancel: (id: string) => api.post(`/runs/${id}/cancel`),
    status: (id: string) => api.get(`/runs/${id}/status`),
    validate: (id: string) => api.post(`/runs/${id}/validate`),
    provenance: (id: string) => api.get(`/runs/${id}/provenance`),
}

export const samplesApi = {
    get: (id: string) => api.get(`/samples/${id}`),
    qc: (id: string) => api.get(`/samples/${id}/qc`),
    variants: (id: string, params?: any) => api.get(`/samples/${id}/variants`, { params }),
    lineage: (id: string) => api.get(`/samples/${id}/lineage`),
}

export const reportsApi = {
    generate: (runId: string, data: any) => api.post(`/reports/${runId}/generate`, data),
    download: (runId: string, reportId: string, format = 'html') =>
        `${API_BASE_URL}/reports/${runId}/download/${reportId}?format=${format}`,
    exports: (runId: string, exportType: string) =>
        `${API_BASE_URL}/reports/${runId}/exports/${exportType}`,
    package: (runId: string) =>
        `${API_BASE_URL}/reports/${runId}/package`,
}

export const adminApi = {
    users: (params?: any) => api.get('/admin/users', { params }),
    createUser: (data: any) => api.post('/admin/users', data),
    updateUser: (id: string, data: any) => api.patch(`/admin/users/${id}`, data),
    deactivateUser: (id: string) => api.post(`/admin/users/${id}/deactivate`),
    databases: () => api.get('/admin/databases'),
    updateDatabase: (name: string) => api.post(`/admin/databases/${name}/update`),
    auditLog: (params?: any) => api.get('/admin/audit-log', { params }),
    status: () => api.get('/admin/status'),
}

export const uploadApi = {
    createSession: () => api.post('/upload/session'),
    upload: async (sessionId: string, file: File, onProgress?: (progress: number) => void) => {
        const formData = new FormData()
        formData.append('file', file)

        return api.post(`/upload/${sessionId}`, formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
            onUploadProgress: (event) => {
                if (event.total && onProgress) {
                    onProgress(Math.round((event.loaded / event.total) * 100))
                }
            },
        })
    },
}
